# c2py23 Continuation Notes - 2026-06-15

## Current Status: Debugging contiguity check segfault

### What's implemented but broken

**Contiguity check** in `c2py23/generator.py` (`_emit_contiguity_checks`, line ~853):
- Generated C code compiles clean with `-Wall -Werror`
- Logic is correct on paper: checks C-contiguous first, then F-contiguous, rejects strided/negative-stride
- Contiguous numpy arrays pass through fine
- **Strided numpy arrays** (e.g. `a[::2]`) cause a segfault inside the generated wrapper
- **Reversed arrays** (`a[::-1]`, negative strides) same segfault
- GDB says crash is in `PyErr_SetString` → `_PyErr_SetObject`, which suggests the error-reporting path itself crashes
- Without the contiguity check, the fill function runs on strided data (producing wrong results silently — the exact bug we're trying to prevent)

### Key investigation notes

1. The segfault is in `PyErr_SetString(PyExc_ValueError, "buffer not contiguous...")` — this same call pattern works fine for alias errors in the same wrapper
2. `PyErr_Format` was tried but also crashed; reverted to `PyErr_SetString`
3. `I also added `Err_Format` to the runtime API table (`c2py_runtime.h:183`, `c2py_runtime.c:149`) — this shifted all struct fields after it by 8 bytes. New modules compiled against the new header see the new layout. **If an OLD .so is loaded first** (setting up the C2PY table with old layout), and a NEW .so accesses fields after Err_Format offset, there could be offset mismatches. However, the contiguity check only uses Err_SetString (offset 0xb8) and exc_ValueError (offset 0xa0), both BEFORE Err_Format, so this shouldn't matter.
4. You can reproduce: `python3 -c "import sys; sys.path.insert(0,'tests/cases/fill'); import fillmod; import numpy as np; fillmod.fill(np.arange(20.)[::2], 1.0)"`
5. Removing the contiguity check (commenting out `_emit_contiguity_checks` call in `_emit_wrapper_body`) makes the crash go away — strided data passes through silently. Proves the crash is in the contiguity check code path.

### Files changed (uncommitted)

| File | Change |
|------|--------|
| `c2py23/runtime/c2py_runtime.h` | Added `Err_Format` to API struct + macro |
| `c2py23/runtime/c2py_runtime.c` | `RESOLVE_REQ(C2PY.Err_Format, "PyErr_Format")` |
| `c2py23/generator.py` | Added `_emit_contiguity_checks()` function; changed cleanup label condition from `>= 2` to `>= 1`; added call in `_emit_wrapper_body` |
| `tests/test_peer_review.py` | New file: alias + contiguity numpy tests (also crashes on same issue) |

### Completed & committed

All in git (pushed):

1. **Request-status sync** — `c2py23_requests.md` (both c2py23 and c2ImageD11) updated to reflect actual implementation status (7/9 done)
2. **Dispatch-over-all-types** example — `tests/cases/typedispatch/` test case covering all 10 PEP 3118 format chars; Example 4 in `docs/specification.md`
3. **P0/P4 warnings → errors** — `parser.py` now raises `ValueError` instead of `warnings.warn`
4. **GIL release (P2)** — `gil_release: true` on functions, global toggle `_c2py_gil_release_enabled`, per-function flags. Tested and working. `tests/cases/gil_release/`
5. **GIL release design rationale** — New section in `docs/specification.md`
6. **PLAN.md** — Restructured with priorities: P1 SIMD dispatch, P2 GIL release (done), P3 free-threaded, P4 binary wheels (deferred)

### Remaining work (in PLAN.md)

| Item | Status |
|------|--------|
| P1: SIMD dispatch / CPU feature detection | Not started |
| P2: GIL release | **DONE** |
| P3: Free-threaded Python 3.14+ | Not started; no free-threaded build available |
| P4: Binary wheels | Deferred |
| Contiguity check | **IMPLEMENTED, BUGGY** (segfault on strided arrays) |
| Alias detection tests | Test file written (`test_peer_review.py`) but depends on contiguity fix |
| Debug build documentation | Not started |

### Next debugging steps for contiguity

1. Build debug .so: `gcc -shared -g -O0 ... -o fillmod.so`
2. Load in gdb: `gdb --args python3 -c "..."` and set breakpoint at `_fill_fastcall`
3. Check if the `PyErr_SetString` call is really going through our function pointer or directly
4. Check `C2PY` struct values at runtime (print `C2PY.Err_SetString`, `C2PY.exc_ValueError`)
5. Try replacing `PyErr_SetString` with a direct return NULL + error via `PyErr_Occurred` pattern
6. Alternative: move contiguity check to `c2py_runtime.h` as a static inline function instead of generating inline C

### Test all versions

Before contiguity work, all 10 Python versions (2.7-3.14) pass the 13 uniform tests.
After contiguity is fixed, run `python3 tests/test_peer_review.py` with numpy for alias tests.
Then run `python3 tests/test_all.py` for multi-version testing.
