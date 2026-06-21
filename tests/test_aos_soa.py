"""AoS vs SoA shape dispatch demo with numpy.

Demonstrates c2py23 shape-based dispatch: the same Python function
(xfrm.transform) calls different C code depending on buffer shape.

  (N,3) -> transform_aos (array-of-structs, row-major)
  (3,N) -> transform_soa (struct-of-arrays, column-major)

Also shows the f-contiguous / c-contiguous layout distinction and
how transpose + copy converts between them.

Requires: numpy, a built transform module (xfrm.so in tests/cases/transform/)
"""
from __future__ import print_function

import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'transform'))
import xfrm


def test_aos(n=4):
    """Array-of-structs: (N,3) layout, C-contiguous by default."""
    # Each row: [x, y, z]
    arr = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
        [7.0, 8.0, 9.0],
        [10.0, 11.0, 12.0],
    ], dtype=np.float64)
    print("AoS input shape:", arr.shape)
    print("  C-contiguous:", arr.flags['C_CONTIGUOUS'])
    print("  F-contiguous:", arr.flags['F_CONTIGUOUS'])
    print("  strides:", arr.strides)

    out = np.zeros_like(arr)
    xfrm.transform(arr, out)
    print("  output:", out[:2].tolist(), "...")
    # Each element doubled
    expected = arr * 2.0
    assert np.allclose(out, expected), "AoS mismatch"
    print("  PASS: AoS transform correct\n")


def test_soa(n=4):
    """Struct-of-arrays: (3,N) layout, F-contiguous by default."""
    # Each column: [x, y, z]
    arr = np.array([
        [1.0, 4.0, 7.0, 10.0],   # all x
        [2.0, 5.0, 8.0, 11.0],   # all y
        [3.0, 6.0, 9.0, 12.0],   # all z
    ], dtype=np.float64, order='F')
    print("SoA input shape:", arr.shape)
    print("  C-contiguous:", arr.flags['C_CONTIGUOUS'])
    print("  F-contiguous:", arr.flags['F_CONTIGUOUS'])
    print("  strides:", arr.strides)

    out = np.zeros_like(arr, order='F')
    xfrm.transform(arr, out)
    print("  output:", out[:, :2].tolist(), "...")
    expected = arr * 2.0
    assert np.allclose(out, expected), "SoA mismatch"
    print("  PASS: SoA transform correct\n")


def test_layout_conversion(n=4):
    """Convert between C and F layouts using transpose + copy."""
    # Start with AoS (C-contiguous)
    aos = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ], dtype=np.float64)
    print("Layout conversion demo:")
    print("  AoS shape:", aos.shape, "C:", aos.flags['C_CONTIGUOUS'],
          "F:", aos.flags['F_CONTIGUOUS'])

    # Convert AoS -> SoA: transpose to (3,N) then copy for C layout
    soa = aos.T.copy()
    print("  SoA shape:", soa.shape, "C:", soa.flags['C_CONTIGUOUS'],
          "F:", soa.flags['F_CONTIGUOUS'])

    # Convert SoA -> AoS: transpose back then copy
    aos2 = soa.T.copy()
    print("  AoS2 shape:", aos2.shape, "C:", aos2.flags['C_CONTIGUOUS'],
          "F:", aos2.flags['F_CONTIGUOUS'])

    # Verify data preserved through round-trip
    assert np.allclose(aos, aos2), "round-trip mismatch"
    print("  PASS: transpose+copy round-trip preserves data\n")


def test_f_contiguous_dispatch(n=4):
    """An F-contiguous (N,3) array is NOT C-contiguous.
    c2py23 requires C-or-F contiguity.  The transform_aos kernel
    reads row-major, so an F-contiguous (N,3) would read wrong
    memory.  The wrapper accepts it (passes contiguity check)
    because F-contiguous is allowed -- but the C code assumes C
    layout, producing silent wrong results without a stride check.

    Solution: add a checks: guard or use contiguous: C in params.
    """
    arr = np.array([
        [1.0, 4.0],
        [2.0, 5.0],
        [3.0, 6.0],
    ], dtype=np.float64, order='F')  # (3,2) F-contiguous
    print("F-contiguous (3,2) demo:")
    print("  shape:", arr.shape)
    print("  C:", arr.flags['C_CONTIGUOUS'], "F:", arr.flags['F_CONTIGUOUS'])
    print("  strides:", arr.strides)
    print("  (passes C-or-F contiguity check)")

    out = np.zeros_like(arr, order='F')
    xfrm.transform(arr, out)
    expected = arr * 2.0
    ok = np.allclose(out, expected)
    print("  result: %s" % ("correct" if ok else "WRONG (kernel assumed C layout)"))
    # The F-contiguous SoA array IS in the right layout for transform_soa
    # because the kernel's n=shape[1] matches the fast-varying axis
    assert ok, "SoA F-contiguous should give correct results"
    print("  PASS: F-contiguous SoA dispatch correct\n")


if __name__ == '__main__':
    test_aos()
    test_soa()
    test_layout_conversion()
    test_f_contiguous_dispatch()
    print("All AoS vs SoA demos passed.")
