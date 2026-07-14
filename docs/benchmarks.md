# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 14:27.

## No-arg call overhead

10,000,000 calls to a function taking zero arguments and returning `None`.
This isolates the pure Python-to-C-to-Python crossing cost.

| wrapper | timing | c kernel | wrapper | ns/call |
|---------|--------|----------|---------|---------|
| gold METH_FASTCALL |   -- |     -- |     -- | 21.2 |
| gold METH_NOARGS |   -- |     -- |     -- | 25.0 |
| c2py23 |   off |     - |     -- | 27.0 |
| c2py23 |  clock |  85.1 |  55.0 | 184.3 |
| c2py23 |  cycle |  69.4 |  46.1 | 69.4 |

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 115 |
| gold numpy fastcall | PyArray   |  -- |   -- | 102 |
| c2py23 bare |   -- |  no |   off | 121 |
| c2py23 checks only | getbuffer | yes |   off | 125 |
| c2py23 checks + clock | getbuffer | yes |  clock | 274 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 148 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.5 | 12812 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.7 | 12559 |
| c2py23 bare |   -- |  no |   off | 10.5 | 12756 |
| c2py23 checks only | getbuffer | yes |   off | 10.5 | 12832 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.4 | 12852 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.5 | 12788 |

## Getitem overhead (per-call buffer acquisition)

500,000 calls extracting one element from a double buffer and returning
it as a Python float.  Each call acquires the buffer, reads one element,
constructs a Python float, and releases the buffer.

| wrapper | timing | ns/call |
|---------|--------|---------|
| gold (per-call acquire) |   off | 112 |
| gold (pre-acquire) |   off | 95 |
| c2py23 (checks + clock) | clock | 264 |
| c2py23 (checks, timing off) |   off | 122 |
