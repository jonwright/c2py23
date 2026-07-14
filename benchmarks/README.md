# Benchmarks

c2py23 wrapper overhead benchmarks comparing generated wrappers against
handwritten CPython C API extensions (the "gold standard").

## Quick start

```bash
# Build everything and run all benchmarks (single-threaded)
make bench

# Run subsets
make bench-noargs    # No-arg call overhead only
make bench-vnorm     # Vector norm (buffer protocol) only
```

## What is measured

### No-arg overhead (`test_noargs_overhead.py`)

A function taking zero arguments and returning None.  This isolates the
pure Python-to-C-to-Python crossing cost.  No buffer protocol, no
argument conversion, no checks.

10 million calls, reports nanoseconds per call.

Compares:
- `gold METH_FASTCALL` -- handwritten CPython extension using fastcall
- `gold METH_NOARGS` -- handwritten CPython extension (traditional)
- `c2py23` -- generated wrapper with timing off/on (clock/cycle counter)

### Vnorm overhead (`test_vnorm_overhead.py`)

A function taking a (N,3) double input array and writing a (N,) double
output array (vector L2 norm).  C kernel: `sqrt(x^2 + y^2 + z^2)`.

**Tiny** (N=3): pure wrapper overhead.  The C kernel runs in ~1ns, so
wall-clock time measures buffer acquisition + checks + release.

**Large** (N=4M, ~200 MB): throughput benchmark.  The C kernel dominates
(~10 ms), wrapper overhead is invisible.  Reports MB/s.

Compares:
- `gold vnorm fastcall` -- handwritten CPython using `PyObject_GetBuffer`
- `gold numpy fastcall` -- handwritten CPython using PyArray C API
- `c2py23 bare` -- generated wrapper, no checks, no timing
- `c2py23` -- generated wrapper with checks and timing combinations

## Feature cost breakdown

Each c2py23 row isolates one feature's cost:

| Feature | Cost (vs bare) | What it pays for |
|---------|---------------|------------------|
| `checks` | ~7 ns | format, ndim, shape, contiguity checks |
| `timing=clock` | +~180 ns | 4x `clock_gettime` syscalls per call |
| `timing=cycle` | +~45 ns | 4x `rdtsc` CPU instructions per call |

## Gold standard sources

- `src/gold_noargs.c` -- Handwritten METH_NOARGS + METH_FASTCALL for no-arg
- `src/gold_vnorm.c` -- Handwritten buffer-protocol vnorm wrapper
- `src/gold_numpy_vnorm.c` -- Handwritten numpy C API vnorm (no getbuffer)
- `src/tiny_kernel.c` -- The C function used by all wrappers

## Requirements

- Python 3.12+ with development headers
- numpy (for array creation and gold_numpy_vnorm)
- c2py23 installed (`pip install -e .`)
- pytest
- `taskset` (Linux) for single-core pinning
