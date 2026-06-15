# c2py23 Remaining Work

Items from c2py23_requests.md, docs/specification.md Future Work,
and additional safety items not yet implemented.

---

## P0: Parameter count validation (Request #1)

**Severity: Critical** -- caused real CI failure (bloboverlaps on Python 3.11)

The .c2py C signature and the actual C function declaration can diverge silently.
`bloboverlaps` had 9 params but the .c2py C sig had 8, producing UB at runtime.

**Approach**: Parse the C header/source to get actual parameter counts. Compare
against the .c2py C sig at codegen time. Emit a hard error on mismatch.

**Files**: parser.py (C header parser), generator.py (validation pass).

---

## P1: GIL release / threadsafe mode

**Severity: High** -- for OpenMP-heavy functions

c2py23 holds the GIL during all C calls, limiting parallelism. Add a
`threadsafe: true` key on functions or overloads. The wrapper calls
`PyEval_SaveThread` / `PyEval_RestoreThread` around the C call. Requires
that the C function does not touch any Python objects (already true for
buffer-backed functions).

**Files**: parser.py, generator.py, c2py_runtime.h/c (add thread state macros).

---

## P2: YAML type coercion -- int/float vs string in map/when/checks (Request #4, expanded)

**Severity: High** -- parser crashes on bare integers

YAML parses bare integers as Python `int`, but the expression parser expects
strings. Map values like `verbose: 0` crash at parser.py:475 with:
  TypeError: object of type 'int' has no len()

The workaround (`verbose: "0"`) is surprising.

**Approach**: In `_parse_func`, coerce non-string map values to strings before
calling `parse_expr()`. Do the same for `when:` conditions and `checks:` list
items. Print a clear deprecation-style warning ("auto-coerced int 0 to '0' --
quote your YAML values to avoid ambiguity") so users learn the idiom.

**Files**: parser.py (type coercion in `_parse_func` and `load_c2py`).

---

## P3: Better check failure messages (Request #5)

**Severity: Medium**

Current error: `ValueError: check failed: labels1.format == 'i'`
Doesn't tell the user the actual format found.

**Approach**: Generate check code that captures the runtime value and includes it:
  ValueError: check failed: labels1.format == 'i' (got 'l')

**Files**: generator.py (`_emit_check` -- split LHS/RHS, emit got-value code).

---

## P4: Buffer format vs C type compile-time validation (Request #2)

**Severity: High** -- portability risk

Runtime checks like `labels1.format == 'i'` may map to `int32_t*` in one place
and `int*` in another. No compile-time warning when they disagree.

**Approach**: Map PEP 3118 format chars to expected C types. Warn if the C
function prototype uses a different-width type (e.g. `int32_t*` vs `int*`).

**Files**: generator.py (new validation pass), parser.py (format-to-ctype map).

---

## P5: SIMD dispatch / CPU feature detection (Request #7)

**Severity: Medium**  (Phase 3 blocker per original PLAN.md)

Select C functions based on CPU feature detection at module load time.
Overload `when:` conditions check CPU flags.

**Approach**: Run CPUID / check auxv at init, set module-level flags.
Support `when: "cpu_has_avx2"`, `when: "cpu_has_avx512"`, etc.

**Files**: parser.py, generator.py, c2py_runtime.c (CPUID helpers).

---

## P6: Output scalar convention option (Request #6)

**Severity: Low** -- useful for f2py migration

Option to annotate `intent(out)` scalar parameters so c2py23 auto-allocates
1-element buffers and returns them as Python tuple values, matching f2py's
behavior. Reduces test boilerplate from ~20 lines per function.

**Files**: parser.py (new annotation), generator.py (auto-alloc code).

---

## P7: Free-threaded Python 3.14+ thread safety

**Severity: Medium** (future-facing)

When the GIL is optional (3.14 free-threaded builds), wrap critical sections
for atomic refcounting and buffer acquisition.

**Files**: c2py_runtime.h/c, generator.py.

---

## P8: Valgrind/ASan memory validation for wrappers

**Severity: Medium** -- proactive leak detection

Generated wrappers acquire `Py_buffer` structs via `c2py_acquire_buffer()` and
must release them via `PyBuffer_Release` on every code path, including error
returns. A leak in an error path would accumulate over repeated calls.

**Approach**:
1. Add a stress test that calls each wrapped function in a tight loop and
   checks RSS growth via `/proc/self/statm`
2. Run generated .so under valgrind (`--leak-check=full --show-leak-kinds=all`)
   to detect unreleased `Py_buffer` references
3. Audit the `cleanup:` label in the generator to ensure ALL error paths
   (restrict violation, check failure, overload mismatch) hit `PyBuffer_Release`
4. Optionally add ASan (`-fsanitize=address`) to the `c2py23 build` step

**Files**: tests/ (new valgrind/stress test), generator.py (cleanup path audit).

---

## P9: Template pattern support (Request #8)

**Severity: Low** -- Phase 2 nice-to-have

C preprocessor `#include` templates generate type-generic variants. Each variant
needs its own .c2py entry. Support for parameterized function definitions that
expand to multiple variants.

**Files**: parser.py (macro expansion), docs/ (recommended approach).

---

## P10: ABI matrix population (existing P4)

`tests/abi_matrix.json` currently has one entry. Populate across all snakepit
containers for all 10 Python versions.

---

## P11: Arch-specific clock source (existing P5) [COMPLETE]

`rdtsc` (x86), `CNTVCT_EL0` (ARM64), `__builtin_ppc_get_timebase()` (POWER)
for lower-overhead cycle counting in perf mode.

---

## P12: Test coverage gaps (existing P6) [COMPLETE]

All 10 Python versions pass 11 tests each. 2.7 transform skip remains (requires memoryview.cast shape from 3.3+).

---

## Completed

- P0: Parameter count validation (warns on .c2py sig vs C source mismatch) [Request #1]
- P2: YAML type coercion for bare int/float in map/when/checks [Request #4]
- P3: Better check failure messages with runtime values (got format='%c') [Request #5]
- P4: Buffer format vs C type compile-time validation [Request #2]
- P6: Output scalar convention (outputs: key, auto-alloc, tuple return) [Request #6]
- P8: Valgrind/ASan memory validation -- stress test, cleanup path audit, --asan flag
- P9: Template pattern support -- expand: key with ${VAR} substitution [Request #8]
- P10: ABI matrix populated across all 10 Python versions
- P11: Arch-specific clock source (rdtsc, CNTVCT_EL0, mftb)
- P12: Test coverage -- 10 versions x 11 tests passing
- int64_t/uint64_t 32-bit fix: PyLong_FromLongLong macro added
- Fixed-width C types (int8_t..uint64_t) [Request #3]
- Optional params with defaults (int/float only)
- Custom docstrings (doc: key)
- Module-level integer constants
- Format char dispatch (all single-byte PEP 3118 formats)
- METH_FASTCALL vectorcall for Python 3.12+
- Py_buffer size detection (96 for 2.7, 80 for 3.x; fixed from version-based threshold)
- Py_IncRef fallback for pre-3.12 (ABI matrix confirms 2.7-3.10 distro builds have it)
- `or` operator in when/checks conditions
- Per-function perf timing with ctypes decode
- __array_struct__ evaluated and removed (numpy on 2.7 works via PEP 3118)
- Buffer struct layout mismatch fixed
- -Wall -Werror clean on all generated code
- 10 Python versions in test matrix (2.7, 3.6-3.14)
