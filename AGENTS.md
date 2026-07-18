# c2py23 Project Context for AI Agents

## 7-Bit ASCII Encoding Requirement

**IMPORTANT**: All source files in this repository MUST use only 7-bit ASCII encoding.

### Rationale
- Ensures maximum compatibility with legacy systems and HPC environments
- Prevents encoding issues in container environments
- Simplifies cross-platform text processing
- Generated C code must be valid in any C99 compiler

### What This Means

**DO NOT USE:**
- Unicode characters (emoji, special symbols, smart quotes, box-drawing chars)
- Non-ASCII accented characters
- Unicode arrows, checkmarks, mathematical symbols

**EXAMPLES OF WHAT TO REPLACE:**
- `->` (arrow) is fine in C code contexts
- `[OK]` / `[FAIL]` for status markers
- `>>` for progress indicators
- ASCII quotes only: `"` and `'`, never smart quotes

### Verification

```bash
python3 << 'EOF'
import os
with open('filename.txt', 'rb') as f:
    content = f.read()
    non_ascii = [b for b in content if b > 127]
    if non_ascii:
        print("Contains non-ASCII bytes")
    else:
        print("7-bit ASCII compliant")
EOF
```

## Python Compatibility Requirements

All Python files MUST be compatible with Python 2.7 through 3.15.
Note: Windows CI is tested on 2.7, 3.13, 3.14.  Python 3.16+
is guarded at runtime (`version_minor > 15` in c2py_dlsym.c).

### Required
- `from __future__ import print_function` as the first import in every `.py` file
- Use `%` formatting or `.format()` for strings
- Use `except Exception as e:` syntax (works on both 2.7 and 3.x)

### Forbidden
- **NO f-strings** (`f"hello {name}"`) -- Python 3.6+ only
- **NO type annotations** in generator/parser code (works on 3.x but breaks 2.7)
- **NO `subprocess.run()`** in test runner code (Python 3.5+ only; use `subprocess.call()` or `subprocess.Popen()` for 2.7 compat)
- **NO `pathlib`** (Python 3.4+ only; use `os.path`)
- **NO `importlib.reload`** without version guard

### Structuring Python 2.7 Compatible Code
```python
from __future__ import print_function

import sys

IS_PY3 = sys.version_info[0] >= 3

if IS_PY3:
    import importlib
    importlib.reload(module)
else:
    reload(module)
```

## C Code Constraints

### P0: Portability failure is always our bug

When code does not build or run on a platform, compiler, or Python version,
the root cause is ALWAYS insufficient guards or fallbacks in our codebase.
Never attribute failure to:

- "That compiler doesn't support X"  --  guard non-C99 extensions with `#ifdef`
- "That Python version is too old"  --  we support 2.7 through 3.15
- "The build system doesn't handle that"  --  our code is the common denominator
- "The test output is approximate"  --  tests must be exact
- "That CI runner is quirky"  --  our CI YAML must be robust

Every failure is a missing `#ifdef`, a missing fallback, or a missing check.
Find it. Fix it in c2py23. Never dismiss it.

**Standard C99 is the baseline.** Non-standard extensions (inline assembly,
compiler builtins, intrinsics) must be guarded:

```c
#if defined(_MSC_VER)
    __cpuidex(...)           // MSVC intrinsic
#elif defined(__GNUC__) || defined(__clang__)
    __asm__ __volatile__(...) // GCC/Clang inline assembly
#else
    /* no-op fallback: safe C99, no feature probing */
#endif
```

The `#else` fallback must always compile and run correctly  --  degraded
functionality (no SIMD dispatch, no cycle counter) is acceptable;
compilation failure is not.

- **NEVER include `<Python.h>`** -- all CPython API is resolved at runtime via `dlopen(NULL)` + `dlsym()`
- Generated wrappers include only `"c2py_runtime.h"` and user-specified C headers
- **NO malloc, calloc, realloc, or free** in generated wrapper code
  (user C code may use them internally; any allocated memory must be freed before returning)
- All memory is owned and managed by Python
- Buffers are passed in from Python callers; C functions operate on them in-place
- **restrict can always be assumed** -- the wrapper checks for buffer aliasing at call time and raises `ValueError` if writable buffers overlap
- Use C99 features only (no C11 `_Generic`, no C23)

## Quick Commands

Generate a C wrapper from a .c2py interface:
```bash
c2py23 path/to/module.c2py -o wrapper.c
python -m c2py23 path/to/module.c2py -o wrapper.c  # same, via python -m
```

Build test modules for testing (dlsym mode  --  portable, no libpython):
```bash
python tests/runner.py               # generate + build + test
python tests/runner.py --no-build    # test only (use existing .so files)
```

Build test modules in pythonh mode (per-version, links libpython):
```bash
python tests/setup.py build_ext --inplace --pythonh
```

Build with ASan for leak detection:
```bash
CC=gcc CFLAGS="-fsanitize=address -g -O1" LDFLAGS="-fsanitize=address" \
  python tests/runner.py
```

Build for PyPy (experimental -- smoke test in CI, see issue #81):
```bash
CC=gcc CFLAGS="-DC2PY_TARGET_PYPY -O1" make -f tests/Makefile all
# import on PyPy requires ExtensionFileLoader (plain 'import' does not
# find .so files -- PyPy only recognizes ABI-tagged suffixes).
```

Build for Pyodide/WASM (experimental, no CI):
```bash
# uses emcc, not setuptools  --  kept in tests/test_all_wasm.sh
```

Run the full WASM test suite (80 tests):
```bash
# One-time setup:
sudo apt install nodejs npm emscripten
cd tests/wasm/pyodide_pkg && npm install
pip install -e .

# Build + test:
bash tests/test_all_wasm.sh
```

Install c2py23 in development mode:
```bash
pip install -e .
```

Test a single Python version locally:
```bash
python tests/runner.py
```

Test across all supported Python versions via snakepit containers:
```bash
python3 tests/test_all.py
```

Test the manylinux2014 build-once cross-test strategy:
```bash
python3 tests/test_manylinux.py
```

Build only (no tests) for one Python version on any container:
```bash
python tests/runner.py --no-test
```

Run tests only (no rebuild) for one Python version:
```bash
python tests/runner.py --no-build
```

Valgrind leak check:
```bash
valgrind --leak-check=full python3 tests/test_leaks.py
```

Build a c2py23 module as a multi-platform wheel (see examples/wheel_demo/):
```bash
cd examples/wheel_demo && bash build.sh
```

Populate ABI matrix:
```bash
python3 tests/populate_abi_matrix.py
```

Check NumPy ndarray ABI (required for ndarray fast-path):
```bash
gcc tests/check_numpy_abi.c $(python3-config --includes) \
    -I$(python3 -c 'import numpy; print(numpy.get_include())') \
    $(python3-config --ldflags --embed) -o /tmp/check_numpy_abi
/tmp/check_numpy_abi
```

Check DLPack ABI:
```bash
gcc -std=c99 -Wall tests/check_dlpack_abi.c -o /tmp/check_dlpack_abi
/tmp/check_dlpack_abi
```

Regenerate the committed example wrapper (pre-commit hook runs automatically):
```bash
python3 -m c2py23 tests/cases/transform/transform.c2py \
    -o tests/cases/transform/xfrm_wrapper.c
```

## Committed Example Wrapper

`tests/cases/transform/xfrm_wrapper.c` is committed to git as a reference
example (shape dispatch, 2D buffers, `slow_axis` guard).  A pre-commit
hook (`.githooks/pre-commit`) regenerates it when generator, parser,
runtime, or transform source files change.  It can be compiled without
c2py23 installed -- see the README for the gcc command.

## Supported Python Versions

- **debian10.sif**: Python 3.6
- **ubuntu20.04.sif**: Python 2.7, 3.8
- **ubuntu24.04.sif**: Python 3.7, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
- **ubuntu26.04.sif**: Python 3.14, 3.15
- **manylinux2014.sif**: Python 3.9, 3.10, 3.11, 3.12, 3.13, 3.14

### Experimental: PyPy (smoke test in CI)

- **ubuntu24.04_pypy.sif**: PyPy 2.7, 3.9, 3.11 (local testing)
- CI: pypy3.9 + pypy3.10 via `actions/setup-python@v5`
- Build with `CC=gcc CFLAGS="-DC2PY_TARGET_PYPY -O1" make -f tests/Makefile all`
- `import modulename` does not work on PyPy (only ABI-tagged suffixes).  Use
  `importlib.machinery.ExtensionFileLoader` instead.  See `docs/building.md`.

### `--pythonh`: Direct CPython extension (GraalPy, debugging, max perf)

- Build with `python tests/setup.py build_ext --inplace --pythonh`
- Produces a standard CPython extension with `#include <Python.h>`  --  no dlsym trick
- Required for GraalPy (Native Image exports zero CPython symbols)
- Useful for debugging dlsym issues, static builds, and LTO devirtualization
- See `docs/pythonh.md` for full documentation

### Experimental: Pyodide/WASM (no CI, not tested regularly)

- Build with `c2py23 file.c2py -o wrapper.c` then `emcc -s SIDE_MODULE=1 -I runtime/ wrapper.c src.c runtime/c2py_runtime.c -o module.wasm`
- Uses `emcc -s SIDE_MODULE=1` for Pyodide 3.12+
- Experimental, use at your own risk. No CI -- likely to regress if not maintained.

The snakepit container images must be present at `../snakepit/` relative to this project root.

## Architecture

### Core Files
- `c2py23/parser.py` -- Parses `.c2py` interface files into a ModuleDef AST
- `c2py23/generator.py` -- Transpiles ModuleDef AST into compilable C wrapper source
- `c2py23/cli.py` -- Command-line interface (`c2py23 file.c2py -o wrapper.c`)
- `c2py23/perf.py` -- ctypes-free performance data decoder (uses generated C accessors)
- `c2py23/invariant_checker.py` -- Validates generated C code structure
- `c2py23/c2py_loader.py` -- Multi-platform .so loader
- `c2py23/__init__.py` -- Package init and version string
- `c2py23/runtime/c2py_runtime.h` -- Nimpy-style CPython type definitions and API macros
- `c2py23/runtime/c2py_runtime.c` -- Runtime loader using `dlopen()`/`dlsym()`
- `c2py23/runtime/c2py.h` -- Single-header blob (stb-style), merged from all runtime files
- `c2py23/runtime/merge_single_header.py` -- Script that generates `c2py.h` from runtime sources

### How It Works
1. The user writes a `.c2py` interface file declaring Python function signatures, C overloads, and dispatch conditions
2. `c2py23 file.c2py -o wrapper.c` generates a C wrapper, then compiled with any C99 compiler
3. The `.so` uses the nimpy trick -- no `-lpython` link, all CPython API resolved at init via `dlopen(NULL)`/`dlsym()`. This technique originates from [yglukhov/nimpy](https://github.com/yglukhov/nimpy); c2py23 adopts it for C with a minimal API surface.
4. One `.so` works on Python 2.7 through 3.15 (build on oldest target OS)
5. Buffers are acquired via `c2py_acquire_buffer()` which falls back from PEP 3118 to old buffer API on Python 2.7

### Interface File Format
`.c2py` files define (Python dict format):
- `module:` -- Python module name
- `source:` -- C source file(s)
- `headers:` -- C header file(s) to include (optional)
- `timing:` -- enable per-function perf timing (optional)
- `free_threading:` -- declare module safe for 3.14t (optional)
- `constants:` -- module-level integer constants (optional)
- `functions:` -- list of wrapped functions with:
  - `py_sig:` -- Python signature
  - `expand:` -- template expansion with `${VAR}` substitution (optional)
  - `params:` -- per-parameter descriptions (optional)
  - `checks:` -- pre-conditions (optional)
  - `gil_release:` -- release the GIL during C calls (optional, per-function)
  - `c_overloads:` -- ordered list of C function alternatives with `sig:`, `map:`, `when:`, `outputs:`, `name:`, `variants:`, `group:`, `doc:` (optional)
    `sig:` supports array dimension notation (`const double gv[][3]`, `double arr[5]`),
    which auto-generates buffer shape/contiguity checks.
  - `default_raise:` -- error when no overload matches (optional)
  - `doc:` -- custom docstring (optional)

See `docs/specification.md` for the full grammar.

## Testing

**IMPORTANT: Never guard a test.** If a test fails on a specific platform or
Python version, fix the code, not the test.  Patterns to avoid:

- `pytest.skip(...)` inside a test body for platform-specific bugs
- `pytest.importorskip(...)` for runtime platform problems (import errors are
  fine -- missing optional deps should skip)
- `try: ... except ...: pytest.skip(...)` to swallow bugs
- `@pytest.mark.skipif(...)` for version/platform gating that hides real bugs
- `continue-on-error: true` in CI for test steps that should pass

A failing test is the best signal that code is broken.  Masking the failure
with a guard hides the bug and guarantees it will never be found.  The ONLY
acceptable guards are:

- `memoryview.cast(shape)` on Python 2.7 (API does not exist)
- `_xxsubinterpreters` on Python < 3.12 (module does not exist)

All tests use `ctypes` arrays (buffer protocol works on Python 2.7 and 3.x) and `memoryview` for shape casting. No numpy dependency.

On Python 2.7, the `transform` test is skipped because `memoryview.cast(shape)` is Python 3.3+ only.

Run the test suite:
```bash
python tests/runner.py
```

Run the peer review tests (alias + contiguity, requires numpy):
```bash
pip install numpy
python tests/test_peer_review.py
```

## Debug Builds

For segfault investigation, build with debug symbols and no optimization:
```bash
CC=gcc CFLAGS="-g -O0 -Wall -Werror" python tests/runner.py
```

Then run under GDB:
```bash
gdb --args python3 -c "import sys; sys.path.insert(0,'tests/cases/fill'); import fillmod; ..."
```

With ASan for memory error detection:
```bash
CC=gcc CFLAGS="-fsanitize=address -g -O1" LDFLAGS="-fsanitize=address" python tests/runner.py
```

Valgrind leak check:
```bash
valgrind --leak-check=full python3 tests/test_leaks.py
```

## Next Steps

All project planning and status tracking lives in `PLAN.md`.
AGENTS.md does not duplicate it.  Check `PLAN.md` for:

- **Deferred** items (P3 ppc64le, macOS CI, SIMD Windows/ARM)
- **Outstanding (low-priority)** items (FT globals, 32-bit CI, MSVC, complex types)
- **Completed** items (aarch64 CI, PyPI distribution, wheel packaging, etc.)

Design decisions that are settled as "intentionally unsupported" (keyword
arguments #44, named-tuple returns #42, async/await #41, GPU #40) are
documented in `docs/design.md`.

## Contributing Guidelines

**The `main` branch is protected.** All changes go through pull requests.
LLM agents push to branches, CI runs automatically, a human reviews and merges
via the GitHub website admin override. No direct pushes to `main`.

### Branch protection rules

| Rule | Value |
|------|-------|
| Require PR before merging | yes |
| Require 1 approval | yes |
| Dismiss stale reviews on new commits | yes |
| Require last push approval | yes |
| Administrators can bypass | yes |
| Allow squash merging | only option |
| Allow merge/rebase commits | no |
| Disallow force pushes | yes |
| Disallow deletions | yes |

### LLM agent workflow

1. Create a branch: `git checkout -b issue-NN main`
2. Make changes, commit, push to the branch
3. Open a PR from `issue-NN` -> `main`
4. CI runs automatically on the branch
5. A human reviews and approves on the GitHub website
6. Human merges via admin override (squash merge)

**Never push directly to `main`.** All changes go through pull requests.
The only exception is a human with an admin token using the GitHub website
merge button (squash merge).  Direct `git push` to main must never happen.

PR template is at `.github/PULL_REQUEST_TEMPLATE.md`.

### LLM token access

The LLM agent uses a fine-grained PAT with:
- `contents: write` (restricted to non-`main` branches)
- `pull_requests: write`
- `workflows: write`
- No `administration` permission

The human uses a classic `repo`-scoped token for admin tasks.

### Code guidelines

1. **Always use 7-bit ASCII encoding** -- no unicode characters
2. **Maintain Python 2.7 compatibility** in all Python files
3. **Never include `<Python.h>`** in any C file
4. **No memory allocation in wrappers** -- all memory from Python
5. **No Python string/unicode in wrapper ABI** -- generated C code never
   creates Python strings or unicode objects.  Error messages are C string
   literals.  Variant names use ASCII bytes (`PyBytes_FromStringAndSize`).
   No `PyArg_ParseTupleAndKeywords` (c2py23 is positional-only).
6. Test across all supported Python versions before committing
7. Keep the `.c2py` interface grammar minimal -- new features must be expressible in C without runtime overhead
8. Generated C code should compile with `gcc -Wall -Werror`
9. Run the full test suite before committing: `python tests/runner.py`
10. Run `python3 tests/test_all.py` for multi-version container validation
11. Re-populate the ABI matrix (`python3 tests/populate_abi_matrix.py`) when changing the runtime
12. Run valgrind on leak and error-path tests when changing wrapper generation
13. **Use targeted edits.** Never rewrite an entire file when a surgical
    edit will do.  Use `edit` tool with `oldString`/`newString` for each
    change.  Full-file rewrites destroy history, introduce drift, and
    make diffs unreviewable.  This applies especially to PLAN.md and
    AGENTS.md.
14. **Never embed timing/benchmark results in source code.** Timing numbers
    are measurements, not code.  They come from running benchmarks at a
    specific time on specific hardware.  Putting them in Python comments,
    docstrings, or generated C output is lying  --  the number will be stale
    the next time the benchmark runs.  Print timings to stdout during the
    measurement, report them in the commit message or issue comment, but
    never bake them into the source tree.

## Writing Safe .c2py Definitions

**Always validate buffer dimensions in `checks:` blocks.**  Without size
checks, a caller can pass a too-small output buffer, causing the C function
to write past the end and produce a segfault or silent memory corruption.

### Required checks for every function with buffer parameters:

1. **Format:** `"buf.format == 'd'"` -- ensure element type matches C pointer type
2. **Dimensionality:** `"buf.ndim == 1"` or `"buf.ndim == 2"` -- reject unexpected shapes
3. **Size relationships:** `"ibuf.n == obuf.n"` or `"obuf.n >= ibuf.n + 2"` --
   the single most important check for preventing segfaults

### Example: safe output buffer sizing

```python
# Correct: validates output is large enough
checks:
  - "a.format == 'f'"
  - "out.format == 'f'"
  - "out.n >= a.n"          # output at least as large as input

# Wrong: missing size check -- segfault if out is too small
checks:
  - "a.format == 'f'"
  - "out.format == 'f'"
```

### Additional safe checks to consider:

- **Contiguity:** c2py23 enforces C/F-contiguity automatically, but check for specific
  expectations (e.g., C-order only)
- **Non-empty:** `"buf.n > 0"` when zero-length would be invalid
- **Alignment:** `"(uintptr_t)buf.ptr % alignment == 0"` for SIMD overloads in
  `when:` conditions (the scalar fallback handles misaligned cases)
- **Alias:** c2py23 checks writable buffer aliasing at runtime; add
  `default_raise:` for a clear error message

### Format char portability: never use `'l'` or `'L'` for fixed-width dispatch

The PEP 3118 format characters `'l'` (signed long) and `'L'` (unsigned long)
are **platform-sized**: `sizeof(long)` differs between LP64 (Linux/macOS, 8
bytes) and LLP64 (Windows 64-bit, 4 bytes).  A buffer with format `'l'` has
8-byte elements on Linux but 4-byte elements on Windows.

**Do not rely on `'l'`/`'L'` for fixed-width dispatch.**  Use the format
characters that have guaranteed sizes on all platforms:

| Format | C type | Size (all platforms) |
|--------|--------|---------------------|
| `'i'` / `'I'` | `int32_t` / `uint32_t` | 4 bytes |
| `'q'` / `'Q'` | `int64_t` / `uint64_t` | 8 bytes |

c2py23 generates a runtime `itemsize == sizeof(long)` check alongside format
comparisons for `'l'`/`'L'`, so these characters remain usable if you need
platform-native `long` semantics.  But the generated `.so` or `.pyd` will
dispatch to different C code on different platforms -- do not depend on
`'l'`/`'L'` mapping to a specific fixed-width type.

### Buffer writability and overload dispatch

When a function has multiple overloads, the wrapper acquires each buffer with
`PyBUF_WRITABLE` if **any** overload writes to it. If you add a read-only
overload alongside a writable overload for the same buffer parameter, callers
will be forced to provide writable buffers for the read-only path. Keep this
in mind when mixing read and write overloads.

### Remember:

The C function receives raw pointers with no bounds information. If the
Python caller passes a 100-element output buffer for a function expecting
1000 elements, the C code will write 900 elements past the buffer end.
There is no runtime instrumentation to catch this; the ONLY defense is
the `checks:` block.

## Adding Support for a New Python Version

When adding support for a new Python version (e.g., 3.16):

1. **Get the container.** Add a snakepit image that ships the new version
   (e.g., `ubuntu28.04.sif`). Add it to `tests/test_all.py`.

2. **Audit the CPython headers.** Compile `tests/check_abi.c` against the new
   version's headers inside the container and diff against the previous version:
   ```bash
   apptainer exec ../snakepit/ubuntu28.04.sif bash -c '
     gcc tests/check_abi.c $(pythonX.Y-config --includes --ldflags) -o /tmp/check
     /tmp/check
   '
   ```
   Key things to check in the diff:
   - `sizeof(PyObject)`, `sizeof(Py_buffer)`, `sizeof(PyModuleDef)` -- must match
   - `PyObject.ob_refcnt` and `ob_type` offsets -- must match
   - `PY_MOD_GIL` value -- if changed, audit `PyUnstable_Module_SetGIL` call path in `runtime.c`
   - Symbol availability (any symbols removed?) -- update `c2py_runtime.c`

3. **Run the full test suite** across all containers:
   ```bash
   python3 tests/test_all.py
   ```

4. **Add a row** to the version table in `README.md`.

5. **Bump the version ceiling** in `c2py_runtime.c`:
   ```c
   if (C2PY.version_major >= 3 && C2PY.version_minor > 16) { ...
   ```

6. **Commit** with a message documenting any ABI changes found.

## Keeping Documentation Current

### README.md
When adding a new feature, test case, or changing the public API:
1. Update the "Supported Types" table if new types are supported
2. Update the "Limitations" section when removing or adding restrictions

### AGENTS.md
AGENTS.md is the agent-facing operational guide -- build commands, coding
constraints, testing policy.  It intentionally does not duplicate project
status tracking.  For that, see PLAN.md.
