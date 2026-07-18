"""Example: use the lz4mod wrapper from Python.
Build with: make"""

from __future__ import print_function

import ctypes
import sys
import os

IS_PY2 = sys.version_info[0] < 3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz4mod

data = b"Hello, World! " * 100
src = (ctypes.c_uint8 * len(data))(*bytearray(data))
dst = (ctypes.c_uint8 * len(data))()

compressed_size = lz4mod.compress(src, dst)
print("Compressed %d -> %d bytes" % (len(data), compressed_size))

out = (ctypes.c_uint8 * len(data))()
# ctypes array slice returns a list of ints on both Python 2 and 3
buf = (ctypes.c_uint8 * compressed_size)(*dst[:compressed_size])
decompressed_size = lz4mod.decompress(buf, out)
if IS_PY2:
    result = str(bytearray(out[:decompressed_size]))
else:
    result = bytes(out[:decompressed_size])
print("Decompressed: %d bytes, match=%s" % (decompressed_size, result == data))
