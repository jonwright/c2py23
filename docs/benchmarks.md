# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 22:10.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 22.4 |
| gold METH_NOARGS |   -- |     -- |     -- | 24.4 |
| c2py23 |   off |     - |     -- | 23.0 |
| c2py23 |  clock |  87.0 |  55.8 | 190.7 |
| c2py23 |  cycle |  69.6 |  46.1 | 70.3 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 118 |
| gold numpy fastcall | PyArray   |  -- |   -- | 108 |
| c2py23 bare |   -- |  no |   off | 72 |
| c2py23 checks only | getbuffer | yes |   off | 75 |
|   ndarray | ndarray  | yes |   off | 75 |
|   buffer | buffer   | yes |   off | 162 |
|   dlpack | dlpack   | yes |   off | 381 |
| c2py23 checks + clock | getbuffer | yes |  clock | 233 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 138 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.6 | 12666 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.5 | 12730 |
| c2py23 bare |   -- |  no |   off | 10.6 | 12708 |
| c2py23 checks only | getbuffer | yes |   off | 10.6 | 12645 |
|   ndarray | ndarray  | yes |   off | 10.6 | 12690 |
|   buffer | buffer   | yes |   off | 10.6 | 12625 |
|   dlpack | dlpack   | yes |   off | 10.6 | 12701 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.6 | 12719 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.6 | 12696 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 118 |
| gold (numpy, pre-acquire cheat) |   off | 97 |
| gold (array.array, per-call) |   off | 90 |
| numpy arr[i] (pure Python) |   off | 103 |
| array.array arr[i] (pure Python) |   off | 76 |
| c2py23 numpy (checks + clock) | clock | 260 |
| c2py23 numpy (checks, timing off) |   off | 106 |
| c2py23 array.array (timing off) |   off | 104 |
| gold alternating |   off | 106 |
| c2py23 alternating (t=off) |   off | 101 |
| gold numpy warmup -> array |   off | 93 |
| c2py23 numpy warmup -> array |   off | 107 |
