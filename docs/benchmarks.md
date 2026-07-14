# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 20:41.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 22.4 |
| gold METH_NOARGS |   -- |     -- |     -- | 24.0 |
| c2py23 |   off |     - |     -- | 21.2 |
| c2py23 |  clock |  86.9 |  56.1 | 186.5 |
| c2py23 |  cycle |  71.3 |  46.8 | 69.8 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 117 |
| gold numpy fastcall | PyArray   |  -- |   -- | 106 |
| c2py23 bare |   -- |  no |   off | 127 |
| c2py23 checks only | getbuffer | yes |   off | 133 |
| c2py23 checks + clock | getbuffer | yes |  clock | 289 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 160 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.8 | 12459 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.7 | 12512 |
| c2py23 bare |   -- |  no |   off | 11.3 | 11827 |
| c2py23 checks only | getbuffer | yes |   off | 10.9 | 12318 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.9 | 12305 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.7 | 12569 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 123 |
| gold (numpy, pre-acquire cheat) |   off | 92 |
| gold (array.array, per-call) |   off | 88 |
| numpy arr[i] (pure Python) |   off | 103 |
| array.array arr[i] (pure Python) |   off | 79 |
| c2py23 numpy (checks + clock) | clock | 285 |
| c2py23 numpy (checks, timing off) |   off | 129 |
| c2py23 array.array (timing off) |   off | 98 |
| gold alternating |   off | 119 |
| c2py23 alternating (t=off) |   off | 120 |
| gold numpy warmup -> array |   off | 86 |
| c2py23 numpy warmup -> array |   off | 89 |
