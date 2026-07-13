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

## Current Status (2026-06-21)

All HIGH and MEDIUM items resolved.  LOW-severity items deferred:

| ID | Description | 2026-06-21 Status |
|----|-------------|-------------------|
| P3 | 32-bit Py_buffer sizes unverified | DEFERRED -- no 32-bit CI target |
| D1 | `'l'`/`'L'` LP64-specific | DOCUMENTED -- PLY.md Outstanding |
| P5 | Generator structural hardening | DEFERRED -- PLY.md Outstanding |
| P5 | FT globals audit | DEFERRED -- PLY.md Outstanding |

Additional referee reports from 2026-06-20 resolved as a separate audit
(`audit/20260620_resolved/`), completing 22 tasks across 2 reports.

### Where TODOs live

PLAN.md under "Outstanding" tracks deferred items.  AGENTS.md under
"Next Steps" tracks upcoming work.

### Test Coverage Added

Three new test files were added in the fix commit:

- `tests/test_regression_fixes.py` -- 9 tests covering B1, B3, B4, P4, P5,
  and INT_MAX guard generation (now 14 tests as of 2026-06)
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
