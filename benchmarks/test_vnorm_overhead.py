# test_vnorm_overhead.py -- Phases 2+3: buffer acquisition overhead + throughput
from __future__ import print_function

import gc
import sys
import time

import numpy as np
from conftest import make_vectors, make_mods, read_builtin_perf, _results, TINY_VNORM_N, TINY_VNORM_ITERS, LARGE_VNORM_N
import c2py23.perf


def verify_vnorm(vec, mods):
    ref = np.sqrt((vec * vec).sum(axis=1))
    ok = np.allclose(mods, ref, rtol=1e-12, atol=1e-12)
    if not ok:
        raise AssertionError("norm mismatch: max err {:.1e}".format(np.abs(mods - ref).max()))
    return ok


class TestVnormTiny:
    def test_all(self):
        import gold_vnorm, gold_numpy_vnorm, c2py_vnorm, c2py_vnorm_bare
        import c2py_vnorm_ndarray, c2py_vnorm_buffer, c2py_vnorm_dlpack

        gc.disable()
        print()
        print("=== Vnorm wrapper overhead (N=3, {:,} calls, -O2) ===".format(TINY_VNORM_ITERS))
        print("    {:35s} {:>9s} {:>4s} {:>6s} {:>8s}".format("wrapper", "acquire", "chk", "timing", "ns/call"))
        print("    " + "-" * 69)

        vec = make_vectors(TINY_VNORM_N)
        mods = make_mods(TINY_VNORM_N)

        def run(label, fn, iters=TINY_VNORM_ITERS, warmup=500):
            for _ in range(warmup):
                fn(vec, mods)
            t0 = time.perf_counter_ns()
            for _ in range(iters):
                fn(vec, mods)
            elapsed = (time.perf_counter_ns() - t0) / iters
            verify_vnorm(vec, mods)
            return elapsed

        def add(label, acquire, checks, timing, ns, c_m="", w_m=""):
            print(
                "    {:35s} {:>9s} {:>4s} {:>6s} {:>8.0f}  {}".format(
                    label, acquire, checks, timing, ns, ("c={} w={}".format(c_m, w_m) if c_m else "")
                )
            )
            _results.add(
                "vnorm_tiny",
                {
                    "label": label,
                    "acquire": acquire,
                    "checks": checks,
                    "timing": timing,
                    "ns_per_call": ns,
                    "c_mean": c_m,
                    "wrap": w_m,
                },
            )

        ns = run("gold vnorm fastcall", gold_vnorm.fastcall)
        add("gold vnorm fastcall", "getbuffer", " --", "  --", ns)
        ns = run("gold numpy fastcall", gold_numpy_vnorm.fastcall)
        add("gold numpy fastcall", "PyArray  ", " --", "  --", ns)

        ns = run("c2py23 bare", c2py_vnorm_bare.vnorm)
        add("c2py23 bare", "  --", " no", "  off", ns)

        c2py23.perf.set_enabled(c2py_vnorm.vnorm, 0)
        c2py23.perf.reset_perf(c2py_vnorm.vnorm)
        ns = run("c2py23 checks only", c2py_vnorm.vnorm)
        add("c2py23 checks only", "getbuffer", "yes", "  off", ns)

        # Per-backend acquisition
        ns = run("  ndarray", c2py_vnorm_ndarray.vnorm)
        add("  ndarray", "ndarray ", "yes", "  off", ns)
        ns = run("  buffer", c2py_vnorm_buffer.vnorm)
        add("  buffer", "buffer  ", "yes", "  off", ns)
        try:
            ns = run("  dlpack", c2py_vnorm_dlpack.vnorm)
            add("  dlpack", "dlpack  ", "yes", "  off", ns)
        except Exception:
            add("  dlpack", "dlpack  ", "yes", "  off", 0)

        c2py_vnorm._c2py_set_tick_source("clock")
        c2py23.perf.set_enabled(c2py_vnorm.vnorm, 1)
        c2py23.perf.reset_perf(c2py_vnorm.vnorm)
        ns = run("c2py23 checks + clock", c2py_vnorm.vnorm)
        perf = read_builtin_perf(c2py_vnorm.vnorm)
        c_m = "{:.0f}".format(perf["c_mean_ns"]) if perf else ""
        w_m = "{:.0f}".format(perf["wrap_mean_ns"]) if perf else ""
        add("c2py23 checks + clock", "getbuffer", "yes", " clock", ns, c_m, w_m)

        try:
            c2py_vnorm._c2py_set_tick_source("cycle")
            c2py23.perf.reset_perf(c2py_vnorm.vnorm)
            ns = run("c2py23 checks + cycle", c2py_vnorm.vnorm)
            perf = read_builtin_perf(c2py_vnorm.vnorm)
            c_m = "{:.0f}".format(perf["c_mean_ns"]) if perf else ""
            w_m = "{:.0f}".format(perf["wrap_mean_ns"]) if perf else ""
            add("c2py23 checks + cycle", "getbuffer", "yes", " cycle", ns, c_m, w_m)
        except Exception:
            add("c2py23 checks + cycle", "getbuffer", "yes", " cycle", 0)
        print()


class TestVnormLarge:
    def test_all(self):
        import gold_vnorm, gold_numpy_vnorm, c2py_vnorm, c2py_vnorm_bare
        import c2py_vnorm_ndarray, c2py_vnorm_buffer, c2py_vnorm_dlpack

        gc.disable()
        total_mb = LARGE_VNORM_N * 4 * 8 / 1e6  # N*3*8 + N*8
        print()
        print("=== Vnorm throughput (N={:,}, ~{:.0f} MB, single call, -O2) ===".format(LARGE_VNORM_N, total_mb))
        print(
            "    {:35s} {:>9s} {:>4s} {:>6s} {:>7s} {:>8s}".format("wrapper", "acquire", "chk", "timing", "ms", "MB/s")
        )
        print("    " + "-" * 75)

        vec = make_vectors(LARGE_VNORM_N)
        mods = make_mods(LARGE_VNORM_N)

        def run(label, fn):
            fn(vec, mods)  # warmup page touch
            fn(vec, mods)
            t0 = time.perf_counter_ns()
            fn(vec, mods)
            ms = (time.perf_counter_ns() - t0) / 1e6
            tp = total_mb / (ms / 1000.0)
            verify_vnorm(vec, mods)
            return ms, tp

        def add(label, acquire, checks, timing, ms, tp, c_m="", w_m=""):
            print(
                "    {:35s} {:>9s} {:>4s} {:>6s} {:>7.1f} {:>8.0f}  {}".format(
                    label, acquire, checks, timing, ms, tp, ("c={} w={}".format(c_m, w_m) if c_m else "")
                )
            )
            _results.add(
                "vnorm_large",
                {
                    "label": label,
                    "acquire": acquire,
                    "checks": checks,
                    "timing": timing,
                    "ms": ms,
                    "mb_s": tp,
                    "c_mean": c_m,
                    "wrap": w_m,
                },
            )

        ms, tp = run("gold vnorm fastcall", gold_vnorm.fastcall)
        add("gold vnorm fastcall", "getbuffer", " --", "  --", ms, tp)
        ms, tp = run("gold numpy fastcall", gold_numpy_vnorm.fastcall)
        add("gold numpy fastcall", "PyArray  ", " --", "  --", ms, tp)

        ms, tp = run("c2py23 bare", c2py_vnorm_bare.vnorm)
        add("c2py23 bare", "  --", " no", "  off", ms, tp)

        c2py23.perf.set_enabled(c2py_vnorm.vnorm, 0)
        c2py23.perf.reset_perf(c2py_vnorm.vnorm)
        ms, tp = run("c2py23 checks only", c2py_vnorm.vnorm)
        add("c2py23 checks only", "getbuffer", "yes", "  off", ms, tp)

        # Per-backend acquisition
        ms, tp = run("  ndarray", c2py_vnorm_ndarray.vnorm)
        add("  ndarray", "ndarray ", "yes", "  off", ms, tp)
        ms, tp = run("  buffer", c2py_vnorm_buffer.vnorm)
        add("  buffer", "buffer  ", "yes", "  off", ms, tp)
        try:
            ms, tp = run("  dlpack", c2py_vnorm_dlpack.vnorm)
            add("  dlpack", "dlpack  ", "yes", "  off", ms, tp)
        except Exception:
            add("  dlpack", "dlpack  ", "yes", "  off", 0, 0)

        c2py_vnorm._c2py_set_tick_source("clock")
        c2py23.perf.set_enabled(c2py_vnorm.vnorm, 1)
        c2py23.perf.reset_perf(c2py_vnorm.vnorm)
        ms, tp = run("c2py23 checks + clock", c2py_vnorm.vnorm)
        perf = read_builtin_perf(c2py_vnorm.vnorm)
        c_m = "{:.0f}".format(perf["c_mean_ns"]) if perf else ""
        w_m = "{:.0f}".format(perf["wrap_mean_ns"]) if perf else ""
        add("c2py23 checks + clock", "getbuffer", "yes", " clock", ms, tp, c_m, w_m)

        try:
            c2py_vnorm._c2py_set_tick_source("cycle")
            c2py23.perf.reset_perf(c2py_vnorm.vnorm)
            ms, tp = run("c2py23 checks + cycle", c2py_vnorm.vnorm)
            perf = read_builtin_perf(c2py_vnorm.vnorm)
            c_m = "{:.0f}".format(perf["c_mean_ns"]) if perf else ""
            w_m = "{:.0f}".format(perf["wrap_mean_ns"]) if perf else ""
            add("c2py23 checks + cycle", "getbuffer", "yes", " cycle", ms, tp, c_m, w_m)
        except Exception:
            add("c2py23 checks + cycle", "getbuffer", "yes", " cycle", 0, 0)
        print()
