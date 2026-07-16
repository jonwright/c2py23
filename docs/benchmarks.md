# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-16 19:08.
`--pythonh` is the `#include <Python.h>` path (no dlsym).  The delta
between `c2py23` and `c2py23 --pythonh` is the cost of cross-version
portability from the nimpy-style dlsym trick.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 23.7 |
| gold METH_NOARGS |   -- |     -- |     -- | 24.0 |
| c2py23 |   off |     - |     -- | 22.1 |
| c2py23 |  clock |  85.0 |  54.7 | 182.8 |
| c2py23 |  cycle |  69.4 |  46.0 | 69.1 |
| c2py23 --pythonh |   off |     - |     -- | 21.1 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 117 |
| gold numpy fastcall | PyArray   |  -- |   -- | 105 |
| c2py23 bare |   -- |  no |   off | 52 |
| c2py23 checks only | getbuffer | yes |   off | 58 |
|   ndarray | ndarray  | yes |   off | 57 |
|   buffer | buffer   | yes |   off | 132 |
|   dlpack | dlpack   | yes |   off | 364 |
| c2py23 checks + clock | getbuffer | yes |  clock | 203 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 84 |
| c2py23 --pythonh | getbuffer | yes |   off | 55 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.5 | 12834 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.5 | 12822 |
| c2py23 bare |   -- |  no |   off | 10.5 | 12783 |
| c2py23 checks only | getbuffer | yes |   off | 10.5 | 12742 |
|   ndarray | ndarray  | yes |   off | 10.5 | 12798 |
|   buffer | buffer   | yes |   off | 10.5 | 12820 |
|   dlpack | dlpack   | yes |   off | 10.5 | 12789 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.6 | 12682 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | -- | -- |
| c2py23 --pythonh | getbuffer | yes |   off | 10.6 | 12703 |
