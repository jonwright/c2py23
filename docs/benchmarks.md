# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 15:22.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 21.4 |
| gold METH_NOARGS |   -- |     -- |     -- | 24.8 |
| c2py23 |   off |     - |     -- | 23.5 |
| c2py23 |  clock |  85.9 |  55.4 | 186.5 |
| c2py23 |  cycle |  69.4 |  46.0 | 69.4 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 111 |
| gold numpy fastcall | PyArray   |  -- |   -- | 99 |
| c2py23 bare |   -- |  no |   off | 51 |
| c2py23 checks only | getbuffer | yes |   off | 56 |
| c2py23 checks + clock | getbuffer | yes |  clock | 208 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 91 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.5 | 12808 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.5 | 12792 |
| c2py23 bare |   -- |  no |   off | 10.5 | 12769 |
| c2py23 checks only | getbuffer | yes |   off | 10.5 | 12756 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.5 | 12789 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.5 | 12755 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (per-call acquire) |   off | 126 |
| gold (pre-acquire) |   off | 101 |
| c2py23 (checks + clock) | clock | 258 |
| c2py23 (checks, timing off) |   off | 98 |
