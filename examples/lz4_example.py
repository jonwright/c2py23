"""Example usage of lz4mod -- LZ4 compression via c2py23.

Build the module first:
    c2py23 build examples/lz4.c2py

Then run this script from the project root:
    python3 examples/lz4_example.py
"""
from __future__ import print_function

import ctypes
import sys

sys.path.insert(0, '.')
import lz4mod


def test_compress_decompress():
    data = b"Hello, c2py23! This is a test of LZ4 compression via c2py23 buffers."
    n = len(data)

    src = (ctypes.c_uint8 * n)(*data)
    max_dst = n + 256
    dst = (ctypes.c_uint8 * max_dst)(0)

    compressed_size = lz4mod.compress(src, dst)
    if compressed_size <= 0:
        print("Compression failed: %d" % compressed_size)
        return

    print("Original: %d bytes -> Compressed: %d bytes (%.1f%%)" % (
        n, compressed_size, 100.0 * compressed_size / n))

    compressed = (ctypes.c_uint8 * compressed_size)(*dst[:compressed_size])
    decompressed = (ctypes.c_uint8 * n)(0)
    result = lz4mod.decompress(compressed, decompressed)

    if result < 0:
        print("Decompression failed: %d" % result)
        return

    result_bytes = bytes(decompressed[:result])
    print("Decompressed: %d bytes" % result)
    print("Content: %s" % result_bytes.decode('ascii'))
    print("Match: %s" % (result_bytes == data))


if __name__ == '__main__':
    test_compress_decompress()
