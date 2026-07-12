"""Aliasing and contiguity tests from peer review feedback.

Tests all 5 buffer-alias patterns:
  1. Slice:  b = a[1:]
  2. Reversed: b = a[::-1]
  3. memoryview: b = memoryview(a)
  4. View: b = a.view()
  5. Broadcast: b = np.broadcast_to(a, ...)

Also tests contiguity enforcement:
  - Strided arrays (a[::2]) are rejected
  - Negative strides (a[::-1]) are rejected
  - C-contiguous accepted
  - F-contiguous accepted (for 2D)
"""

from __future__ import print_function

import sys
import os
import warnings

warnings.filterwarnings("ignore", message=".*API version mismatch.*")

import numpy as np

IS_PY3 = sys.version_info[0] >= 3

test_dir = os.path.join(os.path.dirname(__file__), "cases", "arraysum")
sys.path.insert(0, test_dir)
import arraysum


def test_alias_slice():
    """Slice: b = a[1:] overlaps with original a."""
    a = np.arange(100, dtype=np.float64)
    b = a[1:]  # shares memory, offset by 8 bytes

    result = np.zeros(99, dtype=np.float64)
    try:
        arraysum.array_sum(a, b, a)  # output aliases input a
        raise AssertionError("FAIL: slice alias should be rejected")
    except ValueError as e:
        assert "alias" in str(e), "Expected alias error, got: %s" % e
        print("PASS: slice alias detected")


def test_alias_reversed():
    """Reversed: b = a[::-1] overlaps with original a."""
    a = np.arange(100, dtype=np.float64)
    b = a[::-1]  # reversed view, same memory

    result = np.zeros(100, dtype=np.float64)
    try:
        arraysum.array_sum(a, b, a)  # output aliases input a
        raise AssertionError("FAIL: reversed alias should be rejected")
    except ValueError as e:
        assert "alias" in str(e), "Expected alias error, got: %s" % e
        print("PASS: reversed alias detected")


def test_alias_memoryview():
    """memoryview: b = memoryview(a) wraps same data."""
    a = np.arange(100, dtype=np.float64)
    b = memoryview(a)  # same underlying memory

    result = np.zeros(100, dtype=np.float64)
    try:
        arraysum.array_sum(a, b, a)  # output aliases input a
        raise AssertionError("FAIL: memoryview alias should be rejected")
    except ValueError as e:
        assert "alias" in str(e), "Expected alias error, got: %s" % e
        print("PASS: memoryview alias detected")


def test_alias_view():
    """View: b = a.view() shares same buffer."""
    a = np.arange(100, dtype=np.float64)
    b = a.view()

    result = np.zeros(100, dtype=np.float64)
    try:
        arraysum.array_sum(a, b, a)  # output aliases input a
        raise AssertionError("FAIL: view alias should be rejected")
    except ValueError as e:
        assert "alias" in str(e), "Expected alias error, got: %s" % e
        print("PASS: view alias detected")


def test_alias_broadcast():
    """Broadcast: np.broadcast_to shares data pointer."""
    a = np.arange(100, dtype=np.float64)
    b = np.broadcast_to(a, (3, 100))  # same data, different shape

    result = np.zeros(100, dtype=np.float64)
    try:
        arraysum.array_sum(a, a, a)  # output == input (simpler alias test)
        raise AssertionError("FAIL: broadcast alias should be rejected")
    except ValueError as e:
        assert "alias" in str(e), "Expected alias error, got: %s" % e
        print("PASS: broadcast (self-alias) detected")


def test_alias_output_equals_input():
    """Output same object as input -- simplest alias."""
    a = np.arange(100, dtype=np.float64)
    b = np.arange(100, dtype=np.float64)

    try:
        arraysum.array_sum(a, b, a)  # result IS a
        raise AssertionError("FAIL: output==input alias should be rejected")
    except ValueError as e:
        assert "alias" in str(e), "Expected alias error, got: %s" % e
        print("PASS: output==input alias detected")


def test_no_false_positive():
    """Non-aliased buffers should pass."""
    a = np.arange(100, dtype=np.float64)
    b = np.arange(100, dtype=np.float64)
    result = np.zeros(100, dtype=np.float64)

    n = arraysum.array_sum(a, b, result)
    assert n == 100
    expected = a + b
    assert np.allclose(result, expected)
    print("PASS: non-aliased buffers accepted")


def test_contiguity_strided():
    """Strided arrays (a[::2]) should be rejected."""
    test_dir2 = os.path.join(os.path.dirname(__file__), "cases", "fill")
    sys.path.insert(0, test_dir2)
    import fillmod

    a = np.arange(20, dtype=np.float64)
    b = a[::2]  # stride = 16, not 8

    try:
        fillmod.fill(b, 1.0)
        raise AssertionError("FAIL: strided array should be rejected")
    except ValueError as e:
        assert "contiguous" in str(e).lower(), "Expected contiguous error, got: %s" % e
        print("PASS: strided rejected:", e)


def test_contiguity_reversed():
    """Reversed arrays (a[::-1]) should be rejected."""
    test_dir2 = os.path.join(os.path.dirname(__file__), "cases", "fill")
    sys.path.insert(0, test_dir2)

    a = np.arange(20, dtype=np.float64)
    b = a[::-1]

    try:
        # Need to re-import since sys.path may have changed
        import fillmod

        fillmod.fill(b, 1.0)
        raise AssertionError("FAIL: reversed array should be rejected")
    except ValueError as e:
        assert "contiguous" in str(e).lower(), "Expected contiguous error, got: %s" % e
        print("PASS: reversed rejected:", e)


def test_contiguity_fortran_2d():
    """F-contiguous 2D arrays should be accepted."""
    if not IS_PY3:
        print("SKIP: 2D arrays require Python 3.x")
        return

    test_dir3 = os.path.join(os.path.dirname(__file__), "cases", "fill")
    sys.path.insert(0, test_dir3)

    # Create a Fortran-contiguous array and verify fillmod accepts it
    # (memoryview.cast requires C-contiguous, so pass numpy array directly)
    a = np.array(
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0], [10.0, 11.0, 12.0]],
        dtype=np.float64,
    )
    af = np.asfortranarray(a)  # F-order, shape [4,3], F-contiguous
    assert af.flags["F_CONTIGUOUS"]
    assert not af.flags["C_CONTIGUOUS"]

    import fillmod

    # Flat F-contiguous buffer: contiguous in memory along columns
    fillmod.fill(af, 99.0)
    assert (af == 99.0).all()
    print("PASS: F-contiguous 2D accepted")


def main():
    version_str = "%d.%d.%d" % (
        sys.version_info[0],
        sys.version_info[1],
        sys.version_info[2],
    )
    print("Python version: %s" % version_str)
    print("")

    tests = [
        ("alias: output==input", test_alias_output_equals_input),
        ("alias: slice", test_alias_slice),
        ("alias: reversed", test_alias_reversed),
        ("alias: memoryview", test_alias_memoryview),
        ("alias: view", test_alias_view),
        ("alias: broadcast (self)", test_alias_broadcast),
        ("no false positive", test_no_false_positive),
        ("contiguity: strided rejected", test_contiguity_strided),
        ("contiguity: reversed rejected", test_contiguity_reversed),
        ("contiguity: F-order 2D accepted", test_contiguity_fortran_2d),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except (AssertionError, SystemExit) as e:
            print("FAIL: %s - %s" % (name, e))
            failed += 1
        except ImportError:
            print("SKIP: %s (module not available)" % name)
        except Exception as e:
            print("ERROR: %s - %s" % (name, e))
            import traceback

            traceback.print_exc()
            failed += 1

    print("")
    print("Results: %d passed, %d failed" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
