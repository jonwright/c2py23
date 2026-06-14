# c2py23 Remaining Work

Items from docs/specification.md Future Work and C2PY23_REQUESTS.md
that are not yet implemented.

## P0: GIL release (REQ-7 from C2PY23_REQUESTS.md)

c2py23 holds the GIL during all C calls. f2py's `threadsafe` annotation
releases the GIL. For OpenMP-heavy functions, this limits parallelism.

**Approach**: Add a `threadsafe: true` key on functions or overloads.
The wrapper would call `Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS`
around the C call. Resolve `PyEval_SaveThread` / `PyEval_RestoreThread`
at runtime (both available since Python 1.x). Requires that the C function
does not touch any Python objects (already true for buffer-backed functions).

**Files**: parser.py, generator.py, c2py_runtime.h/c (add thread state macros).

## P1: SIMD dispatch

Select C functions based on CPU feature detection at module load time,
or at the wrapper level based on buffer alignment and size.

**Approach**: Run CPUID / check auxv at init, set module-level flags.
Overload `when:` conditions can check these flags. Or add a `simd:` key
that auto-generates the dispatch.

## P2: Free-threaded Python 3.14+ thread safety

When the GIL is optional (3.14 free-threaded builds), wrap critical
sections where appropriate. This is mostly about making refcounting
and buffer acquisition atomic.

## P3: Static analysis

Verify at code generation time that C function signatures match,
pointer types are consistent, and restrict constraints are satisfied.

## P4: ABI matrix

`tests/abi_matrix.json` currently has one entry (Linux-x86_64, 3.12.3).
Should be populated across all snakepit containers (debian10, ubuntu20,
ubuntu24) for all 10 Python versions using `tests/check_abi.c`.

Each entry records: sizeof(Py_buffer), field offsets, PyObject layout,
symbol availability for Py_IncRef, PyObject_Vectorcall, etc.

## P5: Arch-specific clock source

Timing currently uses `clock_gettime(CLOCK_MONOTONIC)` everywhere.
Could add `rdtsc` (x86), `CNTVCT_EL0` (ARM64), `mftb` (POWER9) as
compile-time or init-time options for lower-overhead cycle counting.

## P6: Test coverage gaps

`test_uniform.py` tests pass on 3.12.3 but have not been run against
all 10 Python versions. The snakepit test_all.py infrastructure is
in place but the containers need Apptainer available on the host.

Tests are skipped on Python 2.7 for:
- `transform` (memoryview.cast shape requires Python 3.3+)
- `types` (old buffer API has no format info, so dispatch to wrong overload)

## Completed

- ✅ Fixed-width C types (int8_t..uint64_t)
- ✅ Optional params with defaults (int/float only)
- ✅ Custom docstrings (doc: key)
- ✅ Module-level integer constants
- ✅ Format char dispatch (all single-byte PEP 3118 formats)
- ✅ METH_FASTCALL vectorcall for Python 3.12+
- ✅ Py_buffer size detection (smalltable removed in 3.12)
- ✅ Py_IncRef fallback for pre-3.12
- ✅ `or` operator in when/checks conditions
- ✅ Per-function perf timing with ctypes decode
- ✅ `__array_struct__` evaluated and removed (numpy on 2.7 works via PEP 3118)
- ✅ Buffer struct layout mismatch fixed
- ✅ -Wall -Werror clean on all generated code
- ✅ 10 Python versions in test matrix (2.7, 3.6-3.14)
