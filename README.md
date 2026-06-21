# c2py23

Wrap a strict subset of C99 code as Python C extensions via the buffer protocol.
One compiled `.so` works on Python 2.7 through 3.15 with no recompilation.
Now supports Linux x86_64 (gcc) and Windows x64 (MSVC / MinGW).

## Install

```bash
cd c2py23
pip install -e .
```

Requires PyYAML and a C99 compiler (gcc, clang, or MSVC on Windows).

## Quick Start

Create a C function:

```c
/* arraysum.c */
int array_sum(const double *a, const double *b, double *result, int n) {
    for (int i = 0; i < n; i++) result[i] = a[i] + b[i];
    return n;
}
```

Write the interface file:

```yaml
# arraysum.c2py
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

Build and use:

```bash
c2py23 build arraysum.c2py        # produces arraysum.so

python3 -c "
import ctypes, sys
sys.path.insert(0, '.')
import arraysum
a = (ctypes.c_double * 4)(1, 2, 3, 4)
b = (ctypes.c_double * 4)(5, 6, 7, 8)
r = (ctypes.c_double * 4)(0, 0, 0, 0)
n = arraysum.array_sum(a, b, r)
print(n, list(r))   # 4 [6.0, 8.0, 10.0, 12.0]
"
```

### Shape Dispatch (AoS vs SoA)

The same Python function can dispatch to different C code based on buffer
shape.  Below, a `(n,3)` layout calls `transform_aos` (array-of-structs),
and a `(3,n)` layout calls `transform_soa` (struct-of-arrays) -- same raw
pointer, zero copies, different interpretation:

```c
/* transform.c -- AoS vs SoA dispatch */
void transform_aos(double *points, int n, double *out) {
    /* points[n][3] -- array of structs */
    for (int i = 0; i < n; i++) {
        out[i*3+0] = points[i*3+0] * 2.0;
        out[i*3+1] = points[i*3+1] * 2.0;
        out[i*3+2] = points[i*3+2] * 2.0;
    }
}

void transform_soa(double *points, int n, double *out) {
    /* points[3][n] -- struct of arrays */
    for (int i = 0; i < n; i++) {
        out[0*n + i] = points[0*n + i] * 2.0;
        out[1*n + i] = points[1*n + i] * 2.0;
        out[2*n + i] = points[2*n + i] * 2.0;
    }
}
```

Interface file:

```yaml
# transform.c2py
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
      - sig: "transform_aos(double *points, intptr_t n, double *out)"
        map: {points: "points.ptr", n: "points.shape[0]", out: "out.ptr"}
        when: "points.shape[1] == 3"
      - sig: "transform_soa(double *points, intptr_t n, double *out)"
        map: {points: "points.ptr", n: "points.shape[1]", out: "out.ptr"}
        when: "points.shape[0] == 3"
    default_raise: "ValueError: expected [N,3] or [3,N] buffer"
```

Usage:

```python
import ctypes
from ctypes import c_double

aos = (c_double * 12)(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
out = (c_double * 12)()
mv_aos = memoryview(aos).cast('B').cast('d', [4, 3])
mv_out = memoryview(out).cast('B').cast('d', [4, 3])
xfrm.transform(mv_aos, mv_out)  # shape[1]==3 -> transform_aos, n=shape[0]=4

soa = (c_double * 12)(1, 4, 7, 10, 2, 5, 8, 11, 3, 6, 9, 12)
out2 = (c_double * 12)()
mv_soa = memoryview(soa).cast('B').cast('d', [3, 4])
mv_out2 = memoryview(out2).cast('B').cast('d', [3, 4])
xfrm.transform(mv_soa, mv_out2)  # shape[0]==3 -> transform_soa, n=shape[1]=4
```

The wrapper never transposes or copies data.  `n` is computed from the
appropriate dimension via `map:`, and `when:` picks the C function.

The generated wrapper for this example is committed at
[`tests/cases/transform/xfrm_wrapper.c`](tests/cases/transform/xfrm_wrapper.c)
and can be compiled without c2py23 installed:

```bash
gcc -shared -fPIC -I c2py23/runtime \
    tests/cases/transform/xfrm_wrapper.c \
    tests/cases/transform/transform.c \
    c2py23/runtime/c2py_runtime.c \
    -ldl -lm -o xfrm.so
```

A git pre-commit hook (`.githooks/pre-commit`) regenerates the wrapper
when the generator, parser, runtime, or transform source files change.

### Two-Step Workflow (generate then compile)

For build system integration, c2py23 supports a split workflow:

```bash
# Generate C wrapper only (no compilation)
c2py23 generate mymod.c2py -o mymod_wrapper.c

# Compile separately (for meson/cmake/setuptools integration)
c2py23 compile mymod_wrapper.c -s mymod.c -I include/ -o mymod.so
```

The `build` subcommand also supports `--generate-only` and `--compile-only` flags.

## Platforms

| OS | Architecture | Compiler | Status |
|----|-------------|----------|--------|
| Linux | x86_64 | gcc | Supported |
| Windows | x64 | MSVC / MinGW | Supported |
| Linux | aarch64 | gcc cross | Planned |
| Linux | ppc64le | gcc cross | Planned |
| macOS | arm64 | clang | Future |

On Windows, set `CC=cl` for MSVC (recommended) or `CC=gcc` for MinGW.
The compiler is auto-detected in `c2py23 build`.  Output extension is
`.pyd` on Windows, `.so` elsewhere.

## Supported Types

| Python type | C types |
|-------------|---------|
| `buffer` | `const T*` / `T*` for any integer or float C type below |
| `int` | `int` |
| `float` | `float`, `double` |
| Return `void` | C `void` function |
| Return `int` | C `int` return |
| Return `float` | C `float` or `double` return |

**C pointer element types**: `int8_t`, `uint8_t`, `int16_t`, `uint16_t`, `int32_t`,
`uint32_t`, `int64_t`, `uint64_t`, `intptr_t`, `size_t`, `int`, `float`, `double`, `char`, `void`

The `void*` pointer type maps from Python `int` (pointer-width, casts via `intptr_t`).
This is for opaque addresses the user manages (GPU memory, custom allocators, etc.).
The wrapper never dereferences `void*` -- it is a pure address passthrough.

**Output scalars** (`outputs:` key): supports `int8_t`, `int16_t`, `int32_t`,
`uint8_t`, `uint16_t`, `uint32_t`, `int64_t`, `uint64_t`, `float`, `double`,
`int` as return-by-pointer parameters.

## What It Doesn't Do

- No structs, enums, nested pointers, or heap allocation -- all memory is flat and owned by Python
- No `-lpython` link -- one `.so`/`.pyd` works on Python 2.7 through 3.15.  Uses nimpy-style `dlopen(NULL)` + `dlsym()` (Linux) or `GetModuleHandle` + `GetProcAddress` (Windows) at load time.
- No copies or transpositions -- zero-copy, C functions operate on buffers in-place
- No numpy required -- `ctypes` arrays, `memoryview`, `bytearray`, and anything supporting PEP 3118 works

**Warning for Python 3.14t (free-threaded) users:** By default, c2py23 modules
re-enable the GIL globally on load (safe default). Set `free_threading: true` in
your `.c2py` file to opt into true free-threading -- but only after verifying
your C code is thread-safe. See `docs/user_guide.md` for a guide to thread-safe
C patterns.

## Examples

| Example | Build System | Description |
|---------|-------------|-------------|
| [`kissfft_wrap/`](examples/kissfft_wrap/) | c2py23 build | real + complex FFT over float buffers |
| [`lz4_wrap/`](examples/lz4_wrap/) | c2py23 build | compress/decompress over byte buffers |
| [`simd_dispatch/`](examples/simd_dispatch/) | Makefile, Meson, CMake, setuptools | multi-flag compilation + CPU feature dispatch |
| [`threading_bench/`](examples/threading_bench/) | c2py23 build | GIL release, free-threading, OpenMP |
| [`wheel_demo/`](examples/wheel_demo/) | setuptools + gcc | minimal `py3-none-any` wheel |
| [`meson_demo/`](examples/meson_demo/) | meson.build | arraysum wheel built with meson |
| [`cmake_demo/`](examples/cmake_demo/) | CMakeLists.txt | arraysum wheel built with cmake |

The `simd_dispatch/` example demonstrates the full variant API: `default: false`
for benchmark-only variants, `_variants_*()` for enumeration, `_rebind_*()` for
runtime selection, and per-variant perf metadata.  See `examples/simd_dispatch/Makefile`
for multi-flag compilation.

## Wheel Packaging

c2py23 modules can be distributed as multi-platform `py3-none-any` wheels.
The approach follows the ctypes peer model: ship platform-specific `.so` files,
load by explicit filename.

Filename convention: `_mymodule.c2py23-{os}_{arch}.so`

```bash
# Build inside manylinux2014 (glibc 2.17) for portable binaries
c2py23 generate mymodule.c2py -o wrapper.c
gcc -shared -fPIC wrapper.c mymodule.c c2py_runtime.c -ldl -lm \
    -o mymodule/_mymodule.c2py23-linux_x86_64.so

# Package as py3-none-any wheel (setuptools bdist_wheel.get_tag() override)
python3 -m build
```

The `c2py_loader` module (`c2py23/c2py_loader.py`) loads the right `.so` at
import time by explicit path via `ExtensionFileLoader` (3.x) or
`imp.load_dynamic` (2.7).  No `EXTENSION_SUFFIXES` monkeypatching, no
`sys.path` hacking.  Set `C2PY_TRACE=1` to see which file was loaded.

Multiple platform-specific `.so` files can coexist in the same wheel.
pip installs on any arch; the loader picks the right one.

See `examples/wheel_demo/` for a complete working example and `docs/user_guide.md`
for the full packaging guide.

## Testing

```bash
# Test a specific Python version locally
bash tests/run_tests.sh python3.12

# Test across all versions via snakepit containers
python3 tests/test_all.py

# Test the manylinux2014 build-once cross-test strategy
python3 tests/test_manylinux.py

# Valgrind memory leak check
valgrind --leak-check=full python3 tests/test_leaks.py

# ASan build
c2py23 build --asan module.c2py
```

Requires the snakepit SIF containers at `../snakepit/`.



## Documentation

- `AGENTS.md` -- guidelines for AI agents working on the codebase
- `docs/specification.md` -- full grammar, worked examples, architecture
- `docs/user_guide.md` -- thread safety guide and packaging instructions

## Limitations

- No structs, enums, or nested data types
- Flat memory only (contiguous buffers)
- On Free Threading (FT) 3.14t, CPython re-enables the GIL globally when a c2py23 module loads (no `Py_MOD_GIL_NOT_USED`). All Python threads are serialized; parallel C execution requires `gil_release: true` (same as standard CPython). Set `PYTHON_GIL=0` or `-Xgil=0` for true free-threading at your own risk (C code must be thread-safe). See `docs/user_guide.md` for a practical guide and `docs/specification.md` for technical details.
- Subinterpreters (Python 3.12+ `_xxsubinterpreters`) are not supported. The nimpy-style module init bypasses the multi-phase initialization slot (`Py_mod_multiple_interpreters`) required by subinterpreters. This is not a practical limitation -- `multiprocessing`, `concurrent.futures`, and `asyncio` do not use subinterpreters.
- 32-bit platforms are not supported. Module import fails at runtime with a clear diagnostic. Only LP64 (64-bit) targets are tested.
