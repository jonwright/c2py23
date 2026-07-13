# Threading Benchmark

Monte Carlo Pi estimation benchmark demonstrating GIL release and OpenMP
parallelism.  Declares `free_threading: true` for Python 3.14t.

--8<-- "examples/threading_bench/README.md"

## How It Works

`mc_pi` releases the GIL (`gil_release: true`) during C computation,
allowing other Python threads to run.  The C function generates random
points in a unit square and counts how many fall inside the unit circle.

`mc_pi_omp` uses OpenMP `#pragma omp parallel for` for multi-core scaling.
It is built with `-fopenmp` and linked against `libgomp`.

Both functions take an optional seed for deterministic runs (`seed: int = 0`).

`free_threading: true` at module level declares this module safe for
Python 3.14t true parallelism (no GIL re-enablement).
