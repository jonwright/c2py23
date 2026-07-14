# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 21:19.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 22.2 |
| gold METH_NOARGS |   -- |     -- |     -- | 25.4 |
| c2py23 |   off |     - |     -- | 24.5 |
| c2py23 |  clock |  84.7 |  54.6 | 181.1 |
| c2py23 |  cycle |  69.6 |  46.3 | 71.6 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 129 |
| gold numpy fastcall | PyArray   |  -- |   -- | 120 |
| c2py23 bare |   -- |  no |   off | 164 |
| c2py23 checks only | getbuffer | yes |   off | 149 |
| c2py23 checks + clock | getbuffer | yes |  clock | 303 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 177 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.5 | 12746 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.6 | 12663 |
| c2py23 bare |   -- |  no |   off | 10.5 | 12844 |
| c2py23 checks only | getbuffer | yes |   off | 10.6 | 12641 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.6 | 12678 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.5 | 12744 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 139 |
| gold (numpy, pre-acquire cheat) |   off | 103 |
| gold (array.array, per-call) |   off | 87 |
| numpy arr[i] (pure Python) |   off | 105 |
| array.array arr[i] (pure Python) |   off | 78 |
| c2py23 numpy (checks + clock) | clock | 290 |
| c2py23 numpy (checks, timing off) |   off | 134 |
| c2py23 array.array (timing off) |   off | 96 |
| gold alternating |   off | 107 |
| c2py23 alternating (t=off) |   off | 115 |
| gold numpy warmup -> array |   off | 91 |
| c2py23 numpy warmup -> array |   off | 96 |
