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
variants = ["scalar", "avx2", "avx512"]
results = {}
for v in variants:
    polysimd._rebind_poly(v)
    polysimd.poly(a, b, out)
    results[v] = list(out[:3])
    print("%-8s out[:3] = %s" % (v, results[v]))

# All should match
ref = results["scalar"]
for v in ["avx2", "avx512"]:
    if results[v] != ref:
        print("MISMATCH: %s != scalar!" % v)
    else:
        print("%-8s matches scalar" % v)

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
    # Determine tick source: default clock_gettime gives ns, CPU cycle counter gives cycles
    freq_hz = polysimd._c2py_tick_frequency()
    using_cycles = (freq_hz != 0 and freq_hz != 1000000000)
    unit = "cycles" if using_cycles else "ns"
    print()
    print("=== c2py23 built-in perf (%s, 100 iterations) ===" % unit)
    variant_short = {"scalar": "poly_f32_scalar", "avx2": "poly_f32_avx2", "avx512": "poly_f32_avx512"}
    for v in variants:
        polysimd._rebind_poly(v)
        for _ in range(N_WARM):
            polysimd.poly(a, b, out)
        for _ in range(N_ITER):
            polysimd.poly(a, b, out)

        perf_key = '_perf_poly__' + variant_short[v]
        ptr = getattr(polysimd, perf_key, 0)
        if ptr:
            stats = read_perf(ptr, freq_hz=freq_hz)
            if using_cycles:
                val = stats.get('c_mean_cycles', 0)
            else:
                val = stats.get('c_mean_ns', 0)
            print("  %-8s  %8.0f %s/call" % (v, val, unit))
        else:
            print("  %-8s  (no perf struct)" % v)

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
print("Done.")
