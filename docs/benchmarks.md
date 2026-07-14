# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 21:14.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 23.2 |
| gold METH_NOARGS |   -- |     -- |     -- | 26.6 |
| c2py23 |   off |     - |     -- | 24.2 |
| c2py23 |  clock |  84.6 |  54.5 | 180.4 |
| c2py23 |  cycle |  70.1 |  46.7 | 71.1 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 154 |
| gold numpy fastcall | PyArray   |  -- |   -- | 132 |
| c2py23 bare |   -- |  no |   off | 122 |
| c2py23 checks only | getbuffer | yes |   off | 128 |
| c2py23 checks + clock | getbuffer | yes |  clock | 283 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 154 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.6 | 12668 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.5 | 12753 |
| c2py23 bare |   -- |  no |   off | 10.6 | 12705 |
| c2py23 checks only | getbuffer | yes |   off | 10.5 | 12733 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.6 | 12719 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.6 | 12699 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 122 |
| gold (numpy, pre-acquire cheat) |   off | 94 |
| gold (array.array, per-call) |   off | 85 |
| numpy arr[i] (pure Python) |   off | 100 |
| array.array arr[i] (pure Python) |   off | 76 |
| c2py23 numpy (checks + clock) | clock | 277 |
| c2py23 numpy (checks, timing off) |   off | 126 |
| c2py23 array.array (timing off) |   off | 93 |
| gold alternating |   off | 101 |
| c2py23 alternating (t=off) |   off | 114 |
| gold numpy warmup -> array |   off | 89 |
| c2py23 numpy warmup -> array |   off | 93 |
