# SIMD Dispatch

Demonstrates CPU-feature dispatch across all supported architectures
(x86_64, aarch64, ppc64le) and two SIMD strategies:
auto-vectorization (polysimd example) and intrinsics (simd_fill test case).

--8<-- "examples/simd_dispatch/README.md"

## How It Works

### Architecture-Independent Design

c2py23 has no "special" CPU.  Every architecture declares its own feature
flags in a runtime header:

| Architecture | Header | Feature Detection |
|-------------|--------|-------------------|
| x86_64 / amd64 | `c2py_amd64.h` | `cpuid` instruction (GCC, Clang, MSVC) |
| aarch64 / arm64 | `c2py_arm64.h` | `getauxval(AT_HWCAP)` on Linux; `mrs` on macOS/iOS |
| ppc64le | `c2py_ppc64.h` | `getauxval(AT_HWCAP)` on Linux |

All feature flags are zero-initialized booleans, set to 1 at module init
time by `c2py_runtime_init()`.  The generated wrapper dispatches based on
these flags using either:

- **Grouped variants** (`variants:` key): `switch` statement resolved once
  at init, with `_rebind_<name>()` for manual override.  Used by the
  polysimd example.
- **Flat overloads**: `if/else if/else` chain evaluated at each call.
  Used by the simd_fill test case.

### Two SIMD Strategies

**Auto-vectorization** (poly_kernel.c): plain C99 compiled multiple times
with different `-m` flags (gcc/clang) or `/arch:` flags (MSVC).  The
compiler auto-vectorizes based on the target ISA.  No intrinsics needed.

```
# Linux / macOS (gcc/clang)
gcc -c -O3 -mavx512f -DKERNEL_FN=poly_f32_avx512 poly_kernel.c -o ...o
gcc -c -O3 -mavx2   -DKERNEL_FN=poly_f32_avx2   poly_kernel.c -o ...o
gcc -c -O3          -DKERNEL_FN=poly_f32_scalar  poly_kernel.c -o ...o

# Windows MSVC
cl /c /O2 /arch:AVX512 /DKERNEL_FN=poly_f32_avx512 poly_kernel.c
cl /c /O2 /arch:AVX2   /DKERNEL_FN=poly_f32_avx2   poly_kernel.c
cl /c /O2              /DKERNEL_FN=poly_f32_scalar  poly_kernel.c
```

**Intrinsics** (simd_fill.c): explicit SSE2/NEON/Altivec intrinsics
guarded by `#ifdef` on the target architecture.  Non-matching platforms
get scalar fallback stubs.  This guarantees the `.so` compiles on ALL
platforms even if intrinsics are unavailable for a given target.

```c
#ifdef __x86_64__
#include <emmintrin.h>
void fill_sse2(float *buf, int n, float val) { /* SSE2 intrinsics */ }
#else
void fill_sse2(float *buf, int n, float val) { fill_scalar(buf, n, val); }
#endif

#ifdef __aarch64__
#include <arm_neon.h>
void fill_neon(float *buf, int n, float val) { /* NEON intrinsics */ }
#else
void fill_neon(float *buf, int n, float val) { fill_scalar(buf, n, val); }
#endif
```

### Runtime Dispatch

At call time, the wrapper checks feature flags and routes to the best
available function.  On x86_64: SSE2 -> scalar.  On aarch64: NEON ->
scalar.  On ppc64le: AltiVec -> scalar.  The scalar fallback is
always last and has no `when:` condition.

## Platform Support

All three architectures are tested in CI:

| Platform | Runner | SIMD Tested |
|----------|--------|-------------|
| Linux x86_64 | `ubuntu-24.04` | SSE2, AVX2, AVX-512 (via gcc) |
| Linux aarch64 | `ubuntu-24.04-arm` | NEON (via `getauxval`) |
| Windows x86_64 | `windows-latest` | SSE2 (via `__cpuidex` / MSVC) |
| macOS x86_64 | `macos-13` | SSE2, AVX2 (via clang) |
| macOS aarch64 | `macos-latest` | NEON (via `mrs` / clang) |

ppc64le is validated via container emulation; no CI runner is available yet.

### Manual Override

```python
import polysimd
polysimd._rebind_poly("poly_f32_scalar")  # force scalar fallback
polysimd._rebind_poly(None)               # reset to auto-dispatch
```
