# c2py23

Zero-copy C99 function wrapping for Python 2.7 through 3.15.

One compiled `.so` works everywhere -- no recompilation, no `#include <Python.h>`,
no numpy dependency.

**GraalPy, PyPy, or debugging?** See `docs/pythonh.md` for
standard CPython extension that includes `<Python.h>` directly.
See [--pythonh mode](pythonh.md).

## How It Works

1. Write a `.c2py` interface file describing your C function signatures, buffer
   formats, and dispatch conditions
2. Run `c2py23 mymod.c2py -o mymod_wrapper.c` to generate the wrapper
3. Compile with any C99 compiler: `cc -shared ... mymod_wrapper.c ... -o mymod.so`
4. Import the resulting `.so` from Python and call your C functions with
   ctypes arrays, memoryviews, or any buffer-protocol object

## Key Features

- **Zero-copy**: raw C pointers from Python buffers, no allocation in wrappers
- **One `.so` everywhere**: Python 2.7 through 3.15, Linux/Windows/macOS/aarch64
- **Format dispatch**: route to different C functions based on buffer type (`float` vs `double` vs `int32` ...)
- **CPU feature dispatch**: compile AVX-512/AVX2/scalar variants, select at runtime
- **GIL release**: release the GIL during pure-C computation
- **Free-threading**: opt in to `python3.14t` true parallelism
- **No heap allocation** in generated wrappers -- all memory owned by Python

## What It Does NOT Do

- **No copies** -- the wrapper never reallocates or copies buffer data
- **No numpy dependency** -- uses PEP 3118 buffer protocol directly
- **No GPU kernels** -- CPU-only buffer access (see [design decisions](design.md))
- **No complex type** -- use interleaved float pairs in float buffers
- **No keyword arguments** -- positional-only, matching C calling conventions

## Quick Example

```python
# arraysum.c2py
{
    "module": "arraysum",
    "source": ["arraysum.c"],
    "functions": [
        {
            "py_sig": "add_arrays(a: buffer, b: buffer, out: buffer) -> void",
            "checks": [
                "a.format == 'd'",
                "b.format == 'd'",
                "out.format == 'd'",
                "a.n == b.n",
                "b.n == out.n",
            ],
            "c_overloads": [
                {
                    "sig": "add_d(const double *a, const double *b, int n, double *out)",
                    "map": {
                        "a": "a.ptr",
                        "b": "b.ptr",
                        "n": "a.n",
                        "out": "out.ptr",
                    },
                },
            ],
        },
    ],
}
```

```python
import ctypes, arraysum

a = (ctypes.c_double * 3)(1.0, 2.0, 3.0)
b = (ctypes.c_double * 3)(4.0, 5.0, 6.0)
out = (ctypes.c_double * 3)()
arraysum.add_arrays(a, b, out)
# out == [5.0, 7.0, 9.0]
```

## Where to Go Next

- [Getting Started](getting_started.md) -- install and build your first module
- [Building Extensions](building.md) -- cmake, meson, setuptools, wheel packaging
- [User Guide](user_guide.md) -- thread safety, timing, packaging
- [Specification](specification.md) -- full grammar and architecture
- [Examples](examples/simd_dispatch.md) -- worked examples with live test output
