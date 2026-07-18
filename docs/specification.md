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

The project defines a strict subset language: Python on one side (memory
blocks with metadata  --  acquired via NumPy struct-cast, DLPack, or the
PEP 3118 buffer protocol), C99 on the other (flat pointers, scalar returns).
The interface is described declaratively as a Python dict. The code generator
transpiles this into a CPython C extension that acquires pointers to the
underlying memory, then dispatches to the right C function based on buffer
properties: element type, dimensionality, and layout. The wrapper itself is
zero-copy and allocation-free.

c2py23 targets the narrow intersection of C99, Python 2.7, and Python 3.x
that avoids the Unicode/bytes schism entirely: parameters are parsed as
flat pointers (buffers) or numbers (int, float). Error messages and
attribute names are C string literals. Variant names use ASCII bytes.
There are no keyword arguments, no Python strings, no Unicode objects,
and no string encodings anywhere in the wrapper ABI or the generated C code.
This design eliminates an entire category of Python 2/3 portability bugs.

The long-term goal is a substrate for:
- SIMD dispatch within C functions, potentially at the wrapper level
- Accurate timing instrumentation (cycle counters, wall-clock)
- GIL release for pure-C sections
- Thread-safe extensions in free-threaded Python builds (3.14t+)

## Grammar

### Python Dict Format (Canonical)

The Python dict format is the canonical representation.  When embedding
c2py23 definitions in C source comments (C2PY_BEGIN blocks), the dict
format is used because it parses safely via `ast.literal_eval` with
no external dependencies.  An early version of c2py23 used YAML as the
interface format but this was removed in v0.4.0 -- YAML's indentation
rules and C-extension dependency (PyYAML) proved too fragile for the
cross-platform, backwards-compatible mission.  The `tools/convert_c2py_to_dict.py`
script in the source repository can migrate legacy YAML files.

The `load_c2py()` function auto-detects the format:

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
            "acquire": ["ndarray", "buffer"],          # optional: backend order
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

The key names and values are shown in the schema below.
Differences from YAML (legacy, no longer supported):

- Dict keys use Python strings (e.g. "c_overloads", "py_sig", "when")
- **Boolean values**: `True`/`False`
- **None** (optional keys omitted or set to `None`)
- **Strings** use Python quoting (single or double)
- **No indentation sensitivity** -- dict boundaries are `{`/`}`

The `load_c2py()` function supports both dict format (.c2py) and C2PY_BEGIN blocks (.c/.h):

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

# Export to .c2py dict format (requires source checkout: tools/convert_c2py_to_dict.py):
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

### .c2py File Format (Python dict)

The `.c2py` file is a Python dict literal (parsed via `ast.literal_eval`).
The canonical example above shows all available keys.

**Dict ordering guarantee:** c2py23 never relies on Python dict insertion
order for correct behavior.  All ordering-dependent data (`"c_overloads"`,
`"variants"`, `"functions"`, `"checks"`, Python and C signature parameter
lists) is stored in Python lists, which always preserve declaration order
on every Python version (2.7 through 3.15).  Dicts (`"map"`, `"outputs"`,
`"constants"`, `"params"`) are accessed exclusively via key lookup.  No
`OrderedDict` is required.

Additional per-key details:

**Module-level keys:**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `"module"` | `str` | yes | Python module name |
| `"source"` | `list[str]` | yes | C source files |
| `"headers"` | `list[str]` | no | C headers to `#include` |
| `"constants"` | `dict[str, int]` | no | module-level integer constants |
| `"timing"` | `bool` | no | enable perf timing |
| `"free_threading"` | `bool` | no | declare `Py_MOD_GIL_NOT_USED` |

**Per-function keys:**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `"py_sig"` | `str` | yes | Python signature `"name(arg: type, ...) -> ret"` |
| `"doc"` | `str` | no | custom docstring |
| `"params"` | `dict[str, str]` | no | per-parameter descriptions |
| `"gil_release"` | `bool` | no | release the GIL during C calls |
| `"acquire"` | `list[str]` | no | acquisition backend order (default: `["ndarray", "buffer"]`) |
| `"expand"` | `dict[str, list[str]]` | no | template expansion variables |
| `"checks"` | `list[str]` | no | pre-condition expressions |
| `"c_overloads"` | `list[dict]` | yes | ordered list of C overloads |
| `"default_raise"` | `str` | no | error when no overload matches |

**Per-overload keys (flat):**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `"sig"` | `str` | yes | C function signature |
| `"map"` | `dict[str, str]` | yes | C param name to expression |
| `"when"` | `str` | no | dispatch condition |
| `"name"` | `str` | no | label for timing/reference |
| `"doc"` | `str` | no | per-overload notes in docstring |
| `"outputs"` | `dict[str, str]` | no | return-by-pointer scalar params |

**Grouped dispatch (instead of flat `"sig"`):**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `"map"` | `dict[str, str]` | yes | shared argument map for all variants |
| `"when"` | `str` | no | per-call group dispatch condition |
| `"group"` | `str` | no | group name for rebind/docstrings |
| `"doc"` | `str` | no | group-level docstring notes |
| `"variants"` | `list[dict]` | yes | variant list, each with `"sig"`, optional `"when"`, `"name"`, `"outputs"`, `"default"`

### Template Expansion (expand:)

The `expand:` key produces multiple function definitions from a single template
via `${VAR}` string substitution. All value lists under `expand:` must have the
same length N. For each index i, a copy of the function definition is generated
with `${VAR}` replaced by `values[i]` in all string fields.

```python
{
    "functions": [
        {
            "expand": {
                "TYPE": ["uint8_t", "uint16_t", "int32_t"],
                "SUFFIX": ["u8", "u16", "i32"],
            },
            "py_sig": "sum_${SUFFIX}(data: buffer) -> int",
            "c_overloads": [
                {
                    "sig": "int sum_${SUFFIX}(const ${TYPE} *data, int n)",
                    "map": {
                        "data": "data.ptr",
                        "n": "data.n",
                    },
                },
            ],
        },
    ],
}
```

Expands to three functions: `sum_u8`, `sum_u16`, `sum_i32`.

### Output Scalars (outputs:)

The `outputs:` key on a C overload declares parameters that are written by the
C function rather than passed by the Python caller. c2py23 auto-allocates a
1-element stack variable, passes a pointer to the C function, and returns the
resulting value as part of the Python return tuple.

```python
{
    "c_overloads": [
        {
            "sig": "stats(const double *data, int n, double *minval, double *maxval)",
            "map": {
                "data": "data.ptr",
                "n": "data.n",
            },
            "outputs": {
                "minval": "double",
                "maxval": "double",
            },
        },
    ],
}
```

Python call returns a tuple:
```python
minval, maxval = statmod.stats(data)
```

If there is also a C return value, it comes first in the tuple.

**Tuple order**: The order of values in the returned tuple always follows the C
function parameter order (left to right in the C signature), not the
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
- `buffer` -- any Python object that can provide a pointer to memory plus metadata
  (shape, strides, dtype). Acquired via one of three backends, tried in the order
  specified by the `acquire:` key (default: ndarray struct-cast, then PEP 3118
  buffer protocol). Const pointers are read-only; non-const pointers are read-write.
- `int` -- Python int, converted to C `int`
- `float` -- Python float, converted to C `double`

Returns:
- `void` -- the Python function returns `None`
- `int` -- the C function returns `int`, converted to Python `int`
- `float` -- the C function returns `float` or `double`, converted to Python `float`

### Opaque Pointers (`void*`)

A C parameter with type `void*` maps from Python `int` (a pointer-width integer).
The wrapper casts through `intptr_t` and never dereferences the pointer:

```python
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

```python
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

```python
map: {a: "a.ptr", n: "a.slow_dim", out: "out.ptr"}
```

This works for any ndim -- `slow_dim` is always the size of the axis
that the C loop iterates over.

#### Quoting in map values

In the dict format `.`, `[`, `(`, and spaces as syntax.  Values containing
these characters MUST be quoted:

```python
map: {ng: "gv.shape[0]"}     # quoted -- . and [ are Python syntax
map: {ptr: "buf.ptr"}        # quoted -- . is Python syntax
map: {tol: tol}               # no quotes -- bare scalar
```

The rule: bare dict values (scalars, ints) need no quotes; any value
containing `.`, `[`, `(`, or whitespace must be quoted.

#### Variant Ordering

Variant dispatch respects declaration order. The first variant whose
`when:` condition matches wins auto-dispatch. Variants are stored in
lists, so declaration order is always preserved across all Python versions.

Variants with `default: False` are skipped during auto-resolve and are
reachable only via `_rebind_<name>()`. At least one variant per group
must have `default: True` (the default).

#### Variant Naming

The `name` field on a variant defaults to the C function name extracted
from `sig` (e.g., `poly_f32_avx512`). If specified, `name` must match
the C function name exactly  --  enforced at parse time. This ensures
`_variants_<name>()` returns names that correspond to real .so symbols.

```python
variants:
  - sig: "void poly_f32_avx512(...)"   # name -> "poly_f32_avx512"
    when: "c2py_amd64_avx512f"
  - sig: "void poly_f32_scalar(...)"   # name -> "poly_f32_scalar"
```

#### Variant Enumeration and Rebind

Every function with grouped variants gets:

- `_rebind_<name>(variant_name)`  --  sets the active variant by name.
  Call with `None` to re-run auto-resolve.
- `_variants_<name>()`  --  returns a tuple of all variant names (including
  `default: False` variants) in declaration order.

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
```python
{
    "module": "arraysum",
    "source": ["arraysum.c"],
    "functions": [
        {
            "py_sig": "array_sum(a: buffer, b: buffer, result: buffer) -> int",
            "checks": [
                "a.format == 'd'",
                "b.format == 'd'",
                "result.format == 'd'",
                "a.n == b.n",
                "a.n == result.n",
            ],
            "c_overloads": [
                {
                    "sig": "array_sum(const double *a, const double *b, double *result, int n) -> int",
                    "map": {
                        "a": "a.ptr",
                        "b": "b.ptr",
                        "result": "result.ptr",
                        "n": "a.n",
                    },
                },
            ],
        },
    ],
}
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
```python
{
    "module": "fillmod",
    "source": ["fill.c"],
    "functions": [
        {
            "py_sig": "fill(arr: buffer, value: float) -> void",
            "c_overloads": [
                {
                    "sig": "fill_f(float *arr, int n, float value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'f'",
                },
                {
                    "sig": "fill_d(double *arr, int n, double value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'd'",
                },
            ],
            "default_raise": "TypeError: expected float or double buffer",
        },
    ],
}
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
```python
{
    "module": "xfrm",
    "source": ["transform.c"],
    "timing": True,
    "functions": [
        {
            "py_sig": "transform(points: buffer, out: buffer) -> void",
            "checks": [
                "points.format == 'd'",
                "out.format == 'd'",
                "out.n == points.n",
                "points.ndim == 2",
                "points.slow_axis == 0",
            ],
            "c_overloads": [
                {
                    "sig": "transform_aos(double *points, intptr_t n, double *out)",
                    "map": {
                        "points": "points.ptr",
                        "n": "points.shape[0]",
                        "out": "out.ptr",
                    },
                    "when": "points.shape[1] == 3",
                },
                {
                    "sig": "transform_soa(double *points, intptr_t n, double *out)",
                    "map": {
                        "points": "points.ptr",
                        "n": "points.shape[1]",
                        "out": "out.ptr",
                    },
                    "when": "points.shape[0] == 3",
                },
            ],
            "default_raise": "ValueError: expected [N,3] or [3,N] buffer",
        },
    ],
}
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
```python
{
    "module": "dispatchmod",
    "source": ["typedispatch.c"],
    "headers": ["stdint.h"],
    "functions": [
        {
            "py_sig": "fill(arr: buffer, value: float) -> void",
            "c_overloads": [
                {
                    "sig": "fill_u8(uint8_t *arr, int n, uint8_t value)",
                    "when": "arr.format == 'B'",
                },
                {
                    "sig": "fill_i8(int8_t *arr, int n, int8_t value)",
                    "when": "arr.format == 'b'",
                },
                {
                    "sig": "fill_u16(uint16_t *arr, int n, uint16_t value)",
                    "when": "arr.format == 'H'",
                },
                {
                    "sig": "fill_i16(int16_t *arr, int n, int16_t value)",
                    "when": "arr.format == 'h'",
                },
                {
                    "sig": "fill_u32(uint32_t *arr, int n, uint32_t value)",
                    "when": "arr.format == 'I'",
                },
                {
                    "sig": "fill_i32(int32_t *arr, int n, int32_t value)",
                    "when": "arr.format == 'i'",
                },
                {
                    "sig": "fill_u64(uint64_t *arr, int n, uint64_t value)",
                    "when": "arr.format == 'Q'",
                },
                {
                    "sig": "fill_i64(int64_t *arr, int n, int64_t value)",
                    "when": "arr.format == 'q'",
                },
                {
                    "sig": "fill_f32(float *arr, int n, float value)",
                    "when": "arr.format == 'f'",
                },
                {
                    "sig": "fill_f64(double *arr, int n, double value)",
                    "when": "arr.format == 'd'",
                },
            ],
            "default_raise": "TypeError: expected buffer of type B,b,H,h,I,i,Q,q,f,d",
        },
    ],
}
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

## Acquisition Backends

For each `buffer` parameter, c2py23 tries acquisition backends in the order
specified by the `acquire:` key:

| Backend | C constant | Method | Overhead (vnorm tiny) |
|---------|-----------|--------|----------------------|
| `ndarray` | `C2PY_PIN_NDARRAY` | NumPy struct-cast (zero API calls) | **~75ns** |
| `buffer` | `C2PY_PIN_PEP3118` | PEP 3118 `PyObject_GetBuffer` | ~162ns |
| `dlpack` | `C2PY_PIN_DLPACK` | `__dlpack__()` capsule extraction | ~381ns |

Default order is `[ndarray, buffer]` -- the ndarray struct-cast is tried first
and succeeds for `numpy.ndarray` objects (detected via type-pointer comparison,
no import of numpy). For non-numpy types (array.array, memoryview, ndarray
subclasses, masked arrays), the ndarray check fails in ~1ns and falls through
to the buffer protocol.

Use `acquire: [buffer]` to disable the ndarray fast-path (e.g., if wrapping a
non-numpy buffer library). Use `acquire: [ndarray, dlpack, buffer]` for
maximum portability across numpy, DLPack exporters, and buffer-protocol objects.

The DLPack backend is slower for CPU arrays (~381ns) because `__dlpack__()`
is a Python method dispatch. Its value is for GPU device pointers (CuPy,
PyTorch) where the buffer protocol cannot return a GPU address, and for
non-CPython runtimes (PyPy, GraalPy) where the buffer protocol emulation
is slow.

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

Takes `PyObject *self, PyObject *args` (METH_VARARGS). Structure:

```
1. PyArg_ParseTuple -- extract Python objects and scalar values
2. c2py_pin -- for each buffer param, acquire pointer+metadata via
   the configured backend order (ndarray struct-cast, buffer protocol,
   or DLPack). The info is stored in a unified c2py_ptr_info struct.
3. Restrict checks -- verify no writable buffer aliases any other buffer
4. Call _impl function (receives c2py_ptr_info* pointers)
5. Cleanup -- c2py_unpin_buffer for each acquired buffer
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

#### Example of auto-generated docstrings

With `doc:` set:

```python
{
    "functions": [
        {
            "py_sig": "inc(x: int) -> int",
            "doc": "Increment x by 1 and return the result",
            "c_overloads": [
                {
                    "sig": "add_one(int x) -> int",
                    "map": {"x": "x"},
                },
            ],
        },
    ],
}
```

`help(inc)` in Python produces:

```
inc(x)
--

inc(x: int) -> int

Increment x by 1 and return the result

Parameters
----------
x : int

Overloads
---------
  add_one(int x) -> int
    Map: x = x (int)
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
- The GIL is held during all C function calls by default (see [GIL Release](#gil-release-and-thread-safety))
- `restrict` is enforced at the wrapper level: aliasing writable buffers raises `ValueError`.

  In C99, `restrict` is a promise from the programmer to the compiler that
  two pointers will never alias (point to overlapping memory).  c2py23 provides
  this same guarantee at runtime: before calling your C function, the wrapper
  checks that no writable output buffer overlaps with any other buffer.
  If aliasing is detected, `ValueError` is raised before the C call.
  This lets you write C code that looks like FORTRAN -- flat arrays, no
  pointer provenance complications, just numerical loops over disjoint memory.
  As Ed Post wrote in 1983: "Real Programmers can write FORTRAN programs in
  any language."

```python
{
    "functions": [
        {
            "py_sig": "compute(data: buffer) -> void",
            "gil_release": True,
        },
    ],
}
```

## GIL Release and Thread Safety

On Python 3.14t (free-threading), the GIL is disabled by default but
c2py23 modules re-enable it unless `free_threading: true` is declared at
module level:

```python
{
    "module": "mymod",
    "free_threading": True,
}
```

See the [User Guide](user_guide.md) for full thread safety guidance
including static buffer hazards, OpenMP interaction, and free-threading
compatibility.

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

Set compiler flags via environment variables when building:

```bash
CC=gcc CFLAGS="-fsanitize=address -g -O1" LDFLAGS="-fsanitize=address" python tests/runner.py
```

This adds `-fsanitize=address` to the compile and link flags via setuptools, enabling
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

## Build Modes

c2py23 supports multiple build modes for different runtimes:

- **dlsym mode** (default)  --  Uses `dlopen(NULL)`/`dlsym()` (the nimpy trick).
  No `#include <Python.h>`, no `-lpython`.  One `.so` works on Python 2.7 through
  3.15.  The most portable option.

- **`--pythonh` mode**  --  Standard CPython extension with `#include <Python.h>`.
  Build with `python tests/setup.py build_ext --inplace --pythonh`.  Required for
  GraalPy (Native Image `dlopen(NULL)` exports zero symbols).  Useful for debugging
  dlsym issues, static builds, and LTO devirtualization.  See `docs/pythonh.md`.

- **PyPy**  --  Build with `CC=gcc CFLAGS="-DC2PY_TARGET_PYPY -O1"`.  Produces
  PyPy-compatible `.so` files that resolve `PyPy_*`-prefixed cpyext symbols at
  runtime.  `import` on PyPy requires `ExtensionFileLoader` (PyPy only recognizes
  ABI-tagged suffixes).  CI runs full test suite on PyPy 3.9/3.10.

- **Pyodide/WASM**  --  Build with `emcc -s SIDE_MODULE=1`.  23 WASM modules,
  80/80 tests pass inside Pyodide via Node.js.  Uses `dlopen(NULL)`/`dlsym()`;
  DLPack works (numpy exports `__dlpack__`).  See `docs/building.md` for emcc flags.

## Ongoing Work

- **ppc64le CI** -- CPU detection implemented (getauxval/mftb); needs QEMU or cloud runner.
- **Windows free-threading** -- no x64 FT Python builds available on CI yet.

## Migration Guide: c2ImageD11

c2ImageD11 uses `C2PY_BEGIN` blocks embedded in C comments to define its
c2py23 interface.  The `c2py23.harvester` module extracts these blocks
as Python dicts (via `ast.literal_eval()`), assembles them into a YAML
file (`lib/interface/_cImageD11.c2py`), and runs `c2py23` to
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
subprocess.check_call(["python3", "-m", "c2py23",
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
