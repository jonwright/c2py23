# Benchmark Results

**Platform**: Linux x86_64, Python 3.12.3, GCC 13.3.0, single core (`taskset -c 0`).
All C code compiled with `-O2`.  Generated 2026-07-14 22:45.

## Vnorm wrapper overhead (tiny, N=3)

200,000 calls to `vnorm(vec, mods)` with a single 3D vector.
The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.

| wrapper | acquire | checks | timing | ns/call |
|---------|---------|--------|--------|---------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 116 |
| gold numpy fastcall | PyArray   |  -- |   -- | 104 |
| c2py23 bare |   -- |  no |   off | 70 |
| c2py23 checks only | getbuffer | yes |   off | 73 |
|   ndarray | ndarray  | yes |   off | 73 |
|   buffer | buffer   | yes |   off | 156 |
|   dlpack | dlpack   | yes |   off | -- |
| c2py23 checks + clock | getbuffer | yes |  clock | 221 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 104 |

## Vnorm throughput (large, N=4.2M, ~134 MB)

Single call, C kernel dominates (~10 ms). Throughput in MB/s.
All paths are zero-copy; wrapper overhead is constant regardless of N.

| wrapper | acquire | checks | timing | ms | MB/s |
|---------|---------|--------|--------|-----|------|
| gold vnorm fastcall | getbuffer |  -- |   -- | 10.5 | 12811 |
| gold numpy fastcall | PyArray   |  -- |   -- | 10.5 | 12725 |
| c2py23 bare |   -- |  no |   off | 10.6 | 12688 |
| c2py23 checks only | getbuffer | yes |   off | 10.6 | 12686 |
|   ndarray | ndarray  | yes |   off | 10.6 | 12653 |
|   buffer | buffer   | yes |   off | 10.6 | 12680 |
|   dlpack | dlpack   | yes |   off | -- | -- |
| c2py23 checks + clock | getbuffer | yes |  clock | 10.5 | 12728 |
| c2py23 checks + cycle | getbuffer | yes |  cycle | 10.5 | 12725 |
