"""Example: use the kissfftmod wrapper from Python.
Build with: make"""

from __future__ import print_function

import ctypes
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kissfftmod

N = 256
# Real FFT: N real -> N/2+1 complex (stored as float pairs)
data = (ctypes.c_float * N)(*[math.sin(2 * math.pi * 7 * i / N) for i in range(N)])
spec = (ctypes.c_float * (N + 2))()  # (N/2+1)*2 floats

kissfftmod.rfft_forward(data, spec)
print("rfft: spec[0]=%.2f spec[1]=%.2f" % (spec[0], spec[1]))

# Complex FFT: N complex -> N complex
fin = (ctypes.c_float * (N * 2))(*(list(data) + [0.0] * N))
fout = (ctypes.c_float * (N * 2))()

kissfftmod.cfft_forward(fin, fout)
print("cfft: fout[0]=%.2f fout[1]=%.2f" % (fout[0], fout[1]))
