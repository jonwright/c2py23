# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 21:59.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 21.7 |
| gold METH_NOARGS |   -- |     -- |     -- | 23.5 |
| c2py23 |   off |     - |     -- | 22.1 |
| c2py23 |  clock |  88.0 |  56.6 | 187.9 |
| c2py23 |  cycle |  71.6 |  47.1 | 72.4 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 120 |
| gold numpy fastcall | PyArray   |  -- |   -- | 123 |
| c2py23 bare |   -- |  no |   off | 53 |
| c2py23 checks only | getbuffer | yes |   off | 63 |
| c2py23 checks + clock | getbuffer | yes |  clock | 229 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 94 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.7 | 12497 |
| gold numpy fastcall | PyArray   |  -- |   -- | 11.0 | 12243 |
| c2py23 bare |   -- |  no |   off | 11.0 | 12236 |
| c2py23 checks only | getbuffer | yes |   off | 11.0 | 12241 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.8 | 12448 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 11.0 | 12192 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 144 |
| gold (numpy, pre-acquire cheat) |   off | 93 |
| gold (array.array, per-call) |   off | 100 |
| numpy arr[i] (pure Python) |   off | 122 |
| array.array arr[i] (pure Python) |   off | 92 |
| c2py23 numpy (checks + clock) | clock | 284 |
| c2py23 numpy (checks, timing off) |   off | 122 |
| c2py23 array.array (timing off) |   off | 125 |
| gold alternating |   off | 134 |
| c2py23 alternating (t=off) |   off | 111 |
| gold numpy warmup -> array |   off | 118 |
| c2py23 numpy warmup -> array |   off | 125 |
