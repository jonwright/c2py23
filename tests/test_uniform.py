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


def main():
    version_str = "%d.%d.%d" % (sys.version_info[0], sys.version_info[1], sys.version_info[2])
    print("Python version: %s" % version_str)
    tests = [
        ("arraysum", test_arraysum),
        ("fill", test_fill),
        ("dot", test_dot),
        ("transform", test_transform),
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
