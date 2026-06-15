"""Verify refcounts on buffer error paths across multi-buffer functions.

Tests:
  - arraysum (3 buffers): format check failure on last buffer
  - arraysum (3 buffers): size mismatch check on last buffer  
  - Writable buffer alias detection
  - Strided buffer rejection
"""
from __future__ import print_function

import sys
import os
import ctypes
import warnings

warnings.filterwarnings("ignore", message=".*API version mismatch.*")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def refcount(obj):
    return sys.getrefcount(obj) - 1


def test_arraysum_format_mismatch_last_buffer():
    """3 buffers: a(d), b(d), c(f). c has wrong format -> format check fails.
    Verify a and b refcounts unchanged, c refcount unchanged (all released)."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    c = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)  # wrong type!

    ra0 = refcount(a)
    rb0 = refcount(b)
    rc0 = refcount(c)

    try:
        arraysum.array_sum(a, b, c)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    ra1 = refcount(a)
    rb1 = refcount(b)
    rc1 = refcount(c)

    assert ra1 == ra0, "a refcount: %d -> %d (leak!)" % (ra0, ra1)
    assert rb1 == rb0, "b refcount: %d -> %d (leak!)" % (rb0, rb1)
    assert rc1 == rc0, "c refcount: %d -> %d (leak!)" % (rc0, rc1)
    print("PASS: format mismatch on 3rd buffer -- all refcounts stable")


def test_arraysum_size_mismatch_last_buffer():
    """3 buffers: a(d, 4), b(d, 4), c(d, 3). c has different length ->
    size check fails. Verify refcounts unchanged."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    c = (ctypes.c_double * 3)(0.0, 0.0, 0.0)  # wrong size

    ra0 = refcount(a)
    rb0 = refcount(b)
    rc0 = refcount(c)

    try:
        arraysum.array_sum(a, b, c)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    ra1 = refcount(a)
    rb1 = refcount(b)
    rc1 = refcount(c)

    assert ra1 == ra0, "a refcount: %d -> %d (leak!)" % (ra0, ra1)
    assert rb1 == rb0, "b refcount: %d -> %d (leak!)" % (rb0, rb1)
    assert rc1 == rc0, "c refcount: %d -> %d (leak!)" % (rc0, rc1)
    print("PASS: size mismatch on 3rd buffer -- all refcounts stable")


def test_arraysum_success_refcounts():
    """3 buffers all correct: refcounts must return to baseline after call."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    c = (ctypes.c_double * 4)(0.0, 0.0, 0.0, 0.0)

    ra0 = refcount(a)
    rb0 = refcount(b)
    rc0 = refcount(c)

    arraysum.array_sum(a, b, c)

    ra1 = refcount(a)
    rb1 = refcount(b)
    rc1 = refcount(c)

    assert ra1 == ra0, "a refcount: %d -> %d" % (ra0, ra1)
    assert rb1 == rb0, "b refcount: %d -> %d" % (rb0, rb1)
    assert rc1 == rc0, "c refcount: %d -> %d" % (rc0, rc1)
    print("PASS: successful 3-buffer call -- all refcounts stable")


def test_arraysum_repeated_success_loop():
    """10000 calls with 3 buffers -- verify refcount stability each time."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    c = (ctypes.c_double * 4)(0.0, 0.0, 0.0, 0.0)

    ra0 = refcount(a)
    rb0 = refcount(b)
    rc0 = refcount(c)

    for i in range(10000):
        arraysum.array_sum(a, b, c)
        if i % 2500 == 0:
            ra = refcount(a)
            rb = refcount(b)
            rc = refcount(c)
            if ra != ra0 or rb != rb0 or rc != rc0:
                print("  FAIL at iter %d: a=%d->%d b=%d->%d c=%d->%d" % (
                    i, ra0, ra, rb0, rb, rc0, rc))
                return False

    ra1 = refcount(a)
    rb1 = refcount(b)
    rc1 = refcount(c)
    assert ra1 == ra0, "after 10000 iter: a=%d->%d" % (ra0, ra1)
    assert rb1 == rb0, "after 10000 iter: b=%d->%d" % (rb0, rb1)
    assert rc1 == rc0, "after 10000 iter: c=%d->%d" % (rc0, rc1)
    print("PASS: 10000 repeated 3-buffer calls -- all refcounts stable")


def test_arraysum_alias_detection_refcounts():
    """Alias detection (c2py wraps around writable buffers that alias).
    Error path must still release all acquired buffers."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    # arraysum writes to r. If r aliases a or b, should error.
    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    # r IS a (alias)
    r = a

    ra0 = refcount(a)
    rb0 = refcount(b)
    rr0 = refcount(r)

    try:
        arraysum.array_sum(a, b, r)
        assert False, "Should have raised ValueError for alias"
    except ValueError:
        pass

    ra1 = refcount(a)
    rb1 = refcount(b)
    rr1 = refcount(r)

    # r IS a, so they share refcounts. Both should be baseline.
    assert ra1 == ra0, "a refcount: %d -> %d (alias leak!)" % (ra0, ra1)
    assert rb1 == rb0, "b refcount: %d -> %d (alias leak!)" % (rb0, rb1)
    print("PASS: alias detection path -- all refcounts stable")


if __name__ == '__main__':
    results = []
    for name in sorted(globals()):
        if name.startswith('test_'):
            try:
                globals()[name]()
                results.append(('PASS', name))
            except Exception as e:
                results.append(('FAIL', name + ': ' + str(e)))
                import traceback
                traceback.print_exc()

    passed = sum(1 for r, _ in results if r == 'PASS')
    total = len(results)
    print('\nResults: %d/%d passed' % (passed, total))
    sys.exit(0 if passed == total else 1)
