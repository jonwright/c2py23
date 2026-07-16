# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-16 21:26.
`--pythonh` is the `#include <Python.h>` path (no dlsym).  The delta
between `c2py23` and `c2py23 --pythonh` is the cost of cross-version
portability from the nimpy-style dlsym trick.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 21.6 |
| gold METH_NOARGS |   -- |     -- |     -- | 25.2 |
| c2py23 |   off |     - |     -- | 24.6 |
| c2py23 |  clock |  84.4 |  54.4 | 180.7 |
| c2py23 |  cycle |  69.6 |  46.1 | 69.1 |
| c2py23 --pythonh |   off |     - |     -- | 21.9 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 114 |
| gold numpy fastcall | PyArray   |  -- |   -- | 105 |
| c2py23 bare |   -- |  no |   off | 53 |
| c2py23 checks only | getbuffer | yes |   off | 58 |
|   ndarray | ndarray  | yes |   off | 57 |
|   buffer | buffer   | yes |   off | 133 |
|   dlpack | dlpack   | yes |   off | 349 |
| c2py23 checks + clock | getbuffer | yes |  clock | 202 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 82 |
| c2py23 --pythonh | getbuffer | yes |   off | 55 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.6 | 12685 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.5 | 12780 |
| c2py23 bare |   -- |  no |   off | 10.6 | 12713 |
| c2py23 checks only | getbuffer | yes |   off | 10.5 | 12831 |
|   ndarray | ndarray  | yes |   off | 10.5 | 12830 |
|   buffer | buffer   | yes |   off | 10.5 | 12830 |
|   dlpack | dlpack   | yes |   off | 10.6 | 12685 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.7 | 12568 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | -- | -- |
| c2py23 --pythonh | getbuffer | yes |   off | 10.5 | 12782 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 122 |
| gold (numpy, pre-acquire cheat) |   off | 94 |
| gold (array.array, per-call) |   off | 88 |
| numpy arr[i] (pure Python) |   off | 101 |
| array.array arr[i] (pure Python) |   off | 78 |
| c2py23 numpy (checks + clock) | clock | 246 |
| c2py23 numpy (checks, timing off) |   off | 92 |
| c2py23 array.array (timing off) |   off | 97 |
| gold alternating |   off | 101 |
| c2py23 alternating (t=off) |   off | 93 |
| gold numpy warmup -> array |   off | 91 |
| c2py23 numpy warmup -> array |   off | 100 |
