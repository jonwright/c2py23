# c2py23 Remaining Work

## Deferred

### ppc64le CI (was P3)

**Status: aarch64 CI done (ubuntu-24.04-arm runner). ppc64le still needs CI.**

The runtime has full CPU feature detection for POWER (`getauxval`,
`mftb`, `c2py_ppc64.h`).  No testing on real hardware or CI.
Approach: QEMU user-mode emulation inside Apptainer containers (similar
to existing manylinux2014 strategy in snakepit).

### macOS CI (#38)

No macOS runner in CI.  The code is designed to be POSIX-portable and
should work on macOS (clang, `dlopen`/`dlsym`), but this has never
been tested.

### SIMD dispatch: test and document on Windows and ARM (#54)

CPU feature detection works on x86_64 (`cpuid`) and aarch64
(`getauxval`/`mrs`).  MSVC detection of CPU features needs testing.
ARM64/POWER64 SIMD kernels exist but are validated via container
emulation only -- no real hardware testing.

## Outstanding (low-priority)

### Free Threading (FT) globals audit

Review `_c2py_gil_release_enabled`, `_c2py_timing_enabled`, per-function
`_gil_release_*`, variant `_var_*` globals for atomic safety under
free-threading.  Low priority since FT is opt-in.

The `free_threading` .c2py feature (`tests/cases/freethreading/`) has
NO integration test that imports `freethreadmod` at runtime (the
conftest builds the .so but no test exercises it).

### 32-bit CI

No 32-bit CI target (i386/ARM32).  Reject 32-bit builds at module import
with a clear diagnostic.  Only LP64 (64-bit) targets are tested.

### MSVC detection only searches PATH

`_find_msvc` in `cli.py` iterates only `PATH` entries for `cl.exe`.
Standard Visual Studio installs require `vcvarsall.bat` to be sourced
first.  Consider using `vswhere.exe` for VS detection on user machines.

### C99 complex type support (`'Z'`/`'z'` format) (#53)

Buffer protocol supports complex float/double formats (`'Z'` = DCOMPLEX,
`'z'` = FCOMPLEX) but c2py23 does not generate wrappers for them.
Would unlock DSP/scientific use cases (FFTW, BLAS) that use interleaved
complex arrays.

## Completed

### P4: PyPI distribution

c2py23 is published on PyPI.  The wheel packaging demo
(`examples/wheel_demo/`) demonstrates multi-platform `.so` coexistence
in a single `py3-none-any` wheel using `c2py_loader`.  Users can
produce wheels for their own modules following the demo.

### P3: aarch64 CI

aarch64 CI added (ubuntu-24.04-arm native runner).  CPU feature flags
defined unconditionally for cross-arch portability.  Cycle counter
is now a runtime selector (`_c2py_set_tick_source()`).

### Earlier completions

- Variant dispatch, buffer layout guard, generator structural hardening
- Wheel packaging, manylinux2014 cross-testing
- P2: Windows port (MSVC + MinGW, all 14 tests pass)
- GIL release, free-threading, SIMD dispatch
- Referee audit (June 2026, 22 tasks from 2 reports)
- Lifecycle tests, subinterpreter support
- ABI matrix, ASan/Valgrind validation, debug builds
- Full list in PLAN.md history (June 2026)

## Design Decisions (intentionally unsupported)

These are settled design decisions, documented in `docs/design.md`:

| Issue | Topic | Status |
|-------|-------|--------|
| #44 | Keyword arguments | Intentionally unsupported -- positional-only API |
| #42 | Named-tuple returns | Design discussion -- may revisit |
| #41 | Async/await support | Not planned -- c2py23 is synchronous C wrapping |
| #40 | GPU / array API compat | Exploratory -- no active development |
