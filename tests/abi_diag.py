"""ABI diagnostic: print platform sizes and ctypes buffer format chars.
Runs without any dependencies -- just the Python stdlib.
Useful for debugging format-dispatch failures on CI.
"""
from __future__ import print_function

import sys
import struct
import ctypes

print("platform: {}".format(sys.platform))
print("sizeof(void*): {}".format(struct.calcsize('P')))
print("sizeof(long): {}".format(struct.calcsize('l')))
print("sizeof(long long): {}".format(struct.calcsize('q')))
print()

print("=== ctypes buffer format chars ===")
for name in ['c_int8', 'c_uint8', 'c_int16', 'c_uint16',
             'c_int32', 'c_uint32', 'c_int64', 'c_uint64',
             'c_float', 'c_double', 'c_long', 'c_ulong']:
    typ = getattr(ctypes, name, None)
    if typ is None:
        continue
    arr = (typ * 2)()
    mv = memoryview(arr)
    print("  {:12s}  format={:6s}  itemsize={}".format(
        name, repr(mv.format), mv.itemsize))
