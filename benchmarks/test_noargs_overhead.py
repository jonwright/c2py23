# test_noargs_overhead.py -- Phase 1: pure Python->C->Python overhead
from __future__ import print_function

import gc
import sys
import time

from conftest import measure, NOARGS_ITERS, read_builtin_perf, _results, load_pythonh_module
import c2py23.perf


def test_noargs_overhead():
    import gold_noargs, c2py_noargs

    gc.disable()

    print()
    print("=== No-arg call overhead ({:,} iterations, -O2) ===".format(NOARGS_ITERS))
    print("    {:30s} {:>6s} {:>7s} {:>7s} {:>7s}".format("wrapper", "timing", "c_mean", "wrap", "ns/call"))
    print("    " + "-" * 65)

    def add(label, timing, c_mean, w_mean, ns):
        print("    {:30s} {:>6s} {:>7s} {:>7s} {:>7.1f}".format(label, timing, c_mean, w_mean, ns))
        _results.add("noargs", {"label": label, "timing": timing, "c_mean": c_mean, "wrap": w_mean, "ns_per_call": ns})

    def run_gold(label, fn):
        _, ns = measure(fn, NOARGS_ITERS)
        add(label, "  --", "    --", "    --", ns)

    run_gold("gold METH_FASTCALL", gold_noargs.fastcall)
    run_gold("gold METH_NOARGS", gold_noargs.noargs)

    c2py23.perf.set_enabled(c2py_noargs.noargs, 0)
    c2py23.perf.reset_perf(c2py_noargs.noargs)
    _, ns = measure(c2py_noargs.noargs, NOARGS_ITERS)
    add("c2py23", "  off", "    -", "    --", ns)

    c2py23.perf.set_enabled(c2py_noargs.noargs, 1)
    c2py_noargs._c2py_set_tick_source("clock")
    c2py23.perf.reset_perf(c2py_noargs.noargs)
    N = max(NOARGS_ITERS // 4, 1)
    _, ns = measure(c2py_noargs.noargs, N)
    perf = read_builtin_perf(c2py_noargs.noargs)
    c_m = "{:5.1f}".format(perf["c_mean_ns"]) if perf else "    --"
    w_m = "{:5.1f}".format(perf["wrap_mean_ns"]) if perf else "    --"
    add("c2py23", " clock", c_m, w_m, ns)

    try:
        c2py_noargs._c2py_set_tick_source("cycle")
        c2py23.perf.reset_perf(c2py_noargs.noargs)
        _, ns = measure(c2py_noargs.noargs, N)
        perf = read_builtin_perf(c2py_noargs.noargs)
        c_m = "{:5.1f}".format(perf["c_mean_ns"]) if perf else "    --"
        w_m = "{:5.1f}".format(perf["wrap_mean_ns"]) if perf else "    --"
        add("c2py23", " cycle", c_m, w_m, ns)
    except Exception:
        add("c2py23", " cycle", "  n/a", "  n/a", 0)

    # ---- Pythonh variant ----
    try:
        ph = load_pythonh_module("c2py_noargs")
        c2py23.perf.set_enabled(ph.noargs, 0)
        c2py23.perf.reset_perf(ph.noargs)
        _, ns = measure(ph.noargs, NOARGS_ITERS)
        add("c2py23 --pythonh", "  off", "    -", "    --", ns)
    except Exception as e:
        print("    (pythonh not built: {})".format(e))

    print()
