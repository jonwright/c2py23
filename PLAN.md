# c2py23 Remaining Work

## Not Yet Implemented

### P1: SIMD dispatch / CPU feature detection

**Severity: High** -- Phase 3 blocker for ImageD11

Select C functions based on CPU feature detection at module load time.
Support `when: "cpu_has_avx2"`, `when: "cpu_has_avx512f"`, `when: "cpu_has_neon"`.
The condition is evaluated once at module init, not per call.

**NEEDS DESIGN DISCUSSION** -- see AGENTS.md for open questions about which
architectures to support, how CPUID/MRS detection should work, and the grammar
for `cpu_has_*` conditions.

Parser: accept cpu_has_* identifiers in when: conditions.
Generator: emit a static int flag per feature, set once from CPUID/MRS.
Runtime: add CPUID helper to c2py_runtime.c (__get_cpuid on x86, /proc/cpuinfo,
mrs on ARM64).

**Files**: parser.py, generator.py, c2py_runtime.h/c.

---

### P2: GIL release via `gil_release: true`

**Severity: High** -- enables true Python-thread parallelism

Add a `gil_release: true` key on functions or per-overload. The wrapper calls
`PyEval_SaveThread` before the C call and `PyEval_RestoreThread` after.

**Safety model -- buffer references, not content locks:**

The wrapper acquires `Py_buffer` structs during argument parsing, before
releasing the GIL. These references keep the underlying Python objects alive
so memory cannot be freed. However, a second Python thread that also holds a
buffer reference to the same object can still write to it. This is the caller's
responsibility, not c2py23's. The philosophy is that a real programmer knows
what they are doing: you tag a function `gil_release: true` if you know the
C code can tolerate concurrent buffer mutation from other Python threads.

**OpenMP is about oversubscription, not correctness:**

OpenMP threads within a single call are safe regardless of GIL state -- the
GIL only serializes Python threads. The concern is oversubscription: if N
Python threads each launch an M-way OpenMP call, N*M threads compete for
cores. The user may choose NOT to release the GIL specifically to prevent
this. The decision depends on the workload.

**Global toggle:**

A module-level runtime flag `_c2py_gil_release_enabled` (similar to the timing
`_c2py_timing_enabled` flag) lets callers globally disable GIL release across
all functions. This allows the same `.so` to work in both serial and parallel
contexts without recompilation. Per-function `get_gil_release` / `set_gil_release`
methods on each Python function object expose the individual toggle.

**Free-threading (P3):** On 3.14+ free-threaded builds the GIL is absent.
The `gil_release` flag becomes a no-op, but the buffer-acquisition path needs
atomic refcounting. See P3 below.

**Files**: parser.py, generator.py, c2py_runtime.h/c.
**Design doc**: docs/specification.md `## GIL Release and Thread Safety`.

---

### P3: Free-threaded Python 3.14+ thread safety

**Severity: Medium** (future-facing)

When the GIL is optional (3.14 free-threaded builds), wrap critical sections
for atomic refcounting and buffer acquisition.

**Files**: c2py_runtime.h/c, generator.py.

---

### P4: Binary wheel distribution

**Severity: Low** -- replaces --no-build-isolation workflow

Publish binary wheels to PyPI: one per platform (linux, windows, macos) and
one per architecture (x86_64, aarch64). Python-version-independent (the .so
works on 2.7-3.14 via nimpy trick). Similar to ctypes-style distribution --
install via pip, import from any Python version. May need a wrapper import
mechanism or `ctypes.CDLL` loader bootstrap.

**Status: DEFERRED** -- design TBD, implement later.

---

## Completed

- P0: Parameter count validation -- raises ValueError on sig mismatch
- P2: GIL release (`gil_release: true`) -- global toggle, per-function enable, tested
- YAML type coercion -- auto-coerce bare int/float in map/when/checks
- Better check failure messages -- include actual runtime values
- Buffer format vs C type compile-time validation -- raises ValueError
- Output scalar convention -- `outputs:` key, auto-alloc, tuple return
- Template expansion -- `expand:` key with `${VAR}` substitution
- Comprehensive dispatch-over-all-types example -- typedispatch test case, Example 4 in spec
- Valgrind/ASan validation -- stress test, cleanup audit, `--asan` flag
- Test coverage -- 10 versions x 13 uniform tests, 10 peer review tests
- GIL release design rationale -- documented in specification.md
- ABI matrix populated across all 10 Python versions
- Arch-specific clocks -- rdtsc (x86), CNTVCT_EL0 (ARM64), mftb (POWER)
- int64_t/uint64_t 32-bit fix -- PyLong_FromLongLong macro
- Py_buffer size fix -- 80 bytes for 3.x, 96 for 2.x (ABI matrix)
- Fixed-width C types (int8_t..uint64_t)
- Optional params with defaults (int/float only)
- Custom docstrings (`doc:` key)
- Module-level integer constants
- Format char dispatch (all single-byte PEP 3118 formats)
- METH_FASTCALL vectorcall for Python 3.11+
- Py_buffer size detection (dynamic, version-based)
- Py_IncRef fallback for pre-3.12 (manual refcount incr)
- `or` operator in when/checks conditions
- Per-function perf timing with ctypes decode
- `__array_struct__` evaluated and removed
- Buffer struct layout mismatch fixed
- `-Wall -Werror` clean on all generated code
- 10 Python versions in test matrix (2.7, 3.6-3.14)
- Contiguity check: rejects strided arrays, negative strides, accepts C/F-contiguous
- Alias detection: rejects buffer aliasing between writable buffers (5 patterns)
- Shared-refcount fix: PyExc_* always dereferenced once (handles pre-3.12 heap-type pointers and 3.12+ static shared-refcount)
- Debug build support: `--asan` flag, `CC`/`CFLAGS`/`LDFLAGS` env vars, `gcc -shared -g -O0`
