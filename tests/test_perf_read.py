"""Tests for c2py23.perf -- the ctypes-free performance data decoder.

Exercises c2py23/perf.py (line cover ~61%): the pure helpers (_to_ns,
_make_perf_buf, _read_buf, _get_mod) and the real read/reset/enable paths
against the built `timedmod`.  Pure Python apart from importing timedmod.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import array
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from c2py23.perf import (
    _to_ns,
    _make_perf_buf,
    _read_buf,
    _get_mod,
    _get_perf_ptr,
    read_perf,
    reset_perf,
    read_enabled,
    set_enabled,
    _I_CALL_COUNT,
    _I_T_ENTER,
    _N_FIELDS,
)


def test_to_ns_cases():
    assert _to_ns(1000, None) == 1000
    assert _to_ns(1000, 0) == 1000
    assert _to_ns(1000000000, 1000000000) == 1000000000
    assert _to_ns(1000000000, 1000000000) == 1000000000
    assert _to_ns(1, 2) == 500000000


def test_make_perf_buf_is_array_when_available():
    buf = _make_perf_buf()
    if hasattr(array, "typecodes") and "Q" in array.typecodes:
        assert isinstance(buf, array.array)
    else:
        assert isinstance(buf, bytearray)
    assert len(buf) >= _N_FIELDS


@pytest.mark.skipif(
    not (hasattr(array, "typecodes") and "Q" in array.typecodes),
    reason="array('Q') not available on this build (perf.py falls back to bytearray)",
)
def test_read_buf_array():
    buf = array.array("Q", [0] * _N_FIELDS)
    buf[_I_CALL_COUNT] = 7
    assert _read_buf(buf, _I_CALL_COUNT) == 7


def test_read_buf_bytearray():
    buf = bytearray(_N_FIELDS * 8)
    # pack a uint64 little-endian at index _I_T_ENTER
    import struct

    struct.pack_into("<Q", buf, _I_T_ENTER * 8, 12345)
    assert _read_buf(buf, _I_T_ENTER) == 12345


def test_get_mod_from_self():
    class M(object):
        pass

    m = M()

    class F(object):
        __self__ = m

    assert _get_mod(F()) is m


def test_get_mod_from_module_name():
    def f():
        pass

    f.__module__ = "sys"

    assert _get_mod(f) is sys.modules["sys"]


def test_get_mod_none_fallback_searches_sys_modules():
    def f():
        pass

    f.__module__ = None
    # no sys.modules entry has a function with this name bound to f -> None
    assert _get_mod(f) is None


def _import_timedmod():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "cases", "timing"))
    import timedmod

    return timedmod


def test_real_read_perf_variants():
    timedmod = _import_timedmod()
    stats = read_perf(timedmod.wsum, freq_hz=1000000000)
    for key in ("call_count", "c_dur_ns", "wrap_dur_ns", "c_min_ns", "c_max_ns",
                "c_mean_ns", "wrap_min_ns", "wrap_max_ns", "wrap_mean_ns",
                "variant", "group_idx", "variant_name"):
        assert key in stats, "missing key %s" % key

    # named overload
    named = read_perf(timedmod.wsum, variant="weighted_sum")
    assert "call_count" in named

    # currently-selected variant
    cur = read_perf(timedmod.wsum, variant=True)
    assert "call_count" in cur


def test_real_reset_and_enable():
    timedmod = _import_timedmod()
    reset_perf(timedmod.wsum)
    before = read_perf(timedmod.wsum)
    assert before["call_count"] == 0

    assert read_enabled(timedmod.wsum) == 1
    set_enabled(timedmod.wsum, 0)
    assert read_enabled(timedmod.wsum) == 0
    set_enabled(timedmod.wsum, 1)
    assert read_enabled(timedmod.wsum) == 1


_BAD_HANDLE_SCRIPT = """
import sys
sys.path.insert(0, %r)
import timedmod
names = [n for n in dir(timedmod)
         if n.startswith("_c2py_perf_ptr_") or n.startswith("_c2py_ol_ptr_")]
n_handles = max(getattr(timedmod, n) for n in names) + 1
buf = bytearray(11 * 8)
for bad in (-1, n_handles, 12345, 2 ** 62):
    for call in (lambda h: timedmod._c2py_perf_reset(h),
                 lambda h: timedmod._c2py_perf_read(h, buf),
                 lambda h: timedmod._c2py_perf_meta(h)):
        try:
            call(bad)
        except ValueError as e:
            assert "invalid perf handle" in str(e), str(e)
        else:
            raise SystemExit("no ValueError for handle %%r" %% (bad,))
print("ok")
"""


def test_invalid_perf_handles_raise_valueerror():
    here = os.path.dirname(os.path.abspath(__file__))
    script = _BAD_HANDLE_SCRIPT % os.path.join(here, "cases", "timing")
    p = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    assert p.returncode == 0, (p.returncode, out, err)
    assert b"ok" in out


def test_perf_handles_report_call_counts():
    timedmod = _import_timedmod()
    import ctypes

    data = (ctypes.c_double * 3)(1.0, 2.0, 3.0)
    reset_perf(timedmod.wsum)
    reset_perf(timedmod.wsum, variant="weighted_sum")
    for _ in range(5):
        timedmod.wsum(data, 2.0)
    assert read_perf(timedmod.wsum)["call_count"] == 5
    assert read_perf(timedmod.wsum, variant="weighted_sum")["call_count"] == 5
