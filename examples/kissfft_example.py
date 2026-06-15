"""Example usage of kissfftmod -- real and complex FFT via c2py23.

Build the module first:
    c2py23 build examples/kissfft.c2py

Then run this script from the project root:
    python3 examples/kissfft_example.py
"""
from __future__ import print_function

import ctypes
import math
import sys

sys.path.insert(0, '.')
import kissfftmod


def test_rfft():
    """Real FFT: n real samples -> n/2+1 complex values (n+2 floats)."""
    n = 64
    data_in = (ctypes.c_float * n)(*(
        math.sin(2 * math.pi * 7 * i / n) for i in range(n)
    ))
    spec_out = (ctypes.c_float * (n + 2))(0.0)

    kissfftmod.rfft_forward(data_in, spec_out)

    print("Real FFT of sin(2*pi*7*t/N), N=%d:" % n)
    for k in range(min(10, (n // 2) + 1)):
        re = spec_out[2 * k]
        im = spec_out[2 * k + 1]
        mag = math.sqrt(re * re + im * im)
        print("  bin %2d: %8.4f + %8.4fi  |mag|=%6.4f" % (k, re, im, mag))


def test_cfft():
    """Complex FFT: n complex values (2*n floats interleaved)."""
    n = 32
    c_in = (ctypes.c_float * (2 * n))(0.0)
    c_out = (ctypes.c_float * (2 * n))(0.0)

    for i in range(n):
        c_in[2 * i] = math.sin(2 * math.pi * 3 * i / n)

    kissfftmod.cfft_forward(c_in, c_out)

    print("\nComplex FFT of sin(2*pi*3*t/N), N=%d:" % n)
    for k in range(min(10, n)):
        re = c_out[2 * k]
        im = c_out[2 * k + 1]
        mag = math.sqrt(re * re + im * im)
        print("  bin %2d: %8.4f + %8.4fi  |mag|=%6.4f" % (k, re, im, mag))


if __name__ == '__main__':
    test_rfft()
    test_cfft()
