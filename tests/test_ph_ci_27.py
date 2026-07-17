# -*- coding: utf-8 -*-
# tests/test_ph_ci_27.py — Python 2.7 CI test for --pythonh
"""Load /tmp/fill_ph.so and call fill().  Assumes it was built by CI step."""

from __future__ import print_function
import sys, ctypes, imp

m = imp.load_dynamic("fillmod", "/tmp/fill_ph.so")
arr = (ctypes.c_float * 4)(0, 0, 0, 0)
m.fill(arr, 42.0)
assert list(arr) == [42.0, 42.0, 42.0, 42.0], "got %s" % list(arr)
print("Python 2.7 --pythonh: PASS")
