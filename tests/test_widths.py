"""Integer width tests: > 2 GiB buffers, narrow receivers, 64-bit values.

Builds on tests/cases/widths (widthmod).  The large buffer is an anonymous
mmap: pages are only committed when touched, so only the last page is
written.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import mmap
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases", "widths"))

import widthmod  # noqa: E402

_TWO_GIB = 1 << 31


def _expect_value_error(fn, *args):
    try:
        fn(*args)
    except ValueError as e:
        return str(e)
    raise AssertionError("%s%r did not raise ValueError" % (fn.__name__, args))


def test_buffer_over_2gib_to_size_t():
    """A buffer larger than 2 GiB reaches a size_t length in one call."""
    # A 32-bit process cannot map 2 GiB; Py_ssize_t (and so the buffer
    # length) tops out below it there, so nothing can be truncated.
    if sys.maxsize <= _TWO_GIB:
        return
    size = _TWO_GIB + 4096
    m = mmap.mmap(-1, size)
    try:
        m[size - 1 : size] = b"\x07"
        nbytes, last = widthmod.last_byte(m)
    finally:
        m.close()
    assert nbytes == size, "nbytes = %r, expected %r" % (nbytes, size)
    assert last == 7, "last byte = %r, expected 7" % (last,)


def test_narrow_receiver_range_checked():
    """A uint8_t length receiver accepts 255 bytes and rejects 256."""
    assert widthmod.small_len(bytearray(255)) == 255
    msg = _expect_value_error(widthmod.small_len, bytearray(256))
    assert "out of range for C uint8_t n" in msg, msg


def test_uint32_full_range():
    """uint32_t scalars and outputs round-trip above 2**31."""
    for v in (0, 1, 2**31, 3000000000, 2**32 - 1):
        assert widthmod.echo_u32(v) == v, "echo_u32(%d)" % v
    for v in (-1, 2**32):
        msg = _expect_value_error(widthmod.echo_u32, v)
        assert "out of range for C uint32_t v" in msg, msg


def test_int64_scalars_and_outputs():
    """int64_t/uint64_t scalars and outputs keep all 64 bits."""
    for v in (0, -1, 2**31, -(2**31) - 1, 2**40, 2**63 - 1, -(2**63)):
        assert widthmod.echo_i64(v) == v, "echo_i64(%d)" % v
    for v in (0, 2**40, 2**63 - 1):
        assert widthmod.echo_u64(v) == v, "echo_u64(%d)" % v
    msg = _expect_value_error(widthmod.echo_u64, -1)
    assert "out of range for C uint64_t v" in msg, msg


def test_pointer_width_scalars():
    """size_t/intptr_t/ptrdiff_t take their full range and raise beyond it.

    These are 32-bit on a 32-bit build, so 2**32 and 2**40 must raise there
    rather than arrive truncated; on a 64-bit build they must arrive intact.
    Negative values never wrap into size_t.
    """
    wide = sys.maxsize > 2**32
    big = [2**31, 2**32, 2**40]
    signed_ok = [0, 1, -1, 2**31 - 1, -(2**31), sys.maxsize, -sys.maxsize - 1]
    size_ok = [0, 1, 2**31, 2**32 - 1 if not wide else sys.maxsize]
    if wide:
        signed_ok += big + [-x for x in big]
        size_ok += big
        signed_bad = []
        size_bad = [-1, -(2**40)]
    else:
        signed_bad = big + [-(2**31) - 1, -(2**40)]
        size_bad = [-1, 2**32, 2**40]
    for fn, ctype, ok, bad in (
        (widthmod.echo_size, "size_t", size_ok, size_bad),
        (widthmod.echo_iptr, "intptr_t", signed_ok, signed_bad),
        (widthmod.echo_pdiff, "ptrdiff_t", signed_ok, signed_bad),
    ):
        for v in ok:
            assert fn(v) == v, "%s(%d)" % (fn.__name__, v)
        for v in bad:
            msg = _expect_value_error(fn, v)
            assert "out of range for C %s v" % ctype in msg, msg


def test_check_arithmetic_overflow():
    """out.n >= rows * cols raises when rows * cols overflows instead of wrapping."""
    out = bytearray(6)
    widthmod.fill_grid(out, 2, 3)
    assert out == bytearray(b"\x01" * 6)
    msg = _expect_value_error(widthmod.fill_grid, bytearray(6), 2, 4)
    assert "out.n >= (rows * cols)" in msg, msg
    # 2**32 * 2**32 wraps to 0 in 64 bits: the check must not pass.
    msg = _expect_value_error(widthmod.fill_grid, bytearray(6), 2**32, 2**32)
    assert "integer overflow or division by zero in check: out.n >= (rows * cols)" in msg, msg


def test_map_division_by_zero():
    """data.len / k with k == 0 raises instead of trapping (SIGFPE)."""
    assert widthmod.chunk_len(bytearray(10), 2) == 5
    msg = _expect_value_error(widthmod.chunk_len, bytearray(10), 0)
    assert "integer overflow or division by zero in map: n = (data.len / k)" in msg, msg


def test_when_arithmetic_overflow():
    """An overflowing when: raises instead of picking an overload on a wrapped value."""
    assert widthmod.pick_half(bytearray(10), 11) == 1
    assert widthmod.pick_half(bytearray(10), 10) == 0
    msg = _expect_value_error(widthmod.pick_half, bytearray(10), 2**62)
    assert "integer overflow or division by zero in when: (data.len * k) > 100" in msg, msg


def test_int64_constants():
    assert widthmod.BIG == 2**40
    assert widthmod.INT64_MIN == -(2**63)
    assert widthmod.INT64_MAX == 2**63 - 1


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_"):
            _fn()
            print("PASS: %s" % _name)
