# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 20:45.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 19.8 |
| gold METH_NOARGS |   -- |     -- |     -- | 25.4 |
| c2py23 |   off |     - |     -- | 24.8 |
| c2py23 |  clock |  85.2 |  55.0 | 181.9 |
| c2py23 |  cycle |  71.3 |  47.0 | 72.1 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 116 |
| gold numpy fastcall | PyArray   |  -- |   -- | 105 |
| c2py23 bare |   -- |  no |   off | 126 |
| c2py23 checks only | getbuffer | yes |   off | 128 |
| c2py23 checks + clock | getbuffer | yes |  clock | 285 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 155 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 11.2 | 11999 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.8 | 12483 |
| c2py23 bare |   -- |  no |   off | 10.8 | 12466 |
| c2py23 checks only | getbuffer | yes |   off | 10.7 | 12491 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.8 | 12385 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 11.4 | 11761 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 146 |
| gold (numpy, pre-acquire cheat) |   off | 103 |
| gold (array.array, per-call) |   off | 102 |
| numpy arr[i] (pure Python) |   off | 125 |
| array.array arr[i] (pure Python) |   off | 86 |
| c2py23 numpy (checks + clock) | clock | 295 |
| c2py23 numpy (checks, timing off) |   off | 130 |
| c2py23 array.array (timing off) |   off | 95 |
| gold alternating |   off | 105 |
| c2py23 alternating (t=off) |   off | 114 |
| gold numpy warmup -> array |   off | 92 |
| c2py23 numpy warmup -> array |   off | 98 |
