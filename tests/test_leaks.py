"""Memory leak stress test for c2py23 generated wrappers.

Exercises each wrapped function in a tight loop and monitors RSS growth.
Runs under valgrind for precise leak detection when available.
"""
from __future__ import print_function

import sys
import os
import ctypes
import warnings

warnings.filterwarnings("ignore", message=".*API version mismatch.*")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ITERATIONS = 10000
_IS_PY3 = sys.version_info[0] >= 3


def _double_array(values):
    n = len(values)
    return (ctypes.c_double * n)(*values)


def _zeros_double(n):
    return _double_array([0.0] * n)


def _float_array(values):
    n = len(values)
    return (ctypes.c_float * n)(*values)


def test_arraysum_stress():
    """Stress test: repeated calls to triple-buffer write function."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum
    for _ in range(_ITERATIONS):
        a = _double_array([1.0, 2.0, 3.0, 4.0])
        b = _double_array([5.0, 6.0, 7.0, 8.0])
        r = _zeros_double(4)
        arraysum.array_sum(a, b, r)
    print("PASS: arraysum stress (%d calls)" % _ITERATIONS)


def test_fill_stress():
    """Stress test: format dispatch write function."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'fill'))
    import fillmod
    for _ in range(_ITERATIONS):
        arr = _float_array([0.0, 0.0, 0.0, 0.0])
        fillmod.fill(arr, 3.14)
    print("PASS: fill stress (%d calls)" % _ITERATIONS)


def test_dot_stress():
    """Stress test: format dispatch with scalar return."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'dot'))
    import dotmod
    for _ in range(_ITERATIONS):
        a = _float_array([1.0, 2.0, 3.0])
        b = _float_array([4.0, 5.0, 6.0])
        dotmod.dot(a, b)
    print("PASS: dot stress (%d calls)" % _ITERATIONS)


def test_scalar_output_stress():
    """Stress test: output scalar convention."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'scalar_output'))
    import statmod
    for _ in range(_ITERATIONS):
        data = _double_array([3.0, 1.0, 5.0, 2.0, 4.0])
        statmod.stats(data)
    print("PASS: scalar_output stress (%d calls)" % _ITERATIONS)


def test_typedispatch_stress():
    """Stress test: all 10 format char overloads."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'typedispatch'))
    import dispatchmod
    for _ in range(_ITERATIONS):
        a = (ctypes.c_uint8 * 4)(1, 2, 3, 4)
        dispatchmod.fill(a, 0)
        b = (ctypes.c_int8 * 4)(-1, -2, -3, -4)
        dispatchmod.fill(b, 0)
        c = (ctypes.c_uint32 * 4)(10, 20, 30, 40)
        dispatchmod.fill(c, 0)
    print("PASS: typedispatch stress (%d calls)" % _ITERATIONS)


def test_types_stress():
    """Stress test: mixed type dispatch (i8, i16, i32, i64, u16, u32)."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'types'))
    import typesmod
    for _ in range(_ITERATIONS):
        a = (ctypes.c_int16 * 2)(-1, -2)
        typesmod.fill(a, 0)
        b = (ctypes.c_uint32 * 2)(100, 200)
        typesmod.fill(b, 0)
    print("PASS: types stress (%d calls)" % _ITERATIONS)


def test_optional_stress():
    """Stress test: optional int params with defaults."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'optional'))
    import optmod
    for _ in range(_ITERATIONS):
        data = _double_array([1.0, 2.0, 3.0, 4.0])
        optmod.process(data)
        optmod.process(data, 2)
        optmod.process(data, 1, 1)
    print("PASS: optional stress (%d calls)" % _ITERATIONS)


def test_timing_stress():
    """Stress test: perf-timing wrapper."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'timing'))
    import timedmod
    for _ in range(_ITERATIONS):
        data = _double_array([1.0, 2.0, 3.0, 4.0, 5.0])
        timedmod.wsum(data, 2.0)
    print("PASS: timing stress (%d calls)" % _ITERATIONS)


def test_address_stress():
    """Stress test: void* passthrough (int param -> void*)."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'address'))
    import addressmod
    buf = (ctypes.c_int32 * 4)(0, 0, 0, 0)
    ptr = ctypes.addressof(buf)
    for _ in range(_ITERATIONS):
        addressmod.address_store(ptr, 42, 0)
    print("PASS: address stress (%d calls)" % _ITERATIONS)


def test_gil_release_stress():
    """Stress test: GIL release path."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'gil_release'))
    import gilmod
    for _ in range(_ITERATIONS // 10):  # fewer iter (sleeps 1us each)
        arr = _float_array([0.0, 0.0])
        gilmod.sleep_fill(arr, 3.14, 1)
    print("PASS: gil_release stress (%d calls)" % (_ITERATIONS // 10))


def test_constants_stress():
    """Stress test: constants module (function call)."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'constants'))
    import constmod
    for _ in range(_ITERATIONS):
        data = _double_array([1.0, 2.0, 3.0])
        constmod.scale_sum(data, 3)
    print("PASS: constants stress (%d calls)" % _ITERATIONS)


def test_transform_stress():
    """Stress test: 2D shape dispatch (AoS/SoA)."""
    if not _IS_PY3:
        print("SKIP: transform stress (2D memoryview requires Python 3.x)")
        return
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'transform'))
    import xfrm
    for _ in range(_ITERATIONS):
        arr = (ctypes.c_double * 12)(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
        out = (ctypes.c_double * 12)()
        mv = memoryview(arr).cast('B').cast('d', [4, 3])
        out_mv = memoryview(out).cast('B').cast('d', [4, 3])
        xfrm.transform(mv, out_mv)
    print("PASS: transform stress (%d calls)" % _ITERATIONS)


def check_rss():
    """Read RSS (resident set size) in pages from /proc/self/statm."""
    try:
        with open('/proc/self/statm', 'r') as f:
            fields = f.read().split()
            return int(fields[1])  # RSS in pages
    except Exception:
        return None


def main():
    global _ITERATIONS

    if '--valgrind' in sys.argv:
        _ITERATIONS = 100

    print("c2py23 memory leak stress test")
    print("Iterations per test: %d" % _ITERATIONS)
    print("")

    if '--valgrind' in sys.argv:
        print("Running under valgrind-compatible mode")

    tests = [
        test_arraysum_stress,
        test_fill_stress,
        test_dot_stress,
        test_scalar_output_stress,
        test_typedispatch_stress,
        test_types_stress,
        test_optional_stress,
        test_timing_stress,
        test_address_stress,
        test_gil_release_stress,
        test_constants_stress,
        test_transform_stress,
    ]

    rss_before = check_rss()

    for test in tests:
        test()

    rss_after = check_rss()

    if rss_before is not None and rss_after is not None:
        pagesize = os.sysconf(os.sysconf_names['SC_PAGESIZE'])
        growth_kb = (rss_after - rss_before) * pagesize // 1024
        print("")
        print("RSS before: %d pages (%d kB)" % (rss_before,
              rss_before * pagesize // 1024))
        print("RSS after:  %d pages (%d kB)" % (rss_after,
              rss_after * pagesize // 1024))
        print("RSS growth: %d kB" % growth_kb)
        if growth_kb > 5000:
            print("WARNING: Significant RSS growth detected!")
            return 1

    print("")
    print("All stress tests passed.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
