#!/usr/bin/env python
"""Monte Carlo Pi -- Threading Benchmark

Compares serial, GIL release with threads, free-threading (3.14t+),
and OpenMP parallelism for a pure-C compute workload.

Usage:
    c2py23 build mc_pi.c2py && python bench_mc_pi.py
    EXTRA_CFLAGS=-fopenmp c2py23 build mc_pi.c2py && python bench_mc_pi.py

Python 2.7 compatible (uses threading.Thread, not concurrent.futures).
"""
from __future__ import print_function, division

import ctypes
import os
import sys
import threading
import time
import sysconfig

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import mcpimod
except ImportError:
    print("ERROR: mcpimod.so not found. Build it first:")
    print("  cd {} && c2py23 build mc_pi.c2py".format(HERE))
    sys.exit(1)

IS_PY3 = sys.version_info[0] >= 3

gil_disabled = sysconfig.get_config_var('Py_GIL_DISABLED')
IS_FREE_THREADED = (gil_disabled == 1)

TOTAL_N = 200000000
NUM_THREADS = 4
CHUNK_N = TOTAL_N // NUM_THREADS


def _detect_omp():
    """Check whether the .so was built with real OpenMP support.

    Uses ctypes to look up the mc_pi_has_omp symbol, which returns
    1 when compiled with -fopenmp, 0 otherwise.
    """
    so_path = os.path.join(HERE, "mcpimod.so")
    if not os.path.isfile(so_path):
        return False
    try:
        lib = ctypes.CDLL(so_path)
        fn = lib.mc_pi_has_omp
        fn.restype = ctypes.c_int
        return fn() == 1
    except Exception:
        return False


HAS_OMP = _detect_omp()


def elapsed_since(t0):
    return time.time() - t0


def run_serial():
    """Single-threaded baseline."""
    t0 = time.time()
    inside = mcpimod.mc_pi(TOTAL_N, 12345)
    elapsed = elapsed_since(t0)
    pi = 4.0 * inside / TOTAL_N
    return pi, elapsed


def run_threaded(n_threads):
    """Python threads with GIL release.

    Each thread calls mc_pi with 1/n_threads of the work and an
    independent seed.  On standard Python the C call releases the
    GIL; on free-threaded builds there is no GIL to release.
    """
    results = [0] * n_threads

    def worker(idx):
        seed = 12345 + idx * 7919
        results[idx] = mcpimod.mc_pi(CHUNK_N, seed)

    threads = [threading.Thread(target=worker, args=(i,))
               for i in range(n_threads)]

    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = elapsed_since(t0)

    inside = sum(results)
    pi = 4.0 * inside / (CHUNK_N * n_threads)
    return pi, elapsed


def run_openmp():
    """Single Python thread, C uses #pragma omp parallel for."""
    t0 = time.time()
    inside = mcpimod.mc_pi_omp(TOTAL_N, 12345)
    elapsed = elapsed_since(t0)
    pi = 4.0 * inside / TOTAL_N
    return pi, elapsed


def fmt_time(t):
    return "%.3fs" % t


def fmt_speedup(t_base, t_parallel):
    if t_parallel > 0:
        return "%.1fx" % (t_base / t_parallel)
    return "N/A"


def main():
    print("=== Monte Carlo Pi -- Threading Benchmark ===")
    print("Python: {} (free-threaded: {})".format(
        sys.version.split()[0], "yes" if IS_FREE_THREADED else "no"))
    print("Iterations: {:,} ({} chunks of {:,})".format(
        TOTAL_N, NUM_THREADS, CHUNK_N))
    print()

    # ---- 1. Serial baseline ----
    print("1. Serial")
    pi_s, t_s = run_serial()
    print("   pi = %.6f, wall = %s" % (pi_s, fmt_time(t_s)))
    print()

    t_base = t_s

    # ---- 2. GIL release + threading (or free-threading) ----
    label = "2. GIL release + %d threads" % NUM_THREADS
    if IS_FREE_THREADED:
        label = "2. Free-threading (%d threads)" % NUM_THREADS
    print(label)
    pi_t, t_t = run_threaded(NUM_THREADS)
    print("   pi = %.6f, wall = %s, speedup = %s" % (
        pi_t, fmt_time(t_t), fmt_speedup(t_base, t_t)))
    if NUM_THREADS > 1:
        efficiency = (t_base / t_t) / NUM_THREADS * 100
        print("   efficiency = %.0f%%" % efficiency)
    print()

    # ---- 3. OpenMP ----
    if HAS_OMP:
        print("3. OpenMP (%d threads inside C)" % NUM_THREADS)
        pi_o, t_o = run_openmp()
        print("   pi = %.6f, wall = %s, speedup = %s" % (
            pi_o, fmt_time(t_o), fmt_speedup(t_base, t_o)))
        if NUM_THREADS > 1:
            efficiency = (t_base / t_o) / NUM_THREADS * 100
            print("   efficiency = %.0f%%" % efficiency)
    else:
        print("3. OpenMP -- SKIP (rebuild with EXTRA_CFLAGS=-fopenmp)")
    print()

    # ---- Notes ----
    if IS_FREE_THREADED:
        print("Note: running on free-threaded Python (--disable-gil).")
        print("  PyEval_SaveThread is a no-op; threads overlap natively.")
        print("  c2py23 modules have GIL re-enabled for safety,")
        print("  so true free-threading requires PYTHON_GIL=0.")
    elif not HAS_OMP:
        print("Tip: rebuild with OpenMP for mode 3:")
        print("  EXTRA_CFLAGS=-fopenmp c2py23 build mc_pi.c2py")


if __name__ == '__main__':
    main()
