# c2py23 User Guide

## Introduction

c2py23 wraps C99 functions as Python C extensions using the buffer protocol.
One compiled `.so` works on Python 2.7 through 3.15 with no recompilation.
The wrapper is zero-copy and allocation-free -- Python owns all memory,
C functions receive raw pointers and operate in-place.

**Key features:**
- Zero-copy buffer access (raw C pointers from Python buffers)
- Format dispatch (route to different C functions based on dtype)
- Shape dispatch (AoS vs SoA, variable dimensions)
- CPU feature dispatch (compile with AVX-512/AVX2/NEON and select at runtime)
- GIL release for concurrent C computation
- Free-threading support for Python 3.14t+
- Performance timing instrumentation
- Multi-platform wheel packaging

## How It Works

The pipeline has three steps:

1. **Write a `.c2py` interface file** -- a Python dict literal describing your
   C function signatures, buffer dtype checks, and dispatch conditions.
2. **Generate the wrapper** -- `c2py23 mymod.c2py -o mymod_wrapper.c` transpiles
   the interface into a compilable C99 source file.
3. **Compile and import** -- build the `.so` with any C99 compiler, then
   `import mymod` from Python and call your wrapped C functions.

The `.so` uses the **nimpy trick**: all CPython API symbols (`PyObject_GetBuffer`,
`PyTuple_New`, etc.) are resolved at module load time via `dlopen(NULL)`/`dlsym()`.
This means the compiled binary never links against `-lpython` and never
`#include <Python.h>`. One `.so` works on Python 2.7 through 3.15.

## Acquisition Backends

When your Python code calls a wrapped function with a `buffer` parameter,
c2py23 must acquire a raw C pointer from the Python object. Three backends
are available, selected per-function via the `"acquire"` key:

| Backend | C constant | Method | Overhead | When to Use |
|---------|-----------|--------|---------|-------------|
| `ndarray` | `C2PY_PIN_NDARRAY` | NumPy struct-cast (zero API calls) | ~75 ns | **Default.** Fastest for numpy arrays. Fails transparently for non-numpy objects. |
| `buffer` | `C2PY_PIN_PEP3118` | PEP 3118 `PyObject_GetBuffer` | ~162 ns | ctypes, `array.array`, `memoryview`, any buffer-protocol object. Python 2.7 falls back to the old buffer API, which only provides bytes (format `'B'`): on 2.7 `array.array` passes byte checks only. |
| `dlpack` | `C2PY_PIN_DLPACK` | `__dlpack__()` capsule extraction | ~381 ns | Non-CPython runtimes (PyPy, GraalPy); exporters without the buffer protocol. CPU tensors only. Honours the DLPack 1.0 read-only flag. |

The default order is `["ndarray", "buffer"]` -- the ndarray fast-path is
tried first. For non-numpy types, the struct-cast check fails in ~1 ns and
falls through to the buffer protocol. Use `"acquire": ["buffer"]` to only
use the PEP 3118 path. Use `"acquire": ["ndarray", "dlpack", "buffer"]` for
maximum portability across numpy, DLPack exporters, and buffer-protocol objects.

### Choosing Between dlsym and --pythonh

c2py23 supports two build modes for the runtime:

| Mode | How | Portability | When to Use |
|------|-----|-------------|-------------|
| **dlsym** (default) | `dlopen(NULL)`/`dlsym()` | One `.so` for Python 2.7-3.15, all platforms | Default. Works on CPython, Pyodide/WASM, PyPy. |
| **--pythonh** | `#include <Python.h>`, link `-lpython` | One `.so` per Python version | GraalPy (no exported CPython symbols), debugging, LTO devirtualization |

Build dlsym mode:
```bash
cc -shared -fPIC -I c2py23/runtime wrapper.c mysource.c \
   c2py23/runtime/c2py_runtime.c -ldl -lm -o mymod.so
```

Build pythonh mode:
```bash
python tests/setup.py build_ext --inplace --pythonh
```

See `docs/pythonh.md` for full pythonh documentation, and `docs/building.md`
for cmake, meson, and setuptools build integration.

## Quick Reference

```python
{
    "module": "mymod",
    "source": ["mymod.c"],
    "timing": False,                       # enable perf timing (optional)
    "free_threading": False,               # declare module safe for 3.14t (optional)
    "functions": [
        {
            "py_sig": "myfunc(a: buffer, n: int) -> int",
            "checks": [
                "a.format == 'd'",
                "a.n > 0",
            ],
            "c_overloads": [
                {
                    "sig": "myfunc_c(const double *a, int n) -> int",
                    "map": {
                        "a": "a.ptr",
                        "n": "n",
                    },
                },
            ],
        },
    ],
}
```

## Variant Rebind and the `when:` Guard

A variant is one member of a grouped overload (a `group:` with several
`variants:`).  By default the wrapper selects the active variant in order,
evaluating the `when:` condition of each.  `_rebind_<name>("variant")` forces
a variant by name WITHOUT evaluating its `when:` condition, so Python code can
select a kernel the current CPU does not support (for example forcing an
AVX-512 variant on a CPU without AVX-512).  That can SIGILL.  It is intended
for benchmarking, so treat it as a sharp edge and restore auto-dispatch with
`_rebind_<name>(None)`:

```python
polysimd._rebind_poly("poly_f32_scalar")  # force the scalar fallback
polysimd._rebind_poly(None)               # back to auto-dispatch on when:
```

## For Python Programmers: A C Tutorial

c2py23 wraps C99 functions. The C you need to write is deliberately simple:
flat arrays ("buffers"), scalar inputs, and scalar or void returns.

### Pointers and Buffers

A Python `buffer` parameter becomes a C pointer:

```python
# Python side: pass any buffer-protocol object
"py_sig": "process(data: buffer) -> void"
```
```c
/* C side: receive a raw pointer */
void process(const double *data, intptr_t n) {
    for (intptr_t i = 0; i < n; i++)
        data[i] *= 2.0;
}
```

The pointer has **no bounds information** -- the element count `n` must be
passed separately (derived from `data.n` in the `"map"` block). Always add
`"checks"` to validate buffer sizes before the C call:

```python
"checks": [
    "data.format == 'd'",
    "data.n > 0",
],
```

### Const and Writable Buffers

`const double *data` is read-only. `double *out` is writable. c2py23 checks
that writable buffers do not alias (overlap) each other:

```python
# c2py23 raises ValueError if 'out' overlaps with 'a' or 'b'
"py_sig": "add(a: buffer, b: buffer, out: buffer) -> void"
```

Set `"check_aliasing": false` on a function to skip this scan when the
caller guarantees the buffers are disjoint (a hot path); this gives up the
runtime safety net and relies on the C signature's `restrict` promise.
The check is cheap, so keep the default unless a profile says otherwise.

### Memory Ownership

**Python owns all memory.** Your C function receives pointers to
Python-allocated buffers. Never call `free()` on these pointers. If your C
code needs temporary workspace, allocate it on the stack or receive it as
another buffer parameter.

### Return Values

C functions can return `void`, `int`, `float`, or `double`. For multiple
outputs, use the `"outputs"` key to declare output-by-pointer parameters:

```python
"outputs": {
    "minval": "double",
    "maxval": "double",
}
```

c2py23 allocates a 1-element stack variable, passes the address to your C
function, and returns the values as a Python tuple.

### Built on FORTRAN's Philosophy

c2py23 enforces a FORTRAN-like programming model in C: flat numeric arrays,
no aliasing between outputs, memory owned by the caller. C's `restrict`
keyword is enforced at the wrapper level. This eliminates pointer provenance
issues, use-after-free bugs, and ownership confusion -- you write simple
loops over disjoint arrays, and the wrapper handles the rest.

### Batch Dimensions and Optional Leading Axes

A common pattern: you write a C function that processes one element and want
to extend it to handle many. C has no concept of "missing dimensions," but
the resulting Python API should feel natural for both single-element and
batched calls.

**The scenario.** Your C function operates on a batch of 3x3 matrices and
returns one score per matrix:

```c
/* C: processes N matrices, returns N doubles */
void score_batch(const double ubi[][3][3], double *out, intptr_t n) {
    for (intptr_t b = 0; b < n; b++) {
        out[b] = trace(ubi[b]);
    }
}
```

You want Python callers to be able to pass either a single `[3, 3]` matrix
or a batch of `[N, 3, 3]` matrices.

**The solution: require `[1, 3, 3]` for the single case.** The `.c2py`
interface expects the full dimensionality. There is no automatic promotion:

```python
{
    "py_sig": "score(ubi: buffer, out: buffer) -> void",
    "c_overloads": [{
        "sig": "void score_batch(const double ubi[][3][3], double *out, intptr_t n)",
        "map": {
            "ubi": "ubi.ptr",
            "out": "out.ptr",
            "n": "ubi.shape[0]",
        },
    }],
    "checks": [
        "ubi.format == 'd'",
        "out.format == 'd'",
        "out.n >= ubi.shape[0]",
    ],
}
```

On the Python side, the caller adds the leading dimension explicitly:

```python
import ctypes

# Single 3x3 -- cast to shape [1, 3, 3]
ubi = (ctypes.c_double * 9)(*[1.0, 0.0, 0.0,
                               0.0, 1.0, 0.0,
                               0.0, 0.0, 1.0])
out = (ctypes.c_double * 1)()
mv = memoryview(ubi).cast("B").cast("d", [1, 3, 3])
mymod.score(mv, out)
assert out[0] == 3.0

# Batch of 5 -- cast to shape [5, 3, 3]
ubi5 = (ctypes.c_double * 45)(*range(45))
out5 = (ctypes.c_double * 5)()
mv5 = memoryview(ubi5).cast("B").cast("d", [5, 3, 3])
mymod.score(mv5, out5)
```

With numpy, use `ubi.reshape(1, 3, 3)` or `ubi[np.newaxis, :, :]` to add
the leading dimension. Both are zero-copy operations.

**Why no automatic promotion?** c2py23 never copies, allocates, or reshapes
data behind your back. Promoting a `[3, 3]` buffer to `[1, 3, 3]` would
require either copying the data or synthesizing a new shape array inside the
wrapper. Both violate c2py23's design rules: wrappers are 100%
allocation-free, all memory is owned by Python, and pointers go directly to
the original buffer with no intermediate transformation. The caller controls
the layout, and inserting a `1` dimension costs one `.cast()` or
`.reshape()` call -- explicit, fast, and zero-copy.

The same principle applies to any function where a caller might have a
lower-dimensional buffer than the C signature expects: just add a `1`
dimension on the Python side. It is always valid because `shape == 1`
dimensions contribute zero stride difference in contiguous layouts.

## Writing Safe .c2py Definitions

**Always validate buffer dimensions in `checks:` blocks.**  Without size
checks, a caller can pass a too-small output buffer, causing the C function
to write past the end and produce a segfault or silent memory corruption.

The C function receives raw pointers with no bounds information. If the
Python caller passes a 100-element output buffer for a function expecting
1000 elements, the C code will write 900 elements past the buffer end.
There is no runtime instrumentation to catch this; the ONLY defence is the
`checks:` block together with the element-type and alignment checks below.

### Checks the generator derives for you

c2py23 derives several checks automatically, so the default is safe and an
explicit `checks:` block is an addition rather than the only defence:

1. **Element type.**  For every C pointer parameter mapped to exactly
   `buf.ptr`, the generator derives an element-type check from the pointee
   type (`double *` -> `'d'`, `int32_t *` -> `'i'`/`'l'` with itemsize 4,
   `char *` -> itemsize 1, `void *` -> none; the table is in
   `docs/specification.md`).  An explicit `"buf.format == 'd'"` check is
   still allowed and replaces the derived one for that buffer, keeping the
   same dispatch.  Pointee types outside the table get a generation-time
   warning and no check -- write the check yourself.  Set
   `"check_format": False` on a function to opt out (for example to
   reinterpret raw bytes as `double *`).
2. **Dimensionality.**  `"buf.ndim == 1"` or `"buf.ndim == 2"` rejects
   unexpected shapes.
3. **Alignment.**  Every non-empty buffer must be aligned to its itemsize.
   This is checked automatically right after contiguity and raises
   `ValueError: f: arg 'a': buffer not aligned to its element size
   (itemsize 8, address % 8 == 1); pass an aligned copy, ...`.  Set
   `"check_alignment": False` when your C code tolerates unaligned pointers.
   For stricter SIMD alignment use `"buf.ptr % 32 == 0"` in a `when:`
   condition.
4. **Size relationships.**  `"ibuf.n == obuf.n"` or `"obuf.n >= ibuf.n + 2"`
   -- the single most important check for preventing segfaults.

### Bounds-safe shape and stride access

`buf.shape[k]` and `buf.strides[k]` are bounds-safe.  Reading an out-of-range
`k` never reads out of bounds, and an overload whose `map:` reads `buf.shape[k]`
or `buf.strides[k]` is only eligible when the buffer has more than `k`
dimensions.  If no overload accepts the buffer, the wrapper raises `ValueError`
naming the buffer and the `ndim` it needs rather than crashing.

### How arithmetic on `buf.ptr` is treated

`buf.ptr` is a raw pointer.  Arithmetic on it is rejected: `buf.ptr + off`,
`buf.ptr - 1` and `off + buf.ptr` all raise `ValueError` at generation time
(pass the offset to the C function as a separate argument instead).  The one
exception is the alignment idiom `buf.ptr % N` in a `when:` condition, which
selects an overload on pointer alignment, e.g. `"a.ptr % 32 == 0"` for a SIMD
kernel.  `N` must be a positive integer literal or scalar, and the generator
reduces the pointer in `uintptr_t`.

### Example: safe output buffer sizing

```python
# Correct: validates output is large enough
checks:
  - "a.format == 'f'"
  - "out.format == 'f'"
  - "out.n >= a.n"          # output at least as large as input

# Wrong: missing size check -- segfault if out is too small
checks:
  - "a.format == 'f'"
  - "out.format == 'f'"
```

### Additional safe checks to consider

- **Contiguity:** c2py23 enforces C/F-contiguity automatically, but check for
  specific expectations (e.g., C-order only)
- **Non-empty:** `"buf.n > 0"` when zero-length would be invalid
- **Alias:** c2py23 checks writable buffer aliasing at runtime; add
  `default_raise:` for a clear error message.  Set `check_aliasing: false`
  only when the caller guarantees non-overlap and the check is hot.

### Format char portability: never use `'l'` or `'L'` for fixed-width dispatch

The PEP 3118 format characters `'l'` (signed long) and `'L'` (unsigned long)
are **platform-sized**: `sizeof(long)` differs between LP64 (Linux/macOS, 8
bytes) and LLP64 (Windows 64-bit, 4 bytes).  A buffer with format `'l'` has
8-byte elements on Linux but 4-byte elements on Windows.

**Do not rely on `'l'`/`'L'` for fixed-width dispatch.**  Use the format
characters that have guaranteed sizes on all platforms:

| Format | C type | Size (all platforms) |
|--------|--------|---------------------|
| `'i'` / `'I'` | `int32_t` / `uint32_t` | 4 bytes |
| `'q'` / `'Q'` | `int64_t` / `uint64_t` | 8 bytes |

c2py23 generates a runtime `itemsize == sizeof(long)` check alongside format
comparisons for `'l'`/`'L'`, so these characters remain usable if you need
platform-native `long` semantics.  But the generated `.so` or `.pyd` will
dispatch to different C code on different platforms -- do not depend on
`'l'`/`'L'` mapping to a specific fixed-width type.

### Buffer writability and overload dispatch

When a function has multiple overloads, the wrapper acquires each buffer with
`PyBUF_WRITABLE` if **any** overload writes to it. If you add a read-only
overload alongside a writable overload for the same buffer parameter, callers
will be forced to provide writable buffers for the read-only path. Keep this
in mind when mixing read and write overloads.

### Subclasses and masked arrays

numpy subclasses use their base class's buffer layout, not the subclass.  A
`numpy.ma.MaskedArray` is passed to your C function as its underlying data
with the mask silently ignored -- the mask is not checked and is not passed.
If a mask matters, validate it yourself on the Python side.

## For C Programmers: A Python Tutorial

### The Buffer Protocol

Python's PEP 3118 buffer protocol is the key interface. Any object that
exposes a flat memory region can be used as a `buffer` parameter:
- `ctypes` arrays (Python 2.7+)
- `memoryview` (Python 3.3+)
- `numpy.ndarray`
- `array.array`
- `bytearray` / `bytes`

```python
import ctypes
a = (ctypes.c_double * 1000)(*range(1000))   # allocate 1000 doubles
out = (ctypes.c_double * 1000)()             # zero-initialized
mymod.process(a, out)                        # C receives raw pointers
```

### How the `.so` Loads

c2py23 modules are compiled `.so` files. They use `dlopen(NULL)` +
`dlsym()` at init time to resolve all CPython API functions from the
running interpreter. This means:
- The `.so` has no compile-time dependency on `Python.h`
- The same `.so` binary imports into Python 2.7, 3.6, ..., 3.15
- On PyPy, the `.so` resolves `PyPy_*`-prefixed symbols instead
- On GraalPy, use `--pythonh` mode (see `docs/pythonh.md`)

### No Heap Allocation in Wrappers

The generated wrapper never calls `malloc`, `calloc`, `realloc`, or `free`.
All memory comes from Python. Your C code owns nothing that Python didn't
provide. This means no leaks, no double-frees, and no ownership confusion.

### The Call Flow

When Python calls `mymod.myfunc(a, b, out, 42)`:

1. `PyArg_ParseTuple` extracts the Python objects and scalar values
2. `c2py_pin` acquires raw pointers from each buffer object (using the
   configured acquisition backend: ndarray struct-cast, PEP 3118, or DLPack)
3. Restrict check: verifies no writable buffers overlap (skipped when the
   function sets `"check_aliasing": false`)
4. Checks: evaluates all `"checks"` expressions; raises `ValueError` on failure
5. Overload dispatch: iterates the `"c_overloads"` list, evaluates `"when"`
   conditions, calls the first matching C function
6. Cleanup: releases all acquired buffers
7. Returns the result to Python

## Type Mapping

c2py23 bridges Python and C types as follows:

| Python `py_sig` type | C type (in `sig`) | Python value | Notes |
|---------------------|-------------------|-------------|-------|
| `buffer` | `type *ptr` (any pointer) | Any buffer-protocol object | Use `"map"` to bind `buf.ptr`, `buf.n`, `buf.shape[i]` |
| `int` | `int` | Python `int` | Converted via `PyLong_AsLong` |
| `int` | `intptr_t`, `size_t` | Python `int` | Pointer-width integer |
| `float` | `double` | Python `float` | Converted via `PyFloat_AsDouble` |
| `int` | `void*` | Python `int` (address) | Opaque pointer passthrough (GPU, custom allocators) |

| Python return type | C return type | Python value |
|-------------------|--------------|-------------|
| `void` | `void` | `None` |
| `int` | `int` | Python `int` |
| `float` | `double` or `float` | Python `float` |

### `void*` parameters are raw addresses

An `int` parameter mapped to a C `void*` (or any other pointer) accepts ANY
integer as a raw address.  This is the documented pass-through feature for
GPU handles and custom allocators, and there is no validation.  Passing a
wrong value hands an invalid pointer to your C code and can crash the process.
Use it only for handles your own C code produced; never compute an address in
Python.

## Tour of Examples

The `examples/` directory contains worked examples demonstrating different
features. Clone the GitHub repository to access them (not in the PyPI sdist).

| Example | Demonstrates |
|---------|-------------|
| `examples/wheel_demo/` | Multi-platform wheel packaging, `c2py_loader` |
| `examples/simd_dispatch/` | CPU feature dispatch (AVX-512/AVX2/scalar), variant rebind, timing |
| `examples/threading_bench/` | GIL release, free-threading, OpenMP, Monte Carlo Pi |
| `examples/timing_demo/` | Performance timing instrumentation, tick source switching |
| `examples/kissfft_wrap/` | Real + complex FFT over float buffers |
| `examples/lz4_wrap/` | Compress/decompress over byte buffers |
| `examples/cmake_demo/` | CMake build integration |
| `examples/meson_demo/` | Meson build integration |
| `examples/mp_bench/` | Multiprocessing with GIL release |

## Performance Timing

Set `"timing": True` in your `.c2py` module to enable per-function timing.
Each wrapped function gets a `_perf_<name>()` introspection method.

```python
{
    "module": "mymod",
    "source": ["mymod.c"],
    "timing": True,
}
```

```python
import mymod
mymod.myfunc(data, out)
print(mymod._perf_myfunc())
# {'calls': 1, 't_c_total_ns': 23400, 't_c_min_ns': 23400, ...}
```

### Timing Overhead

When timing is enabled, every call toggles a timer before and after the C
function call. The overhead depends on the tick source:

| Tick source | Overhead per call |
|-------------|------------------|
| `clock` (default, `clock_gettime`) | ~130-150 ns |
| `cycle` (CPU cycle counter, `rdtsc`/`CNTVCT_EL0`) | ~45-70 ns |
| Timing disabled (`"timing": False`) | 0 ns |

The tick source defaults to `clock_gettime(CLOCK_MONOTONIC)` (nanoseconds).
Call `mymod._c2py_set_tick_source("cycle")` to switch to the CPU cycle
counter for higher precision with lower overhead.

All tick calls are guarded by `_c2py_do_time` so there is zero overhead
when timing is disabled or not compiled in.

See `specification.md` for per-overload timing, the full perf struct schema,
and the `c2py23.perf` Python-side decoder.

### Timing counters are not thread-safe

The timing counters are updated without locks or atomics, so they are not
thread-safe.  With `gil_release` or on a free-threaded build, two threads can
race on a function's call count and min/max timings, making the reported
numbers unreliable (ThreadSanitizer will flag them).  They never crash the
process, but do not use per-function timing to compare two concurrent paths.

## Thread Safety

### GIL Release

The wrapper holds the GIL by default. Set `"gil_release": True` on a
function to release the GIL during the C call, allowing other Python
threads to execute in parallel:

```python
{
    "py_sig": "compute(data: buffer) -> void",
    "gil_release": True,
    "c_overloads": [
        {
            "sig": "void compute(const double *data, intptr_t n)",
            "map": {"data": "data.ptr", "n": "data.n"},
        },
    ],
}
```

### Free-Threading (Python 3.14t+)

Free-threaded CPython (`--disable-gil`, `python3.14t`) eliminates the GIL
at the interpreter level. By default, c2py23 modules re-enable it (safe
default). Set `"free_threading": True` at module level to leave the GIL
disabled:

```python
{
    "module": "mymod",
    "source": ["mymod.c"],
    "free_threading": True,
}
```

**`"free_threading": True` is a promise that every wrapped C function is
reentrant.**  c2py23 does not analyze your C code for thread safety.  The flag
asserts that each wrapped function uses no hidden statics and no non-reentrant
library calls; if it breaks that promise, two threads can race inside it and
c2py23 will not detect it.  The alias check is per call, not per thread: two
threads writing the same array in two calls is a data race that c2py23 does
not catch.

The wrapper's own counters are not all thread-safe either.  Timing counters
and the variant selectors are updated without atomics, so the reported timing
numbers are unreliable when several threads call a timing-enabled function at
once (ThreadSanitizer will flag them).  They cannot crash the process, but do
not treat concurrent timing output as exact.  User C code with thread-safety
bugs -- not the wrapper state -- is where a free-threaded crash comes from.

### Common Unsafe Patterns in C

When `"free_threading": True` is enabled, watch for these patterns:

1. **Static scratch buffers** -- two threads clobber each other. Use
   stack allocation or pass buffers from Python.
2. **Global accumulators** -- lost updates. Return partial results.
3. **One-time initialization with static flag** -- double-init. Use
   `pthread_once` or static const initializers.
4. **Non-reentrant C library functions** (`strtok`, `rand`) -- use `_r`
   variants.
5. **Lazy-populated global caches** -- races on allocation. Pre-allocate
   at init.
6. **Assuming GIL protects C global state** -- counters need atomics on
   free-threaded builds.

The `examples/threading_bench/` directory has a complete worked example
comparing serial, GIL release with threads, free-threading, and OpenMP.

## Building and Testing

```bash
# Build
c2py23 mymod.c2py -o mymod_wrapper.c

# Test single Python version
python tests/runner.py

# Test all versions via snakepit containers
python3 tests/test_all.py

# Leak check
valgrind --leak-check=full python3 tests/test_leaks.py
```

## Packaging as a Wheel

c2py23 modules can be distributed as multi-platform `py3-none-any` wheels.
One wheel contains `.so` files for multiple architectures -- pip installs
the same artifact everywhere, the loader selects the right binary at import
time.

### Filename Convention

Each `.so` is named `_module.c2py23-{os}_{arch}.so`:

```
mymodule/_mymodule.c2py23-linux_x86_64.so
mymodule/_mymodule.c2py23-linux_aarch64.so
mymodule/_mymodule.c2py23-linux_ppc64le.so
```

### Loader

The package's `__init__.py` uses `c2py_loader` to load the right `.so`
by explicit path:

```python
import os as _os
from c2py23.c2py_loader import load_native

_mod = load_native(_os.path.dirname(_os.path.abspath(__file__)), '_mymodule')
for _k, _v in _mod.__dict__.items():
    if _k.startswith('__') and _k.endswith('__'):
        continue
    globals()[_k] = _v
```

Set `C2PY_TRACE=1` to see which `.so` file was loaded. See
`examples/wheel_demo/` for a complete worked project.

## See Also

- `docs/specification.md` -- Full grammar, architecture, runtime internals
- `docs/building.md` -- cmake, meson, setuptools, and wheel packaging
- `docs/design.md` -- Settled design decisions (what c2py23 intentionally excludes)
- `docs/pythonh.md` -- `--pythonh` mode for GraalPy and debugging
- `AGENTS.md` -- Contributor guidelines
- `PLAN.md` -- Roadmap and future work
