"""Test kissfft_wrap and lz4_wrap example modules.

These are run by pytest.  The conftest.py fixture builds the .so files
before any tests run.
"""
from __future__ import print_function

import ctypes
import sys
import os
import math


def test_kissfft_wrap():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                     "..", "examples", "kissfft_wrap"))
    import kissfftmod

    N = 256
    data = (ctypes.c_float * N)(
        *[math.sin(2 * math.pi * 7 * i / N) for i in range(N)])
    spec = (ctypes.c_float * (N + 2))()

    kissfftmod.rfft_forward(data, spec)
    assert abs(spec[0]) < 0.01, "rfft DC bin should be near zero"
    assert abs(spec[1]) < 0.01, "rfft nyquist bin should be near zero"

    fin = (ctypes.c_float * (N * 2))(*list(data) + [0.0] * N)
    fout = (ctypes.c_float * (N * 2))()
    kissfftmod.cfft_forward(fin, fout)
    assert abs(fout[0]) < 0.01, "cfft[0] should be near zero"


def test_lz4_wrap():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                     "..", "examples", "lz4_wrap"))
    import lz4mod

    IS_PY2 = sys.version_info[0] < 3
    data = b"Hello, World! " * 100
    src = (ctypes.c_uint8 * len(data))(*bytearray(data))
    dst = (ctypes.c_uint8 * len(data))()

    compressed_size = lz4mod.compress(src, dst)
    assert compressed_size > 0, "compress should produce output"
    assert compressed_size < len(data), "should compress"

    out = (ctypes.c_uint8 * len(data))()
    buf_slice = dst[:compressed_size]
    buf = (ctypes.c_uint8 * compressed_size)(
        *buf_slice if not IS_PY2 else [buf_slice[i] for i in range(compressed_size)])
    decompressed_size = lz4mod.decompress(buf, out)
    assert decompressed_size == len(data), "decompressed size mismatch"

    if IS_PY2:
        result = str(bytearray(out[:decompressed_size]))
    else:
        result = bytes(out[:decompressed_size])
    assert result == data, "decompressed data mismatch"
