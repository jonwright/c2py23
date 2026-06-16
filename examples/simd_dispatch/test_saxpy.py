"""Test the SAXPY SIMD dispatch module.

Demonstrates:
  - Automatic variant selection (CPU features)
  - Manual rebinding via _rebind_saxpy()
  - Timing via built-in c2py23 perf counters
"""
from __future__ import print_function

import ctypes
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import saxpy

# c2py23 perf decoder (ctypes-based, bundled with c2py23)
try:
    from c2py23.perf import read_perf, read_enabled, set_enabled
    HAVE_PERF = True
except ImportError:
    HAVE_PERF = False
    print("(c2py23.perf not available; skipping built-in timing)")

# --- Allocate test data ---
N = 1000000
a = (ctypes.c_float * N)(*range(N))
b = (ctypes.c_float * N)(*range(N))
out = (ctypes.c_float * N)()

scale = 0.5
expected = ctypes.c_float(a[0] * scale + b[0]).value

print("=== SAXPY SIMD dispatch example ===")
print("Array size: %d" % N)
print("Docstring:")
print(saxpy.saxpy.__doc__)
print()

# --- Auto-resolve (uses best available ISA) ---
saxpy.saxpy(a, scale, b, out)
print("Auto:  out[0] = %.1f  (expected %.1f)" % (out[0], expected))

# --- Force AVX2 variant ---
saxpy._rebind_saxpy("avx2")
saxpy.saxpy(a, scale, b, out)
print("AVX2:  out[0] = %.1f  (expected %.1f)" % (out[0], expected))

# --- Force scalar variant ---
saxpy._rebind_saxpy("scalar")
saxpy.saxpy(a, scale, b, out)
print("Scalar: out[0] = %.1f  (expected %.1f)" % (out[0], expected))

# --- Back to auto ---
saxpy._rebind_saxpy(None)
saxpy.saxpy(a, scale, b, out)
print("Auto:  out[0] = %.1f  (expected %.1f)" % (out[0], expected))

# --- Timing via built-in perf ---
if HAVE_PERF:
    print()
    print("=== Built-in timing (c2py23 perf, %d iterations, %d elements) ===" % (50, N))

    variants = ["scalar", "avx2", "avx512"]
    for vname in variants:
        saxpy._rebind_saxpy(vname)
        # Reset perf counters for this variant
        for attr in dir(saxpy):
            if attr.startswith('_perf_saxpy'):
                ptr = getattr(saxpy, attr)
                if isinstance(ptr, int) and ptr:
                    set_enabled(ptr, 1)  # ensure enabled

        # Warmup
        for _ in range(5):
            saxpy.saxpy(a, scale, b, out)

        # Reset timing: disable then re-enable (clears min/max)
        for attr in dir(saxpy):
            if attr.startswith('_perf_saxpy'):
                ptr = getattr(saxpy, attr)
                if isinstance(ptr, int) and ptr and attr != '_perf_saxpy':
                    set_enabled(ptr, 0)
                    set_enabled(ptr, 1)

        for _ in range(50):
            saxpy.saxpy(a, scale, b, out)

        # Read per-variant perf
        best_ns = float('inf')
        for attr in dir(saxpy):
            if attr.startswith('_perf_saxpy__'):
                ptr = getattr(saxpy, attr)
                if isinstance(ptr, int) and ptr:
                    stats = read_perf(ptr)
                    if stats.get('c_mean_ns'):
                        best_ns = min(best_ns, stats['c_mean_ns'])
        if best_ns < float('inf'):
            print("  %-8s  %8.1f ns/call" % (vname, best_ns))
        else:
            print("  %-8s  (no timing data)" % vname)

    # Restore auto
    saxpy._rebind_saxpy(None)

print()
print("Done.")
