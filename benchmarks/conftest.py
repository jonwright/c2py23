"""benchmarks conftest.py -- shared fixtures and helpers."""

from __future__ import print_function

import json
import os
import sys
import time

import numpy as np
import pytest

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(BENCH_DIR, "build")
BUILD_DIR_PH = os.path.join(BENCH_DIR, "build_ph")
RESULTS_FILE = os.path.join(BENCH_DIR, ".bench_results.json")
sys.path.insert(0, BUILD_DIR)

IS_PY3 = sys.version_info[0] >= 3

# ---------------------------------------------------------------------------
# Results collector -- gathered across all tests, written at session end
# ---------------------------------------------------------------------------


class ResultsCollector:
    def __init__(self):
        self.rows = []  # list of dicts

    def add(self, section, row):
        row["section"] = section
        self.rows.append(row)

    def save(self):
        with open(RESULTS_FILE, "w") as f:
            json.dump(self.rows, f, indent=1)


_results = ResultsCollector()


@pytest.fixture(scope="session", autouse=True)
def _save_results(request):
    request.addfinalizer(_results.save)


# ---------------------------------------------------------------------------
# Iteration counts
# ---------------------------------------------------------------------------

NOARGS_ITERS = int(os.environ.get("BENCH_N_NOARGS", 10_000_000))
TINY_VNORM_N = 3
TINY_VNORM_ITERS = int(os.environ.get("BENCH_N_TINY", 200_000))
LARGE_VNORM_N = 4_194_304  # 2**22, ~134 MB total


# ---------------------------------------------------------------------------
# Array helpers
# ---------------------------------------------------------------------------


def make_vectors(n, dtype=np.float64):
    return np.random.rand(n, 3).astype(dtype)


def make_mods(n, dtype=np.float64):
    return np.zeros(n, dtype=dtype)


# ---------------------------------------------------------------------------
# Timed runner
# ---------------------------------------------------------------------------


def measure(fn, iterations, warmup=500, gc_disable=True):
    """Call fn iterations times, return elapsed_ns, ns_per_call."""
    if gc_disable:
        import gc

        gc.disable()
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter_ns()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter_ns() - t0
    return elapsed, elapsed / iterations


# ---------------------------------------------------------------------------
# c2py23 built-in perf reader
# ---------------------------------------------------------------------------


def read_builtin_perf(func):
    """Read c2py_perf_t for a c2py23 wrapped function.  Returns dict or None."""
    mod = sys.modules.get(func.__module__)
    if mod is None:
        mod = getattr(func, "__self__", None)
        if mod is None:
            return None
    fname = func.__name__
    ptr_name = "_c2py_perf_ptr_" + fname
    try:
        ptr = int(getattr(mod, ptr_name))
    except (AttributeError, TypeError, ValueError):
        return None

    import ctypes

    buf = (ctypes.c_uint64 * 11)()
    getattr(mod, "_c2py_perf_read")(ptr, buf)
    freq_hz = mod._c2py_tick_frequency()
    result = {
        "call_count": buf[0],
        "c_min_ns": buf[5],
        "c_max_ns": buf[6],
        "c_total_ns": buf[7],
        "wrap_min_ns": buf[8],
        "wrap_max_ns": buf[9],
        "wrap_total_ns": buf[10],
    }
    cc = result["call_count"]
    if cc > 0:
        result["c_mean_ns"] = float(result["c_total_ns"]) / cc
        result["wrap_mean_ns"] = float(result["wrap_total_ns"]) / cc
    else:
        result["c_mean_ns"] = 0.0
        result["wrap_mean_ns"] = 0.0
    return result


# ---------------------------------------------------------------------------
# Pythonh module loader
# ---------------------------------------------------------------------------


def load_pythonh_module(mod_name):
    """Load a c2py23 pythonh module by path from build_ph/.
    Returns the loaded module without colliding with the nimpy
    version already in sys.modules under the same name."""
    so_path = os.path.join(BUILD_DIR_PH, mod_name + ".so")
    if not os.path.isfile(so_path):
        raise ImportError("pythonh module not built: {}".format(so_path))
    mod_key = mod_name + "_ph"
    if mod_key in sys.modules:
        return sys.modules[mod_key]
    import importlib.machinery as _m
    import importlib.util as _u

    loader = _m.ExtensionFileLoader(mod_key, so_path)
    spec = _u.spec_from_file_location(mod_name, so_path, loader=loader)
    mod = _u.module_from_spec(spec)
    sys.modules[mod_key] = mod
    loader.exec_module(mod)
    return mod
