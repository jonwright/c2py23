# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 20:23.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 27.5 |
| gold METH_NOARGS |   -- |     -- |     -- | 30.7 |
| c2py23 |   off |     - |     -- | 28.4 |
| c2py23 |  clock |  85.6 |  55.1 | 192.4 |
| c2py23 |  cycle |  69.7 |  46.4 | 69.8 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 112 |
| gold numpy fastcall | PyArray   |  -- |   -- | 102 |
| c2py23 bare |   -- |  no |   off | 136 |
| c2py23 checks only | getbuffer | yes |   off | 155 |
| c2py23 checks + clock | getbuffer | yes |  clock | 283 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 160 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.6 | 12700 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.6 | 12688 |
| c2py23 bare |   -- |  no |   off | 10.6 | 12720 |
| c2py23 checks only | getbuffer | yes |   off | 10.6 | 12677 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.5 | 12725 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.7 | 12600 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 135 |
| gold (numpy, pre-acquire cheat) |   off | 91 |
| gold (array.array, per-call) |   off | 104 |
| numpy arr[i] (pure Python) |   off | 109 |
| array.array arr[i] (pure Python) |   off | 99 |
| c2py23 numpy (checks + clock) | clock | 294 |
| c2py23 numpy (checks, timing off) |   off | 141 |
| c2py23 array.array (timing off) |   off | 108 |
| gold alternating |   off | 111 |
| c2py23 alternating (t=off) |   off | 116 |
| gold numpy warmup -> array |   off | 103 |
| c2py23 numpy warmup -> array |   off | 116 |
