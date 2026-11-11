# Getting Started

## Installation

```bash
pip install c2py23
```

Requires a C99 compiler (gcc, clang, or MSVC on Windows).  For a development
checkout use `pip install -e .` instead.

## Your First Module

Create a C file and a `.c2py` interface:

**`myadd.c`**

```c
void add_d(const double *a, const double *b, int n, double *out) {
    for (int i = 0; i < n; i++)
        out[i] = a[i] + b[i];
}
```

**`myadd.c2py`**

```python
{
    "module": "myadd",
    "source": ["myadd.c"],
    "functions": [
        {
            "py_sig": "add_arrays(a: buffer, b: buffer, out: buffer) -> void",
            "checks": [
                "a.n == b.n",
                "out.n >= a.n",
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

Generate and compile it:

```bash
# Generate the C wrapper and the single-header runtime (c2py.h) next to it
c2py23 myadd.c2py -o myadd_wrapper.c --emit-header

# Compile  --  no libpython, no include path (see building.md for all options)
cc -O2 -shared -fPIC myadd_wrapper.c myadd.c -ldl -lm -o myadd.so
```

The wrapper checks element type, alignment, contiguity and overlap of
writable buffers on every call (derived from the C signature).  It cannot
know how far your C code reads or writes: every output buffer needs a size
check in `checks:`.  See
[Writing Safe .c2py Definitions](user_guide.md#writing-safe-c2py-definitions).

Use it from Python:

```python
import ctypes, myadd

a = (ctypes.c_double * 3)(1.0, 2.0, 3.0)
b = (ctypes.c_double * 3)(4.0, 5.0, 6.0)
out = (ctypes.c_double * 3)()
myadd.add_arrays(a, b, out)
# out == [5.0, 7.0, 9.0]
```

## Next Steps

- Learn the [.c2py grammar](specification.md) in full
- Read the [Building Extensions](building.md) guide for cmake, meson, setuptools, and wheel packaging
- See the [User Guide](user_guide.md) for thread safety, timing, and packaging
- Study [the examples](examples/simd_dispatch.md)
