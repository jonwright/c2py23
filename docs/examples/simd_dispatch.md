# SIMD Dispatch

Demonstrates CPU-feature dispatch with multi-flag compilation.  The same C
kernel (`poly_kernel.c`) is compiled three times with different `-m` flags
(avx512, avx2, scalar).  At module init time, c2py23 selects the best
available variant based on CPUID feature flags.

## Interface

```yaml
--8<-- "examples/simd_dispatch/polysimd.c2py"
```

## Build & Run

```bash
cd examples/simd_dispatch
pip install -e ../..
make test
```

The Makefile compiles three `.o` files from the same source, then `c2py23 build`
links them into `.so`.  At runtime, `_rebind_poly()` allows manual variant
selection:

```python
import polysimd
polysimd._rebind_poly("poly_f32_scalar")  # fall back to scalar
polysimd._rebind_poly("poly_f32_avx2")    # select AVX2
```

## Test Script Output

```
$ python3 test_polysimd.py
...
```

## Key Design Decisions

- `variants:` with `when: c2py_amd64_avx512f` / `c2py_amd64_avx2` for CPU dispatch
- Final variant (no `when:`) is the scalar fallback
- `group: float` groups variants under a shared format/map precondition
- `timing: true` enables per-variant cycle-counter profiling
- Pre-built `.o` files are committed for convenience; the Makefile rebuilds them
