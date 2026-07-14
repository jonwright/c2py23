# test_getitem_overhead.py -- per-call buffer acquision cost
#
# Measures element extraction from a double buffer: acquire buffer,
# extract one element, return as Python float, release buffer.
# This isolates the per-call buffer-acquire cost, which is the
# expensive path c2py23 takes.
#
# Compares: gold per-call, gold pre-acquire, c2py23, c2py23 timing off.
from __future__ import print_function

import gc
import sys
import time

import numpy as np
from conftest import read_builtin_perf, _results
import c2py23.perf

GETITEM_ITERS = 500_000


def test_getitem_overhead():
    import gold_getitem, c2py_getitem

    gc.disable()

    N = 10000
    arr = np.random.rand(N).astype(np.float64)
    indices = np.random.randint(0, N, GETITEM_ITERS).tolist()

    print()
    print("=== Getitem overhead (buffer={:,}, {:,} calls, -O2) ===".format(N, GETITEM_ITERS))
    print("    Each call: acquire buffer -> read arr[i] -> return float -> release")
    print()
    print("    {:35s} {:>6s} {:>8s}".format("wrapper", "timing", "ns/call"))
    print("    " + "-" * 55)

    def add(label, timing, ns):
        print("    {:35s} {:>6s} {:>8.0f}".format(label, timing, ns))
        _results.add("getitem", {"label": label, "timing": timing, "ns_per_call": ns})

    # --- Gold: per-call acquire/release ---
    def run_gold(fn, iters=GETITEM_ITERS):
        warmup = min(100, iters // 100)
        for _ in range(warmup):
            fn(arr, int(indices[0]))
        t0 = time.perf_counter_ns()
        for i in range(iters):
            fn(arr, int(indices[i]))
        elapsed = (time.perf_counter_ns() - t0) / iters
        # verify correctness on last call
        expected = arr[indices[-1]]
        result = fn(arr, int(indices[-1]))
        assert abs(result - expected) < 1e-15, "{} != {}".format(result, expected)
        return elapsed

    ns = run_gold(gold_getitem.fastcall)
    add("gold (per-call acquire)", "  off", ns)

    # --- Gold: pre-acquire (cheat mode) ---
    # Use a fixed index, just to measure the base cost of getting an element
    # from an already-acquired pointer. This is the theoretical minimum.
    def run_batched(fn, iters=GETITEM_ITERS):
        # batched_fastcall acquires once, reads one element per call from
        # a pre-acquired buffer and returns it. Calls fn(arr, i) directly.
        warmup = min(100, iters // 100)
        for _ in range(warmup):
            fn(arr, 0)
        t0 = time.perf_counter_ns()
        for _ in range(iters):
            fn(arr, 0)
        elapsed = (time.perf_counter_ns() - t0) / iters
        return elapsed

    ns = run_batched(gold_getitem.batched_fastcall)
    add("gold (pre-acquire)", "  off", ns)

    # --- c2py23 ---
    c2py_getitem._c2py_set_tick_source("clock")
    c2py23.perf.set_enabled(c2py_getitem.getitem, 1)
    c2py23.perf.reset_perf(c2py_getitem.getitem)
    ns = run_gold(c2py_getitem.getitem)
    perf = read_builtin_perf(c2py_getitem.getitem)
    c_m = "{:.0f}".format(perf["c_mean_ns"]) if perf else "--"
    w_m = "{:.0f}".format(perf["wrap_mean_ns"]) if perf else "--"
    print("    {:35s} {:>6s} {:>8.0f}  c={} w={}".format("c2py23 (checks + clock)", " clock", ns, c_m, w_m))
    _results.add(
        "getitem",
        {"label": "c2py23 (checks + clock)", "timing": "clock", "ns_per_call": ns, "c_mean": c_m, "wrap": w_m},
    )

    # --- c2py23 timing OFF ---
    c2py23.perf.set_enabled(c2py_getitem.getitem, 0)
    c2py23.perf.reset_perf(c2py_getitem.getitem)
    ns = run_gold(c2py_getitem.getitem)
    add("c2py23 (checks, timing off)", "  off", ns)

    print()
