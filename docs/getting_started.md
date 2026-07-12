# Getting Started

## Installation

```bash
pip install -e .
```

Or from a wheel (once published to PyPI).

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

```yaml
module: myadd
source: [myadd.c]

functions:
  - py_sig: "add_arrays(a: buffer, b: buffer, out: buffer) -> void"
    checks:
      - "a.format == 'd'"
      - "b.format == 'd'"
      - "out.format == 'd'"
      - "a.n == b.n"
      - "b.n == out.n"
    c_overloads:
      - sig: "add_d(const double *a, const double *b, int n, double *out)"
        map: {a: "a.ptr", b: "b.ptr", n: "a.n", out: "out.ptr"}
```

Build it:

```bash
c2py23 build myadd.c2py
```

This produces `myadd.c2py23-linux_x86_64.so` (name varies by platform).

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
- Read the [User Guide](user_guide.md) for thread safety, timing, and packaging
- Study [the examples](examples/simd_dispatch.md)
