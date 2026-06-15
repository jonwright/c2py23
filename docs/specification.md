# c2py23 Specification

## Motivation

> "Real Programmers can write FORTRAN programs in any language."

-- Ed Post, "Real Programmers Don't Use Pascal", Datamation, July 1983

c2py23 targets the narrow intersection of C99 and Python needed for high-performance
numerical extensions. Rather than wrapping arbitrary C libraries, it enforces a
discipline where Python owns all memory, C functions operate on buffers passed in
by the caller, and the wrapper never copies or allocates. This eliminates entire
categories of bugs -- leaks, use-after-free, ownership confusion -- while keeping
the C code trivially simple.

The project defines a strict subset language: Python on one side (buffer protocol,
int, float), C99 on the other (flat pointers, scalar returns). The interface is
described declaratively in YAML. The code generator transpiles this into a CPython
C extension that dispatches to the right C function based on buffer properties:
element type, dimensionality, and layout. The wrapper itself is zero-copy and
allocation-free.

The long-term goal is a substrate for:
- SIMD dispatch within C functions, potentially at the wrapper level
- Accurate timing instrumentation (cycle counters, wall-clock)
- GIL release for pure-C sections
- Thread-safe extensions in free-threaded Python builds

## Grammar

### Module-Level YAML Schema

```yaml
module: <python-module-name>          # required
source: [file1.c, file2.c, ...]       # required: C source files
headers: [header1.h, header2.h, ...]  # optional: C headers to #include
constants:                            # optional: module-level integer constants
  NAME1: 42
  NAME2: 7
timing: true                          # optional: enable perf timing

functions:                            # required: list of wrapped functions
  - py_sig: "name(arg: type, ...) -> return_type"
    doc: "Custom docstring"           # optional: override auto-generated doc
    expand:                           # optional: template expansion
      VAR1: [val_a, val_b, ...]       #   variable name -> list of values
      VAR2: [val_a, val_b, ...]       #   all lists must have same length
    checks:                           # optional: pre-conditions
      - "expression"
      - ...
    c_overloads:                      # required: ordered list of alternatives
      - sig: "c_function(c_params...) -> c_return"
        map: {c_param: expression, ...}
        when: "condition"             # optional: dispatch condition
        outputs:                      # optional: return-by-pointer scalars
          c_param_name: ctype         #   ctype: int, float, double, int32_t, etc.
      - ...
    default_raise: "TypeError: msg"   # optional: error when no overload matches
```

### Template Expansion (expand:)

The `expand:` key produces multiple function definitions from a single template
via `${VAR}` string substitution. All value lists under `expand:` must have the
same length N. For each index i, a copy of the function definition is generated
with `${VAR}` replaced by `values[i]` in all string fields.

```yaml
functions:
  - expand:
      TYPE: [uint8_t, uint16_t, int32_t]
      SUFFIX: [u8, u16, i32]
    py_sig: "sum_${SUFFIX}(data: buffer) -> int"
    c_overloads:
      - sig: "int sum_${SUFFIX}(const ${TYPE} *data, int n)"
        map: {data: "data.ptr", n: "data.n"}
```

Expands to three functions: `sum_u8`, `sum_u16`, `sum_i32`.

### Output Scalars (outputs:)

The `outputs:` key on a C overload declares parameters that are written by the
C function rather than passed by the Python caller. c2py23 auto-allocates a
1-element stack variable, passes a pointer to the C function, and returns the
resulting value as part of the Python return tuple.

```yaml
c_overloads:
  - sig: "stats(const double *data, int n, double *minval, double *maxval)"
    map: {data: "data.ptr", n: "data.n"}
    outputs:
      minval: double
      maxval: double
```

Python call returns a tuple:
```python
minval, maxval = statmod.stats(data)
```

If there is also a C return value, it comes first in the tuple.

### Python Signature

```
py_sig ::= name "(" [py_param ("," py_param)*] ")" "->" py_ret
py_param ::= name ":" py_type
            | name ":" py_type "=" default
py_type ::= "buffer" | "int" | "float"
py_ret ::= "void" | "int" | "float"
default ::= integer_literal | float_literal
```

Optional parameters (with `=` default) are only supported for `int` and `float`
types, never `buffer`. All optional parameters must appear after all required
parameters.

Parameters:
- `buffer` -- any Python object supporting the buffer protocol. Passed as a pointer
  to the C function. Const pointers are read-only; non-const pointers are read-write
  and the caller must provide a writable buffer.
- `int` -- Python int, converted to C `int`
- `float` -- Python float, converted to C `double`

Returns:
- `void` -- the Python function returns `None`
- `int` -- the C function returns `int`, converted to Python `int`
- `float` -- the C function returns `float` or `double`, converted to Python `float`

### C Function Signature

```
c_sig ::= c_name "(" [c_param ("," c_param)*] ")" ["->" c_ret]
c_param ::= ["const"] c_ctype ["*"] name
c_ctype ::= "int" | "float" | "double" | "char"
          | "int8_t" | "uint8_t" | "int16_t" | "uint16_t"
          | "int32_t" | "uint32_t" | "int64_t" | "uint64_t"
c_ret ::= "int" | "float" | "double" | "void"
```

If `-> c_ret` is omitted, the return type is `void`.

Examples of valid C signatures:
```
array_sum(const double *a, const double *b, double *result, int n) -> int
fill_f(float *arr, int n, float value) -> void
dot(const double *a, const double *b, int n) -> double
```

### Map Expressions

`map:` entries connect C parameter names to expressions that compute their values
at call time from the Python parameters and buffer metadata.

```
map_expr ::= py_param_name
           | buffer_attr
           | literal

buffer_attr ::= buf "." attr
attr ::= "ptr" | "n" | "len" | "format" | "ndim" | "shape" "[" int "]" | "itemsize" | "strides" "[" int "]"
```

Buffer attribute reference:

| Expression | C equivalent | Description |
|-----------|-------------|-------------|
| `buf.ptr` | `buf->buf` cast to appropriate C type | Raw memory pointer |
| `buf.n` | `buf->len / buf->itemsize` | Element count |
| `buf.len` | `buf->len` | Byte length |
| `buf.format` | `buf->format` | PEP 3118 format string ("d", "f", "i", "B") |
| `buf.ndim` | `buf->ndim` | Number of dimensions |
| `buf.shape[i]` | `buf->shape[i]` | Size of dimension i |
| `buf.itemsize` | `buf->itemsize` | Bytes per element |
| `buf.strides[i]` | `buf->strides[i]` | Bytes between elements along dimension i |

For scalar Python parameters (`int`, `float`), the expression is simply the
parameter name. The generated code uses the local C variable (`c_name`).

### When Expressions

`when:` conditions determine which C overload is called. They are evaluated at
runtime in the generated `_impl` function, in declaration order. The first
overload whose `when` condition evaluates to true is selected. Overloads without
a `when` always match (useful as a default).

```
when_expr ::= compare ("and" compare | "or" compare)*
            | "not" when_expr
            | "(" when_expr ")"

compare ::= map_expr cmp_op map_expr
cmp_op ::= "==" | "!=" | "<" | ">" | "<=" | ">="
```

Format comparison with a single-character string literal uses last-character
matching to handle PEP 3118 endianness prefixes:
```
arr.format == 'd'   matches "d", "<d", ">d", "=d", "!d"
arr.format == 'f'   matches "f", "<f", ">f", "=f", "!f"
```

When the format pointer is NULL (old buffer protocol on Python 2.7), the
condition evaluates to true, allowing the first matching overload to proceed.

### Checks

`checks:` are pre-conditions evaluated before dispatch. If a check fails,
a `ValueError` is raised. Checks use the same expression language as `when:`
conditions.

```
checks:
  - "a.format == 'd'"
  - "a.n == b.n"
  - "a.n == result.n"
```

### Default Raise

`default_raise:` specifies the error raised when no overload matches:

```
default_raise: "TypeError: expected float or double buffer"
default_raise: "ValueError: expected [N,3] or [3,N] buffer"
```

The format is `"ExceptionType: message"`. Only `TypeError` and `ValueError`
are supported.

## Worked Examples

### Example 1: Element-wise Array Addition

**C source** (`arraysum.c`):
```c
int array_sum(const double *a, const double *b, double *result, int n) {
    int i;
    for (i = 0; i < n; i++) {
        result[i] = a[i] + b[i];
    }
    return n;
}
```

**Interface** (`arraysum.c2py`):
```yaml
module: arraysum
source: [arraysum.c]

functions:
  - py_sig: "array_sum(a: buffer, b: buffer, result: buffer) -> int"
    checks:
      - "a.format == 'd'"
      - "b.format == 'd'"
      - "result.format == 'd'"
      - "a.n == b.n"
      - "a.n == result.n"
    c_overloads:
      - sig: "array_sum(const double *a, const double *b, double *result, int n) -> int"
        map: {a: "a.ptr", b: "b.ptr", result: "result.ptr", n: "a.n"}
```

**Python call**:
```python
import ctypes, sys
sys.path.insert(0, '.')
import arraysum

a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
result = (ctypes.c_double * 4)()

n = arraysum.array_sum(a, b, result)
# n == 4
# result == [6.0, 8.0, 10.0, 12.0]
```

**Mapping at runtime**:

| Step | C parameter | Expression | Computed value |
|------|------------|-----------|---------------|
| 1 | `const double *a` | `a.ptr` | `(const double*)buf_a->buf` |
| 2 | `const double *b` | `b.ptr` | `(const double*)buf_b->buf` |
| 3 | `double *result` | `result.ptr` | `(double*)buf_result->buf` |
| 4 | `int n` | `a.n` | `(int)(buf_a->len / buf_a->itemsize)` = 4 |

The restrict check verifies that the writable buffer (`result`) does not overlap
with either read-only buffer (`a`, `b`).

### Example 2: Type Dispatch (float vs double)

**C source** (`fill.c`):
```c
void fill_f(float *arr, int n, float value) {
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_d(double *arr, int n, double value) {
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}
```

**Interface** (`fill.c2py`):
```yaml
module: fillmod
source: [fill.c]

functions:
  - py_sig: "fill(arr: buffer, value: float) -> void"
    c_overloads:
      - sig: "fill_f(float *arr, int n, float value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'f'"
      - sig: "fill_d(double *arr, int n, double value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'd'"
    default_raise: "TypeError: expected float or double buffer"
```

**Python call**:
```python
import ctypes, sys
sys.path.insert(0, '.')
import fillmod

# Float dispatch
arr_f = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
fillmod.fill(arr_f, 3.14)
# arr_f == [3.14, 3.14, 3.14, 3.14]

# Double dispatch
arr_d = (ctypes.c_double * 3)(0.0, 0.0, 0.0)
fillmod.fill(arr_d, 2.718)
# arr_d == [2.718, 2.718, 2.718]
```

**Dispatch at runtime**:

| Buffer format | Overload selected | C function called |
|--------------|-------------------|-------------------|
| `"f"` or `"<f"` | 0 | `fill_f((float*)buf->buf, n, (float)c_value)` |
| `"d"` or `"<d"` | 1 | `fill_d((double*)buf->buf, n, c_value)` |
| NULL (old API) | 0 | `fill_f(...)` (first overload, format unknown) |
| anything else | -- | `TypeError: expected float or double buffer` |

### Example 3: Shape Dispatch (AoS vs SoA)

**C source** (`transform.c`):
```c
void transform_aos(double *points, int n, double *out) {
    /* points: [n, 3] -- array of structs */
    int i;
    for (i = 0; i < n; i++) {
        double x = points[i * 3 + 0];
        double y = points[i * 3 + 1];
        double z = points[i * 3 + 2];
        out[i * 3 + 0] = x * 2.0;
        out[i * 3 + 1] = y * 2.0;
        out[i * 3 + 2] = z * 2.0;
    }
}

void transform_soa(double *points, int n, double *out) {
    /* points: [3, n] -- struct of arrays */
    int i;
    for (i = 0; i < n; i++) {
        double x = points[0 * n + i];
        double y = points[1 * n + i];
        double z = points[2 * n + i];
        out[0 * n + i] = x * 2.0;
        out[1 * n + i] = y * 2.0;
        out[2 * n + i] = z * 2.0;
    }
}
```

**Interface** (`transform.c2py`):
```yaml
module: xfrm
source: [transform.c]

functions:
  - py_sig: "transform(points: buffer, out: buffer) -> void"
    checks:
      - "points.format == 'd'"
      - "out.format == 'd'"
      - "out.n == points.n"
      - "points.ndim == 2"
    c_overloads:
      - sig: "transform_aos(double *points, int n, double *out)"
        map: {points: "points.ptr", n: "points.shape[0]", out: "out.ptr"}
        when: "points.shape[1] == 3"
      - sig: "transform_soa(double *points, int n, double *out)"
        map: {points: "points.ptr", n: "points.shape[1]", out: "out.ptr"}
        when: "points.shape[0] == 3"
    default_raise: "ValueError: expected [N,3] or [3,N] buffer"
```

**Python call**:
```python
import ctypes, sys
sys.path.insert(0, '.')
import xfrm

# AoS dispatch: [4, 3] shape
pts = (ctypes.c_double * 12)(1,2,3, 4,5,6, 7,8,9, 10,11,12)
out = (ctypes.c_double * 12)()
mv = memoryview(pts).cast('B').cast('d', [4, 3])
mv_out = memoryview(out).cast('B').cast('d', [4, 3])
xfrm.transform(mv, mv_out)
# Calls transform_aos, n = shape[0] = 4
# out == [2,4,6, 8,10,12, 14,16,18, 20,22,24]

# SoA dispatch: [3, 4] shape
pts2 = (ctypes.c_double * 12)(1,4,7,10, 2,5,8,11, 3,6,9,12)
out2 = (ctypes.c_double * 12)()
mv2 = memoryview(pts2).cast('B').cast('d', [3, 4])
mv_out2 = memoryview(out2).cast('B').cast('d', [3, 4])
xfrm.transform(mv2, mv_out2)
# Calls transform_soa, n = shape[1] = 4
# out2 == [2,8,14,20, 4,10,16,22, 6,12,18,24]
```

**Dispatch at runtime**:

| Buffer shape | Condition matched | C function called | n computed as |
|-------------|-------------------|-------------------|--------------|
| `(4, 3)` | `shape[1] == 3` | `transform_aos` | `shape[0] = 4` |
| `(3, 4)` | `shape[0] == 3` | `transform_soa` | `shape[1] = 4` |
| `(5, 2)` | none | `ValueError` | -- |
| 1D | `ndim == 2` fails | `ValueError` | -- |

Key design point: the wrapper never transposes or copies data. Both C functions
receive the same raw pointer; the dispatch only changes how `n` is computed and
which C function interprets the layout.

### Example 4: Dispatch Over All Buffer Types

This example demonstrates `when:` dispatch over all 10 PEP 3118 format
characters, mapping each to its corresponding C fixed-width type.

**C source** (`typedispatch.c`):
```c
#include <stdint.h>

void fill_u8(uint8_t *arr, int n, uint8_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_i8(int8_t *arr, int n, int8_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_u16(uint16_t *arr, int n, uint16_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_i16(int16_t *arr, int n, int16_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_u32(uint32_t *arr, int n, uint32_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_i32(int32_t *arr, int n, int32_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_u64(uint64_t *arr, int n, uint64_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_i64(int64_t *arr, int n, int64_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_f32(float *arr, int n, float value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_f64(double *arr, int n, double value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
```

**Interface** (`typedispatch.c2py`):
```yaml
module: dispatchmod
source: [typedispatch.c]
headers: [stdint.h]

functions:
  - py_sig: "fill(arr: buffer, value: float) -> void"
    c_overloads:
      - sig: "fill_u8(uint8_t *arr, int n, uint8_t value)"
        when: "arr.format == 'B'"
      - sig: "fill_i8(int8_t *arr, int n, int8_t value)"
        when: "arr.format == 'b'"
      - sig: "fill_u16(uint16_t *arr, int n, uint16_t value)"
        when: "arr.format == 'H'"
      - sig: "fill_i16(int16_t *arr, int n, int16_t value)"
        when: "arr.format == 'h'"
      - sig: "fill_u32(uint32_t *arr, int n, uint32_t value)"
        when: "arr.format == 'I'"
      - sig: "fill_i32(int32_t *arr, int n, int32_t value)"
        when: "arr.format == 'i'"
      - sig: "fill_u64(uint64_t *arr, int n, uint64_t value)"
        when: "arr.format == 'Q'"
      - sig: "fill_i64(int64_t *arr, int n, int64_t value)"
        when: "arr.format == 'q'"
      - sig: "fill_f32(float *arr, int n, float value)"
        when: "arr.format == 'f'"
      - sig: "fill_f64(double *arr, int n, double value)"
        when: "arr.format == 'd'"
    default_raise: "TypeError: expected buffer of type B,b,H,h,I,i,Q,q,f,d"
```

**Complete Format-to-C-Type Mapping**:

| PEP 3118 | Format char | C Type      | Size |
|----------|-------------|-------------|------|
| ubyte    | `B`         | `uint8_t`   | 1    |
| byte     | `b`         | `int8_t`    | 1    |
| ushort   | `H`         | `uint16_t`  | 2    |
| short    | `h`         | `int16_t`   | 2    |
| uint     | `I`         | `uint32_t`  | 4    |
| int      | `i`         | `int32_t`   | 4    |
| ulonglong| `Q`         | `uint64_t`  | 8    |
| longlong | `q`         | `int64_t`   | 8    |
| float    | `f`         | `float`     | 4    |
| double   | `d`         | `double`    | 8    |

**Python call**:
```python
import ctypes, sys
sys.path.insert(0, '.')
import dispatchmod

# Dispatch by buffer format character
arr = (ctypes.c_uint8 * 5)(0,0,0,0,0)
dispatchmod.fill(arr, 42)
# arr == [42, 42, 42, 42, 42]  -- dispatched to fill_u8

arr2 = (ctypes.c_double * 3)(0,0,0)
dispatchmod.fill(arr2, 3.14)
# arr2 == [3.14, 3.14, 3.14]   -- dispatched to fill_f64
```

## Generated Wrapper Structure

For each function in the `.c2py` file, the generator produces two C functions:

### `_impl` Function

Takes `Py_buffer*` for each buffer param and C scalar values. Structure:

```
1. Evaluate checks -- raise ValueError on failure
2. Overload dispatch -- ordered if/else chain:
   a. For each overload with a `when` condition, test and enter `if` block
   b. For each overload without `when`, enter `else` block
   c. In each block: map expressions -> C args, call C function, return result
3. Default raise -- if no overload matched, raise TypeError or ValueError
```

### `_wrapper` Function

Takes `PyObject *self, *args, *kwargs` (standard CPython method). Structure:

```
1. PyArg_ParseTuple -- extract Python objects and scalar values
2. c2py_acquire_buffer -- for each buffer param, get Py_buffer struct
   (uses PEP 3118 on Python 3.x, falls back to old API on 2.7)
3. Restrict checks -- verify no writable buffer aliases any other buffer
4. Call _impl function
5. Cleanup -- release all acquired buffers
6. Return result
```

### Module Init

Two entry points are provided:

- `PyInit_<name>(void)` -- called by Python 3.x, returns `PyObject*`
- `init<name>(void)` -- called by Python 2.7, returns `void`

Both call `c2py_runtime_init()` which populates the function pointer table via
`dlopen(NULL)` + `dlsym()`. The module definition struct (`PyModuleDef`) and
method table (`PyMethodDef[]`) are compiled into the shared object.

## Nimpy Runtime

The runtime avoids linking against `libpython` entirely. The approach originates from
[yglukhov/nimpy](https://github.com/yglukhov/nimpy), a Nim-Python bridge designed for
ABI compatibility across Python versions. The key insight from nimpy: compiled modules
should not depend on a particular Python version; the C API symbols are loaded at runtime
from whichever process has launched the module.

c2py23 adapts this technique for C, trimming it to the smallest possible CPython C API
surface: buffer protocol, argument parsing, scalar construction, exception handling,
and module creation. No other CPython APIs are exposed or used.

1. At module load time, `c2py_runtime_init()` calls `dlopen(NULL, RTLD_LAZY | RTLD_GLOBAL)`
   to get a handle to the running Python interpreter's symbol table

2. All needed CPython C API functions are resolved via `dlsym()` and stored in a
   global function pointer table (`C2PY`)

3. Macros in `c2py_runtime.h` redirect standard CPython API names to the
   function pointer table:
   ```c
   #define PyObject_GetBuffer  C2PY.GetBuffer
   #define PyErr_SetString     C2PY.Err_SetString
   ```

4. CPython types (`PyObject`, `Py_buffer`, `PyMethodDef`, `PyModuleDef`) are
   redefined with ABI-stable layouts in `c2py_runtime.h`

5. The `Py_buffer` struct supports both 96-byte (Python 2.7, with smalltable)
   and 80-byte (Python 3.x, without smalltable) layouts; the runtime selects
   the correct size based on the Python version

6. `c2py_acquire_buffer()` is a version-aware wrapper: on Python 3.x it uses
   `PyObject_GetBuffer` with `PyBUF_STRIDES | PyBUF_FORMAT` flags; on Python 2.7
   it tries PEP 3118 first, then falls back to `PyObject_AsReadBuffer`/
   `PyObject_AsWriteBuffer` (old buffer API). Old buffers have `format = NULL`
   and `ndim = 1`

### Function Pointer Table

```c
typedef struct {
    void *dl_handle;
    int version_major, version_minor;

    /* Buffer protocol */
    int (*GetBuffer)(PyObject*, Py_buffer*, int);
    void (*ReleaseBuffer)(Py_buffer*);
    int (*AsReadBuffer)(PyObject*, const void**, Py_ssize_t*);   /* 2.7 only */
    int (*AsWriteBuffer)(PyObject*, void**, Py_ssize_t*);        /* 2.7 only */
    void (*Err_Clear)(void);
    int buffer_api_is_pep3118;  /* 0 on 2.7, 1 on 3.x */
    size_t pybuffer_size;
    int use_fastcall;

    /* Argument parsing */
    int (*ParseTuple)(PyObject*, const char*, ...);
    int (*ParseTupleAndKeywords)(PyObject*, PyObject*, const char*, char**, ...);

    /* Value construction */
    PyObject* (*Long_FromLong)(long);
    PyObject* (*Long_FromLongLong)(long long);
    PyObject* (*Float_FromDouble)(double);

    /* Tuple construction */
    PyObject* (*Tuple_New)(Py_ssize_t);
    int (*Tuple_SetItem)(PyObject*, Py_ssize_t, PyObject*);

    /* Scalar conversion */
    long (*Long_AsLong)(PyObject*);
    double (*Float_AsDouble)(PyObject*);

    /* Exception handling */
    void *exc_TypeError, *exc_ValueError, *exc_RuntimeError, *exc_MemoryError;
    void (*Err_SetString)(PyObject*, const char*);
    PyObject* (*Err_Occurred)(void);

    /* Module creation */
    PyObject* (*Module_Create2)(PyModuleDef*, int);
    PyObject* (*InitModule_2_7)(const char*, PyMethodDef*);

    /* Object attribute access */
    int (*SetAttrString)(PyObject*, const char*, PyObject*);

    /* Pointer-to-int conversion (for exposing perf struct addresses) */
    PyObject* (*Long_FromVoidPtr)(void*);

    /* Reference counting */
    void (*IncRef)(PyObject*);
    void (*DecRef)(PyObject*);

    /* None singleton */
    PyObject *none_obj;
} c2py_api_t;
```

## Cross-Version Portability

### One .so for Multiple Python Versions

The compiled `.so` is Python-version-independent because:
- No compile-time Python headers are included
- All CPython API is resolved at module load time
- Both `PyInit_*` (Python 3) and `init*` (Python 2.7) entry points are exported
- The `PyModuleDef` struct has a stable ABI layout across Python 3.x

### OS/Libc Compatibility

The `.so` uses only C99 and POSIX `dlopen`/`dlsym`. To achieve maximum portability,
build on the oldest target OS. A `.so` built on Ubuntu 20.04 (glibc 2.31) imports
correctly on Ubuntu 24.04 (glibc 2.39). The reverse does not work, as expected
for any glibc-linked binary.

## Restrictions

- No `malloc`, `calloc`, `realloc`, or `free` in generated wrapper code
  (user C code may use them internally; allocated memory must be freed before return)
- No copies or transposes in the wrapper -- all memory is passed through
- All buffers must be contiguous (C-contiguous or F-contiguous as appropriate)
- The GIL is held during all C function calls
- `restrict` is enforced at the wrapper level: aliasing writable buffers raises `ValueError`

## Future Work

- **GIL release / threadsafe mode** -- for pure-C sections that do not touch
  Python objects, release the GIL via `PyEval_SaveThread`/`PyEval_RestoreThread`
  to allow true parallelism in threaded applications
- **SIMD dispatch** -- select C functions based on CPU feature detection at
  module load time (`cpu_has_avx2`, `cpu_has_avx512f`, `cpu_has_neon` etc.)
- **Thread safety** -- for free-threaded Python 3.14+, wrap critical sections
  for atomic refcounting and buffer acquisition
