# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 22:23.

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 123 |
| gold numpy fastcall | PyArray   |  -- |   -- | 107 |
| c2py23 bare |   -- |  no |   off | 76 |
| c2py23 checks only | getbuffer | yes |   off | 74 |
|   ndarray | ndarray  | yes |   off | 72 |
|   buffer | buffer   | yes |   off | 158 |
|   dlpack | dlpack   | yes |   off | 385 |
| c2py23 checks + clock | getbuffer | yes |  clock | 226 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 105 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 11.6 | 11532 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.6 | 12648 |
| c2py23 bare |   -- |  no |   off | 10.5 | 12812 |
| c2py23 checks only | getbuffer | yes |   off | 10.5 | 12771 |
|   ndarray | ndarray  | yes |   off | 10.5 | 12793 |
|   buffer | buffer   | yes |   off | 10.5 | 12803 |
|   dlpack | dlpack   | yes |   off | 10.5 | 12775 |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.5 | 12836 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.5 | 12760 |
