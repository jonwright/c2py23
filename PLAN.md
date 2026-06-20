# c2py23 Remaining Work

## Deferred

### P4: Binary wheel distribution

**Severity: Low** -- replaces --no-build-isolation workflow

**Status: DEFERRED** -- design TBD, implement later.

**Open design questions (from referee review):**

1. **Wheel tagging:** The c2py23 .so uses the nimpy trick -- one binary works
   on CPython 2.7-3.15 without linking libpython. Standard wheel tags
   (cp312-cp312-*, cp37-abi3-*, etc.) assume a specific CPython ABI. A
   bare `modulename.so` with no Python link dependency has no standard
   wheel tag. Need to investigate whether `py3-none` tag can be used.

2. **Symbol export dependency:** c2py_runtime_init() does dlopen(NULL,
   RTLD_GLOBAL) and expects CPython API symbols already loaded. This
   depends on the interpreter being built with --enable-shared. Not
   guaranteed for: musllinux/Alpine, some conda builds, embedded/frozen
   Python, PyPy.

3. **Build-backend integration:** Current cli.py shells out to gcc
   directly. No setuptools build_ext / meson-python / scikit-build-core
   hookup for pip wheel . or cibuildwheel. This integration layer must
   be built from scratch.

4. **Platform matrix:** Need verification on manylinux2014 x86_64 and
   aarch64, musllinux, macOS, and Windows before distribution.

**Next steps before implementation:**
- Build and test on manylinux2014 containers (request snakepit addition)
- Evaluate py3-none vs. platform-specific wheel tags
- Evaluate setuptools vs. meson-python vs. scikit-build-core for build backend

---

## Outstanding (low-priority)

### Generator structural hardening (P5)

The generator emits C via hundreds of `out.append(...)` calls building a string
list. This is prone to logical errors: a re-order can miss a cleanup, GIL
save/restore, or null-check. The existing regression tests (21 tests in
`test_regression_fixes.py`) cover known bug patterns but do not verify
invariant-level properties. A future improvement could add a structural
invariant checker that walks the generated C and validates properties
(e.g. every buffer acquire has matching release, every GIL save has matching
restore, every error path releases all acquired buffers). See
`audit/20260620/workplan.md` Task O for discussion.

### FT globals audit (P5)

Review `_c2py_gil_release_enabled`, `_c2py_timing_enabled`, per-function
`_gil_release_*`, variant `_var_*` globals for atomic safety under
free-threading. Low priority since FT is opt-in.

---

## Completed
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
- YAML type coercion -- auto-coerce bare int/float in map/when/checks
- Better check failure messages -- include actual runtime values
- Buffer format vs C type compile-time validation -- raises ValueError
- Output scalar convention -- `outputs:` key, auto-alloc, tuple return
- Template expansion -- `expand:` key with `${VAR}` substitution
- Comprehensive dispatch-over-all-types example -- typedispatch test case, Example 4 in spec
- Valgrind/ASan validation -- stress test, cleanup audit, `--asan` flag
- Test coverage -- 11 versions x 14 uniform tests, 10 peer review tests
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
- Per-function perf timing with ctypes decode
- `__array_struct__` evaluated and removed
- Buffer struct layout mismatch fixed
- `-Wall -Werror` clean on all generated code
- 11 Python versions in test matrix (2.7, 3.6-3.14, 3.14t); 3.15 struct layouts verified identical
- Contiguity check: rejects strided arrays, negative strides, accepts C/F-contiguous
- Alias detection: rejects buffer aliasing between writable buffers (5 patterns)
- Shared-refcount fix: PyExc_* always dereferenced once (handles pre-3.12 heap-type pointers and 3.12+ static shared-refcount)
- Debug build support: `--asan` flag, `CC`/`CFLAGS`/`LDFLAGS` env vars, `gcc -shared -g -O0`

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
  All 59/59 tests pass.
- **Subinterpreter limitation documented** in README.md Limitations section.

### Reviewer Response

**Status: Completed (2026-06-20)** -- Point-by-point response addressing all
four referee reports. All HIGH and MEDIUM severity items resolved. LOW-severity
items (generator structural hardening, FT globals audit, 32-bit CI) tracked in
Outstanding section above.
