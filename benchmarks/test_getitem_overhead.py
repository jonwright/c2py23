# test_getitem_overhead.py -- per-call buffer acquisition cost
#
# Measures element extraction from a double buffer: acquire buffer,
# read one element, return as Python float, release buffer.
# Tests numpy ndarray, array.array, and alternating between them.

from __future__ import print_function

import array
import gc
import sys
import time

import numpy as np
from conftest import read_builtin_perf, _results
import c2py23.perf

GETITEM_ITERS = 200_000

ARRAY_N = 10000


def make_numpy(N):
    return np.random.rand(N).astype(np.float64)


def make_array(N):
    return array.array("d", np.random.rand(N))


def test_getitem_overhead():
    import gold_getitem, c2py_getitem

    gc.disable()

    numpy_arr = make_numpy(ARRAY_N)
    array_arr = make_array(ARRAY_N)
    numpy_idx = list(np.random.randint(0, ARRAY_N, GETITEM_ITERS))
    array_idx = list(np.random.randint(0, ARRAY_N, GETITEM_ITERS))

    print()
    print("=== Getitem: per-call buffer acquisition ({:,} calls, N={:,}) ===".format(GETITEM_ITERS, ARRAY_N))
    print("    Each call: acquire buffer -> arr[i] -> float -> release")
    print()
    print("    {:40s} {:>6s} {:>8s}".format("wrapper", "timing", "ns/call"))
    print("    " + "-" * 62)

    def add(label, timing, ns):
        print("    {:40s} {:>6s} {:>8.0f}".format(label, timing, ns))
        _results.add("getitem", {"label": label, "timing": timing, "ns_per_call": ns})

    # -------------------------------------------------------------------
    # gold standard: per-call acquire/release (PyObject_GetBuffer each call)
    # -------------------------------------------------------------------
    def run_gold(fn, arr, indices, verify=True):
        warmup = 100
        for _ in range(warmup):
            fn(arr, int(indices[0]))
        t0 = time.perf_counter_ns()
        for i in range(GETITEM_ITERS):
            fn(arr, int(indices[i]))
        elapsed = (time.perf_counter_ns() - t0) / GETITEM_ITERS
        if verify:
            expected = arr[indices[-1]]
            result = fn(arr, int(indices[-1]))
            assert abs(result - expected) < 1e-13
        return elapsed

    def run_batched(fn, arr):
        warmup = 100
        for _ in range(warmup):
            fn(arr, 0)
        t0 = time.perf_counter_ns()
        for _ in range(GETITEM_ITERS):
            fn(arr, 0)
        elapsed = (time.perf_counter_ns() - t0) / GETITEM_ITERS
        return elapsed

    # --- Gold, numpy ---
    ns = run_gold(gold_getitem.fastcall, numpy_arr, numpy_idx)
    add("gold (numpy, per-call acquire)", "  off", ns)

    ns = run_batched(gold_getitem.batched_fastcall, numpy_arr)
    add("gold (numpy, pre-acquire cheat)", "  off", ns)

    # --- Gold, array.array ---
    ns = run_gold(gold_getitem.fastcall, array_arr, array_idx)
    add("gold (array.array, per-call)", "  off", ns)

    # --- Pure Python numpy arr[i] ---
    def run_python(arr, indices):
        warmup = min(100, GETITEM_ITERS // 100)
        for _ in range(warmup):
            _ = arr[int(indices[0])]
        t0 = time.perf_counter_ns()
        for i in range(GETITEM_ITERS):
            _ = arr[int(indices[i])]
        elapsed = (time.perf_counter_ns() - t0) / GETITEM_ITERS
        return elapsed

    ns = run_python(numpy_arr, numpy_idx)
    add("numpy arr[i] (pure Python)", "  off", ns)

    ns = run_python(array_arr, array_idx)
    add("array.array arr[i] (pure Python)", "  off", ns)

    # -------------------------------------------------------------------
    # c2py23 -- numpy (ndarray fast path active)
    # -------------------------------------------------------------------
    c2py_getitem._c2py_set_tick_source("clock")
    c2py23.perf.set_enabled(c2py_getitem.getitem, 1)
    c2py23.perf.reset_perf(c2py_getitem.getitem)
    ns = run_gold(c2py_getitem.getitem, numpy_arr, numpy_idx)
    perf = read_builtin_perf(c2py_getitem.getitem)
    c_m = "{:.0f}".format(perf["c_mean_ns"]) if perf else "--"
    w_m = "{:.0f}".format(perf["wrap_mean_ns"]) if perf else "--"
    print("    {:40s} {:>6s} {:>8.0f}  c={} w={}".format("c2py23 numpy (checks + clock)", " clock", ns, c_m, w_m))
    _results.add(
        "getitem",
        {"label": "c2py23 numpy (checks + clock)", "timing": "clock", "ns_per_call": ns, "c_mean": c_m, "wrap": w_m},
    )

    c2py23.perf.set_enabled(c2py_getitem.getitem, 0)
    c2py23.perf.reset_perf(c2py_getitem.getitem)
    ns = run_gold(c2py_getitem.getitem, numpy_arr, numpy_idx)
    add("c2py23 numpy (checks, timing off)", "  off", ns)

    # -------------------------------------------------------------------
    # c2py23 -- array.array (buffer protocol only, ndarray probe fails)
    # -------------------------------------------------------------------
    ns = run_gold(c2py_getitem.getitem, array_arr, array_idx)
    add("c2py23 array.array (timing off)", "  off", ns)

    # -------------------------------------------------------------------
    # Alternating: numpy -> array.array -> numpy ...
    # -------------------------------------------------------------------
    print()
    print("=== Alternating: numpy <-> array.array ({:,} calls) ===".format(GETITEM_ITERS))
    print("    {:40s} {:>6s} {:>8s}".format("wrapper", "timing", "ns/call"))
    print("    " + "-" * 62)

    def run_alternating(fn, warmup=100):
        """Cycle: numpy[0], array[0], numpy[1], array[1], ..."""
        for _ in range(warmup):
            fn(numpy_arr, 0)
            fn(array_arr, 0)
        t0 = time.perf_counter_ns()
        for i in range(GETITEM_ITERS // 2):
            fn(numpy_arr, int(numpy_idx[i]))
            fn(array_arr, int(array_idx[i]))
        elapsed = (time.perf_counter_ns() - t0) / GETITEM_ITERS
        return elapsed

    ns = run_alternating(gold_getitem.fastcall)
    add("gold alternating", "  off", ns)

    c2py23.perf.reset_perf(c2py_getitem.getitem)
    ns = run_alternating(c2py_getitem.getitem)
    add("c2py23 alternating (t=off)", "  off", ns)

    # -------------------------------------------------------------------
    # Alternating with numpy FIRST (ndarray probe triggers on call 1)
    # then heavy array.array use (probe survives but is never hit)
    # -------------------------------------------------------------------
    print()
    print("=== Mixed: numpy warmup, then array.array ({:,} calls) ===".format(GETITEM_ITERS))
    print("    {:40s} {:>6s} {:>8s}".format("wrapper", "timing", "ns/call"))
    print("    " + "-" * 62)

    def run_mixed(fn, warmup_numpy=5):
        """Warmup with numpy so ndarray probe fires, then array.array only."""
        for _ in range(warmup_numpy):
            fn(numpy_arr, 0)
        for _ in range(100):
            fn(array_arr, int(array_idx[0]))
        t0 = time.perf_counter_ns()
        for i in range(GETITEM_ITERS):
            fn(array_arr, int(array_idx[i]))
        elapsed = (time.perf_counter_ns() - t0) / GETITEM_ITERS
        return elapsed

    ns = run_mixed(gold_getitem.fastcall)
    add("gold numpy warmup -> array", "  off", ns)

    ns = run_mixed(c2py_getitem.getitem)
    add("c2py23 numpy warmup -> array", "  off", ns)

    print()
