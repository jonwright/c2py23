# Multiprocessing

Demonstrates c2py23-wrapped C functions called across process and thread
boundaries.  Compares four parallelism approaches on Monte Carlo Pi:

1. Serial (GIL released but single thread)
2. Python threads with GIL release
3. `multiprocessing.Pool` (process-level, bypasses GIL)
4. `concurrent.futures.ProcessPoolExecutor`

All approaches call the same `mc_pi()` C function.

## Interface

```python
--8<-- "examples/mp_bench/mc_pi.c2py"
```

## C Source

```c
--8<-- "examples/mp_bench/mc_pi.c"
```

## Benchmark Script

```python
--8<-- "examples/mp_bench/bench_mp.py"
```

## Build & Run

```bash
pip install -e .                    # from repo root
cd examples/mp_bench
c2py23 mc_pi.c2py -o mcpimod_wrapper.c
python bench_mp.py
```

## How It Works

The `.c2py` declares `gil_release: true`, so the wrapper calls
`Py_BEGIN_ALLOW_THREADS`/`Py_END_ALLOW_THREADS` around the C function.
On standard Python this releases the GIL; on free-threaded builds
(`Py_GIL_DISABLED`) these are no-ops and threads already run truly
in parallel.

For multiprocessing, each worker process imports the module independently.
Because the `.so` contains no global mutable state reachable from Python
(perf counters are the only globals), it is fork-safe.  Each process gets
its own copy of all static data.

`free_threading: true` at module level declares the module safe for
Python 3.14t true parallelism -- no GIL re-enablement at module init.
