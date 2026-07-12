# Threading Benchmark

Monte Carlo Pi estimation benchmark demonstrating GIL release (serial) and
OpenMP parallelism.  Declares `free_threading: true` for Python 3.14t.

## Interface

```yaml
--8<-- "examples/threading_bench/mc_pi.c2py"
```

## Build & Run

```bash
cd examples/threading_bench
pip install -e ../..

# Serial build (default)
make serial
python bench_mc_pi.py

# OpenMP build
make omp
python bench_mc_pi.py
```

## Key Design Decisions

- `gil_release: true` on `mc_pi` -- releases the GIL during C computation,
  allowing other Python threads to run
- `mc_pi_omp` uses OpenMP `#pragma omp parallel for` for multi-core scaling
- `free_threading: true` at module level declares this module safe for
  Python 3.14t true parallelism
- Default seed value (`seed: int = 0`) allows optional deterministic runs
