"""Uniform test script for c2py23 - runs identically on Python 2.7 through 3.14.

Tests all test cases: arraysum, fill, dot, transform, types, optional,
docstring, constants, timing, scalar_output, template, typedispatch, gil_release.
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

    # Check docstring contains the user doc
    actual_doc = docmod.inc.__doc__
    assert "Increment x by 1 and return the result" in actual_doc, \
        "docstring missing user doc: '%s'" % actual_doc
    # Check __text_signature__ is parsed correctly (Python 3.3+)
    if hasattr(docmod.inc, '__text_signature__'):
        assert docmod.inc.__text_signature__ == "(x)", \
            "__text_signature__: got %r" % docmod.inc.__text_signature__
    # Check docstring contains auto-derived info
    assert "Overloads" in actual_doc, "docstring missing Overloads section"
    assert "add_one" in actual_doc, "docstring missing overload C function"

    print("PASS: docstring")


def test_constants():
    """Test module-level integer constants (incl. zero, negative, edge-large)."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'constants'))
    import constmod

    assert constmod.ALPHA == 1, "ALPHA = %s, expected 1" % constmod.ALPHA
    assert constmod.BETA == 2, "BETA = %s, expected 2" % constmod.BETA
    assert constmod.GAMMA == 3, "GAMMA = %s, expected 3" % constmod.GAMMA
    assert constmod.ZERO == 0, "ZERO = %s, expected 0" % constmod.ZERO
    assert constmod.NEG == -1, "NEG = %s, expected -1" % constmod.NEG
    assert constmod.LARGE == 2147483647, (
        "LARGE = %s, expected 2147483647" % constmod.LARGE)

    # Also test the function
    data = _double_array([1.0, 2.0, 3.0])
    r = constmod.scale_sum(data, constmod.ALPHA + constmod.BETA)  # factor=3
    expected = 1.0 * 3 + 2.0 * 3 + 3.0 * 3
    assert abs(r - expected) < 0.001, \
        "scale_sum(factor=3) = %s, expected %s" % (r, expected)

    print("PASS: constants")


def test_timing():
    """Test performance timing feature (no ctypes)."""
    from c2py23.perf import read_perf, read_enabled, set_enabled

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'timing'))
    import timedmod
    import ctypes as ct

    py0 = read_perf(timedmod.wsum)
    ov0 = read_perf(timedmod.wsum, variant="weighted_sum")
    py_count0 = py0['call_count']
    ov_count0 = ov0['call_count']

    arr = (ct.c_double * 5)(1.0, 2.0, 3.0, 4.0, 5.0)
    for i in range(10):
        r = timedmod.wsum(arr, 2.0)
        assert abs(r - 30.0) < 0.001

    py = read_perf(timedmod.wsum)
    ov = read_perf(timedmod.wsum, variant="weighted_sum")

    assert py['call_count'] == py_count0 + 10, (
        "py call_count expected %d, got %d" % (py_count0 + 10, py['call_count']))
    assert py['c_mean_ns'] > 0
    assert py['wrap_mean_ns'] >= 0
    assert ov['call_count'] == ov_count0 + 10, (
        "ov call_count expected %d, got %d" % (ov_count0 + 10, ov['call_count']))
    assert ov['c_mean_ns'] > 0
    assert ov['wrap_dur_ns'] == 0

    # Test toggle off
    enabled = read_enabled(timedmod.wsum)
    assert enabled == 1
    set_enabled(timedmod.wsum, 0)
    assert read_enabled(timedmod.wsum) == 0

    timedmod.wsum(arr, 1.0)
    py2 = read_perf(timedmod.wsum)
    assert py2['call_count'] == py['call_count']  # should NOT have incremented
    set_enabled(timedmod.wsum, 1)

    print("PASS: timing")


def test_scalar_output():
    """Test output scalar convention - C returns values via pointer args."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'scalar_output'))
    import statmod

    data = _double_array([3.0, 1.0, 5.0, 2.0, 4.0])
    minval, maxval = statmod.stats(data)
    assert minval == 1.0, "minval expected 1.0, got %s" % minval
    assert maxval == 5.0, "maxval expected 5.0, got %s" % maxval

    print("PASS: scalar_output")


def test_template():
    """Test template expansion - parameterized function definitions."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'template'))
    import summod

    data_u8 = (ctypes.c_uint8 * 5)(1, 2, 3, 4, 5)
    assert summod.sum_u8(data_u8) == 15

    data_u16 = (ctypes.c_uint16 * 3)(1, 2, 3)
    assert summod.sum_u16(data_u16) == 6

    data_i32 = (ctypes.c_int32 * 4)(10, 20, 30, 40)
    assert summod.sum_i32(data_i32) == 100

    print("PASS: template")


def test_typedispatch():
    """Test format dispatch over all 10 PEP 3118 buffer types.
    
    Covers the complete format-to-ctype mapping:
      'B' -> uint8_t   'b' -> int8_t
      'H' -> uint16_t  'h' -> int16_t
      'I' -> uint32_t  'i' -> int32_t
      'Q' -> uint64_t  'q' -> int64_t
      'f' -> float     'd' -> double
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'typedispatch'))
    import dispatchmod

    # uint8_t (format 'B')
    arr_B = (ctypes.c_uint8 * 3)(0, 0, 0)
    dispatchmod.fill(arr_B, 42)
    assert list(arr_B) == [42, 42, 42], "uint8 fill failed: %s" % list(arr_B)

    # int8_t (format 'b')
    arr_b = (ctypes.c_int8 * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_b, -7)
    assert list(arr_b) == [-7, -7, -7, -7], "int8 fill failed: %s" % list(arr_b)

    # uint16_t (format 'H')
    arr_H = (ctypes.c_uint16 * 3)(0, 0, 0)
    dispatchmod.fill(arr_H, 99)
    assert list(arr_H) == [99, 99, 99], "uint16 fill failed: %s" % list(arr_H)

    # int16_t (format 'h')
    arr_h = (ctypes.c_int16 * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_h, -13)
    assert list(arr_h) == [-13, -13, -13, -13], "int16 fill failed: %s" % list(arr_h)

    # uint32_t (format 'I')
    arr_I = (ctypes.c_uint32 * 3)(0, 0, 0)
    dispatchmod.fill(arr_I, 1000000)
    assert list(arr_I) == [1000000, 1000000, 1000000], "uint32 fill failed: %s" % list(arr_I)

    # int32_t (format 'i')
    arr_i = (ctypes.c_int32 * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_i, -1000000)
    assert list(arr_i) == [-1000000, -1000000, -1000000, -1000000], "int32 fill failed: %s" % list(arr_i)

    # uint64_t (format 'Q')
    arr_Q = (ctypes.c_uint64 * 3)(0, 0, 0)
    dispatchmod.fill(arr_Q, 9999999999)
    assert list(arr_Q) == [9999999999, 9999999999, 9999999999], "uint64 fill failed: %s" % list(arr_Q)

    # int64_t (format 'q')
    arr_q = (ctypes.c_int64 * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_q, -9999999999)
    assert list(arr_q) == [-9999999999, -9999999999, -9999999999, -9999999999], "int64 fill failed: %s" % list(arr_q)

    # float32 (format 'f')
    arr_f = (ctypes.c_float * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_f, 3.14)
    vals_f = _to_list(arr_f)
    for v in vals_f:
        assert abs(v - 3.14) < 0.01, "float32 fill failed: %s" % vals_f

    # float64 (format 'd')
    arr_d = (ctypes.c_double * 3)(0, 0, 0)
    dispatchmod.fill(arr_d, 2.718)
    vals_d = _to_list(arr_d)
    for v in vals_d:
        assert abs(v - 2.718) < 0.0001, "float64 fill failed: %s" % vals_d

    print("PASS: typedispatch")


def test_gil_release():
    """Test GIL release: concurrent calls overlap instead of serializing."""
    import time
    import threading

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'gil_release'))
    import gilmod

    arr = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    arr2 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    sleep_us = 100000  # 100ms

    # Test 1: With GIL release, two threads overlap
    t0 = time.time()
    t1 = threading.Thread(target=gilmod.sleep_fill, args=(arr, 1.0, sleep_us))
    t2 = threading.Thread(target=gilmod.sleep_fill, args=(arr2, 2.0, sleep_us))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    elapsed = time.time() - t0

    # With GIL release, both 100ms sleeps should overlap -> < 150ms
    assert elapsed < 0.150, \
        "GIL release: expected < 150ms, got %.3fs (threads serialized?)" % elapsed
    assert list(arr) == [1.0, 1.0, 1.0, 1.0], "thread 1 fill failed"
    assert list(arr2) == [2.0, 2.0, 2.0, 2.0], "thread 2 fill failed"

    # Test 2: Without GIL release, threads serialize
    arr3 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    arr4 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)

    t0 = time.time()
    t3 = threading.Thread(target=gilmod.sleep_fill_no_gil, args=(arr3, 3.0, 50000))
    t4 = threading.Thread(target=gilmod.sleep_fill_no_gil, args=(arr4, 4.0, 50000))
    t3.start()
    t4.start()
    t3.join()
    t4.join()
    elapsed_no = time.time() - t0

    # Without GIL release, two 50ms sleeps serialize -> > 80ms
    assert elapsed_no > 0.080, \
        "No GIL release: expected > 80ms, got %.3fs (threads overlapped?)" % elapsed_no
    assert list(arr3) == [3.0, 3.0, 3.0, 3.0], "thread 3 fill failed"
    assert list(arr4) == [4.0, 4.0, 4.0, 4.0], "thread 4 fill failed"

    # Test 3: Global toggle disables GIL release
    # Read the global flag pointer and set to 0
    import ctypes as ct
    gil_flag_ptr = gilmod._c2py_gil_release_enabled
    ct.c_int.from_address(gil_flag_ptr).value = 0

    arr5 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    arr6 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)

    t0 = time.time()
    t5 = threading.Thread(target=gilmod.sleep_fill, args=(arr5, 5.0, 50000))
    t6 = threading.Thread(target=gilmod.sleep_fill, args=(arr6, 6.0, 50000))
    t5.start()
    t6.start()
    t5.join()
    t6.join()
    elapsed_disabled = time.time() - t0

    # When disabled, two 50ms sleeps should serialize -> > 80ms
    assert elapsed_disabled > 0.080, \
        "GIL disabled: expected > 80ms, got %.3fs (still overlapping?)" % elapsed_disabled
    assert list(arr5) == [5.0, 5.0, 5.0, 5.0], "thread 5 fill failed"
    assert list(arr6) == [6.0, 6.0, 6.0, 6.0], "thread 6 fill failed"

    # Restore global flag
    ct.c_int.from_address(gil_flag_ptr).value = 1

    # Test 4: Per-function toggle via module attribute
    func_flag_ptr = gilmod._c2py_gil_release_sleep_fill
    ct.c_int.from_address(func_flag_ptr).value = 0

    arr7 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    arr8 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)

    t0 = time.time()
    t7 = threading.Thread(target=gilmod.sleep_fill, args=(arr7, 7.0, 30000))
    t8 = threading.Thread(target=gilmod.sleep_fill, args=(arr8, 8.0, 30000))
    t7.start()
    t8.start()
    t7.join()
    t8.join()
    elapsed_func_disabled = time.time() - t0

    assert elapsed_func_disabled > 0.050, \
        "Per-func disabled: expected > 50ms, got %.3fs" % elapsed_func_disabled
    assert list(arr7) == [7.0, 7.0, 7.0, 7.0]
    assert list(arr8) == [8.0, 8.0, 8.0, 8.0]

    # Restore
    ct.c_int.from_address(func_flag_ptr).value = 1

    print("PASS: gil_release")


def test_address():
    """Test opaque void* pointers passed as Python int.

    Demonstrates that Python int values can map to C void* parameters.
    This is useful for passing GPU pointers, allocator handles, or
    other opaque addresses without Python managing the memory.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'address'))
    import addressmod

    # Allocate a buffer in Python, pass its address as int to C
    buf = (ctypes.c_int * 10)()
    ptr = ctypes.addressof(buf)

    # Store via void* -- C side dereferences the int as a pointer
    ret = addressmod.address_store(ptr, 42, 3)
    assert ret == 0, "address_store(ptr, 42, 3) returned %d, expected 0" % ret
    assert buf[3] == 42, "buf[3] = %d, expected 42 after address_store" % buf[3]

    # NULL pointer returns error
    ret = addressmod.address_store(0, 99, 0)
    assert ret == -1, "address_store(0, 99, 0) returned %d, expected -1" % ret

    # Verify other elements are untouched
    assert buf[0] == 0, "buf[0] was modified, expected 0"
    assert buf[9] == 0, "buf[9] was modified, expected 0"

    print("PASS: address")


def test_array_sig():
    """Test array dimension notation in C sig (gv[][3], ubi[3][3], arr[5], blk[][5][5])."""
    if not IS_PY3:
        print("SKIP: array_sig (2D memoryview requires Python 3.x)")
        return
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'array_sig'))
    import arraymod
    import ctypes as ct

    # sum_rows: gv[][3] -> AoS layout, C-contiguous, shape [ng, 3]
    arr = (ct.c_double * 6)(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    mv = memoryview(arr).cast('B').cast('d', [2, 3])
    r = arraymod.sum_rows(mv)
    assert abs(r - 21.0) < 0.001, "sum_rows([2,3]) = %s, expected 21.0" % r

    # sum_33: ubi[3][3] -> fixed 3x3, C-contiguous
    arr2 = (ct.c_double * 9)(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)
    mv2 = memoryview(arr2).cast('B').cast('d', [3, 3])
    r2 = arraymod.sum_33(mv2)
    assert abs(r2 - 45.0) < 0.001, "sum_33([3,3]) = %s, expected 45.0" % r2

    # sum_1d_fixed: arr[5] -> 1D C-contiguous, exactly 5 elements
    arr3 = (ct.c_double * 5)(1.0, 2.0, 3.0, 4.0, 5.0)
    r3 = arraymod.sum_1d_fixed(arr3)
    assert abs(r3 - 15.0) < 0.001, "sum_1d_fixed = %s, expected 15.0" % r3

    # sum_3d: blk[][5][5] -> shape [nblk, 5, 5], C-contiguous
    arr4 = (ct.c_double * 50)(*range(1, 51))
    mv3 = memoryview(arr4).cast('B').cast('d', [2, 5, 5])
    r4 = arraymod.sum_3d(mv3)
    expected = sum(range(1, 51))
    assert abs(r4 - expected) < 0.001, "sum_3d = %s, expected %s" % (r4, expected)

    # Wrong shape rejection: gv[][3] needs shape[-1] == 3, reject shape[2][4]
    bad_arr = (ct.c_double * 8)(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    bad_mv = memoryview(bad_arr).cast('B').cast('d', [2, 4])
    try:
        arraymod.sum_rows(bad_mv)
        assert False, "sum_rows should reject shape[1] != 3"
    except ValueError:
        pass

    # Wrong element count for 1D fixed: arr[5] needs exactly 5 elements
    short_arr = (ct.c_double * 3)(1.0, 2.0, 3.0)
    try:
        arraymod.sum_1d_fixed(short_arr)
        assert False, "sum_1d_fixed should reject n != 5"
    except ValueError:
        pass

    print("PASS: array_sig")


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
        ("scalar_output", test_scalar_output),
        ("template", test_template),
        ("typedispatch", test_typedispatch),
        ("gil_release", test_gil_release),
        ("address", test_address),
        ("array_sig", test_array_sig),
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
