# Kissfft Wrap

## Interface

```yaml
module: kissfftmod
source:
  - ../kissfft/kiss_fft.c
  - ../kissfft/kiss_fftr.c
  - kissfft_thin.c
headers:
  - ../kissfft/kiss_fft.h
  - ../kissfft/kiss_fftr.h
free_threading: true

functions:
  - py_sig: "rfft_forward(data: buffer, spec: buffer) -> void"
    doc: "Real-to-complex FFT. N real floats input, (N/2+1)*2 floats output (interleaved real/imag pairs)."
    checks:
      - "data.format == 'f'"
      - "spec.format == 'f'"
      - "data.ndim == 1"
      - "spec.ndim == 1"
      - "spec.n >= data.n + 2"
    c_overloads:
      - sig: "kissfft_rfft_forward(const float *data, float *spec, int n)"
        map:
          data: "data.ptr"
          spec: "spec.ptr"
          n: "data.n"

  - py_sig: "cfft_forward(fin: buffer, fout: buffer) -> void"
    doc: "Complex-to-complex FFT. N*2 float32 input (interleaved real/imag), same-size output."
    checks:
      - "fin.format == 'f'"
      - "fout.format == 'f'"
      - "fin.ndim == 1"
      - "fout.ndim == 1"
      - "fin.n == fout.n"
      - "fin.n % 2 == 0"
    c_overloads:
      - sig: "kissfft_cfft_forward(const float *fin, float *fout, int n)"
        map:
          fin: "fin.ptr"
          fout: "fout.ptr"
          n: "fin.n / 2"```

## C Source

```c
#include <stdlib.h>
#include "../kissfft/kiss_fft.h"
#include "../kissfft/kiss_fftr.h"

void kissfft_rfft_forward(const float *data, float *spec, int n) {
    kiss_fftr_cfg cfg = kiss_fftr_alloc(n, 0, NULL, NULL);
    if (cfg) {
        kiss_fftr(cfg, data, (kiss_fft_cpx *)spec);
        free(cfg);
    }
}

void kissfft_cfft_forward(const float *fin, float *fout, int n) {
    kiss_fft_cfg cfg = kiss_fft_alloc(n, 0, NULL, NULL);
    if (cfg) {
        kiss_fft(cfg, (const kiss_fft_cpx *)fin, (kiss_fft_cpx *)fout);
        free(cfg);
    }
}```

## Build

```bash
$ c2py23 build kissfft.c2py
```

## Run

```python
"""Example: use the kissfftmod wrapper from Python.
Build with: c2py23 build kissfft.c2py"""
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
print("cfft: fout[0]=%.2f fout[1]=%.2f" % (fout[0], fout[1]))```

