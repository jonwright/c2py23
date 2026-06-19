"""Example: use the lz4mod wrapper from Python.
Build with: c2py23 build lz4.c2py"""
from __future__ import print_function

import ctypes
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz4mod

data = b"Hello, World! " * 100
src = (ctypes.c_uint8 * len(data))(*bytearray(data))
dst = (ctypes.c_uint8 * len(data))()

compressed_size = lz4mod.compress(src, dst)
print("Compressed %d -> %d bytes" % (len(data), compressed_size))

out = (ctypes.c_uint8 * len(data))()
buf = (ctypes.c_uint8 * compressed_size)(*bytearray(bytes(dst[:compressed_size])))
decompressed_size = lz4mod.decompress(buf, out)
result = bytes(bytearray(out[:decompressed_size]))
print("Decompressed: %d bytes, match=%s" % (decompressed_size, result == data))
