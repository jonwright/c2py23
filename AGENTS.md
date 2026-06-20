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

- **NEVER include `<Python.h>`** -- all CPython API is resolved at runtime via `dlopen(NULL)` + `dlsym()`
- Generated wrappers include only `"c2py_runtime.h"` and user-specified C headers
- **NO malloc, calloc, realloc, or free** in generated wrapper code
  (user C code may use them internally; any allocated memory must be freed before returning)
- All memory is owned and managed by Python
- Buffers are passed in from Python callers; C functions operate on them in-place
- **restrict can always be assumed** -- the wrapper checks for buffer aliasing at call time and raises `ValueError` if writable buffers overlap
- Use C99 features only (no C11 `_Generic`, no C23)

## Quick Commands

Build a module from a .c2py interface:
```bash
c2py23 build path/to/module.c2py
```

Build with ASan for leak detection:
```bash
c2py23 build --asan path/to/module.c2py
```

Install c2py23 in development mode:
```bash
pip install -e .
```

Test a single Python version locally:
```bash
bash tests/run_tests.sh python3.12
```

Test across all supported Python versions via snakepit containers:
```bash
python3 tests/test_all.py
```

Valgrind leak check:
```bash
valgrind --leak-check=full python3 tests/test_leaks.py
```

Populate ABI matrix:
```bash
python3 tests/populate_abi_matrix.py
```

## Supported Python Versions

- **debian10.sif**: Python 3.6
- **ubuntu20.04.sif**: Python 2.7, 3.8
- **ubuntu24.04.sif**: Python 3.7, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
- **ubuntu26.04.sif**: Python 3.14, 3.15

The snakepit container images must be present at `../snakepit/` relative to this project root.

## Architecture

### Core Files
- `c2py23/parser.py` -- Parses `.c2py` YAML interface files into a ModuleDef AST
- `c2py23/generator.py` -- Transpiles ModuleDef AST into compilable C wrapper source
- `c2py23/cli.py` -- Command-line interface (`c2py23 build`)
- `c2py23/perf.py` -- ctypes-based performance data decoder
- `c2py23/runtime/c2py_runtime.h` -- Nimpy-style CPython type definitions and API macros
- `c2py23/runtime/c2py_runtime.c` -- Runtime loader using `dlopen()`/`dlsym()`

### How It Works
1. The user writes a `.c2py` YAML file declaring Python function signatures, C overloads, and dispatch conditions
2. `c2py23 build` generates a CPython C wrapper and compiles it with gcc into a `.so`
3. The `.so` uses the nimpy trick -- no `-lpython` link, all CPython API resolved at init via `dlopen(NULL)`/`dlsym()`. This technique originates from [yglukhov/nimpy](https://github.com/yglukhov/nimpy); c2py23 adopts it for C with a minimal API surface.
4. One `.so` works on Python 2.7 through 3.15 (build on oldest target OS)
5. Buffers are acquired via `c2py_acquire_buffer()` which falls back from PEP 3118 to old buffer API on Python 2.7

### Interface File Format
YAML-based `.c2py` files define:
- `module:` -- Python module name
- `source:` -- C source file(s)
- `headers:` -- C header file(s) to include (optional)
- `timing:` -- enable per-function perf timing (optional)
- `functions:` -- list of wrapped functions with:
  - `py_sig:` -- Python signature
  - `expand:` -- template expansion with `${VAR}` substitution (optional)
  - `checks:` -- pre-conditions (optional)
  - `gil_release:` -- release the GIL during C calls (optional, per-function)
  - `c_overloads:` -- ordered list of C function alternatives with `sig:`, `map:`, `when:`, `outputs:`, `name:`, `variants:`, `group:` (optional)
  - `default_raise:` -- error when no overload matches (optional)
  - `doc:` -- custom docstring (optional)

See `docs/specification.md` for the full grammar.

## Testing

All tests use `ctypes` arrays (buffer protocol works on Python 2.7 and 3.x) and `memoryview` for shape casting. No numpy dependency.

On Python 2.7, the `transform` test is skipped because `memoryview.cast(shape)` is Python 3.3+ only.

Run the uniform test script directly (requires built `.so` files):
```bash
python tests/test_uniform.py
```

Run the peer review tests (alias + contiguity, requires numpy):
```bash
pip install numpy
python tests/test_peer_review.py
```

## Debug Builds

For segfault investigation, build with debug symbols and no optimization:
```bash
CC=gcc CFLAGS="-g -O0 -Wall -Werror" c2py23 build tests/cases/fill/fill.c2py
```

Then run under GDB:
```bash
gdb --args python3 -c "import sys; sys.path.insert(0,'tests/cases/fill'); import fillmod; ..."
```

With ASan for memory error detection:
```bash
c2py23 build --asan tests/cases/fill/fill.c2py
```

Valgrind leak check:
```bash
valgrind --leak-check=full python3 tests/test_leaks.py
```

## Next Steps

### P2: Windows Port

**Status: Not started. Planning.**

The current codebase is Linux-only:
- `dlopen(NULL)` with `RTLD_GLOBAL` -- on Windows this is `GetModuleHandle(NULL)`
  plus `GetProcAddress()`
- `/proc/cpuinfo` fallback -- use `IsProcessorFeaturePresent()` or CPUID on Windows
- `gcc -shared` with `-ldl` -- MSVC/clang-cl build path needed
- `Py_ssize_t` is `__int64` on 64-bit Windows (LP64 vs LLP64)
- PEP 3118 format chars `'l'`/`'L'` are platform-sized and will differ on LLP64
- `memset`, `snprintf`, `strlen`, `strcmp` -- all standard C99, fine on MSVC

Key work items:
1. Runtime: replace `dlopen`/`dlsym` with Windows equivalents
2. Build system: support MSVC or clang-cl compilation
3. ABI matrix: add a Windows column with LLP64 sizes
4. Test: CI on Windows with native Python

### P4: Binary Wheel Distribution

**Severity: Low -- replaces --no-build-isolation workflow**

**Status: Deferred -- design TBD, implement later.**

Publish binary wheels to PyPI: one per platform (linux, windows, macos) and
one per architecture (x86_64, aarch64). Python-version-independent (the .so
works on 2.7-3.15 via nimpy trick). Similar to ctypes-style distribution --
install via pip, import from any Python version. May need a wrapper import
mechanism or `ctypes.CDLL` loader bootstrap.

## Recently Completed

- P1: SIMD dispatch / CPU feature detection (CPUID x86_64, getauxval ARM64/POWER)
- P3: Reviewer response (addressed all three referee reports)
- P4: Free-threaded Python 3.14+ support (dual PyModuleDef, FT ABI detection)
- Issue #5: Biased refcounting on Python 3.14 standard (PEP 763) -- test guard update
- `pthread_once` init, `_Py_IsGILEnabled()` FT detection fallback, test runner timeouts

See `PLAN.md` Completed section for full details.

## Contributing Guidelines

1. **Always use 7-bit ASCII encoding** -- no unicode characters
2. **Maintain Python 2.7 compatibility** in all Python files
3. **Never include `<Python.h>`** in any C file
4. **No memory allocation in wrappers** -- all memory from Python
5. Test across all supported Python versions before committing
6. Keep the `.c2py` YAML grammar minimal -- new features must be expressible in C without runtime overhead
7. Generated C code should compile with `gcc -Wall -Werror`
8. Run the full test suite before committing: `bash tests/run_tests.sh python3`
9. Run `python3 tests/test_all.py` for multi-version container validation
10. Re-populate the ABI matrix (`python3 tests/populate_abi_matrix.py`) when changing the runtime
11. Run valgrind on leak and error-path tests when changing wrapper generation

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

```yaml
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
   - `sizeof(PyObject)`, `sizeof(Py_buffer)`, `sizeof(PyModuleDef)` — must match
   - `PyObject.ob_refcnt` and `ob_type` offsets — must match
   - `PY_MOD_GIL` value — if changed, update `C2PY.py_mod_gil_slot` in `runtime.c`
   - Symbol availability (any symbols removed?) — update `c2py_runtime.c`

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
1. Update the "Features" list if a new capability is added
2. Update the "Supported Types" table if new types are supported
3. Update the "File Structure" diagram if files/directories are added/removed
4. Verify the test count in "Supported Python Versions":
   ```bash
   python3 -c "import tests.test_uniform; print(len([t for t in dir(tests.test_uniform) if t.startswith('test_')]))"
   ```
5. Update the "Limitations" section when removing or adding restrictions

### AGENTS.md
When completing a task listed in "Next Steps":
1. Mark the status accurately -- do not leave "pending" after implementation
2. Remove or archive completed items
3. When adding new planned items, add them under "Next Steps"
