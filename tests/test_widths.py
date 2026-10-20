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


def test_int64_constants():
    assert widthmod.BIG == 2**40
    assert widthmod.INT64_MIN == -(2**63)
    assert widthmod.INT64_MAX == 2**63 - 1


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_"):
            _fn()
            print("PASS: %s" % _name)
