# Lz4 Wrap

## Interface

```python
# Python dict format equivalent of lz4.c2py
{
    "module": "lz4mod",
    "source": [
        "../lz4/lib/lz4.c",
        "lz4_thin.c",
    ],
    "headers": ["../lz4/lib/lz4.h"],
    "functions": [
        {
            "py_sig": "compress(src: buffer, dst: buffer) -> int",
            "checks": [
                "src.format == 'B'",
                "dst.format == 'B'",
                "src.ndim == 1",
                "dst.ndim == 1",
            ],
            "c_overloads": [
                {
                    "sig": "int lz4_compress(const uint8_t *src, uint8_t *dst, int srcSize, int dstCapacity)",
                    "map": {
                        "src": "src.ptr",
                        "dst": "dst.ptr",
                        "srcSize": "src.len",
                        "dstCapacity": "dst.len",
                    },
                },
            ],
        },
        {
            "py_sig": "decompress(src: buffer, dst: buffer) -> int",
            "checks": [
                "src.format == 'B'",
                "dst.format == 'B'",
                "src.ndim == 1",
                "dst.ndim == 1",
            ],
            "c_overloads": [
                {
                    "sig": "int lz4_decompress(const uint8_t *src, uint8_t *dst, int compressedSize, int dstCapacity)",
                    "map": {
                        "src": "src.ptr",
                        "dst": "dst.ptr",
                        "compressedSize": "src.len",
                        "dstCapacity": "dst.len",
                    },
                },
            ],
        },
    ],
}
```

## C Source

```c
#include <stdint.h>
#include "../lz4/lib/lz4.h"

int lz4_compress(const uint8_t *src, uint8_t *dst, int srcSize, int dstCapacity) {
    return LZ4_compress_default((const char *)src, (char *)dst, srcSize, dstCapacity);
}

int lz4_decompress(const uint8_t *src, uint8_t *dst, int compressedSize, int dstCapacity) {
    return LZ4_decompress_safe((const char *)src, (char *)dst, compressedSize, dstCapacity);
}
```

## Build

```bash
$ c2py23 lz4.c2py -o lz4mod_wrapper.c
```


Compile:

```bash
$ cc -shared -fPIC c2py23/runtime/c2py_runtime.c lz4mod_wrapper.c lz4_thin.c -I c2py23/runtime -o lz4mod.so -ldl -lm
```

See [docs/building](building) for cmake, meson, and setuptools options.

## Run

```python
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
```

