# c2py23 completed work (archived from PLAN.md, 2026-11-11)

Historical record only.  Entries describe the code as it was when each item
landed and are not kept up to date.  In particular the manual refcount
fallback (`_c2py_inc_ref_manual` / `_c2py_dec_ref_manual`), the `Py_buffer`
size probe and the layout-probe fallbacks mentioned below were deleted in
the 2026-11 review fixups (`Py_IncRef` / `Py_DecRef` are now required).


- **Wrapper size / thin marshalling (2026-09)**  --  a consumer
  (`jonwright/bslz4_to_sparse`) reported a 3.3 MB / 64,920-line generated
  wrapper whose alias and contiguity checks were inlined per buffer pair
  and multiplied by every `expand` type variant.  Four generator changes
  landed without changing observable behaviour: (1) the writable-vs-any
  overlap scan is now a single `c2py_check_no_overlap()` call
  (`static inline`, `c2py_runtime.h`) per wrapper instead of a 12-line
  block per pair per calling convention, with an opt-out `check_aliasing:
  false` function key for hot paths; (2) the C/F-contiguity validation is
  likewise centralized in `c2py_check_contiguity()`; (3) each docstring is
  emitted once as a `static const char _doc_<name>[]` shared by both the
  VARARGS and FASTCALL tables; (4) the METH_VARARGS wrapper is now a thin
  shim that unpacks the args tuple into a fixed stack array and forwards to
  the METH_FASTCALL function, which owns the marshalling body (adds
  `PyTuple_Size`/`PyTuple_GetItem` to the runtime API table), so that body
  is emitted once per method instead of twice.  For the reporting spec this
  took the wrapper from 3,321,647 bytes / 64,920 lines to 1,036,630 bytes /
  17,239 lines, and the compiled wrapper object's `.text` from 688,308 to
  248,500 bytes (-64%); the compiler had already merged the duplicate
  docstring literals, so that piece is a source/compile-time win, not a
  `.rodata` one.  The full 13-version container matrix (2.7-3.15 incl.
  free-threaded, on the consolidated snakepit-legacy/modern containers) is
  green.  Remaining, deliberately deferred: a polymorphic entry point that
  collapses an `expand` family into one dtype-dispatching method (the only
  fix for the remaining per-type multiplication).  Recorded in
  `c2py23_wrapper_size_issue.md`.

- **Variant `fallback: true` singleton marker (2026-09)**  --  a group's
  auto-resolve fallback (the variant picked when no `when:`-guarded variant
  matches) used to be "the last declared `default: true` variant", which
  silently misresolved in two related ways (see `bug_variant.md`): (1) 2+
  unconditional (when-less) `default: true` variants in one group -- the
  last-declared one won regardless of author intent; (2) a single
  unconditional variant declared *before* a later `when:`-guarded
  `default: true` variant -- the guarded one silently stole the fallback
  slot even when its `when:` condition was false at runtime. The fallback
  is now always the unique unconditional `default: true` variant when
  there is exactly one, full stop, regardless of declaration order. When a
  group has 2+ such candidates, exactly one must be marked `fallback:
  true`, or parsing raises `ValueError` naming the group and the
  competing variants, instead of silently picking one. A third case is
  also now rejected: a group where *every* `default: true` variant is
  `when:`-guarded (zero unconditional variants) has no safe choice when
  none of them match at runtime (e.g. no compiled CPU-feature variant is
  supported by the machine running the code) -- this used to silently
  assign a guarded variant's index anyway; it now raises at parse time,
  telling the author to add one plain fallback variant. All three checks
  run in `from_c2py_dict()`/`load_c2py()` (parse time), not just
  `generate()`, so parse-only consumers (e.g. `harvester.py`) see the
  error immediately too. Every `.c2py` spec in this repo is
  byte-identical (none hits any of these three patterns); a spec with 2+
  unconditional `default: true` variants per group -- like the
  `bslz4_to_sparse_llm` case this closes -- must add `fallback: true` to
  exactly one variant and regenerate, or parsing now fails with a clear
  error instead of producing a silently-wrong wrapper. `generate()` also
  re-checks all three invariants defensively (same messages), in case a
  `ModuleDef` is built programmatically without going through
  `load_c2py()`/`from_c2py_dict()`. Documented in `docs/specification.md`
  (Variant Ordering).

- **`--pythonh` mode (2026-07)**  --  direct `#include <Python.h>` build, no dlsym
  trick.  Works on all runtimes (CPython 2.7-3.15t, PyPy 3.9/3.11, GraalPy 3.12).
  CI covers 3.14t end member (inline in `linux.yml`), i386 2.7 + 3.12 (in
  `windows.yml`).  Full docs in `docs/pythonh.md`.

- **Pyodide/WASM support (2026-07)**  --  build with `emcc -s SIDE_MODULE=1`.
  23 WASM modules, 80/80 tests pass inside Pyodide via Node.js.  CI in `wasm.yml`.

- **Buffers on disk: brainstorm/ removed (2026-07)**  --  useful cross-platform
  scripts moved to `tests/cross_platform/`, Pyodide npm package to
  `tests/wasm/pyodide_pkg/`, setup scripts to `docs/`.

- **Multi-backend buffer acquisition (2026-07)**  --  NumPy struct-cast, PEP 3118
  buffer protocol, and DLPack capsule extraction, selectable via `acquire:` key.
  Default is `[ndarray, buffer]`; ndarray struct-cast is 2-3x faster than gold
  baselines for small arrays (~70ns vs 120ns).  `c2py_ptr_info` abstracts the
  buffer metadata into a unified struct shared by all backends.

- **ABI cleanup (2026-07)**  --  `ob_type_offset` resolved at runtime instead of
  assuming `ob_refcnt + 8`.  Python string/unicode API removed from wrapper ABI
  (no `Unicode_FromString`, `String_FromString`, or `ParseTupleAndKeywords`).
  Variant names use ASCII bytes via `PyBytes_FromStringAndSize`.  `c2py_pin`
  fallback error prevents silent `SystemError` when all backends fail.

- **PyPI distribution (2026-06)** -- c2py23 is published on PyPI.  The wheel
  packaging demo (`examples/wheel_demo/`) demonstrates multi-platform `.so`
  coexistence in a single `py3-none-any` wheel using `c2py_loader`.  Users can
  produce wheels for their own modules following the demo.

- **P3: aarch64 CI (2026-06)** -- aarch64 CI added (ubuntu-24.04-arm native
  runner).  CPU feature flags defined unconditionally for cross-arch header
  portability.  Cycle counter is now a runtime selector
  (`_c2py_set_tick_source()`).

- **Variant dispatch enhancements (2026-06-21)** -- `default: false` for
  benchmark-only variants; `_variants_<name>()` enumeration API; variant
  `name` enforced to match C function name from `sig`; per-variant perf
  metadata (`variant`, `group_idx`, `variant_name`).

- **Buffer layout guard (2026-06-21)** -- `buf.slow_axis`, `buf.fast_axis`,
  `buf.slow_dim` and `buf.fast_dim` expressions; contiguity check enforces C-or-F density;
  `slow_axis == 0` in `checks:` guards against transposed layouts.

- **Generator structural hardening (2026-06-21)** -- `c2py23/invariant_checker.py`
  validates brace balance, buffer acquire/release pairs, output scalar NULL-checks,
  GIL save/restore pairing, and cleanup path invariants.  Runs during `generate()`.

- **Wheel packaging (2026-06-20)** -- `c2py_loader` explicit-filename
  `.so` loader; `py3-none-any` wheel tag; multi-platform `.so` coexistence;
  cross-tested on all snakepit containers.

- **Manylinux2014 cross-testing (2026-06-20)** -- `test_manylinux.py` build-once
  strategy across 6 manylinux Pythons and 11 cross-container test targets.

- **P2: Windows port (2026-06-20)** -- `GetModuleHandle`/`GetProcAddress` runtime
  via `python3.dll` with versioned fallback; MSVC and MinGW build paths in `cli.py`;
  LLP64 format handling (`sizeof(long)` itemsize check, `'L'`/`'l'` dispatch);
  CI on GitHub Actions `windows-latest` (Python 2.7, 3.13, 3.14), 14/14 pass.
  ABI confirmed: `sizeof(long)=4`, all struct layouts identical across 2.7-3.15.
  - Both buffer-length and format-dispatch portability fixed.
  - Buffer length type converted from `int` to `intptr_t` (pointer-width).
  - `_FORMAT_TO_CTYPE` now excludes `'l'`/`'L'`; `_expr_to_c` generates runtime
    `itemsize == sizeof(long)` check for platform correctness.
  - MSVC quirks: `inline` -> `__inline`, `##__VA_ARGS__` guard, `sscanf_s`,
    `C2PY_EXPORT`/`__declspec(dllexport)`, C4152 `#pragma warning` suppression.

  CPUID (x86_64), getauxval (ARM64, POWER), `.rebind()` method, flat + grouped
  overloads, switch/function-pointer dispatch, timing integration, user-defined
  features via `c2py_cpuid_bit()`.  Worked example in `examples/simd_dispatch/`.
  ARM64/POWER64 untested on real hardware; validated via container emulation only.
- P2: GIL release (`gil_release: true`) -- per-function and global toggle, tested.
  `PyEval_SaveThread`/`PyEval_RestoreThread` wrapper injection, no-op on FT builds.
- P3: Free-threaded Python 3.14+ support -- dual PyModuleDef structs, FT detection
  via `Py_GetVersion()` + `_Py_IsGILEnabled()`, `pthread_once` init, atomic
  refcount enforcement on FT.  All 14 uniform + 14 regression + 5 error-path
  tests pass on python3.14t.
- P0: Parameter count validation -- raises ValueError on sig mismatch
- Type coercion -- auto-coerce bare int/float in map/when/checks
- Better check failure messages -- include actual runtime values
- Buffer format vs C type compile-time validation -- raises ValueError
- Output scalar convention -- `outputs:` key, auto-alloc, tuple return
- Template expansion -- `expand:` key with `${VAR}` substitution
- Comprehensive dispatch-over-all-types example -- typedispatch test case, Example 4 in spec
- Valgrind/ASan validation -- stress test, cleanup audit
- Test coverage -- 13 versions x 18 uniform tests, 10 peer review tests
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
- METH_FASTCALL vectorcall for Python 3.12+
- Py_buffer size detection (dynamic, version-based)
- Py_IncRef fallback for pre-3.12 (manual refcount incr)
- `or` operator in when/checks conditions
- Per-function perf timing with C accessor functions (ctypes-free decode)
- `__array_struct__` evaluated and removed
- Buffer struct layout mismatch fixed
- `-Wall -Werror` clean on all generated code
- 13 Python versions in test matrix (2.7, 3.6-3.15, 3.14t, 3.15t)
- Contiguity check: rejects strided arrays, negative strides, accepts C/F-contiguous
- Alias detection: rejects buffer aliasing between writable buffers (5 patterns)
- Shared-refcount fix: PyExc_* always dereferenced once (handles pre-3.12 heap-type pointers and 3.12+ static shared-refcount)
- Debug build support: `CC`/`CFLAGS`/`LDFLAGS` env vars passthrough, `gcc -shared -g -O0`

- **Referee audit (2026-06-20):** 22 tasks from 2 new referee reports:
  - A: fix `int64_t` multi-output tuple bug (missing NULL check + PyTuple_SetItem)
  - B: fix `Unstable_Module_SetGIL` function pointer type mismatch (UB fix)
  - C: remove dead `src_path` assignment in cli.py
  - D: anchor `_C_PARAM_RE` regex to end-of-string
  - E: validate return types against generator capabilities (reject int8_t..uint64_t returns)
  - F: store `c_name` in AST, eliminate both `_extract_c_name()` functions
  - G: fix expression string escape handling (decode `\n`, `\t`, `\\`, `\"`)
  - H: validate template expansion values are strings
  - I: improved error messages for multi-word/unknown return types
  - J: add `assert.h` and runtime static assertions for detected ABI layout
  - K: add `C2PY_FORCE_FT` env var override for free-threading detection
  - L: remove stale "does not yet expose" FT documentation sentence
  - M: document buffer writability per-function limitation (generator, AGENTS.md)
  - N: document `_c2py_dec_ref_manual` fallback limitation (runtime.h)
  - P3: reject 32-bit builds at module import with clear diagnostic
  - V: update P4 wheel entry with concrete open design questions
- **Lifecycle tests:** 10 new tests covering re-import cycles (3), concurrent imports (2),
  exception path stress (3), and subinterpreters (2, documenting known limitation).
  All 90 tests pass.
- **Subinterpreter limitation documented** in README.md Limitations section.

### Reviewer Response

**Status: Completed (2026-06-20)** -- Point-by-point response addressing all
four referee reports. All HIGH and MEDIUM severity items resolved. LOW-severity
items (generator structural hardening, FT globals audit, 32-bit CI) tracked in
Outstanding section above.  Design decisions intentionally unsupported (keyword
arguments #44, named-tuple returns #42, async/await #41) are documented
in `docs/design.md`.
