---
name: c2py23
description: Generate zero-copy C99 Python extensions from declarative YAML interface files. Use when wrapping C functions for Python, creating high-performance numerical extensions, binding SIMD-optimized C code, or when the user mentions c2py23, C extensions, or buffer-protocol wrapping. Supports Python 2.7-3.15, GIL release, free-threading, and automatic buffer shape/type dispatch.
license: MIT
compatibility: Requires Python 2.7+, PyYAML (for .c2py YAML files), and gcc (or compatible C99 compiler). No numpy required.
---

# c2py23 Skill

## What c2py23 Does

c2py23 transpiles declarative `.c2py` interface files into CPython C extensions. It is designed for high-performance numerical code where Python owns all memory and C functions operate on buffers passed in by the caller. The wrapper is zero-copy and allocation-free.

Key capabilities:

- Wraps C functions with zero copy (buffer protocol, no intermediate allocations)
- Automatic dispatch based on buffer properties (element type, dimensionality, contiguity)
- GIL release for pure-C sections (`gil_release: true`)
- Free-threading support for Python 3.14t+ (`free_threading: true`)
- Per-function performance timing instrumentation (`timing: true`)
- Template expansion for generating families of functions (`expand:`)
- Works on Python 2.7 through 3.15 from a single `.so` file

## When to Use

- Wrapping C numerical kernels (FFT, linear algebra, signal processing)
- Performance-critical loops that benefit from GIL release
- Code that must work on Python 2.7 AND modern Python (HPC, legacy systems)
- SIMD dispatch from Python (select fastest code path at runtime)
- Hard real-time or low-latency use cases (zero-copy, no allocation in hot path)

## When NOT to Use

- Wrapping object-oriented C++ libraries (use pybind11 or nanobind)
- Wrapping code that allocates memory and returns it to Python (use ctypes or cffi)
- Simple scalar-only functions (use ctypes)
- Code that requires Python keyword arguments (c2py23 is positional-only)
- Async/await patterns (not supported)

## Quick Start

### 1. Write a .c2py interface file

```yaml
module: mymod
source: [kernel.c]

functions:
  - py_sig: "add_arrays(a: buffer, b: buffer, out: buffer)"
    checks:
      - "a.format == 'd'"
      - "b.format == 'd'"
      - "out.format == 'd'"
      - "a.n == b.n"
      - "out.n >= a.n"
    c_overloads:
      - sig: "void add_double(int n, const double *a, const double *b, double *out)"
        map:
          a: "a.ptr"
          b: "b.ptr"
          out: "out.ptr"
          n: "min(a.n, b.n)"
```

### 2. Build the module

```bash
c2py23 mymod.c2py -o mymod_wrapper.c
cc -shared -fPIC -I c2py23/runtime \
    c2py23/runtime/c2py_runtime.c mymod_wrapper.c mymod.c \
    -o mymod.so -ldl -lm
```

See `docs/building.md` for alternative build systems (CMake, Meson, setuptools).

### 3. Use from Python

```python
import ctypes
import mymod

a = (ctypes.c_double * 1000)(*range(1000))
b = (ctypes.c_double * 1000)(*[1.0] * 1000)
out = (ctypes.c_double * 1000)()

mymod.add_arrays(a, b, out)
```

## Critical Rules

### 1. Always validate buffer dimensions in `checks:`

Without size checks, a caller can pass a too-small output buffer, causing a segfault. This is the most important rule:

```yaml
checks:
  - "out.format == 'd'"       # element type
  - "out.n >= a.n"             # output large enough (prevents segfaults!)
```

### 2. Memory is owned by Python

The C function receives raw pointers with no bounds information. The ONLY defense against buffer overruns is the `checks:` block. There is no runtime bounds checking in the C code.

### 3. Format char portability

Never use `'l'` or `'L'` for fixed-width dispatch. They are platform-sized (`sizeof(long)` differs between Linux and Windows). Use:

| Format | C type | Size |
|--------|--------|------|
| `'i'` / `'I'` | `int32_t` / `uint32_t` | 4 bytes |
| `'q'` / `'Q'` | `int64_t` / `uint64_t` | 8 bytes |
| `'d'` | `double` | 8 bytes |
| `'f'` | `float` | 4 bytes |

### 4. Python dict format preferred over YAML

The Python dict format requires no PyYAML dependency and auto-detects:

```python
{
    "module": "mymod",
    "source": ["kernel.c"],
    "functions": [
        {
            "py_sig": "add_arrays(a: bytes, b: bytes, out: bytes)",
            "checks": ["a.format == 'd'", "out.n >= a.n"],
            "c_overloads": [
                {
                    "sig": "void add_double(int n, const double *a, const double *b, double *out)",
                    "map": {"a": "a.ptr", "b": "b.ptr", "out": "out.ptr", "n": "min(a.n, b.n)"},
                },
            ],
        },
    ],
}
```

## Dispatch System

c2py23 dispatches to the correct C function based on buffer properties at call time:

- `sig:` declares the C function signature and required buffer properties
- `when:` is a C expression evaluated per-overload (e.g., `"out.format == 'd'"`)
- `map:` binds Python parameter attributes to C function arguments
- Overloads are tried in order; first match wins
- Use `default_raise:` for a clear error when no overload matches

### Buffer attributes available in `map:` and `when:` expressions:

| Attribute | Type | Meaning |
|-----------|------|---------|
| `buf.ptr` | `void*` | Pointer to buffer data |
| `buf.n` | `Py_ssize_t` | Number of elements |
| `buf.itemsize` | `Py_ssize_t` | Bytes per element |
| `buf.format` | `char` | PEP 3118 format character |
| `buf.ndim` | `int` | Number of dimensions |
| `buf.shape[i]` | `Py_ssize_t` | Size of dimension i |
| `buf.strides[i]` | `Py_ssize_t` | Stride of dimension i |

## Common Pitfalls

1. **Missing size checks** -- the #1 cause of segfaults. Always check `out.n >= in.n` or similar.
2. **Wrong format character** -- `'d'` for double, `'f'` for float. Mis-match causes silent wrong results.
3. **Using ctypes wrong** -- ctypes arrays implement the buffer protocol on Python 2.7+, use them for test data.
4. **Map expressions that allocate** -- `map:` is evaluated once per call, but generated code is allocation-free. Keep map expressions simple.
5. **Forgetting to `sys.path.insert` when running tests** from example directories that import built `.so` files.

## Building and Testing

```bash
pip install -e .                       # install c2py23 in dev mode
c2py23 mymod.c2py -o mymod_wrapper.c    # generate wrapper (see docs/building.md)
python tests/runner.py                  # build + test all modules
python tests/runner.py --no-build       # test only (use existing .so files)
python3 tests/test_all.py              # cross-version container validation
```

## Spec and Examples

- Full specification: https://jonwright.github.io/c2py23/specification/
- Examples: `examples/` directory in the repo
  - `examples/threading_bench/` -- GIL release + OpenMP benchmark
  - `examples/kissfft_wrap/` -- FFT wrapping
  - `examples/lz4_wrap/` -- Compression wrapping
  - `examples/simd_dispatch/` -- Runtime SIMD dispatch
  - `examples/wheel_demo/` -- Packaging as wheels
