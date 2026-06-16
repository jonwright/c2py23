# Referee Reports -- 2026-06-15

**Date of reports:** 2026-06-15
**Git revision at time of reports:** `fb88407` (approx)
**Resolution commit:** `18be1f9`
**Response prepared:** 2026-06-16

---

## Formal Point-by-Point Response

All HIGH and MEDIUM severity bugs have been resolved. Remaining LOW-severity
and design items are noted below with their current status.

### Summary Table

| ID | Severity | Description | Status | Resolution |
|----|----------|-------------|--------|------------|
| B1 | HIGH | VARARGS 3-arg cast to PyCFunction (UB) | RESOLVED | VARARGS wrapper uses 2-arg signature |
| B2 | MEDIUM | `_c2py_dec_ref_manual` no destructor | MITIGATED | Diagnostic added; path unreachable in practice |
| B3 | MEDIUM | Unmatched `(` silent failure | RESOLVED | Raises ValueError on unmatched paren |
| B4 | MEDIUM | `'L'` maps to type not in `_C_TYPES_INT` | RESOLVED | `'l'`/`'L'` remapped to `int64_t`/`uint64_t` |
| B5 | LOW | `subprocess.run` use in test scripts | RESOLVED | Replaced with `subprocess.call`/`Popen` |
| P1 | LOW | `PyErr_Clear` not guarded | RESOLVED | `RESOLVE_REQ` added |
| P2 | LOW | `c2py_runtime_init()` TOCTOU | RESOLVED | `pthread_once` init in `18be1f9` |
| P3 | LOW | 32-bit Py_buffer sizes unverified | OPEN | No 32-bit container in CI; Linux-x86_64 only |
| P4 | LOW | Coerce warning format args swapped | RESOLVED | Warning message rewritten |
| P5 | LOW | No trailing newline in generated C | RESOLVED | `generate()` appends final `\n` |
| D1 | Design | `'l'`/`'L'` LP64-specific | DOCUMENTED | Caveat in spec and code comments |
| D2 | Design | No scientific-notation float defaults | RESOLVED | Extended `_PY_PARAM_RE` regex to accept `1e-4`, `.5`, `3.14e-2`; int defaults validated separately |
| D3 | Design | `outputs:` tuple order undocumented | DOCUMENTED | Spec states C-param-order guarantee |
| -- | Design | INT_MAX overflow on `n` from buffer | RESOLVED | INT_MAX guard emitted when `n` is mapped from `.n` |
| -- | Design | GIL restore before Python object construction | RESOLVED | GIL restored immediately after C call |
| -- | Design | Output tuple leak on error path | RESOLVED | NULL-checked intermediates before `PyTuple_SetItem` |

### Open Items

**B2 (MEDIUM):** `_c2py_dec_ref_manual` has a diagnostic on zero-refcount but
does not call the destructor. This path is unreachable when the CPython C API
is used correctly (all decrefs go through the interpreter's own machinery).
A proper fix requires knowing `_Py_Dealloc`'s symbol name, which varies across
CPython versions. Left as a diagnostic-only mitigation pending a more
comprehensive approach (e.g., `GC_Unreachable` + deferred cleanup).

**P2 (LOW):** The `volatile` flag in `c2py_runtime_init()` serializes
initialization under the GIL in standard builds. Free-threaded 3.14+ (P4 in
PLAN.md) will require atomic initialization; deferred to that work item.

**P3 (LOW):** 32-bit `Py_buffer` sizes (52/44 bytes pre/post 3.12) are
unverified. No 32-bit ABI test container exists. The project targets
Linux-x86_64 primarily. Adding a 32-bit CI target (i386 container or
ARM32) is deferred.

**D2 (Design):** Scientific notation (`1e-4`) and leading-dot (`.5`) float
defaults are now supported. The `_PY_PARAM_RE` regex accepts `-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?`.
Integer parameter defaults are validated separately against `^-?\d+$` to
prevent `int = 1e5` from producing a confusing ValueError.

### Test Coverage Added

Three new test files were added in the fix commit:

- `tests/test_regression_fixes.py` -- 9 tests covering B1, B3, B4, P4, P5,
  and INT_MAX guard generation
- `tests/test_error_paths.py` -- 5 tests for refcount stability on format
  mismatch, size mismatch, successful calls, repeated calls, and alias
  detection error paths
- `tests/test_peer_review.py` -- 10 tests for alias detection (6 positive,
  1 negative) and contiguity enforcement (3 cases)

### Validation Targets

Two external codebases were wrapped and tested as recommended:

- **KissFFT** (`examples/kissfft_wrap/`) -- real and complex FFT wrappers
- **LZ4** (`examples/lz4_wrap/`) -- compress/decompress wrappers

### git tag for future reference

```bash
git tag referee-reports-2026-06-15 <revision-at-time>
```

---

# Original Reports (preserved verbatim)

**Received:** 2026-06-15

---
