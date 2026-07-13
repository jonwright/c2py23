# Simd Dispatch

## Interface

```yaml
# polysimd.c2py -- SIMD dispatch example with multi-flag compilation
#
# The kernel (poly_kernel.c) is compiled three times with different
# -m flags to produce ISA-specific .o files.  The .c2py file wraps
# each variant and dispatches based on CPU feature flags.
#
# Build:  make
# Test:   python3 test_polysimd.py

module: _polysimd
source: [poly_f32_avx512.o, poly_f32_avx2.o, poly_f32_scalar.o]
headers: [c2py_amd64.h]
timing: true

functions:
  - py_sig: "poly(a: buffer, b: buffer, out: buffer) -> void"
    doc: "Polynomial computation with CPU-feature dispatch (AVX-512/AVX2/scalar)."
    checks:
      - "a.n == b.n"
      - "a.n == out.n"
    c_overloads:
      - when: "a.format == 'f' and b.format == 'f' and out.format == 'f'"
        map: {a: "a.ptr", b: "b.ptr", out: "out.ptr", n: "a.n"}
        group: float
        variants:
          - sig: "void poly_f32_avx512(const float *a, const float *b, float *out, int n)"
            when: "c2py_amd64_avx512f"
          - sig: "void poly_f32_avx2(const float *a, const float *b, float *out, int n)"
            when: "c2py_amd64_avx2"
          - sig: "void poly_f32_scalar(const float *a, const float *b, float *out, int n)"```

## C Source

```c
/* poly_kernel.c -- compute-bound polynomial: out[i] = f(a[i], b[i])
 *
 * Each element does many arithmetic operations per memory load to
 * make the kernel compute-bound rather than memory-bound.  This
 * ensures SIMD width differences (SSE 4-wide, AVX2 8-wide,
 * AVX-512 16-wide) translate to visible throughput differences.
 *
 * This file is compiled multiple times with different -m flags and
 * -DKERNEL_FN=<name> to produce ISA-specific variants.  The kernel
 * itself is plain C99; the compiler auto-vectorizes based on the
 * -m flags supplied at compile time.
 *
 * Build (see Makefile):
 *   gcc -c -O3 -ffast-math -mavx512f -DKERNEL_FN=poly_f32_avx512 poly_kernel.c -o ...
 *   gcc -c -O3 -ffast-math -mavx2   -DKERNEL_FN=poly_f32_avx2   poly_kernel.c -o ...
 *   gcc -c -O3 -ffast-math          -DKERNEL_FN=poly_f32_scalar  poly_kernel.c -o ...
 */

#include <stddef.h>

#ifndef KERNEL_FN
#define KERNEL_FN poly_f32
#endif

/* Horner-like repeated squaring: x = a[i], then x = x*x + b[i] many times.
 * Each inner iteration: 1 mul + 1 add, 0 extra memory accesses.
 * Arithmetic intensity: ~16:1 (16 mul+add per 2 loads + 1 store). */
#define POLY_DEPTH 16

void KERNEL_FN(const float *a, const float *b, float *out, int n)
{
    int i;
    for (i = 0; i < n; i++) {
        float x = a[i];
        float y = b[i];
        int k;
        for (k = 0; k < POLY_DEPTH; k++)
            x = x * x + y;
        out[i] = x;
    }
}```

## Build

```bash
$ c2py23 build polysimd.c2py
```

## Run

```python
"""Test the poly SIMD dispatch module.

Demonstrates:
  - Automatic variant selection (CPU features)
  - Manual rebinding via _rebind_poly()
  - Timing via built-in c2py23 perf counters
  - Compute-bound kernel where SIMD width directly matters
"""
from __future__ import print_function

import ctypes
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polysimd

try:
    from c2py23.perf import read_perf, read_enabled, set_enabled
    HAVE_PERF = True
except ImportError:
    HAVE_PERF = False
    print("(c2py23.perf not available)")

# --- Test data ---
N = 100000
a = (ctypes.c_float * N)(*[float(i % 100) / 100.0 for i in range(N)])
b = (ctypes.c_float * N)(*[float(i % 100) / 100.0 for i in range(N)])
out = (ctypes.c_float * N)()

print("=== Poly SIMD dispatch ===")
print("Array size: %d" % N)
print("Docstring:")
print(polysimd.poly.__doc__)
print()

# --- Correctness check ---
variants = ["poly_f32_scalar", "poly_f32_avx2", "poly_f32_avx512"]
results = {}
for v in variants:
    polysimd._rebind_poly(v)
    polysimd.poly(a, b, out)
    results[v] = list(out[:3])
    print("%-20s out[:3] = %s" % (v, results[v]))

# All should match
ref = results["poly_f32_scalar"]
for v in ["poly_f32_avx2", "poly_f32_avx512"]:
    if results[v] != ref:
        print("MISMATCH: %s != poly_f32_scalar!" % v)
    else:
        print("%-20s matches poly_f32_scalar" % v)

# --- Timing via wall clock (multiple runs, show variance) ---
print()
print("=== Wall-clock timing (100 iterations, %d elements) ===" % N)
N_ITER = 100
N_WARM = 5

for v in variants:
    polysimd._rebind_poly(v)
    for _ in range(N_WARM):
        polysimd.poly(a, b, out)

    runs = []
    for run in range(5):
        t0 = time.time()
        for _ in range(N_ITER):
            polysimd.poly(a, b, out)
        dt = (time.time() - t0) / N_ITER * 1e6
        runs.append(dt)

    mean = sum(runs) / len(runs)
    std = (sum((r - mean)**2 for r in runs) / len(runs)) ** 0.5
    print("  %-8s  %8.1f us/call  (+/- %.1f us, cv=%.1f%%)" % (v, mean, std, 100*std/mean if mean else 0))

# --- Built-in perf ---
if HAVE_PERF:
    freq_hz = polysimd._c2py_tick_frequency()
    using_cycles = (freq_hz != 0 and freq_hz != 1000000000)
    unit = "cycles" if using_cycles else "ns"
    print()
    print("=== c2py23 built-in perf (%s, 100 iterations) ===" % unit)
    variant_short = {
        "poly_f32_scalar": "poly_f32_scalar",
        "poly_f32_avx2": "poly_f32_avx2",
        "poly_f32_avx512": "poly_f32_avx512",
    }
    for v in variants:
        polysimd._rebind_poly(v)
        for _ in range(N_WARM):
            polysimd.poly(a, b, out)
        for _ in range(N_ITER):
            polysimd.poly(a, b, out)

        stats = read_perf(polysimd.poly, variant=variant_short[v],
                           freq_hz=freq_hz)
        if using_cycles:
            val = stats.get('c_mean_cycles', 0)
        else:
            val = stats.get('c_mean_ns', 0)
        print("  %-8s  %8.0f %s/call" % (v, val, unit))

# --- Speedup ratios ---
print()
print("=== Speedup ratios (wall clock, vs scalar) ===")
# Re-measure fresh
scalar_dt = None
for v in variants:
    polysimd._rebind_poly(v)
    for _ in range(N_WARM):
        polysimd.poly(a, b, out)
    t0 = time.time()
    for _ in range(N_ITER):
        polysimd.poly(a, b, out)
    dt = time.time() - t0
    if v == "scalar":
        scalar_dt = dt
    speedup = scalar_dt / dt if scalar_dt else 0
    print("  %-8s  %5.2fx" % (v, speedup))

polysimd._rebind_poly(None)
print()
print("Done.")```

