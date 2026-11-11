"""shape[k] / strides[k] must never read out of bounds (review finding B2).

Builds on tests/cases/shapeguard (shapeguardmod).  Calls that used to
segfault run in a subprocess so a regression fails the test, not pytest.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import array
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_CASE = os.path.join(_HERE, "cases", "shapeguard")
sys.path.insert(0, _CASE)
sys.path.insert(0, _HERE)

import shapeguardmod  # noqa: E402
from _extload import extload_prelude  # noqa: E402

_SNIPPET = (
    extload_prelude()
    + """
import array, sys
import numpy as np
m = c2py_load("shapeguardmod", %r)
bad = [np.zeros(5), np.zeros(()), array.array('d', [1.0, 2.0, 3.0]), bytearray(24)]
for fn in (m.get_cols, m.get_stride1):
    for a in bad:
        if isinstance(a, bytearray):
            continue
        try:
            fn(a)
        except ValueError:
            continue
        sys.exit(3)
sys.exit(0)
"""
)


def _subprocess_ok():
    p = subprocess.Popen([sys.executable, "-c", _SNIPPET % (_CASE,)])
    return p.wait()


def _raises_value_error(fn, a):
    try:
        fn(a)
    except ValueError as e:
        return str(e)
    raise AssertionError("%s did not raise ValueError" % (fn.__name__,))


def test_short_buffers_raise_not_crash():
    """1-D, 0-D and array.array inputs raise ValueError (exit code 0)."""
    assert _subprocess_ok() == 0


def test_error_message_names_buffer_and_ndim():
    msg = _raises_value_error(shapeguardmod.get_cols, np.zeros(5))
    assert "'a'" in msg and "ndim" in msg, msg
    # array.array has no PEP 3118 format on 2.7, so the format check fires
    # first there; either way it is a ValueError, never an out-of-bounds read.
    _raises_value_error(shapeguardmod.get_cols, array.array("d", [1.0, 2.0]))


def test_bytearray_rejected_by_format():
    _raises_value_error(shapeguardmod.get_cols, bytearray(24))


def test_2d_returns_shape_and_stride():
    a = np.zeros((4, 6))
    assert shapeguardmod.get_cols(a) == 6
    assert shapeguardmod.get_stride1(a) == 8


def test_when_shape_not_selected_for_1d():
    msg = _raises_value_error(shapeguardmod.three, np.zeros(5))
    assert "3 columns" in msg, msg
    msg = _raises_value_error(shapeguardmod.three, np.zeros((5, 4)))
    assert "3 columns" in msg, msg
    assert shapeguardmod.three(np.zeros((5, 3))) == 3


def test_ndim_dispatch_still_works():
    assert shapeguardmod.either(np.zeros(7)) == 7
    assert shapeguardmod.either(np.zeros((5, 3))) == 1005
    msg = _raises_value_error(shapeguardmod.either, np.zeros((5, 4)))
    assert "expected" in msg, msg
