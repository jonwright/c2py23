#!/usr/bin/env python
"""Monte Carlo Pi -- Parallelism Benchmark

Compares four approaches:
  1. Serial (GIL released but single thread)
  2. Python threads + GIL release (gil_release: true)
  3. multiprocessing (process-level, bypasses GIL entirely)
  4. concurrent.futures ProcessPoolExecutor

All approaches call the same c2py23-wrapped mc_pi() function.

Usage:
    cd examples/mp_bench && c2py23 build mc_pi.c2py && python bench_mp.py

Python 2.7 compatible for 1 and 2; 3+ enables multiprocessing modes.
"""

from __future__ import print_function, division

import os
import sys
import threading
import time
import sysconfig

IS_PY3 = sys.version_info[0] >= 3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import mcpimod
except ImportError:
    print("ERROR: mcpimod.so not found. Build it first:")
    print("  cd %s && c2py23 build mc_pi.c2py" % HERE)
    sys.exit(1)

gil_disabled = sysconfig.get_config_var("Py_GIL_DISABLED")
IS_FREE_THREADED = gil_disabled == 1

TOTAL_N = 200000000
NUM_WORKERS = 4
CHUNK_N = TOTAL_N // NUM_WORKERS


def elapsed_since(t0):
    return time.time() - t0


def fmt_time(t):
    return "%.3fs" % t


def fmt_speedup(t_base, t_parallel):
    if t_parallel > 0:
        return "%.1fx" % (t_base / t_parallel)
    return "N/A"


# ---------- Serial ----------


def run_serial():
    t0 = time.time()
    inside = mcpimod.mc_pi(TOTAL_N, 12345)
    elapsed = elapsed_since(t0)
    pi = 4.0 * inside / TOTAL_N
    return pi, elapsed


# ---------- Python threads + GIL release ----------


def run_threaded(n_workers):
    results = [0] * n_workers

    def worker(idx):
        seed = 12345 + idx * 7919
        results[idx] = mcpimod.mc_pi(CHUNK_N, seed)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_workers)]

    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = elapsed_since(t0)

    inside = sum(results)
    pi = 4.0 * inside / (CHUNK_N * n_workers)
    return pi, elapsed


# ---------- multiprocessing ----------


def _worker_mp(args):
    n, seed = args
    import mcpimod as mod

    return mod.mc_pi(n, seed)


def run_multiprocessing(n_workers):
    import multiprocessing

    chunks = [(CHUNK_N, 12345 + i * 7919) for i in range(n_workers)]
    pool = multiprocessing.Pool(processes=n_workers)

    t0 = time.time()
    results = pool.map(_worker_mp, chunks)
    pool.close()
    pool.join()
    elapsed = elapsed_since(t0)

    inside = sum(results)
    pi = 4.0 * inside / (CHUNK_N * n_workers)
    return pi, elapsed


# ---------- concurrent.futures ProcessPoolExecutor ----------


def run_processpool(n_workers):
    from concurrent.futures import ProcessPoolExecutor

    chunks = [(CHUNK_N, 12345 + i * 7919) for i in range(n_workers)]

    t0 = time.time()
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        results = list(executor.map(_worker_mp, chunks))
    elapsed = elapsed_since(t0)

    inside = sum(results)
    pi = 4.0 * inside / (CHUNK_N * n_workers)
    return pi, elapsed


# ---------- Main ----------


def main():
    print("=== Monte Carlo Pi -- Parallelism Benchmark ===")
    print("Python: %s (free-threaded: %s)" % (sys.version.split()[0], "yes" if IS_FREE_THREADED else "no"))
    print("Iterations: {0:,} ({1} workers, {2:,} each)".format(TOTAL_N, NUM_WORKERS, CHUNK_N))
    print()

    # 1. Serial
    print("1. Serial (GIL released but single thread)")
    pi_s, t_s = run_serial()
    print("   pi = %.6f, wall = %s" % (pi_s, fmt_time(t_s)))
    print()

    t_base = t_s

    # 2. GIL release + threads (or free-threading)
    label = "2. GIL release + %d threads" % NUM_WORKERS
    if IS_FREE_THREADED:
        label = "2. Free-threading (%d threads)" % NUM_WORKERS
    print(label)
    pi_t, t_t = run_threaded(NUM_WORKERS)
    print("   pi = %.6f, wall = %s, speedup = %s" % (pi_t, fmt_time(t_t), fmt_speedup(t_base, t_t)))
    if NUM_WORKERS > 1 and t_t > 0:
        efficiency = (t_base / t_t) / NUM_WORKERS * 100
        print("   efficiency = %.0f%%" % efficiency)
    print()

    if IS_PY3:
        # 3. multiprocessing
        print("3. multiprocessing.Pool (%d processes)" % NUM_WORKERS)
        try:
            pi_m, t_m = run_multiprocessing(NUM_WORKERS)
            print("   pi = %.6f, wall = %s, speedup = %s" % (pi_m, fmt_time(t_m), fmt_speedup(t_base, t_m)))
            if NUM_WORKERS > 1 and t_m > 0:
                efficiency = (t_base / t_m) / NUM_WORKERS * 100
                print("   efficiency = %.0f%%" % efficiency)
        except Exception as e:
            print("   FAIL: %s" % e)
        print()

        # 4. concurrent.futures ProcessPoolExecutor
        print("4. concurrent.futures ProcessPoolExecutor (%d workers)" % NUM_WORKERS)
        try:
            pi_p, t_p = run_processpool(NUM_WORKERS)
            print("   pi = %.6f, wall = %s, speedup = %s" % (pi_p, fmt_time(t_p), fmt_speedup(t_base, t_p)))
            if NUM_WORKERS > 1 and t_p > 0:
                efficiency = (t_base / t_p) / NUM_WORKERS * 100
                print("   efficiency = %.0f%%" % efficiency)
        except Exception as e:
            print("   FAIL: %s" % e)
        print()
    else:
        print("3. multiprocessing -- SKIP (Python 3 only)")
        print("4. concurrent.futures -- SKIP (Python 3 only)")
        print()

    if IS_FREE_THREADED:
        print("Note: running on free-threaded Python (--disable-gil).")
        print("  This module declares Py_MOD_GIL_NOT_USED, so the GIL")
        print("  stays disabled. Threads run truly in parallel.")


if __name__ == "__main__":
    main()
