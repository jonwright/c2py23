# c2py23 Remaining Work

## In Progress

### PyPy support via `--target pypy`

**Status: functional, not in CI.  Separate .so per target.**

Build with `c2py23 build --target pypy file.c2py` produces a PyPy-compatible
`.so` that resolves `PyPy_*`-prefixed cpyext symbols from `libpypy3.X-c.so`.
Test matrix:

| | PyPy 2.7 | PyPy 3.9 | PyPy 3.11 |
|---|---|---|---|
| Uniform (18) | 18 | 18 | 18 |
| Peer review (10) | 9 | 10 | 10 |
| Regression (31) | 25 | 31 | 31 |

One `.so` for CPython+PyPy is structurally impossible: PyPy's `PyObject`
is 24 bytes (includes `ob_pypy_link`) vs CPython's 16, and `sizeof`
differences are baked into the compiled binary.  HPy was the path to
single-binary cross-implementation support but is not in released PyPy.

No CI — will regress without maintenance.  Pyodide is the next priority.

### Pyodide/WASM support

**Status: `--target wasm` CLI flag implemented.  Tested building a fill.wasm module.**

Pyodide is CPython compiled to WASM via Emscripten.  `dlopen(NULL)` +
`dlsym()` both work.  Gold `vnorm` and `noargs` benchmarks run at
177ns and 1204ns respectively.  `c2py23 build --target wasm` uses
emcc instead of gcc with `-s SIDE_MODULE=1`, skips 32-bit pointer
rejection (`#ifndef __EMSCRIPTEN__`), and drops `-ldl`/`-shared`/`-fPIC`.
CPU feature probes are naturally skipped (no x86/aarch64/ppc64 defines
on wasm32).  DLPack works on Pyodide (numpy in Pyodide exports `__dlpack__`).

Next: build+test fill or uniform modules inside Pyodide in node.js.

## Deferred

### ppc64le CI (was P3)

**Status: aarch64 CI done. ppc64le still needs CI.**

The runtime has full CPU feature detection for POWER (`getauxval`,
`mftb`, `c2py_ppc64.h`).  No testing on real hardware or CI.
Approach: QEMU user-mode emulation inside Apptainer containers (similar
to existing manylinux2014 strategy in snakepit).

### macOS CI (#38)

Apple Silicon CI added (macos-latest, Python 3.12, 96 tests pass).
Intel macOS (x86_64) runner deprecated by GitHub -- Apple stopped selling
Intel Macs in 2023.  Needs self-hosted runner or paid plan for x86_64
SSE2/AVX2 coverage.  Reference: GitHub Actions removed macos-13 in 2025.

### SIMD dispatch: test and document on Windows and ARM (#54)

Completed. aarch64 tests NEON on real hardware (ubuntu-24.04-arm).
macOS tests NEON on Apple Silicon. Windows tests SSE2 via MSVC.
Documentation updated to treat all architectures equally.

### HPy backend for CPython, PyPy and GraalPy (#49)

Investigate the [HPy](https://hpyproject.org/) API as an alternative
backend to the current `dlopen(NULL)`/`dlsym()` CPython ABI hack.
HPy has first-class buffer support (noted after an LLM incorrectly
claimed otherwise) and could provide a single binary that works across
CPython, PyPy, and GraalPy.  Key question: does HPy support Python 2.7
through 3.15 with the buffer protocol?

### GPU support via DLPack (#40)

DLPack is a viable zero-copy protocol for GPU device pointers --
numpy's C source confirms `__dlpack__()` returns the same raw
`PyArray_DATA()` pointer as getbuffer for CPU arrays, and device-typed
pointers for CuPy/PyTorch GPU tensors.  The blocking question is not
buffer access: it's whether a C99 function compiled for a GPU (nvcc,
hipcc) exists to wrap.  All GPU libraries require JIT or pre-compiled
device code.  Deferred until there is a concrete GPU-compiled C
function to wrap.

---

## Outstanding (low-priority)

### Free Threading (FT) globals audit (P5)

Review `_c2py_gil_release_enabled`, `_c2py_timing_enabled`, per-function
`_gil_release_*`, variant `_var_*` globals for atomic safety under
free-threading. Low priority since FT is opt-in.

The `free_threading` .c2py feature (`tests/cases/freethreading/`) has
NO integration test that imports `freethreadmod` at runtime (the
conftest builds the .so but no test exercises it).

### 32-bit CI

No 32-bit CI target (i386/ARM32).  Reject 32-bit builds at module import
with a clear diagnostic.  Only LP64 (64-bit) targets are tested.

### MSVC detection only searches PATH (P5)

`_find_msvc` in `cli.py` iterates only `PATH` entries for `cl.exe`.
Standard Visual Studio installs require `vcvarsall.bat` to be sourced
first.  Consider using `vswhere.exe` for VS detection on user machines.

---

## Completed

- **Multi-backend buffer acquisition (2026-07)** — NumPy struct-cast, PEP 3118
  buffer protocol, and DLPack capsule extraction, selectable via `acquire:` YAML key.
  Default is `[ndarray, buffer]`; ndarray struct-cast is 2-3x faster than gold
  baselines for small arrays (~70ns vs 120ns).  `c2py_ptr_info` abstracts the
  buffer metadata into a unified struct shared by all backends.

- **ABI cleanup (2026-07)** — `ob_type_offset` resolved at runtime instead of
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
- Per-function perf timing with C accessor functions (ctypes-free decode)
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
  All 90 tests pass.
- **Subinterpreter limitation documented** in README.md Limitations section.

### Reviewer Response

**Status: Completed (2026-06-20)** -- Point-by-point response addressing all
four referee reports. All HIGH and MEDIUM severity items resolved. LOW-severity
items (generator structural hardening, FT globals audit, 32-bit CI) tracked in
Outstanding section above.  Design decisions intentionally unsupported (keyword
arguments #44, named-tuple returns #42, async/await #41) are documented
in `docs/design.md`.

## Design Decisions (intentionally unsupported)

These are settled design decisions, documented in `docs/design.md`:

| Issue | Topic | Status |
|-------|-------|--------|
| #53 | C99 complex types | Intentionally unsupported -- C/C++ ABI conflict |
| #44 | Keyword arguments | Intentionally unsupported -- C99 is positional-only |
| #42 | Named-tuple returns | Design discussion -- may revisit |
| #41 | Async/await support | Not planned -- c2py23 is synchronous C wrapping |
