# SIMD Dispatch

Demonstrates CPU-feature dispatch with multi-flag compilation.  The same C
kernel (`poly_kernel.c`) is compiled three times with different `-m` flags
(avx512, avx2, scalar).  At module init time, c2py23 selects the best
available variant based on CPUID feature flags.

## Interface

```yaml
--8<-- "examples/simd_dispatch/polysimd.c2py"
```

## C Source

```c
--8<-- "examples/simd_dispatch/poly_kernel.c"
```

## Makefile

```makefile
--8<-- "examples/simd_dispatch/Makefile"
```

## Build & Run

```bash
pip install -e .               # from repo root
cd examples/simd_dispatch
make test
```

The Makefile compiles `poly_kernel.c` three times with different `-m` flags:

```bash
gcc -c -mavx512f -O3 poly_kernel.c -o poly_f32_avx512.o
gcc -c -mavx2   -O3 poly_kernel.c -o poly_f32_avx2.o
gcc -c           -O3 poly_kernel.c -o poly_f32_scalar.o
```

The three `.o` files are listed in the `.c2py` `source:` key.  `c2py23 build`
links them into a single `.so`.

At runtime, CPUID flags (`c2py_amd64_avx512f`, `c2py_amd64_avx2`) select the
best variant.  On non-x86 platforms (arm64, ppc64le) the scalar fallback is
always used.

Manual override:

```python
import polysimd
polysimd._rebind_poly("poly_f32_scalar")
```

## Platform Support

The SIMD dispatch example targets x86_64.  On aarch64, the scalar fallback
works; AVX-512/AVX2 flags are not detected.  On Windows with MSVC, the `-m`
flags differ -- the Makefile is gcc-specific.  A CMakeLists.txt alternative
exists alongside the Makefile.

## Test Output

```
$ python3 test_polysimd.py
...
```
