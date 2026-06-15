# c2py23 Remaining Work

## Not Yet Implemented

### P1: SIMD dispatch / CPU feature detection

**Severity: High** -- Phase 3 blocker for ImageD11

Select C functions based on CPU feature detection at module load time.
Support `when: "cpu_has_avx2"`, `when: "cpu_has_avx512f"`, `when: "cpu_has_neon"`.
The condition is evaluated once at module init, not per call.

Parser: accept cpu_has_* identifiers in when: conditions.
Generator: emit a static int flag per feature, set once from CPUID/MRS.
Runtime: add CPUID helper to c2py_runtime.c (__get_cpuid on x86, /proc/cpuinfo,
mrs on ARM64).

**Files**: parser.py, generator.py, c2py_runtime.h/c.

---

### P2: GIL release / threadsafe mode

**Severity: High** -- for OpenMP-heavy functions (ImageD11 uses OpenMP)

Add a `threadsafe: true` key on functions or overloads. The wrapper calls
`PyEval_SaveThread` / `PyEval_RestoreThread` around the C call so OpenMP
threads don't contend on the GIL.

**Files**: parser.py, generator.py, c2py_runtime.h/c.

---

### P3: Free-threaded Python 3.14+ thread safety

**Severity: Medium** (future-facing)

When the GIL is optional (3.14 free-threaded builds), wrap critical sections
for atomic refcounting and buffer acquisition.

**Files**: c2py_runtime.h/c, generator.py.

---

### P4: Comprehensive dispatch-over-all-types example

**Severity: Medium** -- documentation gap

Add a test case and specification example showing `when:` dispatch over all
10 PEP 3118 format characters (b, B, h, H, i, I, q, Q, f, d) mapping to
the 10 C fixed-width types (int8_t..uint64_t, float, double). The existing
`types` test covers only 5 formats and `fill`/`dot` cover f/d separately.
A single comprehensive example fills the documentation gap for new users.

**Files**: tests/cases/typedispatch/, tests/test_uniform.py,
docs/specification.md.

---

### P5: Binary wheel distribution

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
- P2: YAML type coercion -- auto-coerce bare int/float in map/when/checks
- P3: Better check failure messages -- include actual runtime values
- P4: Buffer format vs C type compile-time validation -- raises ValueError
- P6: Output scalar convention -- `outputs:` key, auto-alloc, tuple return
- P8: Valgrind/ASan validation -- stress test, cleanup audit, `--asan` flag
- P9: Template expansion -- `expand:` key with `${VAR}` substitution
- P10: ABI matrix populated across all 10 Python versions
- P11: Arch-specific clocks -- rdtsc (x86), CNTVCT_EL0 (ARM64), mftb (POWER)
- P12: Test coverage -- 10 versions x 11 tests passing
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
