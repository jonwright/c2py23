"""Uniform test script for c2py23 - runs identically on Python 2.7 through 3.14.

Tests all four test cases: arraysum, fill, dot, transform.
Uses ctypes arrays (buffer protocol works on 2.7 and 3.x) + memoryview for shape.
On Python 2.7, some tests are skipped due to old buffer protocol limitations.
"""
from __future__ import print_function

import sys
import os
import warnings
import ctypes

warnings.filterwarnings("ignore", message=".*API version mismatch.*")

IS_PY3 = sys.version_info[0] >= 3
IS_PY2 = not IS_PY3


def _has_pep3118():
    """Check if the platform supports PEP 3118 buffer protocol for typed arrays."""
    if IS_PY3:
        return True
    # Python 2.7: ctypes arrays use old buffer protocol (no format info)
    # NumPy arrays support PEP 3118, but we don't depend on numPy
    return False


def _double_array(values):
    n = len(values)
    return (ctypes.c_double * n)(*values)


def _float_array(values):
    n = len(values)
    return (ctypes.c_float * n)(*values)


def _zeros_double(n):
    return _double_array([0.0] * n)


def _to_list(arr):
    return [arr[i] for i in range(len(arr))]


def test_arraysum():
    """Test element-wise addition of double arrays."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'arraysum'))
    import arraysum

    a = _double_array([1.0, 2.0, 3.0, 4.0])
    b = _double_array([5.0, 6.0, 7.0, 8.0])
    result = _zeros_double(4)

    n = arraysum.array_sum(a, b, result)
    assert n == 4, "Expected 4, got %d" % n
    expected = [6.0, 8.0, 10.0, 12.0]
    actual = _to_list(result)
    assert actual == expected, "Expected %s, got %s" % (expected, actual)
    print("PASS: arraysum")


def test_fill():
    """Test type dispatch: fill float vs double arrays."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'fill'))
    import fillmod

    arr_f = _float_array([0.0, 0.0, 0.0, 0.0])
    fillmod.fill(arr_f, 3.14)
    assert _to_list(arr_f) == [3.140000104904175] * 4, "float fill failed: %s" % _to_list(arr_f)

    arr_d = _double_array([0.0, 0.0, 0.0])
    fillmod.fill(arr_d, 2.718)
    assert _to_list(arr_d) == [2.718] * 3, "double fill failed: %s" % _to_list(arr_d)

    print("PASS: fill")


def test_dot():
    """Test type dispatch with scalar return: dot product float vs double."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'dot'))
    import dotmod

    fa = _float_array([1.0, 2.0, 3.0])
    fb = _float_array([4.0, 5.0, 6.0])
    r = dotmod.dot(fa, fb)
    assert abs(r - 32.0) < 0.01, "float dot failed: %s" % r

    da = _double_array([1.0, 2.0, 3.0])
    db = _double_array([4.0, 5.0, 6.0])
    r = dotmod.dot(da, db)
    assert abs(r - 32.0) < 0.01, "double dot failed: %s" % r

    print("PASS: dot")


def test_transform():
    """Test shape dispatch: AoS [N,3] vs SoA [3,N] 2D buffers."""
    if not IS_PY3:
        print("SKIP: transform (2D memoryview.cast requires Python 3.x)")
        return

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'transform'))
    import xfrm

    pts_aos = _double_array([
        1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0
    ])
    out = _zeros_double(12)
    mv = memoryview(pts_aos).cast('B').cast('d', [4, 3])
    mv_out = memoryview(out).cast('B').cast('d', [4, 3])
    xfrm.transform(mv, mv_out)
    expected_aos = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0]
    assert _to_list(out) == expected_aos, "AoS transform failed: %s" % _to_list(out)

    pts_soa = _double_array([
        1.0, 4.0, 7.0, 10.0, 2.0, 5.0, 8.0, 11.0, 3.0, 6.0, 9.0, 12.0
    ])
    out2 = _zeros_double(12)
    mv2 = memoryview(pts_soa).cast('B').cast('d', [3, 4])
    mv_out2 = memoryview(out2).cast('B').cast('d', [3, 4])
    xfrm.transform(mv2, mv_out2)
    expected_soa = [2.0, 8.0, 14.0, 20.0, 4.0, 10.0, 16.0, 22.0, 6.0, 12.0, 18.0, 24.0]
    assert _to_list(out2) == expected_soa, "SoA transform failed: %s" % _to_list(out2)

    print("PASS: transform")


def test_types():
    """Test format character dispatch with fixed-width integer types."""
    import ctypes as ct
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'types'))
    import typesmod

    # uint16_t (format 'H')
    arr_h = (ct.c_uint16 * 4)(0, 0, 0, 0)
    typesmod.fill(arr_h, 42)
    assert list(arr_h) == [42, 42, 42, 42], "uint16 fill failed: %s" % list(arr_h)

    # uint32_t (format 'I')
    arr_i = (ct.c_uint32 * 3)(0, 0, 0)
    typesmod.fill(arr_i, 99)
    assert list(arr_i) == [99, 99, 99], "uint32 fill failed: %s" % list(arr_i)

    # int64_t (format 'q')
    arr_q = (ct.c_int64 * 4)(0, 0, 0, 0)
    typesmod.fill(arr_q, -7)
    assert list(arr_q) == [-7, -7, -7, -7], "int64 fill failed: %s" % list(arr_q)

    # int8_t (format 'b')
    arr_b = (ct.c_int8 * 3)(0, 0, 0)
    typesmod.fill(arr_b, 5)
    assert list(arr_b) == [5, 5, 5], "int8 fill failed: %s" % list(arr_b)

    # int16_t (format 'h')
    arr_h16 = (ct.c_int16 * 4)(0, 0, 0, 0)
    typesmod.fill(arr_h16, 13)
    assert list(arr_h16) == [13, 13, 13, 13], "int16 fill failed: %s" % list(arr_h16)

    print("PASS: types")


def test_optional():
    """Test optional parameters with defaults."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'optional'))
    import optmod

    data = _double_array([1.0, 2.0, 3.0, 4.0, 5.0])

    # All 3 args provided
    r = optmod.process(data, 1, 1)  # stride=1, verbose=1
    assert r == 1015, "process(data, 1, 1) = %d, expected 1015" % r

    # stride provided, verbose default
    r = optmod.process(data, 2)  # stride=2, verbose=0
    assert r == 9, "process(data, 2) = %d, expected 9" % r

    # Only data provided: stride=1 default, verbose=0 default
    r = optmod.process(data)  # stride=1, verbose=0
    assert r == 15, "process(data) = %d, expected 15" % r

    print("PASS: optional")


def test_docstring():
    """Test custom docstring on a function."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'docstring'))
    import docmod

    result = docmod.inc(41)
    assert result == 42, "inc(41) = %d, expected 42" % result

    # Check docstring
    actual_doc = docmod.inc.__doc__
    expected_doc = "Increment x by 1 and return the result"
    assert actual_doc == expected_doc, \
        "docstring: got '%s', expected '%s'" % (actual_doc, expected_doc)

    print("PASS: docstring")


def test_constants():
    """Test module-level integer constants."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'constants'))
    import constmod

    assert constmod.ALPHA == 1, "ALPHA = %s, expected 1" % constmod.ALPHA
    assert constmod.BETA == 2, "BETA = %s, expected 2" % constmod.BETA
    assert constmod.GAMMA == 3, "GAMMA = %s, expected 3" % constmod.GAMMA

    # Also test the function
    data = _double_array([1.0, 2.0, 3.0])
    r = constmod.scale_sum(data, constmod.ALPHA + constmod.BETA)  # factor=3
    expected = 1.0 * 3 + 2.0 * 3 + 3.0 * 3
    assert abs(r - expected) < 0.001, \
        "scale_sum(factor=3) = %s, expected %s" % (r, expected)

    print("PASS: constants")


def test_timing():
    """Test performance timing feature."""
    from c2py23.perf import read_perf, read_enabled, set_enabled

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'timing'))
    import timedmod
    import ctypes as ct

    arr = (ct.c_double * 5)(1.0, 2.0, 3.0, 4.0, 5.0)
    for i in range(10):
        r = timedmod.wsum(arr, 2.0)
        assert abs(r - 30.0) < 0.001

    py = read_perf(timedmod._perf_wsum)
    ov = read_perf(timedmod._perf_wsum__weighted_sum)

    assert py['call_count'] == 10, "py call_count expected 10, got %d" % py['call_count']
    assert py['c_mean_ns'] > 0
    assert py['wrap_mean_ns'] >= 0
    assert ov['call_count'] == 10, "ov call_count expected 10, got %d" % ov['call_count']
    assert ov['c_mean_ns'] > 0
    assert ov['wrap_dur_ns'] == 0

    # Test toggle off
    enabled = read_enabled(timedmod._c2py_timing_enabled)
    assert enabled == 1
    set_enabled(timedmod._c2py_timing_enabled, 0)
    assert read_enabled(timedmod._c2py_timing_enabled) == 0

    timedmod.wsum(arr, 1.0)
    py2 = read_perf(timedmod._perf_wsum)
    assert py2['call_count'] == 10  # should NOT have incremented
    set_enabled(timedmod._c2py_timing_enabled, 1)

    print("PASS: timing")


def main():
    version_str = "%d.%d.%d" % (sys.version_info[0], sys.version_info[1], sys.version_info[2])
    print("Python version: %s" % version_str)
    tests = [
        ("arraysum", test_arraysum),
        ("fill", test_fill),
        ("dot", test_dot),
        ("transform", test_transform),
        ("types", test_types),
        ("optional", test_optional),
        ("docstring", test_docstring),
        ("constants", test_constants),
        ("timing", test_timing),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print("FAIL: %s - %s" % (name, e))
            failed += 1
            import traceback
            traceback.print_exc()

    print("")
    print("Results: %d passed, %d failed" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
