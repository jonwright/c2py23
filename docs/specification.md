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
- Thread-safe extensions in free-threaded Python builds (3.14t+)

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
free_threading: true                  # optional: declare Py_MOD_GIL_NOT_USED

functions:                            # required: list of wrapped functions
  - py_sig: "name(arg: type, ...) -> return_type"
    doc: "Custom docstring"           # optional: override auto-generated doc
    params:                           # optional: per-parameter descriptions
      param_name: "Description text"  #   keys must match py_sig parameter names
    gil_release: true                 # optional: release the GIL during C calls
    expand:                           # optional: template expansion
      VAR1: [val_a, val_b, ...]       #   variable name -> list of values
      VAR2: [val_a, val_b, ...]       #   all lists must have same length
    checks:                           # optional: pre-conditions
      - "expression"

### Alternative: Python Dict Format

Instead of YAML, the same interface can be written as a Python dict literal.
This is auto-detected by `load_c2py()` and requires no PyYAML dependency.

```python
{
    "module": "<python-module-name>",
    "source": ["file1.c", "file2.c"],
    "headers": ["header1.h", "header2.h"],           # optional
    "constants": {"NAME1": 42, "NAME2": 7},           # optional
    "timing": True,                                   # optional
    "free_threading": True,                            # optional
    "functions": [
        {
            "py_sig": "name(arg: type, ...) -> return_type",
            "doc": "Custom docstring",                 # optional
            "params": {"param_name": "description"},   # optional
            "gil_release": True,                       # optional
            "checks": ["expression"],                  # optional
            "c_overloads": [
                {
                    "sig": "void foo(int n, double *out)",
                    "map": {"out": "out.ptr", "n": "out.n"},
                    "when": "out.format == 'd'",       # optional
                },
            ],
            "default_raise": "TypeError: expected d",   # optional
            "expand": {"VAR": ["val_a", "val_b"]},       # optional
        },
    ],
}
```

The key names and values are identical to the YAML schema above.
Differences from YAML:

- **`c_overloads`** instead of `c_overloads:` (same key name, both work)
- **Boolean values**: `True`/`False` (or `true`/`false` in Python)
- **None** (optional keys omitted or set to `None`)
- **Strings** use Python quoting (single or double)
- **No indentation sensitivity** -- dict boundaries are `{`/`}`

The `load_c2py()` function auto-detects between YAML and Python dict:

```python
from c2py23.parser import load_c2py, from_c2py_dict

# From file (auto-detect)
mod = load_c2py("mymod.c2py")

# From Python dict directly
mod = from_c2py_dict({"module": "mymod", ...})
```

See `tests/test_regression_fixes.py::test_python_dict_format` for a full
working example.

#### Debugging Dict-Format Files

The `.c2py` file is data, not code -- it cannot be `import`ed.
To validate or debug your dict structure:

```python
import ast

# Safe: parses only literals, no code execution
data = ast.literal_eval(open("mymod.c2py").read())
# data is now the parsed dict

# Parse and validate with c2py23:
from c2py23.parser import from_c2py_dict
mod = from_c2py_dict(data, "mymod.c2py")
```

First-line comments (`# ...`) are automatically stripped by `load_c2py()`
before parsing, so they do not interfere with `ast.literal_eval()`.

For interactive development, build the dict in a `.py` file with full IDE
support (syntax highlighting, bracket matching), then export to `.c2py`:

```python
# mymod_dev.py -- your development file
interface = {
    "module": "mymod",
    "source": ["mymod.c"],
    "functions": [
        ...
    ],
}

# Validate:
from c2py23.parser import from_c2py_dict
mod = from_c2py_dict(interface, "mymod")
print("OK:", mod.name)

# Export to .c2py dict format:
from tools.convert_c2py_to_dict import py_repr
with open("mymod.c2py", "w") as f:
    f.write("# This file defines the c2py23 interface for mymod\n")
    f.write(py_repr(interface, 0) + "\n")
```

The comment on the first line is stripped by `load_c2py()`'s comment remover
before parsing.  This also lets you debug by `exec()` (for local/trusted
files only -- see security note below):

```python
# For trusted/development use only:
exec(open("mymod.c2py").read())
# data is now available as the `data` variable
```

**Security note**: Executing `.c2py` files with `exec()` is equivalent to
running any build script -- it trusts the source.  For downloaded or
untrusted code, always use `ast.literal_eval()` which only accepts
Python literals (no functions, imports, or expressions).
      - ...
    c_overloads:                      # required: ordered list of alternatives
      # flat overload:
      - sig: "c_function(c_params...) -> c_return"
        name: "label"                 # optional: for timing/reference
        doc: "Overload description"   # optional: per-overload notes in docstring
        map: {c_param: expression, ...}
        when: "condition"             # optional: dispatch condition
        outputs:                      # optional: return-by-pointer scalars
          c_param_name: ctype         #   ctype: int, float, double, int32_t, etc.
      # grouped dispatch (SIMD / CPU feature variants):
      - map: {c_param: expression, ...}
        when: "condition"             # optional: per-call group condition
        group: "label"                # optional: group name
        doc: "Group description"      # optional: group-level docstring notes
        variants:                     # required for grouped: list of variants
          - sig: "c_variant(c_params...) -> c_ret"
            name: "label"             # optional: defaults to c function name
            doc: "Variant description" # optional: per-variant docstring notes
            when: "cpu_feature_check" # optional: static (init-time) dispatch
            default: true|false       # optional: true (auto-select) or false (manual only)
            outputs: {c_param: ctype}
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

**Tuple order**: The order of values in the returned tuple always follows the C
function parameter order (left to right in the C signature), not the YAML
dictionary insertion order. If the function also has a C return value, it
appears first, followed by output parameters in C signature order.

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

### Opaque Pointers (`void*`)

A C parameter with type `void*` maps from Python `int` (a pointer-width integer).
The wrapper casts through `intptr_t` and never dereferences the pointer:

```yaml
c_overloads:
  - sig: "gpu_kernel(void *gpu_buf, int n)"
    map: {gpu_buf: gpu_addr, n: "data.n"}
```

```python
addr = get_gpu_buffer_address()   # returns int
mymod.gpu_kernel(addr, data)
```

The `void*` parameter is a pure address passthrough for user-managed memory
(GPU buffers, custom allocators, etc.).  The C function is responsible for
interpreting the pointer; the wrapper performs no reads or writes through it.

### C Function Signature

```
c_sig ::= c_name "(" [c_param ("," c_param)*] ")" ["->" c_ret]
c_param ::= ["const"] c_ctype ( "*" name
                               | name ( "[" int "]" | "[]" )+ )
c_ctype ::= "int" | "float" | "double" | "char" | "void"
          | "int8_t" | "uint8_t" | "int16_t" | "uint16_t"
          | "int32_t" | "uint32_t" | "int64_t" | "uint64_t"
          | "intptr_t" | "size_t" | "_Bool"
c_ret ::= "void" | "int" | "float" | "double"
```

If `-> c_ret` is omitted, the return type is `void`.

When a parameter uses array notation (`name[3]`, `name[]`, `name[][3]`),
c2py23 automatically derives buffer validation checks (see
**Auto-derived Checks** below).  Without array notation (`*name`),
no automatic shape validation is performed.

Examples of valid C signatures:
```
array_sum(const double *a, const double *b, const double *result, int n) -> int
fill_f(float *arr, int n, float value) -> void
dot(const double *a, const double *b, int n) -> double
sum_rows(const double gv[][3], intptr_t ng) -> double          # AoS: gv[ng][3]
sum_33(const double ubi[3][3]) -> double                       # fixed 3x3 matrix
process_blocks(const double blk[][5][5], intptr_t nblk) -> int # 3D: blocks of 5x5
```

#### Auto-derived Checks

When a C parameter uses array dimension syntax (`name[N]`, `name[N][M]`,
`name[]`, `name[][N]`, etc.), c2py23 automatically generates checks
to verify the Python buffer at runtime.  The C param name is mapped
to the Python buffer param via `map:` expressions (typically
`buf_name.ptr`).

**Generated checks for each pattern:**

| C sig parameter | Auto-generated checks |
|-----------------|-----------------------|
| `double arr[5]` | `arr.slow_axis == 0` (C-contiguous), `arr.shape[0] == 5` |
| `double gv[][3]` | `gv.slow_axis == 0`, `gv.ndim == 2`, `gv.shape[1] == 3` |
| `double ubi[3][3]` | `ubi.slow_axis == 0`, `ubi.ndim == 2`, `ubi.shape[0] == 3`, `ubi.shape[1] == 3` |
| `double blk[][5][5]` | `blk.slow_axis == 0`, `blk.ndim == 3`, `blk.shape[2] == 5` |

**Key points:**

- `slow_axis == 0` is always emitted -- the C function indexes with
  `arr[i][j]` which assumes row-major memory layout.  c2py23 never
  copies or transposes data; the buffer layout must match the C code's
  expectation exactly.
- In numpy terms: `x` (C-contiguous) passes `slow_axis == 0`; `x.T`
  (F-contiguous) is always rejected.  If your C code expects a
  transposed arrangement, pass a C-contiguous buffer that is already
  in that order, or use a separate C overload with SoA indexing.
- `ndim == D` is emitted for multi-dimensional arrays (D >= 2).
- `shape[i] == N` is emitted for every dimension where a fixed size is given.
- Variable dimensions (`[]`) produce no shape constraint.
- **No `*pointer` notation**: when the C sig uses `double *arr` (no array
  coordinates), c2py23 performs no automatic shape validation.  The user is
  responsible for writing explicit `checks:`.

**Interaction with user `checks:`:**

Auto-derived checks are appended to the function's `checks:` block.
If the user writes the same check expression explicitly, it is not
duplicated (the set of auto-checks is deduplicated against user-written
checks).

### Map Expressions

`map:` entries connect C parameter names to expressions that compute their values
at call time from the Python parameters and buffer metadata.

```
map_expr ::= py_param_name
           | buffer_attr
           | literal

buffer_attr ::= buf "." attr
attr ::= "ptr" | "n" | "len" | "format" | "ndim" | "shape" "[" int "]" | "itemsize" | "strides" "[" int "]" | "slow_axis" | "fast_axis" | "slow_dim" | "fast_dim"
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

#### Expression Grammar

All `checks:` and `when:` expressions are compiled to C. The following
attributes and operators are available:

| Expression | C equivalent | Notes |
|---|---|---|
| `buf.n` | `buf->len / buf->itemsize` | Element count |
| `buf.len` | `buf->len` | Byte length (PEP 3118 field) |
| `buf.shape[N]` | `buf->shape[N]` | Array dimension sizes |
| `buf.strides[N]` | `buf->strides[N]` | Byte strides per dimension |
| `buf.itemsize` | `buf->itemsize` | Bytes per element |
| `buf.format` | `buf->format` | PEP 3118 format character |
| `buf.ndim` | `buf->ndim` | Number of dimensions |
| `buf.ptr` | `buf->buf` | Raw pointer |
| `buf.slow_axis` | `_c2py_slow_axis_buf_*` | 0 (C-contiguous) or ndim-1 (F-contiguous) |
| `buf.fast_axis` | `_c2py_fast_axis_buf_*` | ndim-1 (C-contiguous) or 0 (F-contiguous) |
| `buf.slow_dim` | `buf->shape[_c2py_slow_axis_buf_*]` | Size of the slowest-varying dimension |
| `buf.fast_dim` | `buf->shape[_c2py_fast_axis_buf_*]` | Size of the fastest-varying dimension |
| integer literal | `42` | |
| float literal | `3.14` | |
| string literal | `"hello"` | |
| `and` / `or` | `&&` / `\|\|` | Short-circuit |
| `not` | `!` | |
| `==` / `!=` | `==` / `!=` | |
| `<` / `>` / `<=` / `>=` | Same | |
| `+` / `-` / `*` / `/` / `%` | Same | Arithmetic |
| unary `+` / `-` | Same | |

Both `buf.n` and `buf.len` are available; `n` returns the number of
elements, `len` returns the byte length (matching the PEP 3118 `Py_buffer.len`
field).

#### Buffer Layout: slow_axis, fast_axis, slow_dim, fast_dim

c2py23 requires every buffer to be dense -- either C-contiguous or
F-contiguous.  The contiguity check rejects any buffer that is not
one of the two.  For dense buffers, the slowest and fastest varying
axes are always at the endpoints:

| Layout | slow_axis | fast_axis | Example shape | strides |
|--------|-----------|-----------|---------------|---------|
| C-contiguous | `0` | `ndim-1` | (N, 3) | (24, 8) |
| F-contiguous | `ndim-1` | `0` | (3, N) | (8, 24) |

These are integers, not strings.  No Fortran terminology.

`slow_dim` is shorthand for `shape[slow_axis]` -- the size of the
free dimension that a C loop typically iterates over.

`fast_dim` is shorthand for `shape[fast_axis]` -- the size of the
inner (packed) dimension, such as 3 in an `A[n][3]` AoS layout.

**Usage pattern -- layout guard in checks:**

When a kernel assumes a specific axis ordering, put the layout
constraint in `checks:` so it applies to all overloads:

```yaml
checks:
  - "points.slow_axis == 0"      # requires C-contiguous, no transpose
c_overloads:
  - when: "points.shape[1] == 3"  # shape-only dispatch
  - when: "points.shape[0] == 3"
```

The `when:` conditions can then focus purely on shape.

**Usage pattern -- using slow_dim for the loop bound:**

A C kernel that operates on `float A[n][3]` needs `n` as the loop
count.  For C-contiguous data, `n = shape[0]`.  For F-contiguous data,
`n = shape[ndim-1]`.  `slow_dim` gives the correct `n` regardless:

```yaml
map: {a: "a.ptr", n: "a.slow_dim", out: "out.ptr"}
```

This works for any ndim -- `slow_dim` is always the size of the axis
that the C loop iterates over.

#### Quoting in map: and YAML values

YAML interprets `.`, `[`, `(`, and spaces as syntax.  Values containing
these characters MUST be quoted:

```yaml
map: {ng: "gv.shape[0]"}     # quoted -- . and [ are YAML special
map: {ptr: "buf.ptr"}        # quoted -- . is YAML special
map: {tol: tol}               # no quotes -- bare scalar
```

The rule: bare YAML values (scalars, ints) need no quotes; any value
containing `.`, `[`, `(`, or whitespace must be quoted.

#### Variant Ordering

Variant dispatch respects declaration order. The first variant whose
`when:` condition matches wins auto-dispatch. Both Python 3.7+ dicts and
PyYAML `safe_load` preserve insertion order.

Variants with `default: false` are skipped during auto-resolve and are
reachable only via `_rebind_<name>()`. At least one variant per group
must have `default: true` (the default).

#### Variant Naming

The `name` field on a variant defaults to the C function name extracted
from `sig` (e.g., `poly_f32_avx512`). If specified, `name` must match
the C function name exactly — enforced at parse time. This ensures
`_variants_<name>()` returns names that correspond to real .so symbols.

```yaml
variants:
  - sig: "void poly_f32_avx512(...)"   # name → "poly_f32_avx512"
    when: "c2py_amd64_avx512f"
  - sig: "void poly_f32_scalar(...)"   # name → "poly_f32_scalar"
```

#### Variant Enumeration and Rebind

Every function with grouped variants gets:

- `_rebind_<name>(variant_name)` — sets the active variant by name.
  Call with `None` to re-run auto-resolve.
- `_variants_<name>()` — returns a tuple of all variant names (including
  `default: false` variants) in declaration order.

### Default Raise

`default_raise:` specifies the error raised when no overload matches:

```
default_raise: "TypeError: expected float or double buffer"
default_raise: "ValueError: expected [N,3] or [3,N] buffer"
```

The format is `"ExceptionType: message"`. The exception type is prefixed
with `PyExc_` at code generation time; any `PyExc_*` constant available
at build time is valid (typically `TypeError`, `ValueError`, `RuntimeError`).

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
void transform_aos(double *points, intptr_t n, double *out) {
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

void transform_soa(double *points, intptr_t n, double *out) {
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
timing: true

functions:
  - py_sig: "transform(points: buffer, out: buffer) -> void"
    checks:
      - "points.format == 'd'"
      - "out.format == 'd'"
      - "out.n == points.n"
      - "points.ndim == 2"
      - "points.slow_axis == 0"
    c_overloads:
      - sig: "transform_aos(double *points, intptr_t n, double *out)"
        map: {points: "points.ptr", n: "points.shape[0]", out: "out.ptr"}
        when: "points.shape[1] == 3"
      - sig: "transform_soa(double *points, intptr_t n, double *out)"
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

**Note on `'l'` and `'L'` format characters**: PEP 3118 defines `'l'` (signed long)
and `'L'` (unsigned long) as platform-sized types. On LP64 platforms (Linux x86_64,
aarch64) they are 8 bytes wide and map to `int64_t`/`uint64_t`. On ILP32 and LLP64
platforms (32-bit, Windows) they are 4 bytes wide. For portable dispatch, prefer
`'q'`/`'Q'` for 64-bit integers and `'i'`/`'I'` for 32-bit integers. If you use
`'l'` or `'L'`, document that your `.c2py` file is LP64-only.

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

### Auto-Generated Docstrings and `__text_signature__`

The generator produces a rich docstring (`ml_doc`) for each function with:

- **First line**: a parseable signature line (names only, e.g., `fill(arr, value)`) that
  CPython automatically converts to `__text_signature__`.
- **Full annotated signature**: the c2py signature with types
  (e.g., `fill(arr: buffer, value: float) -> void`).
- **User doc**: the `doc:` field from the `.c2py` file.
- **Parameters section**: For each parameter, the generator auto-derives type
  information from `checks:` format comparisons (e.g., `arr.format == 'f'` -->
  `float32`), writability from C pointer const-ness, and size/dimensionality
  constraints from checks like `a.n == b.n` or `arr.ndim == 2`.
  User-provided `params:` descriptions are appended after the auto-derived info.
- **Overloads section**: Lists C function signatures and their dispatch
  conditions. Grouped dispatch shows variant names and CPU feature conditions.
- **Default error**: shows the `default_raise:` error message.

The signature line uses the CPython clinic convention (`funcname(params)`
followed by a `\n--\n\n` separator), which allows `inspect.signature()` and
`help()` to render a proper structured signature.

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

    int use_fastcall;               /* 1 = use METH_FASTCALL wrappers (Python >= 3.12) */
    int is_free_threaded;           /* 1 = Python built with --disable-gil */
    Py_ssize_t pybuffer_size;       /* actual sizeof(Py_buffer) for this version */
    Py_ssize_t pyobject_size;       /* actual sizeof(PyObject) for this version */
    ptrdiff_t ob_refcnt_offset;     /* offset of refcount field within PyObject */

    /* Buffer protocol */
    int (*GetBuffer)(PyObject*, Py_buffer*, int);
    void (*ReleaseBuffer)(Py_buffer*);
    int (*AsReadBuffer)(PyObject*, const void**, Py_ssize_t*);   /* 2.7 only */
    int (*AsWriteBuffer)(PyObject*, void**, Py_ssize_t*);        /* 2.7 only */
    void (*Err_Clear)(void);
    int buffer_api_is_pep3118;  /* 0 on 2.7, 1 on 3.x */

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
    PyObject* (*Err_Format)(PyObject*, const char*, ...);

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

    /* GIL management */
    void* (*SaveThread)(void);
    void (*RestoreThread)(void*);

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
- The GIL is held during all C function calls by default.
  Individual functions may opt into GIL release via
  `gil_release: true` (see below).
- `restrict` is enforced at the wrapper level: aliasing writable buffers raises `ValueError`

## GIL Release and Thread Safety

### The GIL and Buffer Protocol

CPython's Global Interpreter Lock (GIL) serializes Python bytecode execution.
When a C extension is called, the GIL is held. This means:
- No other Python thread can run Python code concurrently.
- Python object reference counts are safe from races.
- The interpreter's internal state is protected.

The buffer protocol creates a reference from the C extension to a Python
object's underlying memory. `PyObject_GetBuffer` increments the object's
reference count indirectly through the buffer's exporter. As long as the
buffer is held, the Python object cannot be garbage collected and its
memory cannot be freed.

**What the buffer reference does NOT protect against:** concurrent writes.
If two Python threads each acquire a buffer reference to the same ndarray,
both hold valid pointers to the same memory. If one thread writes while
the other reads, there is a data race. The buffer protocol provides no
locking mechanism for content access. This is the caller's responsibility.

### Releasing the GIL

When a C function does not call any Python C API (no `PyArg_ParseTuple`,
no `PyLong_FromLong`, no exception setting), the GIL is unnecessary for
correctness. The wrapper can release it:

```yaml
functions:
  - py_sig: "array_stats(data: buffer) -> void"
    gil_release: true                      # release the GIL for all overloads of this function
    c_overloads:
      - sig: "stats_f(const float *data, int n, ...)"
        map: {data: "data.ptr", n: "data.n"}
```

The `gil_release` key appears at the function level only.  If omitted,
the GIL is held -- the safe default.  Having it at function level means
the Python caller can know, from looking at the function name alone,
whether the GIL will be released during the call.

The generated wrapper calls `PyEval_SaveThread()` before entering the C
function and `PyEval_RestoreThread()` after returning. Between these
calls, other Python threads may run. The wrapper's argument parsing and
buffer acquisition happen before the GIL is released; buffer release and
result construction happen after it is reacquired.

### OpenMP and Oversubscription

A common misconception is that GIL release is required for OpenMP. It is
not. OpenMP threads are kernel threads created by the C runtime, not
Python threads. They run entirely within the C call and are unaffected
by the GIL. A function using `#pragma omp parallel for` works correctly
whether or not the GIL is released.

The real concern is oversubscription: if N Python threads each call an
OpenMP function that spawns M threads, N*M threads compete for cores.
In this scenario, NOT releasing the GIL may be desirable -- it serializes
the Python threads, preventing oversubscription. Whether to release
depends on the workload.

### The REAL Programmer Model

The design philosophy follows the spirit of "Real Programmers can write
FORTRAN programs in any language." c2py23 does not try to make thread
safety foolproof. It provides mechanisms, not policies:

- The default (GIL held) is safe for all cases.
- The `gil_release` opt-in is for callers who understand their data
  flow and can guarantee that no other thread will concurrently mutate
  the buffers they have passed.
- The buffer reference ensures memory is not freed. Content races are
  the user's problem.

### Global Toggle

A module-level runtime flag `_c2py_gil_release_enabled` allows callers to
globally enable or disable GIL release without recompilation.  The flag is
exposed as a pointer to the C `int` (same scheme as `_c2py_timing_enabled`),
so it must be accessed via `ctypes`:

```python
import ctypes
import mymod

ptr = mymod._c2py_gil_release_enabled
# 1 = enabled, 0 = disabled (default: enabled)
ctypes.c_int.from_address(ptr).value = 0  # disable all GIL release
```

Per-function enable/disable uses the same pattern:

```python
import ctypes
# disable GIL release for a specific function
ptr = mymod._c2py_gil_release_array_stats
ctypes.c_int.from_address(ptr).value = 0
```

### Free-Threading (Python 3.14t)

Free-threaded CPython (3.14+, compiled with `--disable-gil`, commonly named
`python3.14t`) eliminates the Global Interpreter Lock. This enables true
parallelism but introduces ABI differences that affect any C extension that
defines its own CPython types.

#### ABI Differences

The `PyObject` struct layout differs between GIL-enabled and free-threaded builds:

| Field              | Standard (GIL)   | Free-threaded      |
|--------------------|------------------|--------------------|
| sizeof(PyObject)   | 16 bytes (LP64)  | 32 bytes (LP64)    |
| sizeof(PyModuleDef)| 80 bytes         | 120 bytes          |
| ob_refcnt (refcount)| offset 0       | offset 16 (`ob_ref_shared`) |
| ob_type            | offset 8         | offset 24          |

The free-threaded PyObject has additional fields between the thread-id and the
external refcount: `ob_tid` (thread ID), `ob_flags` (biased refcount flags),
`PyMutex ob_mutex` (per-object lock), `ob_gc_bits` (GC state), `ob_ref_local`
(local refcount), then `ob_ref_shared` (the externally visible refcount) at
offset 16, and `ob_type` at offset 24.

c2py23 defines both layouts (`PyObject` / `PyObject_FT`, `PyModuleDef` /
`PyModuleDef_FT`) in `c2py_runtime.h`. Generated wrappers emit both a standard
and a free-threaded `PyModuleDef` at compile time and select the appropriate
one at module init time.

#### Runtime Detection

Detection happens in `c2py_runtime_init()` using multiple methods (first
successful match wins):

1. Version string -- `Py_GetVersion()` is checked for the substring
   `"free-threading"`.
2. `_Py_IsGILEnabled()` -- if available (CPython 3.13+), calling this
   function returns 0 on free-threaded builds, confirming FT status.
3. Module init uses `pthread_once` for thread safety -- ensures multiple
   threads racing to load the module do not double-initialize the runtime.

```c
/* Method 1: version string */
if (strstr(Py_GetVersion(), "free-threading") != NULL) is_ft = 1;

/* Method 2: _Py_IsGILEnabled() fallback */
if (!is_ft) {
    gil_check_fn fn = dlsym(dl, "_Py_IsGILEnabled");
    if (fn && fn() == 0) is_ft = 1;
}
```

When detected, `C2PY.ob_refcnt_offset` is set to 16 (the `ob_ref_shared` field)
instead of 0. Manual refcount operations (`_c2py_inc_ref_manual`) become
fatal -- `Py_IncRef` / `Py_DecRef` must be resolved from the interpreter.

**Note on Python 3.14 standard (GIL) builds:** Python 3.14 uses biased
reference counting (PEP 763) even in standard GIL-enabled builds. This means
`sys.getrefcount()` returns only `ob_ref_shared`, not the total refcount.
Local variable references are tracked in `ob_ref_local` and are invisible to
`sys.getrefcount()`. The c2py23 test suite accounts for this -- refcount
equality assertions are skipped on Python 3.14+ regardless of FT status.
The actual buffer refcounting by the C wrapper remains correct (verified
by 10000-iteration loop tests with stable refcounts).

#### Generated Code

The generator produces dual module definition structs:

```c
/* Standard GIL layout */
static PyModuleDef _module_def = {
    PyModuleDef_HEAD_INIT,
    "modname", NULL, -1, NULL /* m_methods set at init */,
    NULL, NULL, NULL, NULL
};

/* Free-threaded layout */
static PyModuleDef_FT _module_def_ft = {
    PyModuleDef_HEAD_INIT_FT,
    "modname", NULL, -1, NULL /* m_methods set at init */,
    NULL, NULL, NULL, NULL
};
```

At init time, the correct one is selected:

```c
PyObject* PyInit_modname(void) {
    c2py_runtime_init();
    PyMethodDef *methods = C2PY.use_fastcall ? _methods_fastcall : _methods_varargs;

    if (C2PY.is_free_threaded) {
        _module_def_ft.m_methods = methods;
        return C2PY.Module_Create2((PyModuleDef*)&_module_def_ft, 1013);
    } else {
        _module_def.m_methods = methods;
        return C2PY.Module_Create2(&_module_def, 1013);
    }
}
```

No compile-time Python headers are included, so a single `.so` built on any
machine works on both standard and free-threaded interpreters without
recompilation.

#### GIL Behavior on Free-Threaded Builds

When a c2py23 module is loaded on `python3.14t` (or any `--disable-gil`
build), the module does NOT declare `Py_MOD_GIL_NOT_USED`. This triggers
CPython's backward-compatibility mechanism (PEP 703, "Py_mod_gil Slot"):

> *"If the slot is not set, the interpreter pauses all threads and enables
> the GIL before continuing."*

The GIL is re-enabled **globally** for the entire interpreter -- not per-module.
All Python threads become serialized, exactly as on standard CPython.

**What this means in practice:**

- `PyEval_SaveThread()` / `PyEval_RestoreThread()` -- resolved at runtime
  via `dlsym()` from the CPython binary -- now release and re-acquire the
  (re-enabled) GIL. They behave identically to standard CPython.
- The `gil_release: true` option therefore works normally: it releases the
  GIL during C calls, allowing other Python threads to run concurrently.
- Without `gil_release: true`, a C call blocks all other Python threads.
- `Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS` work the same way.

The only case where `PyEval_SaveThread` is truly a no-op is when the GIL
has NOT been re-enabled. This happens when:
- `PYTHON_GIL=0` or `-Xgil=0` overrides GIL re-enablement at the process
  level (see below).
- The module declares `Py_MOD_GIL_NOT_USED` (see next section).

**RuntimeWarning:**

CPython produces a warning on module load:

```
RuntimeWarning: The global interpreter lock (GIL) has been enabled to load
module 'mymod', which has not declared that it can run safely without the GIL.
```

Users who have verified that their C code is thread-safe can suppress the
GIL re-enablement entirely:

```bash
PYTHON_GIL=0 python3.14t -c "import mymod; ..."
python3.14t -Xgil=0 -c "import mymod; ..."
```

Or suppress just the warning:

```python
import warnings
warnings.filterwarnings("ignore", message=".*GIL.*")
```

#### Opting Into Free-Threading with Py_MOD_GIL_NOT_USED

c2py23 provides a `free_threading: true` YAML option to add the `Py_mod_gil`
slot with `Py_MOD_GIL_NOT_USED` (see Option 2 below).
All other modules omit `Py_MOD_GIL_NOT_USED` by design (safe default).
To declare a module free-threading-safe, you have three options:

**Option 1: PYTHON_GIL=0 (runtime, no code changes)**

```bash
PYTHON_GIL=0 python3.14t -c "import mymod; mymod.do_stuff()"
```

This disables GIL re-enablement for the entire process. Your C code must
be thread-safe: c2py23's buffer alias checks prevent concurrent writes to
overlapping buffers, but internal C state (globals, static variables, file
descriptors) and external library calls are your responsibility.

**Option 2: Use `free_threading: true` in your `.c2py` file**

```yaml
module: mymod
source: [mymod.c]
free_threading: true
```

This is the recommended approach. The generator emits:

```c
if (module != NULL && C2PY.Unstable_Module_SetGIL != NULL) {
    C2PY.Unstable_Module_SetGIL(module, 1);  /* Py_MOD_GIL_NOT_USED */
}
```

`PyUnstable_Module_SetGIL` is resolved at runtime via dlsym. It is only
exported from the CPython shared library on `--disable-gil` builds
(3.13+). On standard builds the symbol is not exported, dlsym returns
NULL, and the call is skipped -- no effect, no error. The same `.so`
works on Python 2.7 through 3.15t without recompilation.

**Option 3: Manual wrapper patch**

For cases where you cannot modify the `.c2py` file, add the same call
manually after `c2py23 generate`:

```c
if (module != NULL && C2PY.Unstable_Module_SetGIL != NULL) {
    C2PY.Unstable_Module_SetGIL(module, 1);
}
```

Do NOT use the `PyModuleDef_Slot` mechanism (`Py_mod_gil`) for this.
The slot is only available on Python 3.13+ and using it in a wrapper
compiled without `<Python.h>` requires fragile compile-time version
guards. The `PyUnstable_Module_SetGIL` function approach resolved at
runtime avoids this entirely.

#### Refcounting on Free-Threaded Builds

On free-threaded builds, `Py_INCREF` / `Py_DECREF` use atomic operations.
c2py23 resolves `Py_IncRef` and `Py_DecRef` at runtime (available from
CPython 3.12+). The manual refcount fallback (`_c2py_inc_ref_manual` /
`_c2py_dec_ref_manual`) is **disabled** on free-threaded builds -- if
`Py_IncRef`/`Py_DecRef` cannot be resolved, init fails with a fatal error.
This prevents silent data races from non-atomic `++op->ob_refcnt`.

#### Compatibility Matrix

| Python Build | sizeof(PyObject) | Refcount field | GIL behavior | Supported |
|-------------|-----------------|----------------|-------------|-----------|
| 2.7 - 3.13 (standard) | 16 bytes | `ob_refcnt` at offset 0 | `PyEval_SaveThread` releases | Yes |
| 3.14 (standard) | 16 bytes | Biased: `ob_ref_shared` at offset 0 | `PyEval_SaveThread` releases | Yes |
| 3.14t (free-threaded) | 32 bytes | `ob_ref_shared` at offset 16 | GIL re-enabled globally; `PyEval_SaveThread` releases it (resolved via dlsym) | Yes |

**Note:** Python 3.14 standard (GIL) uses biased reference counting (PEP 763)
where the PyObject layout is unchanged (16 bytes) but `ob_refcnt` is replaced
by `ob_ref_shared`. Local variable references use `ob_ref_local` (thread-local
storage) and are invisible to `sys.getrefcount()`. The c2py23 runtime uses
`Py_IncRef`/`Py_DecRef` (CPython 3.12+ stable ABI) which correctly handle
biased refcounting. The manual fallback (`_c2py_inc_ref_manual`) is not used
on Python 3.14 because `Py_IncRef`/`Py_DecRef` are always available.

## Performance Timing

Set `timing: true` in the `.c2py` module to enable per-function performance
timing.  Each wrapped function and variant gets a `c2py_perf_t` struct that
records tick counts before and after the C call.

### Module-Level Attributes

Modules built with `timing: true` expose:

- **`_c2py_timing_enabled`** -- pointer to an `int` flag (1 = enabled).
  Toggle via `ctypes`:
  ```python
  import ctypes
  ptr = mymod._c2py_timing_enabled
  ctypes.c_int.from_address(ptr).value = 0  # disable
  ```
- **`_perf_<funcname>`** -- pointer to the perf struct for a function.
  For variant groups also `_perf_<funcname>__<variant_c_name>`.
- **`_c2py_tick_frequency()`** -- returns the active tick source frequency in Hz.
  `1000000000` for the default `clock_gettime` source (nanoseconds), or
  the detected CPU cycle counter frequency when `_c2py_set_tick_source("cycle")`
  has been called (0 if detection failed).
- **`_c2py_ticks_to_ns(ticks, freq_hz)`** -- converts a tick count to
  nanoseconds given the frequency.  Returns 0 if `freq_hz` is 0.
- **`_c2py_set_tick_source("clock"|"cycle")`** -- selects the tick source
  at runtime.  `"clock"` (default) uses `clock_gettime` (Unix) or
  `QueryPerformanceCounter` (Windows), returning nanoseconds.  `"cycle"`
  uses the CPU cycle counter (`rdtsc` on x86, `CNTVCT_EL0` on ARM64,
  `mftb`/`__builtin_ppc_get_timebase` on POWER).  Returns a
  `(old_freq_hz, new_freq_hz)` tuple.  Raises `RuntimeError` if the
  cycle counter frequency is not detected on the current platform.
- **`_c2py_cycle_counter_frequency`** -- module attribute: the detected
  CPU cycle counter frequency in Hz, or 0.  Set at init, independent of
  the current tick source selection.

### Decoding Performance Data

The `c2py23.perf` module provides helpers to decode the raw perf structs:

```python
from c2py23.perf import read_perf, read_enabled, set_enabled

import mymod
stats = read_perf(mymod._perf_wsum)
print(stats["c_dur_ns"])       # last call C duration (ns)
print(stats["c_mean_ns"])      # mean C duration (ns)

# Switch to CPU cycle counter at runtime:
mymod._c2py_set_tick_source("cycle")
stats = read_perf(mymod._perf_wsum)
print(stats["c_dur_ns"])       # converted to ns
print(stats["c_dur_cycles"])   # raw cycles
mymod._c2py_set_tick_source("clock")
```

`read_perf(func, variant=None)` returns:
- `call_count`, `t_enter`, `t_pre_c`, `t_post_c`, `t_exit`
- `c_dur_ns`, `wrap_dur_ns`, `c_min_ns`, `c_max_ns`, `c_mean_ns`
- `wrap_min_ns`, `wrap_max_ns`, `wrap_mean_ns`
- When the cycle counter is active: additional `_cycles` keys
  with raw tick values (`c_dur_cycles`, `c_mean_cycles`, etc.)

`read_enabled(func)` returns 0 or 1.  `set_enabled(func, value)`
sets the flag.

### Tick Source

Both the wall-clock timer (`clock_gettime` on Unix, `QueryPerformanceCounter`
on Windows) and the CPU cycle counter (`rdtsc` on x86, `CNTVCT_EL0` on
aarch64, `mftb`/`__builtin_ppc_get_timebase` on POWER) are compiled into
every timing-enabled module.  The tick source is selected at runtime via
`_c2py_set_tick_source()`.  The cycle counter has lower overhead but
returns platform-dependent cycle counts; use `_c2py_ticks_to_ns()` to
convert deltas to nanoseconds.

All tick calls are guarded by `_c2py_do_time` so there is zero overhead
when timing is disabled or not compiled in.

### Address Sanitizer (ASan)

Pass `--asan` to `c2py23 build` or `c2py23 compile` to enable AddressSanitizer:

```bash
c2py23 build --asan module.c2py
c2py23 compile --asan module_wrapper.c -s module.c -o module.so
```

This adds `-fsanitize=address` to the compile and link flags, enabling
detection of buffer overflows and memory leaks during testing.

## SIMD Dispatch and Multi-Flag Compilation

c2py23 provides CPU feature detection and two-level dispatch (buffer-type groups
+ CPU variants) as described in `PLAN.md` P1.  The build system is orthogonal:
c2py23 wraps and links; the user's build system (make, CMake, meson, etc.)
compiles source files with the appropriate `-m` flags.

**Multi-flag compilation pattern**: a single C kernel is compiled multiple times
with different `-m` flags and a `-DKERNEL_FN=<name>` rename macro, producing
ISA-specific object files.  c2py23 lists the `.o` files in `source:` and
dispatches between them via `c_overloads` with `variants:` and `when:` CPU
feature conditions.

See `examples/simd_dispatch/` for a complete worked example (SAXPY kernel
compiled as avx512/avx2/scalar variants, wrapped with grouped dispatch, with
Makefile and Python test harness).

## Future Work

- **aarch64 CI** -- native ARM64 GitHub runner (ubuntu-24.04-arm) added;
  CPU feature flags, SIMD dispatch, and cycle counter timer tested on
  x86_64 and validated on aarch64 hardware.
- **ppc64le CI** -- CPU detection already implemented (getauxval/mftb);
  needs QEMU user-mode or cloud-native runner.
- **Windows free-threading** -- no x64 FT Python builds available on CI yet
- **Binary wheel distribution** -- c2pypi packer for multi-arch PyPI publishing

## Migration Guide: c2ImageD11

c2ImageD11 uses `C2PY_BEGIN` blocks embedded in C comments to define its
c2py23 interface.  The `tools/harvester.py` script extracts these blocks
as Python dicts (via `ast.literal_eval()`), assembles them into a YAML
file (`lib/interface/_cImageD11.c2py`), and runs `c2py23 generate` to
produce the wrapper.

With c2py23's native dict format support, the YAML intermediate step
can be eliminated:

### Before (current harvester)

```python
# Extract C2PY_BEGIN blocks from C sources (unchanged)
# ...
# Convert to YAML and write intermediate file:
yaml_text = yaml.dump(assembled, ...)
with open("_cImageD11.c2py", "w") as f:
    f.write(yaml_text)
# Shell out to c2py23:
subprocess.check_call(["python3", "-m", "c2py23.cli", "generate",
                        c2py_path, "-o", wrapper_path])
```

### After (migration)

```python
# from_c2py_dict parses the dict directly -- no YAML needed.
from c2py23.parser import from_c2py_dict
from c2py23.generator import generate

# Build the assembled dict (same logic as before, skip yaml.dump):
mod = from_c2py_dict(assembled, "_cImageD11")

# Generate wrapper C code directly:
wrapper_code = generate(mod)
with open("_cImageD11_wrapper.c", "w") as f:
    f.write(wrapper_code)
```

### Benefits

- **PyYAML dependency removed** from c2ImageD11's build chain.
- **No YAML intermediate file** -- the C2PY_BEGIN dicts go straight to
  `from_c2py_dict()` / `generate()`.
- **Same C2PY_BEGIN format** -- the inline Python dicts in C comments
  are unchanged.
- **The assembled `_cImageD11.c2py` can switch to dict format** (or be
  removed and generated on-the-fly in CI).

### Recommended workflow

1. Update `harvester.py` to call `from_c2py_dict()` + `generate()` instead
   of writing YAML + shelling out.
2. Convert the committed `lib/interface/_cImageD11.c2py` to Python dict
   format (or remove it and regenerate in CI).
3. Remove PyYAML from `setup.py`/`pyproject.toml`.
4. The CI regeneration step (which runs harvester before meson setup)
   works identically -- the harvester now produces dict-format `.c2py`
   files instead of YAML.
