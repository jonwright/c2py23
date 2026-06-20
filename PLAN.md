# c2py23 Remaining Work

## Deferred

### P4: Binary wheel distribution

**Severity: Low** -- replaces --no-build-isolation workflow

**Status: DEFERRED** -- design TBD, implement later.

**Open design questions (from referee review):**

1. **Wheel tagging:** The c2py23 .so uses the nimpy trick -- one binary works
   on CPython 2.7-3.14 without linking libpython. Standard wheel tags
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

## Completed

- P1: SIMD dispatch / CPU feature detection -- two-level group/variant dispatch,
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
- 11 Python versions in test matrix (2.7, 3.6-3.14, 3.14t)
- Contiguity check: rejects strided arrays, negative strides, accepts C/F-contiguous
- Alias detection: rejects buffer aliasing between writable buffers (5 patterns)
- Shared-refcount fix: PyExc_* always dereferenced once (handles pre-3.12 heap-type pointers and 3.12+ static shared-refcount)
- Debug build support: `--asan` flag, `CC`/`CFLAGS`/`LDFLAGS` env vars, `gcc -shared -g -O0`

### Reviewer Response

**Status: Completed (2026-06-16)** -- Point-by-point response addressing all three
referee reports (2026-06-15) with fixes for all HIGH and MEDIUM severity items
is prepended to `docs/referee_reports_2026-06-15.md`. LOW-severity items deferred
as noted in the response.
