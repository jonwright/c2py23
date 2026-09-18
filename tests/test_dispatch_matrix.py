"""Parametric dtype x shape dispatch matrix for the generated wrappers.

Drives the per-dtype `when:` dispatch branches (the biggest source of the
30-60% wrapper coverage gap) with a compact, fast parameterisation.

Python 2.7 - 3.15 compatible; uses ctypes arrays (buffer protocol works on
both).  The 2D transform paths use memoryview.cast (Python 3.3+; skipped on
2.7 -- the one allowed platform guard).
"""

from __future__ import print_function

import ctypes
import sys
import os

import pytest

IS_PY3 = sys.version_info[0] >= 3
HERE = os.path.dirname(os.path.abspath(__file__))


def _cases_dir(name):
    return os.path.join(HERE, "cases", name)


def _arr(ct, n, value=0):
    return (ct * n)(*([value] * n))


# directory -> module name mapping (case dir may differ from module name)
_DIR2MOD = {
    "typedispatch": "dispatchmod",
    "fill": "fillmod",
    "dot": "dotmod",
    "transform": "xfrm",
    "arraysum": "arraysum",
    "types": "typesmod",
    "variants": "varcmod",
}


def _import(name):
    mod = _DIR2MOD.get(name, name)
    sys.path.insert(0, _cases_dir(name))
    return __import__(mod)


# (ctypes type, format char, in-range fill value)
DISPATCH_TYPES = [
    (ctypes.c_ubyte, "B", 7),
    (ctypes.c_byte, "b", 7),
    (ctypes.c_ushort, "H", 7),
    (ctypes.c_short, "h", 7),
    (ctypes.c_uint, "I", 7),
    (ctypes.c_int, "i", 7),
    (ctypes.c_ulonglong, "Q", 7),
    (ctypes.c_longlong, "q", 7),
    (ctypes.c_float, "f", 7),
    (ctypes.c_double, "d", 7),
]


@pytest.mark.parametrize("ct,_fmt,val", DISPATCH_TYPES)
def test_dispatchmod_fill_dtype(ct, _fmt, val):
    dispatchmod = _import("typedispatch")
    arr = _arr(ct, 8)
    dispatchmod.fill(arr, float(val))
    for i in range(8):
        assert arr[i] == val, "dispatchmod.fill type %s: element %d = %r" % (ct.__name__, i, arr[i])


@pytest.mark.parametrize("ct,_fmt,val", DISPATCH_TYPES)
def test_fillmod_f_float_double(ct, _fmt, val):
    # fillmod supports only 'f' and 'd'
    if _fmt not in ("f", "d"):
        return
    fillmod = _import("fill")
    arr = _arr(ct, 8)
    fillmod.fill(arr, float(val))
    for i in range(8):
        assert arr[i] == val


@pytest.mark.parametrize("ct,fmt,val", [
    (ctypes.c_ushort, "H", 42),
    (ctypes.c_uint, "I", 99),
    (ctypes.c_int, "i", -3),
    (ctypes.c_longlong, "q", -7),
    (ctypes.c_byte, "b", -5),
    (ctypes.c_short, "h", -9),
])
def test_typesmod_fill_dtype(ct, fmt, val):
    typesmod = _import("types")
    arr = _arr(ct, 5)
    typesmod.fill(arr, val)
    for i in range(5):
        assert arr[i] == val


@pytest.mark.parametrize("ct,_fmt,_val", DISPATCH_TYPES)
def test_dispatchmod_fill_zero_length(ct, _fmt, _val):
    dispatchmod = _import("typedispatch")
    arr = _arr(ct, 0)
    dispatchmod.fill(arr, 7.0)  # zero-length must not crash


def test_typesmod_unsupported_dtype_raises():
    typesmod = _import("types")
    arr = _arr(ctypes.c_double, 4)  # format 'd' not in typesmod set
    with pytest.raises(TypeError):
        typesmod.fill(arr, 7.0)


def test_fillmod_unsupported_dtype_raises():
    fillmod = _import("fill")
    arr = _arr(ctypes.c_int, 4)  # format 'i' not in fillmod set
    with pytest.raises(TypeError):
        fillmod.fill(arr, 7.0)


@pytest.mark.parametrize("ct,_fmt,_val", [t for t in DISPATCH_TYPES if t[0] in (ctypes.c_float, ctypes.c_double)])
def test_dotmod_float_and_double(ct, _fmt, _val):
    dotmod = _import("dot")
    a = _arr(ct, 4, 1)
    b = _arr(ct, 4, 2)
    assert dotmod.dot(a, b) == 8.0


def test_arraysum_double():
    arraysum = _import("arraysum")
    a = _arr(ctypes.c_double, 4, 1.0)
    b = _arr(ctypes.c_double, 4, 2.0)
    out = _arr(ctypes.c_double, 4, 0.0)
    n = arraysum.array_sum(a, b, out)
    assert n == 4
    assert list(out) == [3.0, 3.0, 3.0, 3.0]


@pytest.mark.skipif(not IS_PY3, reason="memoryview.cast is Python 3.3+ (the one allowed platform guard)")
def test_transform_2d_aos_and_soa():
    xfrm = _import("transform")
    pts_aos = _arr(ctypes.c_double, 12)
    src = list(range(1, 13))
    for i, v in enumerate(src):
        pts_aos[i] = v
    out = _arr(ctypes.c_double, 12)
    mv = memoryview(pts_aos).cast("B").cast("d", [4, 3])
    mv_out = memoryview(out).cast("B").cast("d", [4, 3])
    xfrm.transform(mv, mv_out)
    assert list(out) == [v * 2 for v in src]

    pts_soa = _arr(ctypes.c_double, 12)
    soa = [1, 4, 7, 10, 2, 5, 8, 11, 3, 6, 9, 12]
    for i, v in enumerate(soa):
        pts_soa[i] = v
    out2 = _arr(ctypes.c_double, 12)
    mv2 = memoryview(pts_soa).cast("B").cast("d", [3, 4])
    mv_out2 = memoryview(out2).cast("B").cast("d", [3, 4])
    xfrm.transform(mv2, mv_out2)
    expected = [2, 8, 14, 20, 4, 10, 16, 22, 6, 12, 18, 24]
    assert list(out2) == expected


@pytest.mark.skipif(not IS_PY3, reason="memoryview.cast is Python 3.3+")
def test_transform_wrong_shape_raises():
    xfrm = _import("transform")
    pts = _arr(ctypes.c_double, 20)
    mv = memoryview(pts).cast("B").cast("d", [4, 5])  # not [N,3] or [3,N]
    out = _arr(ctypes.c_double, 20)
    mv_out = memoryview(out).cast("B").cast("d", [4, 5])
    with pytest.raises(ValueError):
        xfrm.transform(mv, mv_out)


@pytest.mark.skipif(not IS_PY3, reason="memoryview.cast is Python 3.3+")
def test_transform_alias_same_buffer_raises():
    xfrm = _import("transform")
    buf = _arr(ctypes.c_double, 12)
    mv = memoryview(buf).cast("B").cast("d", [4, 3])
    with pytest.raises(ValueError):
        xfrm.transform(mv, mv)


def test_arraysum_output_too_small_raises():
    arraysum = _import("arraysum")
    a = _arr(ctypes.c_double, 4, 1.0)
    b = _arr(ctypes.c_double, 4, 2.0)
    out = _arr(ctypes.c_double, 2, 0.0)  # too small (should be 4)
    with pytest.raises(ValueError):
        arraysum.array_sum(a, b, out)


def test_arraysum_format_mismatch_raises():
    arraysum = _import("arraysum")
    a = _arr(ctypes.c_double, 4, 1.0)
    b = _arr(ctypes.c_float, 4, 2.0)  # wrong format
    out = _arr(ctypes.c_double, 4, 0.0)
    with pytest.raises(ValueError):
        arraysum.array_sum(a, b, out)


def test_dot_format_mismatch_raises():
    dotmod = _import("dot")
    a = _arr(ctypes.c_float, 4, 1.0)
    b = _arr(ctypes.c_double, 4, 2.0)
    with pytest.raises(ValueError):
        dotmod.dot(a, b)


def test_dot_size_mismatch_raises():
    dotmod = _import("dot")
    a = _arr(ctypes.c_float, 4, 1.0)
    b = _arr(ctypes.c_float, 5, 2.0)
    with pytest.raises(ValueError):
        dotmod.dot(a, b)


def test_dot_zero_length():
    dotmod = _import("dot")
    a = _arr(ctypes.c_float, 0)
    b = _arr(ctypes.c_float, 0)
    assert dotmod.dot(a, b) == 0.0
