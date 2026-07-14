# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 21:51.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 24.0 |
| gold METH_NOARGS |   -- |     -- |     -- | 22.7 |
| c2py23 |   off |     - |     -- | 21.4 |
| c2py23 |  clock |  85.5 |  55.1 | 184.7 |
| c2py23 |  cycle |  69.9 |  46.5 | 73.3 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 141 |
| gold numpy fastcall | PyArray   |  -- |   -- | 132 |
| c2py23 bare |   -- |  no |   off | 70 |
| c2py23 checks only | getbuffer | yes |   off | 75 |
| c2py23 checks + clock | getbuffer | yes |  clock | 233 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 110 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.7 | 12602 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.7 | 12508 |
| c2py23 bare |   -- |  no |   off | 10.5 | 12752 |
| c2py23 checks only | getbuffer | yes |   off | 10.6 | 12641 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.7 | 12550 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.6 | 12685 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (numpy, per-call acquire) |   off | 174 |
| gold (numpy, pre-acquire cheat) |   off | 127 |
| gold (array.array, per-call) |   off | 125 |
| numpy arr[i] (pure Python) |   off | 153 |
| array.array arr[i] (pure Python) |   off | 89 |
| c2py23 numpy (checks + clock) | clock | 270 |
| c2py23 numpy (checks, timing off) |   off | 105 |
| c2py23 array.array (timing off) |   off | 107 |
| gold alternating |   off | 105 |
| c2py23 alternating (t=off) |   off | 121 |
| gold numpy warmup -> array |   off | 95 |
| c2py23 numpy warmup -> array |   off | 104 |
