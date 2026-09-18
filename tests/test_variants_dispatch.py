"""Variant/rebind dispatch tests for the variants case module.

Exercises the _variants_*, _rebind_* and per-variant compute dispatch that the
current suite only touches via zero-arg calls, driving the variant-selection
branches of the generated wrapper.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import ctypes
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _names(seq):
    if sys.version_info[0] >= 3:
        return [x.decode("ascii") if isinstance(x, bytes) else x for x in seq]
    return list(seq)


def _varcmod():
    sys.path.insert(0, os.path.join(HERE, "cases", "variants"))
    import varcmod

    return varcmod


def test_variants_returns_all_names():
    mod = _varcmod()
    assert _names(mod._variants_proc()) == ["proc_a", "proc_b"]


def test_rebind_none_resets_to_default():
    mod = _varcmod()
    mod._rebind_proc(None)
    arr = (ctypes.c_float * 3)(0.0, 0.0, 0.0)
    mod.proc(arr, 5.0)
    # default is proc_a (writes value)
    assert list(arr) == [5.0, 5.0, 5.0]


def test_rebind_proc_a_then_compute():
    mod = _varcmod()
    mod._rebind_proc("proc_a")
    arr = (ctypes.c_float * 3)(0.0, 0.0, 0.0)
    mod.proc(arr, 4.0)
    assert list(arr) == [4.0, 4.0, 4.0]


def test_rebind_proc_b_then_compute():
    mod = _varcmod()
    mod._rebind_proc("proc_b")
    arr = (ctypes.c_float * 3)(0.0, 0.0, 0.0)
    mod.proc(arr, 4.0)
    assert list(arr) == [8.0, 8.0, 8.0]


def test_rebind_unknown_variant_raises():
    mod = _varcmod()
    with pytest.raises(ValueError):
        mod._rebind_proc("bogus")


def test_proc_after_rebind_roundtrip():
    mod = _varcmod()
    mod._rebind_proc("proc_b")
    arr = (ctypes.c_float * 2)(0.0, 0.0)
    mod.proc(arr, 3.0)
    assert list(arr) == [6.0, 6.0]
    mod._rebind_proc("proc_a")
    mod.proc(arr, 3.0)
    assert list(arr) == [3.0, 3.0]
