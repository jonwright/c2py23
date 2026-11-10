"""<buf>.ptr % N in when: selects an overload by pointer alignment.

Builds on tests/cases/ptralign (ptralignmod).  Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import os
import sys

import numpy as np

_CASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases", "ptralign")
sys.path.insert(0, _CASE)

import ptralignmod  # noqa: E402


def _aligned_block(n, align=64):
    """A float64 array of n elements whose data pointer is a multiple of
    align, plus its backing store (kept alive by the array's base)."""
    raw = np.zeros(n + 2 * align // 8, dtype=np.float64)
    off = (-raw.ctypes.data % align) // 8
    a = raw[off : off + n]
    assert a.ctypes.data % align == 0
    return a


def test_aligned_buffer_selects_aligned_overload():
    a = _aligned_block(32)
    assert ptralignmod.which(a) == 1


def test_offset_view_selects_fallback():
    a = _aligned_block(32)
    view = a[1:]  # still 8-byte aligned (passes the element check), not 32
    assert view.ctypes.data % 8 == 0
    assert view.ctypes.data % 32 != 0
    assert ptralignmod.which(view) == 0


def test_every_offset_in_a_cache_line():
    a = _aligned_block(32)
    for k in range(8):
        view = a[k:]
        expect = 1 if view.ctypes.data % 32 == 0 else 0
        assert ptralignmod.which(view) == expect


def test_non_literal_divisor():
    a = _aligned_block(32)
    view = a[1:]
    assert ptralignmod.which_n(a, 64) == 1
    assert ptralignmod.which_n(view, 8) == 1
    assert ptralignmod.which_n(view, 16) == 0
    # a divisor of zero or less never matches and never faults
    assert ptralignmod.which_n(a, 0) == 0
    assert ptralignmod.which_n(a, -8) == 0
