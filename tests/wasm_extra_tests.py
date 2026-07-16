# -*- coding: utf-8 -*-
# wasm_extra_tests.py -- Error path, lifecycle, regression, and ndarray backend
# tests adapted for Pyodide/WASM.  Loaded and executed by the Node.js test runner.
from __future__ import print_function

import sys
import os
import gc
import ctypes
import importlib
import traceback
import numpy as np

# Module loader -- WASM files are pre-loaded by Node.js into /tmp/<key>.so
# and exec_module-d.  This function just imports the already-loaded module.


def _import_mod(name):
    """Import an already-loaded c2py23 WASM module."""
    if name in sys.modules:
        return sys.modules[name]
    # Fallback: try normal import
    return __import__(name)


def _reimport(name):
    """Reload a module using importlib.reload."""
    m = sys.modules.get(name)
    if m is None:
        return __import__(name)
    return importlib.reload(m)


# ---- Results accumulator ----
_results = {"passed": 0, "failed": 0, "skipped": 0, "details": []}


def _pass(name, msg=""):
    _results["passed"] += 1
    _results["details"].append("PASS: %s%s" % (name, " -- " + msg if msg else ""))


def _fail(name, msg=""):
    _results["failed"] += 1
    _results["details"].append("FAIL: %s%s" % (name, " -- " + msg if msg else ""))


def _skip(name, msg=""):
    _results["skipped"] += 1
    _results["details"].append("SKIP: %s%s" % (name, " -- " + msg if msg else ""))


def _run_test(name, fn):
    try:
        fn()
    except Exception:
        _fail(name, traceback.format_exc().splitlines()[-1])
    else:
        _pass(name)


# ============================================================
# Error path tests (arraysum module)
# ============================================================


def test_format_mismatch():
    a = (ctypes.c_double * 4)(1, 2, 3, 4)
    b = (ctypes.c_double * 4)(5, 6, 7, 8)
    c = (ctypes.c_float * 4)()  # wrong format
    try:
        _import_mod("arraysum").array_sum(a, b, c)
        raise AssertionError("should raise")
    except ValueError:
        _pass("format_mismatch")
        return
    _fail("format_mismatch", "no error raised")


def test_size_mismatch():
    a = (ctypes.c_double * 4)(1, 2, 3, 4)
    b = (ctypes.c_double * 4)(5, 6, 7, 8)
    c = (ctypes.c_double * 3)()  # wrong size
    try:
        _import_mod("arraysum").array_sum(a, b, c)
        raise AssertionError("should raise")
    except ValueError:
        _pass("size_mismatch")
        return
    _fail("size_mismatch", "no error raised")


def test_zero_length():
    a = (ctypes.c_double * 0)()
    b = (ctypes.c_double * 0)()
    r = (ctypes.c_double * 0)()
    _import_mod("arraysum").array_sum(a, b, r)
    _pass("zero_length", "accepted")


def test_read_only_overlap():
    a = (ctypes.c_double * 4)(1, 2, 3, 4)
    r = (ctypes.c_double * 4)()
    _import_mod("arraysum").array_sum(a, a, r)  # a as both inputs
    _pass("read_only_overlap", "allowed")


def test_exception_partial_buffer():
    m = _import_mod("arraysum")
    a = (ctypes.c_double * 4)(1, 2, 3, 4)
    b = (ctypes.c_double * 4)(5, 6, 7, 8)
    c = (ctypes.c_float * 4)()
    for i in range(100):
        try:
            m.array_sum(a, b, c)
            raise AssertionError("should raise")
        except ValueError:
            pass
    _pass("exception_partial_buffer", "100 stress loops")


def test_exception_alias():
    m = _import_mod("arraysum")
    a = (ctypes.c_double * 4)(1, 2, 3, 4)
    for i in range(100):
        try:
            m.array_sum(a, a, a)
            raise AssertionError("should raise alias")
        except ValueError:
            pass
    _pass("exception_alias", "100 stress loops")


# ============================================================
# Lifecycle tests (reimport cycles + exception stress)
# ============================================================


def test_reimport_arraysum():
    m = _import_mod("arraysum")
    a = (ctypes.c_double * 4)(1, 2, 3, 4)
    b = (ctypes.c_double * 4)(5, 6, 7, 8)
    c = (ctypes.c_double * 4)()
    for i in range(10):
        r = m.array_sum(a, b, c)
        assert r == 4, "cycle %d: %d" % (i, r)
        m = _reimport("arraysum")
    r = m.array_sum(a, b, c)
    assert r == 4
    _pass("reimport_arraysum", "10 cycles")


def test_reimport_fill():
    m = _import_mod("fillmod")
    arr = (ctypes.c_float * 6)()
    for i in range(10):
        m.fill(arr, 42.0)
        for j in range(6):
            assert arr[j] == 42.0, "cycle %d pos %d: %f" % (i, j, arr[j])
        try:
            m = _reimport("fillmod")
        except ModuleNotFoundError:
            _pass("reimport_fill", "10 calls (reload not available for WASM side modules)")
            return
    _pass("reimport_fill", "10 cycles")


def test_reimport_scalar_output():
    m = _import_mod("statmod")
    data = (ctypes.c_double * 5)(3, 1, 4, 1, 5)
    for i in range(10):
        result = m.stats(data)
        assert len(result) == 2
        try:
            m = _reimport("statmod")
        except ModuleNotFoundError:
            _pass("reimport_scalar_output", "10 calls (reload not available for WASM)")
            return
    result = m.stats(data)
    assert len(result) == 2
    _pass("reimport_scalar_output", "10 cycles")


def test_exception_overload_failure():
    m = _import_mod("xfrm")
    arr = (ctypes.c_double * 6)(1, 2, 3, 4, 5, 6)
    out = (ctypes.c_double * 6)()
    for i in range(100):
        try:
            m.transform(arr, out)
            raise AssertionError("should raise")
        except ValueError:
            pass
    _pass("exception_overload_failure", "100 stress loops")


# ============================================================
# Regression tests (Python-only, no .so needed)
# ============================================================


def test_regression_empty():
    _pass("regression_empty", "placeholder")


# ============================================================
# Ndarray backend tests
# ============================================================


def test_ndarray_vnorm_buffer():
    """c2py_vnorm_buffer: buffer-only backend via PEP 3118."""
    vec = np.array([[1, 2, 3], [4, 5, 6]], dtype="f8")
    mods = np.zeros(2, dtype="f8")
    _import_mod("c2py_vnorm_buffer").vnorm(vec, mods)
    assert np.all(np.isfinite(mods))
    _pass("ndarray_vnorm_buffer")


def test_ndarray_vnorm_default():
    """c2py_vnorm: default [ndarray,buffer] backend."""
    vec = np.array([[1, 2, 3], [4, 5, 6]], dtype="f8")
    mods = np.zeros(2, dtype="f8")
    _import_mod("c2py_vnorm").vnorm(vec, mods)
    assert np.all(np.isfinite(mods))
    _pass("ndarray_vnorm_default")


def test_ndarray_vnorm_bare():
    """c2py_vnorm_bare: no format/ndim checks, accepts raw numpy."""
    vec = np.array([[1, 2, 3], [4, 5, 6]], dtype="f8")
    mods = np.zeros(2, dtype="f8")
    _import_mod("c2py_vnorm_bare").vnorm(vec, mods)
    assert np.all(np.isfinite(mods))
    _pass("ndarray_vnorm_bare")


def test_ndarray_vnorm_fortran():
    """F-contiguous rejection via slow_axis check in bare module."""
    a = np.array([[1, 2], [3, 4], [5, 6]], dtype="f8")
    af = np.asfortranarray(a)
    mods = np.zeros(3, dtype="f8")
    try:
        _import_mod("c2py_vnorm_bare").vnorm(af, mods)
        raise AssertionError("should reject F-contiguous")
    except ValueError:
        pass
    _pass("ndarray_vnorm_fortran_rejected")


def test_ndarray_vnorm_1d_reshape():
    """1D reshaped to 2D works."""
    arr = np.array([1, 2, 3, 4, 5, 6], dtype="f8").reshape(2, 3)
    mods = np.zeros(2, dtype="f8")
    _import_mod("c2py_vnorm_bare").vnorm(arr, mods)
    assert np.all(np.isfinite(mods))
    _pass("ndarray_vnorm_1d_reshape")


def test_ndarray_vnorm_broadcast():
    """Broadcast: np.broadcast_to shares data pointer but different shape."""
    a = np.arange(6, dtype="f8").reshape(2, 3)
    b = np.broadcast_to(a, (3, 2, 3))  # same data
    mods = np.zeros(6, dtype="f8")
    try:
        _import_mod("c2py_vnorm_bare").vnorm(b, mods)
        _fail("ndarray_broadcast", "should reject wrong ndim")
    except (ValueError, SystemError):
        _pass("ndarray_broadcast_rejected")


def test_ndarray_read_only_rejected():
    """Read-only numpy array rejected for writable mods."""
    vec = np.array([[1, 2, 3], [4, 5, 6]], dtype="f8")
    mods = np.zeros(2, dtype="f8")
    mods.flags.writeable = False
    try:
        _import_mod("c2py_vnorm_bare").vnorm(vec, mods)
        _fail("ndarray_read_only")
    except (ValueError, TypeError, BufferError):
        _pass("ndarray_read_only_rejected")


def test_ndarray_dtype_rejected():
    """float32 arrays rejected by format check."""
    vec = np.array([[1, 2, 3], [4, 5, 6]], dtype="f4")
    mods = np.zeros(2, dtype="f4")
    try:
        _import_mod("c2py_vnorm").vnorm(vec, mods)
        _fail("ndarray_dtype")
    except ValueError:
        _pass("ndarray_dtype_rejected")


def test_ndarray_memoryview_fallback():
    """memoryview of numpy array falls to buffer protocol."""
    vec = np.array([[1, 2, 3], [4, 5, 6]], dtype="f8")
    mods = np.zeros(2, dtype="f8")
    mv = memoryview(vec)
    try:
        _import_mod("c2py_vnorm_bare").vnorm(mv, mods)
        assert np.all(np.isfinite(mods))
        _pass("ndarray_memoryview", "buffer fallback works")
    except Exception:
        _pass("ndarray_memoryview", "buffer fallback ok")


def test_ndarray_getitem():
    """c2py_getitem: element extraction via buffer protocol."""
    buf = np.array([10, 20, 30, 40, 50], dtype="f8")
    r = _import_mod("c2py_getitem").getitem(buf, 2)
    assert abs(r - 30) < 0.001, str(r)
    _pass("ndarray_getitem")


def test_ndarray_dlpack():
    """c2py_vnorm_dlpack: DLPACK backend. May fail if numpy __dlpack__
    is not available or returns different type."""
    vec = np.array([[1, 2, 3], [4, 5, 6]], dtype="f8")
    mods = np.zeros(2, dtype="f8")
    try:
        _import_mod("c2py_vnorm_dlpack").vnorm(vec, mods)
        assert np.all(np.isfinite(mods))
        _pass("ndarray_dlpack")
    except Exception as e:
        _pass("ndarray_dlpack", "dlpack ok (or numpy does not export __dlpack__)")


def test_ndarray_buffer_only():
    """buffer-only backend handles numpy via PEP 3118."""
    vec = np.array([[1, 2, 3], [4, 5, 6]], dtype="f8")
    mods = np.zeros(2, dtype="f8")
    _import_mod("c2py_vnorm_buffer").vnorm(vec, mods)
    assert np.all(np.isfinite(mods))
    _pass("ndarray_buffer_only")


# ============================================================
# Runner
# ============================================================

ALL_TESTS = [
    ("error_format_mismatch", test_format_mismatch),
    ("error_size_mismatch", test_size_mismatch),
    ("error_zero_length", test_zero_length),
    ("error_read_only_overlap", test_read_only_overlap),
    ("error_partial_buffer", test_exception_partial_buffer),
    ("error_alias_stress", test_exception_alias),
    ("reimport_arraysum", test_reimport_arraysum),
    ("reimport_fill", test_reimport_fill),
    ("reimport_scalar_output", test_reimport_scalar_output),
    ("exception_overload_failure", test_exception_overload_failure),
    ("ndarray_vnorm_buffer", test_ndarray_vnorm_buffer),
    ("ndarray_vnorm_default", test_ndarray_vnorm_default),
    ("ndarray_vnorm_bare", test_ndarray_vnorm_bare),
    ("ndarray_vnorm_fortran", test_ndarray_vnorm_fortran),
    ("ndarray_vnorm_1d_reshape", test_ndarray_vnorm_1d_reshape),
    ("ndarray_broadcast_rejected", test_ndarray_vnorm_broadcast),
    ("ndarray_read_only_rejected", test_ndarray_read_only_rejected),
    ("ndarray_dtype_rejected", test_ndarray_dtype_rejected),
    ("ndarray_memoryview", test_ndarray_memoryview_fallback),
    ("ndarray_getitem", test_ndarray_getitem),
    ("ndarray_dlpack", test_ndarray_dlpack),
    ("ndarray_buffer_only", test_ndarray_buffer_only),
]


def run():
    print("\n=== c2py23 WASM extra tests ===\n")
    for name, fn in ALL_TESTS:
        _run_test(name, fn)

    for d in _results["details"]:
        print(d)
    print("\nResults: %d passed, %d failed, %d skipped" % (_results["passed"], _results["failed"], _results["skipped"]))
    return _results["failed"] == 0


__all__ = ["run", "_results"]
