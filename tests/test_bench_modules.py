"""Runtime tests for the benchmark modules (built into benchmarks/build).

These wrappers are only exercised by test_ndarray_backends (which needs
numpy), so c2py_noargs and c2py_getitem were barely covered.  Import and
call them with ctypes buffers (no numpy required for the buffer backend).

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(HERE), "benchmarks", "build")


def _import(name):
    sys.path.insert(0, BENCH)
    if name in sys.modules:
        return sys.modules[name]
    return __import__(name)


def test_noargs_and_varargs_call():
    mod = _import("c2py_noargs")
    assert mod.noargs() is None
    assert mod.varargs() is None


def test_getitem_buffer_backend():
    mod = _import("c2py_getitem")
    arr = (ctypes.c_double * 5)(1.0, 2.0, 3.0, 4.0, 5.0)
    assert mod.getitem(arr, 0) == 1.0
    assert mod.getitem(arr, 4) == 5.0
