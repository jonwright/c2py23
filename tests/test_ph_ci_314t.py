# tests/test_ph_ci_314t.py — Python 3.14t CI test for --pythonh
"""Load /tmp/fill_ph.so and call fill().  Assumes it was built by CI step."""

import sys, ctypes
import importlib.machinery, importlib.util

l = importlib.machinery.ExtensionFileLoader("fillmod", "/tmp/fill_ph.so")
s = importlib.util.spec_from_file_location("fillmod", "/tmp/fill_ph.so", loader=l)
m = importlib.util.module_from_spec(s)
l.exec_module(m)
arr = (ctypes.c_float * 4)(0, 0, 0, 0)
m.fill(arr, 42.0)
assert list(arr) == [42.0, 42.0, 42.0, 42.0], "got %s" % list(arr)
print("Python 3.14t --pythonh: PASS")
