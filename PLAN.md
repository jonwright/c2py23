# c2py23 Remaining Work

## In Progress

### PyPy support via `-DC2PY_TARGET_PYPY`

**Status: dlsym smoke test in CI.  Not battle-tested.**

Build with `CC=gcc CFLAGS="-DC2PY_TARGET_PYPY -O1" make -f tests/Makefile all`.
Produces PyPy-compatible `.so` files that resolve `PyPy_*`-prefixed cpyext
symbols at runtime.  CI runs a smoke test (build fill, import via
`ExtensionFileLoader`, verify) on pypy3.9 and pypy3.10.

`import fillmod` does not work on PyPy because its `_imp.extension_suffixes`
only lists ABI-tagged suffixes (`.pypy311-pp73-x86_64-linux-gnu.so`), never
plain `.so`.  CPython includes plain `.so`.  Workaround: preload via
`importlib.machinery.ExtensionFileLoader`.  Documented in `docs/building.md`.

One `.so` for CPython+PyPy is structurally impossible: PyPy's `PyObject`
is 24 bytes (includes `ob_pypy_link`) vs CPython's 16.

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

Per-module globals (`_c2py_gil_release_enabled`, `_c2py_timing_enabled`,
per-function `_gil_release_*`, variant `_var_*_*`) are read-mostly after
init.  They are set once during module init (single-threaded) and read
during every call.  The only write paths are module-level toggle setters
(exposed as `_c2py_gil_release_enabled`, `_c2py_timing_enabled` attributes)
which are rarely called after init.

Under free-threading with `free_threading: true`, concurrent toggles could
race.  Practically harmless: reads are non-atomic int loads (tearing on
int is impossible on all supported LP64 platforms).  Write-write races on
the same int are meaningless (last writer wins).  The GIL is re-enabled
for modules that do NOT declare `free_threading: true`, so the race window
only exists for explicitly FT-safe modules.

Low priority.  If strict atomicity is ever needed: change globals to
`_Atomic int` (C11).

### pythonh mode: 64-bit integer slots NULL on Python 2.7 (false positive -- no action)

Flagged by the local symbol-resolution self-check
(`tools/check_runtime_symbols.py`) but confirmed to be a **false positive**,
not an active bug.  In `--pythonh` mode (compile against `<Python.h>`),
`c2py_pythonh.c` leaves `C2PY.Long_FromLongLong`,
`C2PY.Long_FromUnsignedLongLong`, and `C2PY.Long_AsLongLong` `NULL` on
Python 2.  However those `C2PY.Long_*` slots are consumed **only** in
dlsym mode: the `PyLong_FromLongLong` / `PyLong_AsLongLong` macros that
map to them live inside the `#ifndef C2PY_USE_PYTHON_H` block of
`c2py_runtime.h`, and the generator emits the macros, not `C2PY.Long_*`.
In pythonh mode those macros are undefined, so generated code calls
Python 2.7's real `<Python.h>` `PyLong_FromLongLong` /
`PyLong_FromUnsignedLongLong` / `PyLong_AsLongLong` (all of which DO exist
on CPython 2.7) directly.  The NULL `C2PY` slot is never dereferenced.

No runtime change needed.  The analyzer now recognises dlsym-only
consumers and reports these as informational, not as hazards.  If a future
change ever reads `C2PY.Long_*` in pythonh mode, this should be revisisted.

### 32-bit CI

Windows i386 CI runner (`test-windows-i386` in `windows.yml`) tests both
dlsym and pythonh mode (Python 2.7 and 3.12).  Dlsym mode 32-bit works
(issue #87): the numpy ndarray struct-cast fast-path uses arch-conditional
field offsets (`C2PY_NDARR_OFF_*`), the `PyArray_Descr` type-char offset
is arch-conditional too (13 on ILP32 vs 25 on LP64), and the DLPack
backend copies int64 shapes/strides into `Py_ssize_t` buffers instead of
aliasing the int64 array (which read wrong values on ILP32).  `check_numpy_abi.c`
verifies the offsets for the current pointer size.  ABI3T (limited-API)
numpy builds are unaffected: `Py_TARGET_ABI3T` only hides the struct from
compile-time consumers, so the runtime allocation/layout (and the probed
offsets) are unchanged.  `sizeof(Py_buffer)` is
52/44 bytes on ILP32 (pre/post 3.12) vs 96/80 on LP64; the runtime probe
selects the right size.  Free-threading does not exist on ILP32.

Windows 64-bit uses LLP64 (`sizeof(long)=4`) which we handle correctly
(format-dispatch, length type).  Windows 32-bit i386 is LLP64 + 4-byte
pointers.

Gohlke's numpy binaries cover Windows 32-bit (i386)  --  but for c2py23,
32-bit support would require:
1. `SIZE_T_MAX` -> `INT_MAX` guards on buffer sizes
2. i386 ARM32 CI (GitHub Actions `windows-latest` is x64 only)

Low priority.  Users needing 32-bit can use `--pythonh` on their
target Python (bypasses all dlsym layout detection).

### Left over from the 2026-11 review

- PyPy removal from dlsym mode (review D5, "WP9") is parked: PyPy is not
  used in production, the code stays as an untested-in-anger smoke path.
- Review A9 (lazy `InitializeCriticalSection` race on Windows) not done:
  believed unreachable because module init is serialized by the import lock.
- `_c2py_gil_release_*` module attributes still publish raw addresses
  (the perf attributes were converted to handles; these were not).
- `tests/test_visibility.py` checks ELF symbol visibility only; it returns
  early on Windows.
- `benchmarks/` has no pythonh-mode rows: `load_pythonh_module()` in
  `benchmarks/conftest.py` is unused and `make -C benchmarks c2py_ph`
  builds modules nothing reads.
- numpy 2.5 on CPython 3.14t crashed inside its own buffer export when
  another thread reshaped the array in place (no c2py23 code involved).
  Needs a reproducer against numpy git head on 3.15t before reporting.

### MSVC / Windows build

`_find_msvc` removed from cli.py (build removal).  Windows builds use the
Makefile with `ifdef MSVC` (gated on CC=cl).  Setuptools path via
`setuptools_helper.py` also works for pythonh mode.  No discoverability
issue: `CC=cl` is set in CI and `make` auto-detects it.

---

## Completed

- **Peer review fixups (2026-11)** -- crash and safety findings from an
  external-style review: bounds-safe `buf.shape[k]`, derived element-type
  and alignment checks, pointer-arithmetic rejection in `map:`, perf
  handles instead of raw addresses, ImportError on runtime init failure,
  hidden runtime symbols, removal of dead refcount / layout fallbacks,
  hardened ndarray fast path.  Review, plan and downstream report are in
  `archive/2026-11_*.md`.

Earlier completed items are in `archive/plan_completed.md`.

## Design Decisions (intentionally unsupported)

These are settled design decisions, documented in `docs/design.md`:

| Issue | Topic | Status |
|-------|-------|--------|
| #53 | C99 complex types | Intentionally unsupported -- C/C++ ABI conflict |
| #44 | Keyword arguments | Intentionally unsupported -- C99 is positional-only |
| #42 | Named-tuple returns | Design discussion -- may revisit |
| #41 | Async/await support | Not planned -- c2py23 is synchronous C wrapping |
