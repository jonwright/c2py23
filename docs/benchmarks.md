# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 21:43.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 24.7 |
| gold METH_NOARGS |   -- |     -- |     -- | 26.1 |
| c2py23 |   off |     - |     -- | 23.8 |
| c2py23 |  clock |  85.2 |  55.0 | 182.6 |
| c2py23 |  cycle |  69.5 |  46.3 | 71.0 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 117 |
| gold numpy fastcall | PyArray   |  -- |   -- | 113 |
| c2py23 bare |   -- |  no |   off | 53 |
| c2py23 checks only | getbuffer | yes |   off | 56 |
| c2py23 checks + clock | getbuffer | yes |  clock | 214 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 89 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.5 | 12732 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.4 | 12863 |
| c2py23 bare |   -- |  no |   off | 10.5 | 12826 |
| c2py23 checks only | getbuffer | yes |   off | 10.4 | 12856 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.4 | 12887 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.4 | 12880 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 133 |
| gold (numpy, pre-acquire cheat) |   off | 97 |
| gold (array.array, per-call) |   off | 89 |
| numpy arr[i] (pure Python) |   off | 106 |
| array.array arr[i] (pure Python) |   off | 84 |
| c2py23 numpy (checks + clock) | clock | 270 |
| c2py23 numpy (checks, timing off) |   off | 109 |
| c2py23 array.array (timing off) |   off | 116 |
| gold alternating |   off | 126 |
| c2py23 alternating (t=off) |   off | 116 |
| gold numpy warmup -> array |   off | 106 |
| c2py23 numpy warmup -> array |   off | 98 |
