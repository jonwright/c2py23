# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-11-11 07:27.
`--pythonh` is the `#include <Python.h>` path (no dlsym).  The delta
between `c2py23` and `c2py23 --pythonh` is the cost of cross-version
portability from the nimpy-style dlsym trick.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 18.8 |
| gold METH_NOARGS |   -- |     -- |     -- | 24.2 |
| c2py23 |   off |     - |     -- | 20.5 |
| c2py23 |  clock |  71.0 |  46.1 | 153.7 |
| c2py23 |  cycle |  76.4 |  50.9 | 66.3 |
| c2py23 --pythonh |   off |     - |     -- | 19.6 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

`c2py23 bare` has no user `checks:` and opts out of the derived
element-type, alignment and aliasing checks (`check_format`,
`check_alignment`, `check_aliasing` all false).  It still runs the
contiguity and shape checks implied by the `vec[][3]` signature, which
have no opt-out.  The other c2py23 rows keep every default check.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 110 |
| gold numpy fastcall | PyArray   |  -- |   -- | 95 |
| c2py23 bare |   -- |  no |   off | 45 |
| c2py23 checks only | getbuffer | yes |   off | 51 |
|   ndarray | ndarray  | yes |   off | 48 |
|   buffer | buffer   | yes |   off | 151 |
|   dlpack | dlpack   | yes |   off | 671 |
| c2py23 checks + clock | getbuffer | yes |  clock | 179 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 80 |
| c2py23 --pythonh | getbuffer | yes |   off | 49 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.0 | 13385 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.0 | 13403 |
| c2py23 bare |   -- |  no |   off | 10.1 | 13343 |
| c2py23 checks only | getbuffer | yes |   off | 10.0 | 13408 |
|   ndarray | ndarray  | yes |   off | 10.1 | 13328 |
|   buffer | buffer   | yes |   off | 10.1 | 13354 |
|   dlpack | dlpack   | yes |   off | 10.0 | 13409 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.0 | 13396 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | -- | -- |
| c2py23 --pythonh | getbuffer | yes |   off | 10.0 | 13417 |

## Getitem overhead (per-call buffer acquisition)

200,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 112 |
| gold (numpy, pre-acquire cheat) |   off | 88 |
| gold (array.array, per-call) |   off | 82 |
| numpy arr[i] (pure Python) |   off | 98 |
| array.array arr[i] (pure Python) |   off | 76 |
| c2py23 numpy (checks + clock) | clock | 214 |
| c2py23 numpy (checks, timing off) |   off | 85 |
| c2py23 array.array (timing off) |   off | 90 |
| gold alternating |   off | 97 |
| c2py23 alternating (t=off) |   off | 85 |
| gold numpy warmup -> array |   off | 87 |
| c2py23 numpy warmup -> array |   off | 92 |
