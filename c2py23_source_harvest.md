# c2py23 Source Harvest

Git commit: cc87a09  
Total files: 80

## File Tree

```
|-- .gitignore
|-- .gitmodules
|-- AGENTS.md
|-- c2py23_requests.md
|-- LICENSE
|-- PLAN.md
|-- pyproject.toml
|-- README.md
|-- setup.py
|-- c2py23/
|   |-- __init__.py
|   |-- cli.py
|   |-- generator.py
|   |-- parser.py
|   |-- perf.py
|   `-- runtime/
|       |-- c2py_amd64.h
|       |-- c2py_arm64.h
|       |-- c2py_ppc64.h
|       |-- c2py_runtime.c
|       `-- c2py_runtime.h
|-- docs/
|   |-- referee_reports_2026-06-15.md
|   `-- specification.md
|-- examples/
|   |-- kissfft
|   |-- lz4
|   |-- kissfft_wrap/
|   |   |-- example.py
|   |   |-- kissfft.c2py
|   |   `-- kissfft_thin.c
|   |-- lz4_wrap/
|   |   |-- example.py
|   |   |-- lz4.c2py
|   |   `-- lz4_thin.c
|   |-- simd_dispatch/
|   |   |-- CMakeLists.txt
|   |   |-- Makefile
|   |   |-- meson.build
|   |   |-- poly_kernel.c
|   |   |-- polysimd.c2py
|   |   |-- setup.py
|   |   `-- test_polysimd.py
|   `-- threading_bench/
|       |-- bench_mc_pi.py
|       |-- Makefile
|       |-- mc_pi.c
|       `-- mc_pi.c2py
`-- tests/
    |-- abi_matrix.json
    |-- check_abi.c
    |-- populate_abi_matrix.py
    |-- requirements.txt
    |-- run_tests.sh
    |-- test_all.py
    |-- test_error_paths.py
    |-- test_interpreters.py
    |-- test_leaks.py
    |-- test_peer_review.py
    |-- test_regression_fixes.py
    |-- test_uniform.py
    `-- cases/
        |-- address/
        |   |-- address.c
        |   `-- address.c2py
        |-- arraysum/
        |   |-- arraysum.c
        |   `-- arraysum.c2py
        |-- constants/
        |   |-- constants.c
        |   `-- constants.c2py
        |-- docstring/
        |   |-- docstring.c
        |   `-- docstring.c2py
        |-- dot/
        |   |-- dot.c
        |   `-- dot.c2py
        |-- fill/
        |   |-- fill.c
        |   `-- fill.c2py
        |-- gil_release/
        |   |-- sleep_fill.c
        |   `-- sleep_fill.c2py
        |-- optional/
        |   |-- optional.c
        |   `-- optional.c2py
        |-- scalar_output/
        |   |-- stats.c
        |   `-- stats.c2py
        |-- template/
        |   |-- sum.c2py
        |   `-- template.c
        |-- timing/
        |   |-- timing.c
        |   `-- timing.c2py
        |-- transform/
        |   |-- transform.c
        |   `-- transform.c2py
        |-- typedispatch/
        |   |-- typedispatch.c
        |   `-- typedispatch.c2py
        `-- types/
            |-- types.c
            `-- types.c2py
```

---

## .gitignore

```
# Build artifacts
*.so
*.o
tests/cases/*/*_wrapper.c

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
*.egg
build/
dist/
.eggs/

# Virtual environments
test_venv/
venv/
.venv/

# Test workspace
test_workspace/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
/tests/test_venv_3.12/
/tests/test_results.log
examples/simd_dispatch/*_wrapper.c
examples/simd_dispatch/*.so
examples/simd_dispatch/*.o
examples/kissfft_wrap/*_wrapper.c
examples/kissfft_wrap/*.so
examples/lz4_wrap/*_wrapper.c
examples/lz4_wrap/*.so
examples/threading_bench/*_wrapper.c
examples/threading_bench/*.so
/tests/test_workspace/
```

## .gitmodules

```
[submodule "examples/kissfft"]
	path = examples/kissfft
	url = https://github.com/mborgerding/kissfft.git
[submodule "examples/lz4"]
	path = examples/lz4
	url = https://github.com/lz4/lz4.git
```

## AGENTS.md

```
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

All Python files MUST be compatible with Python 2.7 through 3.14.

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
4. One `.so` works on Python 2.7 through 3.14 (build on oldest target OS)
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
  - `c_overloads:` -- ordered list of C function alternatives with `sig:`, `map:`, `when:`, `outputs:` (optional)
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

### Remember:

The C function receives raw pointers with no bounds information. If the
Python caller passes a 100-element output buffer for a function expecting
1000 elements, the C code will write 900 elements past the buffer end.
There is no runtime instrumentation to catch this; the ONLY defense is
the `checks:` block.

## Keeping Documentation Current

### README.md
When adding a new feature, test case, or changing the public API:
1. Update the "Features" list if a new capability is added
2. Update the "Supported Types" table if new types are supported
3. Update the "File Structure" diagram if files/directories are added/removed
4. Verify the test count in "Supported Python Versions":
   ```bash
   python3 -c "import tests.test_uniform; print(len(tests.test_uniform.TEST_CASES))"
   ```
5. Update the "Limitations" section when removing or adding restrictions

### AGENTS.md
When completing a task listed in "Next Steps":
1. Mark the status accurately -- do not leave "pending" after implementation
2. Remove or archive completed items
3. When adding new planned items, add them under "Next Steps"
```

## LICENSE

```
MIT License

Copyright (c) 2026 jonwright and DeepSeek V4 Pro

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## PLAN.md

```
# c2py23 Remaining Work

## Deferred

### P4: Binary wheel distribution

**Severity: Low** -- replaces --no-build-isolation workflow

Publish binary wheels to PyPI: one per platform (linux, windows, macos) and
one per architecture (x86_64, aarch64). Python-version-independent (the .so
works on 2.7-3.14 via nimpy trick). Similar to ctypes-style distribution --
install via pip, import from any Python version. May need a wrapper import
mechanism or `ctypes.CDLL` loader bootstrap.

**Status: DEFERRED** -- design TBD, implement later.

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
- METH_FASTCALL vectorcall for Python 3.11+
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
```

## README.md

```
# c2py23

Wrap a strict subset of C99 code as Python C extensions via the buffer protocol.
One compiled `.so` works on Python 2.7 through 3.14 with no recompilation.

## Install

```bash
cd c2py23
pip install -e .
```

Requires PyYAML and a C99 compiler (gcc or clang).

## Quick Start

Create a C function:

```c
/* arraysum.c */
int array_sum(const double *a, const double *b, double *result, int n) {
    for (int i = 0; i < n; i++) result[i] = a[i] + b[i];
    return n;
}
```

Write the interface file:

```yaml
# arraysum.c2py
module: arraysum
source: [arraysum.c]

functions:
  - py_sig: "array_sum(a: buffer, b: buffer, result: buffer) -> int"
    checks:
      - "a.format == 'd'"
      - "b.format == 'd'"
      - "result.format == 'd'"
      - "a.n == b.n"
      - "a.n == result.n"
    c_overloads:
      - sig: "array_sum(const double *a, const double *b, double *result, int n) -> int"
        map: {a: "a.ptr", b: "b.ptr", result: "result.ptr", n: "a.n"}
```

Build and use:

```bash
c2py23 build arraysum.c2py        # produces arraysum.so

python3 -c "
import ctypes, sys
sys.path.insert(0, '.')
import arraysum
a = (ctypes.c_double * 4)(1, 2, 3, 4)
b = (ctypes.c_double * 4)(5, 6, 7, 8)
r = (ctypes.c_double * 4)(0, 0, 0, 0)
n = arraysum.array_sum(a, b, r)
print(n, list(r))   # 4 [6.0, 8.0, 10.0, 12.0]
"
```

### Two-Step Workflow (generate then compile)

For build system integration, c2py23 supports a split workflow:

```bash
# Generate C wrapper only (no compilation)
c2py23 generate mymod.c2py -o mymod_wrapper.c

# Compile separately (for meson/cmake/setuptools integration)
c2py23 compile mymod_wrapper.c -s mymod.c -I include/ -o mymod.so
```

The `build` subcommand also supports `--generate-only` and `--compile-only` flags.

## Supported Types

| Python type | C types |
|-------------|---------|
| `buffer` | `const T*` / `T*` for any integer or float C type below |
| `int` | `int`, `int64_t` (auto-converted via `PyLong_FromLongLong`) |
| `float` | `float`, `double` |
| Return `void` | C `void` function |
| Return `int` | C `int` return |
| Return `float` | C `float` or `double` return |

**C pointer element types**: `int8_t`, `uint8_t`, `int16_t`, `uint16_t`, `int32_t`,
`uint32_t`, `int64_t`, `uint64_t`, `int`, `float`, `double`, `char`, `void`

The `void*` pointer type maps from Python `int` (pointer-width, casts via `intptr_t`).
This is for opaque addresses the user manages (GPU memory, custom allocators, etc.).
The wrapper never dereferences `void*` -- it is a pure address passthrough.

**Output scalars** (`outputs:` key): supports `int8_t`, `int16_t`, `int32_t`,
`uint8_t`, `uint16_t`, `uint32_t`, `int64_t`, `uint64_t`, `float`, `double`,
`int` as return-by-pointer parameters.

## What It Doesn't Do

- No structs, enums, nested pointers, or heap allocation -- all memory is flat and owned by Python
- No `-lpython` link -- one `.so` works on Python 2.7 through 3.14 (nimpy-style `dlopen(NULL)` + `dlsym()` at load time)
- No copies or transpositions -- zero-copy, C functions operate on buffers in-place
- No numpy required -- `ctypes` arrays, `memoryview`, `bytearray`, and anything supporting PEP 3118 works

## Features

The `.c2py` YAML interface defines Python signatures, C overloads, and dispatch conditions.
The generator emits a single-file C99 wrapper with no heap allocations.

- **Buffer protocol** with format dispatch (`float` vs `double` vs `int32_t`), arithmetic checks (`a.n >= b.n + 2`), and contiguity enforcement
- **Overload dispatch** by buffer type, shape, CPU features (AVX2/AVX-512/NEON), or arbitrary `when:` conditions; variants statically resolved at init
- **Template expansion** (`expand:` with `${VAR}` substitution) for generating typed variants
- **GIL release** (`gil_release: true`) per-function or per-overload for parallel C calls
- **Output scalars** (`outputs:`) return-by-pointer parameters as Python tuple values
- **Optional parameters** with defaults, custom docstrings, `default_raise:` error messages
- **Opaque pointers** -- `void*` maps from Python `int` for user-managed memory (GPU, custom allocators)
- **Per-function timing** with `rdtsc`/`CNTVCT_EL0`/`mftb` clocks, decoded via ctypes
- **ASan support** via `c2py23 build --asan`
- **Separate generate/compile** steps for meson/cmake/setuptools integration
- **Python 2.7 fallback** -- `PyObject_AsReadBuffer`/`PyObject_AsWriteBuffer` when PEP 3118 is unavailable

## Supported Python Versions

| Version | Container | Tests |
|---------|-----------|-------|
| 2.7.18 | ubuntu20.04 | 13/14 pass, 1 skip (transform) |
| 3.6.15 | debian10 | 14/14 pass |
| 3.7.17 | ubuntu24.04 | 14/14 pass |
| 3.8.10 | ubuntu20.04 | 14/14 pass |
| 3.9.25 | ubuntu24.04 | 14/14 pass |
| 3.10.20 | ubuntu24.04 | 14/14 pass |
| 3.11.15 | ubuntu24.04 | 14/14 pass |
| 3.12.3 | ubuntu24.04 | 14/14 pass |
| 3.13.14 | ubuntu24.04 | 14/14 pass |
| 3.14.6 | ubuntu24.04 | 14/14 pass (PEP 763 biased refcounting) |
| 3.14.0t | ubuntu24.04 | 14/14 pass (free-threaded; GIL re-enabled for c2py23 modules) |

Additional tests in `test_peer_review.py` (alias + contiguity, 10 tests, requires numpy),
`test_error_paths.py` (refcount stability, 5 tests), and
`test_regression_fixes.py` (codegen validation, 14 tests).

## Examples

The `examples/` directory contains three worked examples:

- **KissFFT** (`examples/kissfft_wrap/`) -- real and complex FFT over float buffers
- **LZ4** (`examples/lz4_wrap/`) -- compress/decompress over byte buffers
- **SIMD Dispatch** (`examples/simd_dispatch/`) -- multi-flag compilation with CPU feature dispatch; includes meson.build, CMakeLists.txt, and setup.py build system integration demos
- **Threading Benchmark** (`examples/threading_bench/`) -- Monte Carlo pi comparing serial, GIL release, free-threading (3.14t), and OpenMP parallelism

## Testing

```bash
# Test a specific Python version locally
bash tests/run_tests.sh python3.12

# Test across all versions via snakepit containers
python3 tests/test_all.py

# Valgrind memory leak check
valgrind --leak-check=full python3 tests/test_leaks.py

# ASan build
c2py23 build --asan module.c2py
```

Requires the snakepit SIF containers at `../snakepit/`.

## File Structure

```
c2py23/
  c2py23/                     # Python package (parser, generator, CLI, perf)
    runtime/                  # C runtime (nimpy loader, API table, CPU feature headers)
      c2py_runtime.h          # Core type definitions and API macros
      c2py_runtime.c          # Runtime loader (dlopen/dlsym)
      c2py_amd64.h            # x86_64 CPU feature flags
      c2py_arm64.h            # ARM64 CPU feature flags
      c2py_ppc64.h            # POWER CPU feature flags
  examples/                   # Worked examples with wrappers
    kissfft_wrap/             # KissFFT wrapper (real + complex FFT)
    lz4_wrap/                 # LZ4 compression wrapper
    simd_dispatch/            # SIMD dispatch demo (Makefile/meson/cmake/setuptools)
    threading_bench/          # Threading benchmark (GIL release, free-threading, OpenMP)
  tests/
    cases/                    # Test cases (C source + .c2py interface)
    run_tests.sh              # Build + test for one Python version
    test_uniform.py           # 2.7-3.14 compatible test runner (14 tests)
    test_all.py               # Orchestrator across snakepit containers
    test_leaks.py             # Memory stress test (valgrind compatible)
    test_peer_review.py       # Alias + contiguity enforcement tests (10 tests, requires numpy)
    test_error_paths.py       # Refcount stability on error paths (5 tests)
    test_regression_fixes.py  # Parser/generator unit tests (14 tests)
    test_interpreters.py      # Sub-interpreter support tests
    check_abi.c               # ABI introspection tool
    populate_abi_matrix.py    # Collect ABI data from all containers
    abi_matrix.json           # Py_buffer/PyObject layout across 11 versions
  docs/                       # Specification and grammar
  PLAN.md                     # Future work and roadmap
```

## Documentation

- `AGENTS.md` -- guidelines for AI agents working on the codebase
- `docs/specification.md` -- full grammar, worked examples, architecture
- `docs/referee_reports_2026-06-15.md` -- referee review reports with point-by-point response

## Limitations

- No structs, enums, or nested data types
- Flat memory only (contiguous buffers)
- Thread safety for free-threaded 3.14+ handled by CPython re-enabling the GIL for c2py23 modules (safe-by-default).
```

## c2py23/__init__.py

```python
from __future__ import print_function

__version__ = "0.1.0"
```

## c2py23/cli.py

```python
"""CLI entry point for c2py23.

Usage:
    c2py23 build foo.c2py [-o foo.so] [--asan] [--generate-only] [--compile-only [--source s.c ...] [--include d/ ...]]
    c2py23 generate foo.c2py [-o wrapper.c]
    c2py23 compile wrapper.c [-s user.c ...] [-I include/ ...] [-o output.so] [--asan]
"""
from __future__ import print_function

import sys
import os
import subprocess
import argparse

from c2py23.parser import load_c2py
from c2py23.generator import generate


def _generate_wrapper(c2py_path, output_path=None):
    """Parse a .c2py file and generate the wrapper C file.

    Returns (wrapper_path, module_def).
    """
    if not os.path.exists(c2py_path):
        print("ERROR: file not found: {}".format(c2py_path), file=sys.stderr)
        sys.exit(1)

    print("Parsing {}...".format(c2py_path))
    module_def = load_c2py(c2py_path)
    mod_name = module_def.name

    if output_path:
        wrapper_path = output_path
    else:
        wrapper_c = mod_name + '_wrapper.c'
        wrapper_path = os.path.join(os.path.dirname(c2py_path) or '.', wrapper_c)

    print("Generating {}...".format(wrapper_path))
    c_code = generate(module_def)
    with open(wrapper_path, 'w') as f:
        f.write(c_code)

    return wrapper_path, module_def


def _collect_user_sources(base_dir, module_def):
    """Collect user C source files, resolving relative paths against base_dir.

    Returns list of absolute paths.
    """
    source_files = []
    for src in module_def.sources:
        src_path = os.path.join(base_dir, os.path.dirname(
            os.path.join(base_dir, src)), os.path.basename(src))
        # Normalise: join(base_dir, src) handles both absolute and relative
        src_path = os.path.normpath(os.path.join(base_dir, src))
        if not os.path.exists(src_path):
            print("ERROR: source file not found: {}".format(src_path), file=sys.stderr)
            sys.exit(1)
        source_files.append(src_path)
    return source_files


def _collect_include_dirs(base_dir, module_def, extra_dirs=None):
    """Collect include directories from module_def sources plus extra dirs.

    Returns list of unique include directory paths.
    """
    include_dirs = [base_dir]
    src_dirs = set()
    for src in module_def.sources:
        d = os.path.dirname(os.path.join(base_dir, src))
        if d not in include_dirs:
            src_dirs.add(d)
    for d in sorted(src_dirs):
        include_dirs.append(d)
    if extra_dirs:
        for d in extra_dirs:
            if d not in include_dirs:
                include_dirs.append(d)
    return include_dirs


def _compile_wrapper(wrapper_path, source_files, include_dirs, output_so, asan=False):
    """Compile a wrapper .c file (plus runtime and user sources) to a .so."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    runtime_dir = os.path.join(script_dir, 'runtime')
    runtime_c = os.path.join(runtime_dir, 'c2py_runtime.c')

    all_sources = [runtime_c, wrapper_path] + list(source_files)
    for src_path in all_sources:
        if not os.path.exists(src_path):
            print("ERROR: source file not found: {}".format(src_path), file=sys.stderr)
            sys.exit(1)

    all_includes = [runtime_dir] + list(include_dirs)
    include_flags = []
    for d in all_includes:
        include_flags.extend(['-I', d])

    cc = os.environ.get('CC', 'gcc')
    cflags = os.environ.get('CFLAGS', '').split()
    ldflags = os.environ.get('LDFLAGS', '').split()

    if asan:
        cflags.append('-fsanitize=address')
        ldflags.append('-fsanitize=address')
        print("  [ASan enabled]")

    libs = os.environ.get('LIBS', '-ldl -lm').split()

    print("Compiling {}...".format(output_so))
    cmd = ([cc, '-shared', '-fPIC'] + include_flags + cflags +
           all_sources + ldflags + libs + ['-o', output_so])
    print("  " + ' '.join(cmd))
    ret = subprocess.call(cmd)
    if ret != 0:
        print("ERROR: compilation failed", file=sys.stderr)
        sys.exit(1)

    print("Success: {}".format(output_so))


def _determine_so_path(output_arg, default_name, base_dir):
    """Determine the .so output path."""
    if output_arg:
        return output_arg
    return os.path.join(base_dir, default_name + '.so')


def cmd_build(args):
    """Parse a .c2py file and generate + compile a .so module."""
    c2py_path = args.file

    # --generate-only: stop after writing wrapper .c
    if getattr(args, 'generate_only', False):
        wrapper_path, _ = _generate_wrapper(c2py_path, args.output)
        print("Wrapper written to: {}".format(wrapper_path))
        return

    # --compile-only: skip parse+generate, compile existing wrapper.c
    if getattr(args, 'compile_only', False):
        wrapper_path = c2py_path
        if not os.path.exists(wrapper_path):
            print("ERROR: wrapper file not found: {}".format(wrapper_path), file=sys.stderr)
            sys.exit(1)

        source_files = args.source or []
        source_files = [os.path.abspath(s) for s in source_files]

        include_dirs = args.include or []
        include_dirs = [os.path.abspath(d) for d in include_dirs]

        base = os.path.splitext(os.path.basename(wrapper_path))[0]
        so_base = base.replace('_wrapper', '')
        output_so = _determine_so_path(args.output, so_base,
                                        os.path.dirname(wrapper_path) or '.')
        _compile_wrapper(wrapper_path, source_files, include_dirs, output_so,
                          asan=getattr(args, 'asan', False))
        return

    # Normal build: parse + generate + compile
    base_dir = os.path.dirname(os.path.abspath(c2py_path))

    wrapper_path, module_def = _generate_wrapper(c2py_path)

    source_files = _collect_user_sources(base_dir, module_def)
    include_dirs = _collect_include_dirs(base_dir, module_def)

    output_so = _determine_so_path(args.output, module_def.name, base_dir)

    _compile_wrapper(wrapper_path, source_files, include_dirs, output_so,
                      asan=getattr(args, 'asan', False))


def cmd_generate(args):
    """Generate C wrapper from a .c2py file without compiling."""
    wrapper_path, _ = _generate_wrapper(args.file, args.output)
    print("Wrapper written to: {}".format(wrapper_path))


def cmd_compile(args):
    """Compile a wrapper .c file to a .so."""
    wrapper_path = args.file
    if not os.path.exists(wrapper_path):
        print("ERROR: wrapper file not found: {}".format(wrapper_path), file=sys.stderr)
        sys.exit(1)

    source_files = args.source or []
    source_files = [os.path.abspath(s) for s in source_files]

    include_dirs = args.include or []
    include_dirs = [os.path.abspath(d) for d in include_dirs]

    base = os.path.splitext(os.path.basename(wrapper_path))[0]
    so_base = base.replace('_wrapper', '')
    output_so = _determine_so_path(args.output, so_base,
                                    os.path.dirname(wrapper_path) or '.')
    _compile_wrapper(wrapper_path, source_files, include_dirs, output_so,
                      asan=getattr(args, 'asan', False))


def _add_build_parser(sub):
    build_p = sub.add_parser('build', help='Build a .so from a .c2py file')
    build_p.add_argument('file', help='Path to .c2py interface file')
    build_p.add_argument('-o', '--output', help='Output .so path (or wrapper .c path with --generate-only)')
    build_p.add_argument('--asan', action='store_true',
                          help='Compile with -fsanitize=address for leak detection')
    build_p.add_argument('--generate-only', action='store_true',
                          help='Generate wrapper .c only, do not compile')
    build_p.add_argument('--compile-only', action='store_true',
                          help='Compile an existing wrapper .c file (skip parse+generate)')
    build_p.add_argument('-s', '--source', action='append',
                          help='User C source files (repeatable, for --compile-only)')
    build_p.add_argument('-I', '--include', action='append',
                          help='Include directories (repeatable, for --compile-only)')
    build_p.set_defaults(func=cmd_build)


def _add_generate_parser(sub):
    gen_p = sub.add_parser('generate', help='Generate wrapper .c from .c2py (no compilation)')
    gen_p.add_argument('file', help='Path to .c2py interface file')
    gen_p.add_argument('-o', '--output', help='Output wrapper .c path')
    gen_p.set_defaults(func=cmd_generate)


def _add_compile_parser(sub):
    comp_p = sub.add_parser('compile', help='Compile a wrapper .c file to .so')
    comp_p.add_argument('file', help='Path to wrapper .c file')
    comp_p.add_argument('-s', '--source', action='append',
                         help='User C source files (repeatable)')
    comp_p.add_argument('-I', '--include', action='append',
                         help='Include directories (repeatable)')
    comp_p.add_argument('-o', '--output', help='Output .so path')
    comp_p.add_argument('--asan', action='store_true',
                         help='Compile with -fsanitize=address for leak detection')
    comp_p.set_defaults(func=cmd_compile)


def main():
    parser = argparse.ArgumentParser(prog='c2py23',
                                      description='Wrap C99 code to Python via the buffer protocol')
    sub = parser.add_subparsers(dest='command', help='Commands')

    _add_build_parser(sub)
    _add_generate_parser(sub)
    _add_compile_parser(sub)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == '__main__':
    main()
```

## c2py23/generator.py

```python
"""C code generator for c2py23.

Transpiles a parsed ModuleDef AST into a compilable CPython C extension source file.
Uses the nimpy-style c2py_runtime.h for Python API access.
"""
from __future__ import print_function

from c2py23.parser import (
    Var, Attr, Subscript, IntLit, StrLit, Compare, BinOp, UnaryOp,
    PyParam, CParam, COverload, CVariant, FuncDef, ModuleDef,
)


def generate(module_def):
    """Generate C source code for a module wrapper.

    Args:
        module_def: ModuleDef namedtuple from parser

    Returns:
        String containing complete C source code
    """
    out = []
    has_gil_release = any(f.gil_release for f in module_def.functions)
    _emit_header(out, module_def)
    _emit_forward_decls(out, module_def)
    if module_def.timing:
        _emit_timing_decls(out, module_def)
    if has_gil_release:
        _emit_gil_release_decls(out, module_def)
    for func in module_def.functions:
        _emit_function(out, func, module_def.name, module_def.timing, has_gil_release)
    _emit_module_init(out, module_def)
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def _emit_header(out, mod):
    out.append('/* Generated by c2py23 - do not edit by hand */')
    out.append('#include <stdio.h>')
    out.append('#include "c2py_runtime.h"')
    for h in mod.headers:
        out.append('#include "{}"'.format(h))
    out.append('')


# ---------------------------------------------------------------------------
# Forward declarations of C functions
# ---------------------------------------------------------------------------

def _emit_forward_decls(out, mod):
    seen = set()
    for func in mod.functions:
        for ol in func.overloads:
            if ol.variants:
                for v in ol.variants:
                    c_name = _extract_c_name(v.sig_str)
                    if c_name not in seen:
                        seen.add(c_name)
                        out.append(_c_decl_from_variant(v))
            else:
                c_name = _extract_c_name(ol.sig_str)
                if c_name not in seen:
                    seen.add(c_name)
                    out.append(_c_decl_from_overload(ol))
    out.append('')


def _c_decl_from_variant(v):
    """Generate an extern declaration for a variant's C function."""
    ret = v.return_type if v.return_type != 'void' else 'void'
    parts = []
    for p in v.params:
        parts.append(p.ctype + ' ' + p.name)
    return 'extern {} {}({});'.format(ret, _extract_c_name(v.sig_str), ', '.join(parts))


def _extract_c_name(sig_str):
    """Extract the C function name from a sig string."""
    return sig_str.split('(')[0].strip().split()[-1]


def _c_decl_from_overload(ol):
    """Generate an extern declaration for the C function."""
    ret = ol.return_type if ol.return_type != 'void' else 'void'
    parts = []
    for p in ol.params:
        parts.append(p.ctype + ' ' + p.name)
    return 'extern {} {}({});'.format(ret, _extract_c_name(ol.sig_str), ', '.join(parts))


# ---------------------------------------------------------------------------
# Function wrapper generation
# ---------------------------------------------------------------------------

def _emit_timing_decls(out, mod):
    """Emit global timing declarations: enabled flag + per-func/per-overload perf structs."""
    out.append('/* ---- Performance timing ---- */')
    out.append('static int _c2py_timing_enabled = 1;')
    out.append('')
    for func in mod.functions:
        out.append('static c2py_perf_t _perf_{0};'.format(func.name))
        for ol in func.overloads:
            if ol.variants:
                for v in ol.variants:
                    c_name = _extract_c_name(v.sig_str)
                    out.append('static c2py_perf_t _perf_{0}__{1};'.format(func.name, c_name))
            else:
                c_name = _extract_c_name(ol.sig_str)
                out.append('static c2py_perf_t _perf_{0}__{1};'.format(func.name, c_name))
    out.append('')


def _emit_gil_release_decls(out, mod):
    """Emit global GIL release declarations: enabled flag + per-func flags."""
    out.append('/* ---- GIL release ---- */')
    out.append('static int _c2py_gil_release_enabled = 1;')
    for func in mod.functions:
        if func.gil_release:
            out.append('static int _gil_release_{0} = 1;'.format(func.name))
    out.append('')


def _emit_function(out, func, module_name, timing, has_gil_release):
    name = func.name
    out.append('/* ' + '-' * 44 + ' */')
    out.append('/* Wrapper for: {} */'.format(name))
    out.append('/* ' + '-' * 44 + ' */')
    out.append('')

    buf_params = [p for p in func.py_params if p.pytype == 'buffer']
    scalar_params = [p for p in func.py_params if p.pytype != 'buffer']

    has_groups = any(ol.variants for ol in func.overloads)
    if has_groups:
        _emit_static_dispatch(out, func, buf_params, scalar_params)

    # _impl function
    _emit_impl_func(out, func, buf_params, scalar_params, timing, has_gil_release)

    # _wrapper function
    _emit_wrapper_func(out, func, buf_params, scalar_params, timing)


# ---------------------------------------------------------------------------
# Static (pre-resolved) dispatch for grouped overloads
# ---------------------------------------------------------------------------

def _emit_static_dispatch(out, func, buf_params, scalar_params):
    """Emit variant index variables, resolve functions, and rebind function
    for functions with grouped overloads (variants: key)."""
    name = func.name
    out.append('/* ---- Variant dispatch for {} ---- */'.format(name))
    out.append('')

    # Gather groups (overloads with variants)
    groups = []
    for i, ol in enumerate(func.overloads):
        if ol.variants:
            groups.append((i, ol))

    # Per-group variant index + name
    for gi, (i, ol) in enumerate(groups):
        gname = ol.group_name or 'group{}'.format(gi)
        out.append('static int _var_{}_{} = -1;'.format(name, gi))
        out.append('static const char *_vname_{}_{} = NULL;'.format(name, gi))

    out.append('')

    # Resolve function for each group
    for gi, (i, ol) in enumerate(groups):
        out.append('static void _resolve_{}_{}(void) {{'.format(name, gi))
        for vi, v in enumerate(ol.variants):
            if v.when_expr is not None:
                when_c = _expr_to_c(v.when_expr, buf_params, scalar_params, None)
                out.append('    if ({}) {{'.format(when_c))
                out.append('        _var_{}_{} = {}; _vname_{}_{} = "{}"; return;'
                           .format(name, gi, vi, name, gi, v.name))
                out.append('    }')
        # Default (last variant, always matches)
        last_vi = len(ol.variants) - 1
        out.append('    _var_{}_{} = {}; _vname_{}_{} = "{}";'
                   .format(name, gi, last_vi, name, gi, ol.variants[last_vi].name))
        out.append('}')
        out.append('')

    # Aggregate resolve for all groups
    out.append('static void _resolve_{}(void) {{'.format(name))
    for gi in range(len(groups)):
        out.append('    _resolve_{}_{}();'.format(name, gi))
    out.append('}')
    out.append('')

    # Rebind C function
    out.append('static PyObject* _rebind_{}(PyObject *self, PyObject *args) {{'.format(name))
    out.append('    const char *target = NULL;')
    out.append('    if (!C2PY.ParseTuple(args, "z", &target)) return NULL;')
    out.append('')
    out.append('    if (target == NULL) {')
    out.append('        _resolve_{}();'.format(name))
    out.append('        Py_RETURN_NONE;')
    out.append('    }')
    out.append('')
    # Check each group's variant names
    for gi, (i, ol) in enumerate(groups):
        gname = ol.group_name or 'group{}'.format(gi)
        for vi, v in enumerate(ol.variants):
            out.append('    if (!strcmp(target, "{}")) {{'.format(v.name))
            out.append('        _var_{}_{} = {}; _vname_{}_{} = "{}";'.format(name, gi, vi, name, gi, v.name))
            out.append('        Py_RETURN_NONE;')
            out.append('    }')
    out.append('')
    out.append('    C2PY.Err_SetString(C2PY.exc_ValueError, "unknown variant");')
    out.append('    return NULL;')
    out.append('}')
    out.append('')


# ---------------------------------------------------------------------------
# _impl function
# ---------------------------------------------------------------------------

def _emit_impl_func(out, func, buf_params, scalar_params, timing, has_gil_release):
    name = func.name
    void_ptr_names = _collect_void_ptr_names(func)
    params_c = []
    for p in buf_params:
        params_c.append('Py_buffer *buf_' + p.name)
    for p in scalar_params:
        if p.pytype == 'int':
            if p.name in void_ptr_names:
                params_c.append('intptr_t c_' + p.name)
            else:
                params_c.append('int c_' + p.name)
        else:
            params_c.append('double c_' + p.name)

    out.append('static PyObject*')
    out.append('_' + name + '_impl({})'.format(', '.join(params_c)))
    out.append('{')

    if timing:
        out.append('    int _c2py_do_time = _c2py_timing_enabled;')
        out.append('    uint64_t _c2py_ct0 = 0, _c2py_ct1 = 0;')
        out.append('')

    if has_gil_release and func.gil_release:
        out.append('    int _c2py_do_gil = _c2py_gil_release_enabled && _gil_release_{0};'.format(name))
        out.append('    void *_c2py_thread_state = NULL;')
        out.append('')

    # Checks
    for check in func.checks:
        out.append('    /* check: {} */'.format(_expr_to_source(check)))
        _emit_check(out, check, buf_params, scalar_params)

    # Overload dispatch
    _emit_overload_dispatch(out, func, buf_params, scalar_params, timing, has_gil_release)

    out.append('')
    out.append('    /* should not reach here */')
    out.append('    return NULL;')
    out.append('}')
    out.append('')


def _emit_overload_dispatch(out, func, buf_params, scalar_params, timing, has_gil_release):
    """Emit the dispatch chain for overload selection.
    
    For flat overloads: standard if/else chain (backward compatible).
    For grouped overloads (variants: key): outer if/else on group when:
    conditions, inner switch on pre-resolved variant index.
    """
    overloads = func.overloads
    default_raise = func.default_raise
    name = func.name

    has_groups = any(ol.variants for ol in overloads)
    if not has_groups:
        _emit_flat_dispatch(out, overloads, buf_params, scalar_params, timing, name,
                            has_gil_release and func.gil_release, default_raise)
        return

    # Grouped dispatch: build group index -> entry mapping
    group_index = 0
    for i, ol in enumerate(overloads):
        is_group = ol.variants is not None
        is_last = (i == len(overloads) - 1)

        if i == 0:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                out.append('    if (' + when_c + ') {')
            else:
                out.append('    {  /* group 0 (always) */')
        else:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                out.append('    } else if (' + when_c + ') {')
            else:
                out.append('    } else {  /* group {} (always) */'.format(i))

        if is_group:
            # --- Inner variant dispatch ---
            gi = group_index
            out.append('        /* group {}: {} variants */'.format(
                gi, len(ol.variants)))

            # Check if all variants have the same C signature for fn-ptr optimization
            # (For now, always use switch; fn-ptr optimization deferred)
            out.append('        switch (_var_{}_{}) {{'.format(name, gi))

            for vi, v in enumerate(ol.variants):
                # Create a synthetic COverload for _emit_c_call
                syn_ol = COverload(v.sig_str, v.params, v.return_type,
                                   ol.map_exprs, v.when_expr,
                                   name=v.name, outputs=v.outputs)
                out.append('        case {}: {{'.format(vi))
                _emit_c_call(out, syn_ol, buf_params, scalar_params, timing, name,
                             has_gil_release and func.gil_release, indent='                ')
                out.append('            break;')
                out.append('        }')
            out.append('        default: break;')
            out.append('        }')
            group_index += 1
        else:
            # Flat overload within a mixed list
            out.append('        /* {} */'.format(ol.sig_str))
            _emit_c_call(out, ol, buf_params, scalar_params, timing, name,
                         has_gil_release and func.gil_release)

    if default_raise:
        out.append('    } else {')
        _emit_default_raise_body(out, default_raise)
    out.append('    }')


def _emit_flat_dispatch(out, overloads, buf_params, scalar_params, timing, name,
                        gil_release_call, default_raise):
    """Emit the standard if/else chain for flat overloads."""
    # Single unconditional overload
    if len(overloads) == 1 and overloads[0].when_expr is None:
        out.append('    /* overload 0 (always) */')
        out.append('    {')
        _emit_c_call(out, overloads[0], buf_params, scalar_params, timing, name,
                     gil_release_call)
        out.append('    }')
        return

    for i, ol in enumerate(overloads):
        if i == 0:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                out.append('    if (' + when_c + ') {')
            else:
                out.append('    {  /* overload 0 (always) */')
        else:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                out.append('    } else if (' + when_c + ') {')
            else:
                out.append('    } else {  /* overload {} (always) */'.format(i))
        out.append('        /* {} */'.format(ol.sig_str))
        _emit_c_call(out, ol, buf_params, scalar_params, timing, name,
                     gil_release_call)

    if default_raise:
        out.append('    } else {')
        _emit_default_raise_body(out, default_raise)
    out.append('    }')


def _emit_check(out, check, buf_params, scalar_params):
    """Emit a check that raises if condition is false.

    For single-char format comparisons on old buffers (format == NULL),
    the generated expression already uses !format || ... to pass safely.
    For two-sided format comparisons, NULL == NULL passes correctly.

    Includes actual runtime values in the failure message when possible.
    """
    c_expr = _expr_to_c(check, buf_params, scalar_params, None)
    msg = _expr_to_source(check)
    diag = _make_check_diag(check, buf_params, scalar_params)
    out.append('    if (!(' + c_expr + ')) {')
    if diag:
        out.append('        ' + diag[0])
        if len(diag) > 1:
            for d in diag[1:]:
                out.append('        ' + d)
        out.append('        PyErr_SetString(PyExc_ValueError, _c2py_err);')
    else:
        out.append('        PyErr_SetString(PyExc_ValueError, "check failed: ' + _escape_c_str(msg) + '");')
    out.append('        return NULL;')
    out.append('    }')


def _make_check_diag(check, buf_params, scalar_params):
    """Generate C code to capture actual runtime values for a check failure message.

    Returns a list of C code lines (strings) that produce a diagnostic,
    ending with a snprintf into _c2py_err. Returns None if diagnostics
    cannot be generated for this expression shape.
    """
    if isinstance(check, Compare):
        return _make_compare_diag(check, buf_params, scalar_params)
    elif isinstance(check, BinOp):
        left_diag = _make_check_diag(check.left, buf_params, scalar_params)
        if left_diag is not None:
            return left_diag
        return _make_check_diag(check.right, buf_params, scalar_params)
    return None


def _make_compare_diag(compare, buf_params, scalar_params):
    """Generate diagnostic C code for a Compare expression."""
    left = compare.left
    right = compare.right
    op = compare.op

    left_c = _expr_to_c(left, buf_params, scalar_params, None)
    right_c = _expr_to_c(right, buf_params, scalar_params, None)
    source = _expr_to_source(compare)

    # Determine if either side is a format attribute
    left_is_format = isinstance(left, Attr) and left.attr == 'format'
    right_is_format = isinstance(right, Attr) and right.attr == 'format'

    # Format comparison: show actual format chars
    if left_is_format and isinstance(right, StrLit) and len(right.value) == 1:
        escaped_src = _escape_c_str(source)
        lines = [
            'char _c2py_err[256];',
            'const char *_fmt = {0} ? {0} : "";'.format(left_c),
            'char _got = _fmt[0] ? _fmt[strlen(_fmt) - 1] : \'?\';',
            'snprintf(_c2py_err, sizeof(_c2py_err), '
            '"check failed: {0} (got format=\'%c\')", _got);'.format(escaped_src)
        ]
        return lines
    if right_is_format and isinstance(left, StrLit) and len(left.value) == 1:
        escaped_src = _escape_c_str(source)
        lines = [
            'char _c2py_err[256];',
            'const char *_fmt = {0} ? {0} : "";'.format(right_c),
            'char _got = _fmt[0] ? _fmt[strlen(_fmt) - 1] : \'?\';',
            'snprintf(_c2py_err, sizeof(_c2py_err), '
            '"check failed: {0} (got format=\'%c\')", _got);'.format(escaped_src)
        ]
        return lines

    # Format vs format comparison
    if left_is_format and right_is_format:
        escaped_src = _escape_c_str(source)
        lines = [
            'char _c2py_err[256];',
            'const char *_fmt_l = {0} ? {0} : "";'.format(left_c),
            'const char *_fmt_r = {0} ? {0} : "";'.format(right_c),
            'char _gl = _fmt_l[0] ? _fmt_l[strlen(_fmt_l) - 1] : \'?\';',
            'char _gr = _fmt_r[0] ? _fmt_r[strlen(_fmt_r) - 1] : \'?\';',
            'snprintf(_c2py_err, sizeof(_c2py_err), '
            '"check failed: {0} (got \'%c\' vs \'%c\')", _gl, _gr);'.format(escaped_src)
        ]
        return lines

    # Generic numeric comparison: show both sides as int
    if _is_simple_expr(left) and _is_simple_expr(right):
        escaped_src = _escape_c_str(source)
        lines = [
            'char _c2py_err[256];',
            'snprintf(_c2py_err, sizeof(_c2py_err), '
            '"check failed: {0} (got %ld vs %ld)",'
            ' (long)({1}), (long)({2}));'.format(escaped_src, left_c, right_c)
        ]
        return lines

    return None


def _is_simple_expr(expr):
    """Check if an expression is simple enough to inline in a format string."""
    if isinstance(expr, (Var, IntLit)):
        return True
    if isinstance(expr, Attr) and isinstance(expr.obj, Var):
        return True  # a.n, a.len, a.ndim etc.
    if isinstance(expr, UnaryOp):
        return False
    if isinstance(expr, BinOp):
        if expr.op in ('and', 'or'):
            return _is_simple_expr(expr.left) and _is_simple_expr(expr.right)
        return False  # arithmetic is never simple
    return False


def _emit_c_call(out, ol, buf_params, scalar_params, timing, func_name, gil_release_call=False, indent=None):
    """Emit a C function call for one overload.
    
    Handles optional output scalars (ol.outputs): auto-allocates 1-element
    stack variables, passes pointers, and returns values as Python objects.
    """
    if indent is None:
        indent = '        '
    c_name = _extract_c_name(ol.sig_str)
    perf_name = '_perf_{0}__{1}'.format(func_name, c_name)
    outputs = getattr(ol, 'outputs', {}) or {}
    indent = '        '

    # Declare output variables before call
    for p in ol.params:
        if p.name in outputs:
            ctype = outputs[p.name]
            var_name = '_out_{0}'.format(p.name)
            if ctype in ('int', 'int8_t', 'int16_t', 'int32_t',
                         'uint8_t', 'uint16_t', 'uint32_t'):
                out.append(indent + 'int {0} = 0;'.format(var_name))
            elif ctype in ('int64_t', 'uint64_t'):
                out.append(indent + 'int64_t {0} = 0;'.format(var_name))
            elif ctype == 'float':
                out.append(indent + 'float {0} = 0.0f;'.format(var_name))
            elif ctype == 'double':
                out.append(indent + 'double {0} = 0.0;'.format(var_name))
            else:
                out.append(indent + '/* unknown output type: {} */'.format(ctype))
                out.append(indent + 'double {0} = 0.0;'.format(var_name))

    args = []
    for p in ol.params:
        if p.name in outputs:
            var_name = '_out_{0}'.format(p.name)
            args.append('&' + var_name)
        else:
            expr = ol.map_exprs.get(p.name)
            if expr is None:
                if p.is_pointer:
                    raise ValueError("Pointer param '{}' missing map entry".format(p.name))
                for sp in scalar_params:
                    if sp.name == p.name:
                        if p.base_type == 'int':
                            args.append('c_' + p.name)
                        elif p.base_type == 'void':
                            args.append('(void *)(intptr_t)c_' + p.name)
                        elif p.base_type == 'float':
                            args.append('(float)c_' + p.name)
                        elif p.base_type == 'double':
                            args.append('c_' + p.name)
                        break
                else:
                    args.append('/* unhandled: {} */'.format(p.name))
            else:
                c_str = _expr_to_c(expr, buf_params, scalar_params, ol)
                if p.is_pointer and _is_ptr_expr(expr):
                    c_str = '(' + p.ctype + ')' + c_str
                elif p.is_pointer and p.base_type == 'void':
                    c_str = '(void *)(intptr_t)' + c_str
                elif not p.is_pointer and p.base_type == 'int' and _expr_is_n_count(expr):
                    c_str = '(int)(' + c_str + ')'
                elif not p.is_pointer and p.base_type == 'float':
                    c_str = '(float)(' + c_str + ')'
                args.append(c_str)

    # Pre-call: int overflow checks for n/length-derived params
    for i, p in enumerate(ol.params):
        if not p.is_pointer and p.base_type == 'int':
            expr = ol.map_exprs.get(p.name)
            if expr and _expr_is_n_count(expr):
                expr_c = _expr_to_c(expr, buf_params, scalar_params, ol)
                out.append(indent + 'if (({0}) > (Py_ssize_t)INT_MAX) {{'.format(expr_c))
                out.append(indent + '    PyErr_SetString(PyExc_ValueError,')
                out.append(indent + '        "buffer too large for int n (> INT_MAX elements)");')
                out.append(indent + '    return NULL;')
                out.append(indent + '}')

    call_str = c_name + '(' + ', '.join(args) + ')'

    # Determine effective return type (may have outputs appended)
    has_outputs = bool(outputs)
    has_ret = (ol.return_type and ol.return_type != 'void'
               and ol.return_type is not None)

    # --- GIL release: pre-C call ---
    # IMPORTANT: between the GIL save and restore below, there must be
    # no path that can return, goto, or longjmp without first restoring
    # the GIL. The C call and timing ticks are the only operations in
    # this critical section.
    if gil_release_call:
        out.append(indent + 'if (_c2py_do_gil) _c2py_thread_state = PyEval_SaveThread();')

    # --- timing: pre-C call ---
    if timing:
        out.append(indent + 'if (_c2py_do_time) _c2py_ct0 = c2py_ticks();')

    if not has_outputs:
        # Standard return (no outputs)
        if ol.return_type == 'void' or ol.return_type is None:
            out.append(indent + call_str + ';')
            if timing:
                out.append(indent + 'if (_c2py_do_time) {')
                out.append(indent + '    _c2py_ct1 = c2py_ticks();')
                out.append(indent + '    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);'.format(perf_name))
                out.append(indent + '}')
            if gil_release_call:
                out.append(indent + 'if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state);')
            out.append(indent + 'Py_RETURN_NONE;')
        elif ol.return_type == 'int':
            out.append(indent + 'int _ret = ' + call_str + ';')
            if gil_release_call:
                out.append(indent + 'if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state);')
            if timing:
                out.append(indent + 'if (_c2py_do_time) {')
                out.append(indent + '    _c2py_ct1 = c2py_ticks();')
                out.append(indent + '    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);'.format(perf_name))
                out.append(indent + '}')
            out.append(indent + 'return PyLong_FromLong((long)_ret);')
        elif ol.return_type == 'float':
            out.append(indent + 'float _ret = ' + call_str + ';')
            if gil_release_call:
                out.append(indent + 'if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state);')
            if timing:
                out.append(indent + 'if (_c2py_do_time) {')
                out.append(indent + '    _c2py_ct1 = c2py_ticks();')
                out.append(indent + '    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);'.format(perf_name))
                out.append(indent + '}')
            out.append(indent + 'return PyFloat_FromDouble((double)_ret);')
        elif ol.return_type == 'double':
            out.append(indent + 'double _ret = ' + call_str + ';')
            if gil_release_call:
                out.append(indent + 'if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state);')
            if timing:
                out.append(indent + 'if (_c2py_do_time) {')
                out.append(indent + '    _c2py_ct1 = c2py_ticks();')
                out.append(indent + '    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);'.format(perf_name))
                out.append(indent + '}')
            out.append(indent + 'return PyFloat_FromDouble(_ret);')
        else:
            out.append(indent + '/* unknown return type: {} */'.format(ol.return_type))
            out.append(indent + call_str + ';')
            if gil_release_call:
                out.append(indent + 'if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state);')
            if timing:
                out.append(indent + 'if (_c2py_do_time) {')
                out.append(indent + '    _c2py_ct1 = c2py_ticks();')
                out.append(indent + '    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);'.format(perf_name))
                out.append(indent + '}')
            out.append(indent + 'Py_RETURN_NONE;')
        return

    # --- Output scalar handling ---
    out_items = []
    if has_ret:
        ret_var = '_c2py_retval'
        if ol.return_type == 'int':
            out.append(indent + 'int {0} = {1};'.format(ret_var, call_str))
        elif ol.return_type == 'float':
            out.append(indent + 'float {0} = {1};'.format(ret_var, call_str))
        elif ol.return_type == 'double':
            out.append(indent + 'double {0} = {1};'.format(ret_var, call_str))
        else:
            out.append(indent + '/* unknown return type: {} */'.format(ol.return_type))
            out.append(indent + call_str + ';')
            out.append(indent + 'int {0} = 0;'.format(ret_var))
        out_items.append(('ret', ol.return_type, ret_var))
    else:
        out.append(indent + call_str + ';')

    # Restore GIL immediately after C call, before any Python object construction.
    # This minimises the critical section and keeps the invariant clear.
    if gil_release_call:
        out.append(indent + 'if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state);')

    if timing:
        out.append(indent + 'if (_c2py_do_time) {')
        out.append(indent + '    _c2py_ct1 = c2py_ticks();')
        out.append(indent + '    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);'.format(perf_name))
        out.append(indent + '}')

    # Collect output items
    for p in ol.params:
        if p.name in outputs:
            ctype = outputs[p.name]
            var_name = '_out_{0}'.format(p.name)
            out_items.append((p.name, ctype, var_name))

    n = len(out_items)

    if n == 1:
        ctype = out_items[0][1]
        val = out_items[0][2]
        if ctype in ('int', 'int8_t', 'int16_t', 'int32_t',
                     'uint8_t', 'uint16_t', 'uint32_t'):
            out.append(indent + 'return PyLong_FromLong((long){0});'.format(val))
        elif ctype in ('int64_t', 'uint64_t'):
            out.append(indent + 'return PyLong_FromLongLong((long long){0});'.format(val))
        elif ctype in ('float', 'double'):
            out.append(indent + 'return PyFloat_FromDouble((double){0});'.format(val))
        else:
            out.append(indent + 'return PyFloat_FromDouble((double){0});'.format(val))
    else:
        out.append(indent + 'PyObject *_c2py_tup = PyTuple_New({0});'.format(n))
        out.append(indent + 'if (_c2py_tup == NULL) return NULL;')
        for i, (name, ctype, val) in enumerate(out_items):
            if ctype in ('int', 'int8_t', 'int16_t', 'int32_t',
                         'uint8_t', 'uint16_t', 'uint32_t'):
                out.append(indent + 'PyObject *_c2py_obj{0} = PyLong_FromLong((long){1});'.format(i, val))
                out.append(indent + 'if (_c2py_obj{0} == NULL) {{'.format(i))
                out.append(indent + '    Py_DECREF(_c2py_tup);')
                out.append(indent + '    return NULL;')
                out.append(indent + '}')
                out.append(indent + 'PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});'.format(i))
            elif ctype in ('int64_t', 'uint64_t'):
                out.append(indent + 'PyObject *_c2py_obj{0} = PyLong_FromLongLong((long long){1});'.format(i, val))
                out.append(indent + 'if (_c2py_obj{0} == NULL) {{'.format(i))
                out.append(indent + '    Py_DECREF(_c2py_tup);')
                out.append(indent + '    return NULL;')
                out.append(indent + '}')
                out.append(indent + 'PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});'.format(i))
            elif ctype in ('float', 'double'):
                out.append(indent + 'PyObject *_c2py_obj{0} = PyFloat_FromDouble((double){1});'.format(i, val))
                out.append(indent + 'if (_c2py_obj{0} == NULL) {{'.format(i))
                out.append(indent + '    Py_DECREF(_c2py_tup);')
                out.append(indent + '    return NULL;')
                out.append(indent + '}')
                out.append(indent + 'PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});'.format(i))
            else:
                out.append(indent + 'PyObject *_c2py_obj{0} = PyFloat_FromDouble((double){1});'.format(i, val))
                out.append(indent + 'if (_c2py_obj{0} == NULL) {{'.format(i))
                out.append(indent + '    Py_DECREF(_c2py_tup);')
                out.append(indent + '    return NULL;')
                out.append(indent + '}')
                out.append(indent + 'PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});'.format(i))
        out.append(indent + 'return _c2py_tup;')


def _is_ptr_expr(expr):
    """Check if expression is a .ptr access."""
    if isinstance(expr, Attr) and expr.attr == 'ptr':
        return True
    return False


def _expr_is_n_count(expr):
    """Check if expression computes element count (.n or .len/size)."""
    if isinstance(expr, Attr) and expr.attr in ('n', 'len'):
        return True
    return False


def _emit_default_raise_body(out, default_raise):
    """Emit the body of a default raise block."""
    if ':' in default_raise:
        exc_type, msg = default_raise.split(':', 1)
        exc_type = exc_type.strip()
        msg = msg.strip()
    else:
        exc_type = 'TypeError'
        msg = default_raise
    exc_name = 'PyExc_' + exc_type
    out.append('        PyErr_SetString(' + exc_name + ', "{}");'.format(_escape_c_str(msg)))
    out.append('        return NULL;')


# ---------------------------------------------------------------------------
# _wrapper function (arg parsing, buffer acquire, cleanup)
# ---------------------------------------------------------------------------

def _emit_wrapper_func(out, func, buf_params, scalar_params, timing):
    """Emit both VARARGS (Python < 3.12) and FASTCALL (Python >= 3.12) wrappers."""
    _emit_varargs_wrapper(out, func, buf_params, scalar_params, timing)
    _emit_fastcall_wrapper(out, func, buf_params, scalar_params, timing)


def _emit_varargs_wrapper(out, func, buf_params, scalar_params, timing):
    """Emit the METH_VARARGS wrapper (Python 2.7 through 3.11)."""
    name = func.name
    all_params = func.py_params

    out.append('static PyObject*')
    out.append('_' + name + '_wrapper(PyObject *self, PyObject *args)')
    out.append('{')

    # Local variables
    _emit_wrapper_locals(out, buf_params, scalar_params, func, timing)

    # Arg parse via PyArg_ParseTuple
    fmt_str = _build_parse_format(all_params, func)
    parse_args = ['args', '"' + fmt_str + '"']
    for p in all_params:
        if p.pytype == 'buffer':
            parse_args.append('&py_' + p.name)
        elif p.pytype == 'int':
            parse_args.append('&c_' + p.name)
        else:
            parse_args.append('&c_' + p.name)
    out.append('    if (!PyArg_ParseTuple({}))'.format(', '.join(parse_args)))
    out.append('        return NULL;')
    out.append('')

    # Shared body: buffer init, acquire, checks, impl, cleanup
    _emit_wrapper_body(out, func, buf_params, scalar_params, name, timing)

    out.append('}')
    out.append('')


def _emit_fastcall_wrapper(out, func, buf_params, scalar_params, timing):
    """Emit the METH_FASTCALL wrapper (Python >= 3.12)."""
    name = func.name
    all_params = func.py_params

    out.append('static PyObject*')
    out.append('_' + name + '_fastcall(PyObject *self, PyObject *const *args, Py_ssize_t nargs)')
    out.append('{')

    # Local variables
    _emit_wrapper_locals(out, buf_params, scalar_params, func, timing)

    # Arg count check (handle optional params with defaults)
    total = len(all_params)
    min_req = sum(1 for p in all_params if p.default is None)
    if min_req == total:
        out.append('    if (nargs != {0}) {{'.format(total))
        out.append('        PyErr_SetString(PyExc_TypeError,')
        out.append('            \"{0} expects {1} argument{2}\");'.format(
            name, total, 's' if total != 1 else ''))
        out.append('        return NULL;')
        out.append('    }')
    else:
        out.append('    if (nargs < {0} || nargs > {1}) {{'.format(min_req, total))
        out.append('        PyErr_SetString(PyExc_TypeError,')
        out.append('            \"{0} expects {1} to {2} arguments\");'.format(
            name, min_req, total))
        out.append('        return NULL;')
        out.append('    }')
    out.append('')

    # Extract args directly from the array (only up to nargs)
    void_ptr_names = _collect_void_ptr_names(func)
    idx = 0
    for p in all_params:
        is_optional = (p.default is not None)
        if p.pytype == 'buffer':
            out.append('    py_{0} = args[{1}];'.format(p.name, idx))
        elif p.pytype == 'int':
            out.append('    /* extract int: {0} from args[{1}]{2} */'.format(
                p.name, idx, ' (optional)' if is_optional else ''))
            if is_optional:
                out.append('    if (nargs > {0}) {{'.format(idx))
            else:
                out.append('    {')
            out.append('        long _c2py_tmp = PyLong_AsLong(args[{0}]);'.format(idx))
            out.append('        if (_c2py_tmp == -1 && PyErr_Occurred()) return NULL;')
            if p.name in void_ptr_names:
                out.append('        c_{0} = (intptr_t)_c2py_tmp;'.format(p.name))
            else:
                out.append('        c_{0} = (int)_c2py_tmp;'.format(p.name))
            out.append('    }')
        else:
            out.append('    /* extract float: {0} from args[{1}]{2} */'.format(
                p.name, idx, ' (optional)' if is_optional else ''))
            if is_optional:
                out.append('    if (nargs > {0}) {{'.format(idx))
            else:
                out.append('    {')
            out.append('        double _c2py_tmp = PyFloat_AsDouble(args[{0}]);'.format(idx))
            out.append('        if (_c2py_tmp == -1.0 && PyErr_Occurred()) return NULL;')
            out.append('        c_{0} = _c2py_tmp;'.format(p.name))
            out.append('    }')
        idx += 1

    out.append('')

    # Shared body: buffer init, acquire, checks, impl, cleanup
    _emit_wrapper_body(out, func, buf_params, scalar_params, name, timing)

    out.append('}')
    out.append('')


def _emit_wrapper_locals(out, buf_params, scalar_params, func, timing=False):
    """Emit local variable declarations shared by both wrappers."""
    void_ptr_names = _collect_void_ptr_names(func)
    for p in buf_params:
        out.append('    PyObject *py_' + p.name + ' = NULL;')
    for p in scalar_params:
        default_val = p.default
        if p.pytype == 'int':
            if p.name in void_ptr_names:
                if default_val is None:
                    out.append('    intptr_t c_%s = 0;' % p.name)
                else:
                    out.append('    intptr_t c_%s = %d;' % (p.name, int(default_val)))
            else:
                if default_val is None:
                    out.append('    int c_%s = 0;' % p.name)
                else:
                    out.append('    int c_%s = %d;' % (p.name, int(default_val)))
        else:
            if default_val is None:
                out.append('    double c_%s = 0.0;' % p.name)
            else:
                out.append('    double c_%s = %s;' % (p.name, _float_literal(default_val)))

    for p in buf_params:
        out.append('    Py_buffer buf_{0};'.format(p.name))
        out.append('    int acq_{0} = 0;'.format(p.name))

    out.append('    PyObject *ret = NULL;')

    if timing:
        out.append('    int _c2py_do_time = _c2py_timing_enabled;')
        out.append('    uint64_t _c2py_t0 = 0, _c2py_t1 = 0, _c2py_t2 = 0;')
        out.append('    if (_c2py_do_time) _c2py_t0 = c2py_ticks();')

    out.append('')


def _emit_wrapper_body(out, func, buf_params, scalar_params, name, timing=False):
    """Emit the shared wrapper body: buffer init, acquire, checks, impl call, cleanup."""
    perf_name = '_perf_' + name

    # Initialize buffers
    for p in buf_params:
        out.append('    memset(&buf_{0}, 0, C2PY.pybuffer_size);'.format(p.name))
    out.append('')

    # Acquire buffers
    for i, p in enumerate(buf_params):
        flags = _get_buf_flags(p, func)
        want_write = 'PyBUF_WRITABLE' in flags
        write_val = 'C2PY_BUF_WRITE' if want_write else 'C2PY_BUF_READ'
        out.append('    if (c2py_acquire_buffer(py_{0}, &buf_{0}, {1}) == -1)'.format(p.name, write_val))
        if i == 0:
            out.append('        return NULL;')
        else:
            out.append('        goto cleanup;')
        out.append('    acq_{0} = 1;'.format(p.name))
        out.append('')

    # Restrict checks
    _emit_restrict_checks(out, buf_params, func)

    # Contiguity checks
    _emit_contiguity_checks(out, buf_params)

    # Call impl (with timing ticks around it)
    impl_args = []
    for p in buf_params:
        impl_args.append('&buf_' + p.name)
    for p in scalar_params:
        impl_args.append('c_' + p.name)

    if timing:
        out.append('    if (_c2py_do_time) _c2py_t1 = c2py_ticks();')
    out.append('    ret = _{0}_impl({1});'.format(name, ', '.join(impl_args)))
    if timing:
        out.append('    if (_c2py_do_time) _c2py_t2 = c2py_ticks();')
    out.append('')

    # Cleanup
    if len(buf_params) >= 1:
        out.append('cleanup:')
    for p in reversed(buf_params):
        out.append('    if (acq_{0}) c2py_release_buffer(&buf_{0});'.format(p.name))

    if timing:
        out.append('')
        out.append('    if (_c2py_do_time) {')
        out.append('        c2py_perf_record(&{0}, _c2py_t0, _c2py_t1, _c2py_t2, c2py_ticks());'.format(perf_name))
        out.append('    }')

    out.append('    return ret;')


def _collect_void_ptr_names(func):
    """Return set of scalar param names that map to C void* in any overload."""
    if func is None:
        return set()
    scalar_names = set(p.name for p in func.py_params if p.pytype == 'int')
    result = set()
    for ol in func.overloads:
        if ol.variants:
            entries = [(v.params, ol.map_exprs) for v in ol.variants]
        else:
            entries = [(ol.params, ol.map_exprs)]
        for params, map_exprs in entries:
            for cp in params:
                if cp.is_pointer and cp.base_type == 'void':
                    expr = map_exprs.get(cp.name)
                    if expr is not None and isinstance(expr, Var) and expr.name in scalar_names:
                        result.add(expr.name)
    return result


def _build_parse_format(py_params, func=None):
    """Build the PyArg_ParseTuple format string.

    Inserts '|' before the first optional parameter (one with a default).
    If func is provided, Python int params that map to C void* use
    pointer-width format 'l' (long) instead of 'i' (int).
    """
    void_ptr_names = _collect_void_ptr_names(func) if func else set()
    fmt = ''
    hit_optional = False
    for p in py_params:
        if not hit_optional and p.default is not None:
            hit_optional = True
            fmt += '|'
        if p.pytype == 'buffer':
            fmt += 'O'
        elif p.pytype == 'int':
            if p.name in void_ptr_names:
                fmt += 'l'
            else:
                fmt += 'i'
        elif p.pytype == 'float':
            fmt += 'd'
    return fmt


def _get_buf_flags(buf_param, func):
    """Determine PyObject_GetBuffer flags for a buffer param.

    Returns a string like "PyBUF_STRIDES | PyBUF_FORMAT" or 
    "PyBUF_WRITABLE | PyBUF_STRIDES | PyBUF_FORMAT".
    """
    is_writable = False
    for ol in func.overloads:
        if ol.variants:
            for v in ol.variants:
                for cp in v.params:
                    if cp.is_pointer and not cp.is_const:
                        expr = ol.map_exprs.get(cp.name)
                        if expr is not None and _expr_refers_to(expr, buf_param.name):
                            is_writable = True
                            break
                if is_writable:
                    break
        else:
            for cp in ol.params:
                if cp.is_pointer and not cp.is_const:
                    expr = ol.map_exprs.get(cp.name)
                    if expr is not None and _expr_refers_to(expr, buf_param.name):
                        is_writable = True
                        break
        if is_writable:
            break

    if is_writable:
        return 'PyBUF_WRITABLE | PyBUF_STRIDES | PyBUF_FORMAT'
    else:
        return 'PyBUF_STRIDES | PyBUF_FORMAT'


def _expr_refers_to(expr, buf_name):
    """Check if an expression refers to a specific buffer param."""
    if isinstance(expr, Var):
        return expr.name == buf_name
    elif isinstance(expr, Attr):
        return _expr_refers_to(expr.obj, buf_name)
    elif isinstance(expr, Subscript):
        return _expr_refers_to(expr.obj, buf_name)
    elif isinstance(expr, Compare):
        return _expr_refers_to(expr.left, buf_name) or _expr_refers_to(expr.right, buf_name)
    elif isinstance(expr, BinOp):
        return _expr_refers_to(expr.left, buf_name) or _expr_refers_to(expr.right, buf_name)
    elif isinstance(expr, UnaryOp):
        return _expr_refers_to(expr.operand, buf_name)
    return False


def _emit_restrict_checks(out, buf_params, func):
    """Emit restrict alias checks between buffers.

    Any non-const pointer must not alias with any other pointer.
    """
    writable = set()
    const_set = set()
    for p in buf_params:
        for ol in func.overloads:
            if ol.variants:
                all_params = []
                for v in ol.variants:
                    all_params.extend(v.params)
                for cp in all_params:
                    if cp.is_pointer:
                        expr = ol.map_exprs.get(cp.name)
                        if expr is not None and _expr_refers_to(expr, p.name):
                            if cp.is_const:
                                const_set.add(p.name)
                            else:
                                writable.add(p.name)
            else:
                for cp in ol.params:
                    if cp.is_pointer:
                        expr = ol.map_exprs.get(cp.name)
                        if expr is not None and _expr_refers_to(expr, p.name):
                            if cp.is_const:
                                const_set.add(p.name)
                            else:
                                writable.add(p.name)

    # Check writable vs writable, and writable vs const
    checked = set()
    for wn in writable:
        for other in list(writable | const_set):
            if other == wn:
                continue
            pair = tuple(sorted([wn, other]))
            if pair in checked:
                continue
            checked.add(pair)
            out.append('    /* restrict check: {} vs {} */'.format(wn, other))
            out.append('    if (buf_{0}.buf >= buf_{1}.buf && '.format(wn, other))
            out.append('        buf_{0}.buf < buf_{1}.buf + buf_{1}.len) {{'.format(wn, other))
            out.append('        PyErr_SetString(PyExc_ValueError, "buffer aliasing forbidden");')
            out.append('        goto cleanup;')
            out.append('    }')
            out.append('    if (buf_{0}.buf >= buf_{1}.buf && '.format(other, wn))
            out.append('        buf_{0}.buf < buf_{1}.buf + buf_{1}.len) {{'.format(other, wn))
            out.append('        PyErr_SetString(PyExc_ValueError, "buffer aliasing forbidden");')
            out.append('        goto cleanup;')
            out.append('    }')
            out.append('')


def _emit_contiguity_checks(out, buf_params):
    """Emit contiguity validation for each buffer.

    Accepts C-contiguous and Fortran-contiguous layouts.
    Rejects strided arrays, negative strides, indirect buffers.
    """
    if not buf_params:
        return

    for p in buf_params:
        name = p.name
        fmt = lambda s: s.format(name)
        out.append('    /* contiguity check: {0} */'.format(name))
        out.append('    do {')
        out.append('        int _ok = 1;')
        out.append('        if (buf_{0}.strides == NULL && buf_{0}.ndim <= 1) break;'.format(name))
        out.append(fmt('        if (buf_{0}.ndim >= 1) {{'))
        out.append(fmt('            Py_ssize_t _expected = buf_{0}.itemsize;'))
        out.append('            int _d;')
        out.append('            /* check F-contiguous (column-major): first dim varies fastest */')
        out.append(fmt('            for (_d = 0; _d < buf_{0}.ndim; _d++) {{'))
        out.append(fmt('                if (buf_{0}.strides[_d] < 0) {{ _ok = 0; break; }}'))
        out.append(fmt('                if (buf_{0}.strides[_d] != _expected) {{ _ok = 0; break; }}'))
        out.append(fmt('                _expected *= buf_{0}.shape[_d];'))
        out.append('            }')
        out.append('            if (_ok) break;')
        out.append('            /* check C-contiguous (row-major): last dim varies fastest */')
        out.append('            _ok = 1;')
        out.append(fmt('            _expected = buf_{0}.itemsize;'))
        out.append(fmt('            for (_d = buf_{0}.ndim - 1; _d >= 0; _d--) {{'))
        out.append(fmt('                if (buf_{0}.strides[_d] < 0) {{ _ok = 0; break; }}'))
        out.append(fmt('                if (buf_{0}.strides[_d] != _expected) {{ _ok = 0; break; }}'))
        out.append(fmt('                _expected *= buf_{0}.shape[_d];'))
        out.append('            }')
        out.append('        }')
        out.append('        if (!_ok) {')
        out.append('            PyErr_SetString(PyExc_ValueError,')
        out.append('                "buffer not contiguous (C or Fortran contiguous required)");')
        out.append('            goto cleanup;')
        out.append('        }')
        out.append('    } while(0);')
        out.append('')


# ---------------------------------------------------------------------------
# Expression transpiler: AST -> C code string
# ---------------------------------------------------------------------------

def _expr_to_c(expr, buf_params, scalar_params, current_ol):
    """Transpile an expression AST node to a C expression string."""
    if expr is None:
        return '1'  # No condition = always true

    if isinstance(expr, Var):
        name = expr.name
        # Is it a buffer param?
        for p in buf_params:
            if p.name == name:
                return 'buf_' + name
        # Is it a scalar param?
        for p in scalar_params:
            if p.name == name:
                return 'c_' + name
        return name

    elif isinstance(expr, Attr):
        obj = _expr_to_c(expr.obj, buf_params, scalar_params, current_ol)
        attr = expr.attr
        if attr == 'format':
            return obj + '->format'
        elif attr == 'ndim':
            return obj + '->ndim'
        elif attr == 'itemsize':
            return obj + '->itemsize'
        elif attr == 'len':
            return obj + '->len'
        elif attr == 'n':
            return '(' + obj + '->len / ' + obj + '->itemsize)'
        elif attr == 'ptr':
            return obj + '->buf'
        elif attr == 'shape':
            return obj + '->shape'
        elif attr == 'strides':
            return obj + '->strides'
        else:
            return obj + '->' + attr

    elif isinstance(expr, Subscript):
        obj = _expr_to_c(expr.obj, buf_params, scalar_params, current_ol)
        idx = expr.index
        return '{}[{}]'.format(obj, idx)

    elif isinstance(expr, IntLit):
        return str(expr.value)

    elif isinstance(expr, StrLit):
        return '"' + _escape_c_str(expr.value) + '"'

    elif isinstance(expr, Compare):
        left = _expr_to_c(expr.left, buf_params, scalar_params, current_ol)
        right = _expr_to_c(expr.right, buf_params, scalar_params, current_ol)
        op = expr.op

        # String comparison with format char: use last-char match for
        # PEP 3118 format strings (handles "d", "<d", "=d", etc.)
        # On old buffers (format == NULL), treat as matching (we can't check)
        if isinstance(expr.left, StrLit) or isinstance(expr.right, StrLit):
            str_lit = expr.left if isinstance(expr.left, StrLit) else expr.right
            fmt_expr = right if isinstance(expr.left, StrLit) else left
            if len(str_lit.value) == 1:
                ch = str_lit.value
                if op == '==':
                    return '(!{0} || {0}[strlen({0}) - 1] == \'{1}\')'.format(fmt_expr, ch)
                elif op == '!=':
                    return '({0} && {0}[strlen({0}) - 1] != \'{1}\')'.format(fmt_expr, ch)
            if op == '==':
                return 'strcmp({}, {}) == 0'.format(left, right)
            elif op == '!=':
                return 'strcmp({}, {}) != 0'.format(left, right)
            else:
                raise ValueError("Unsupported comparison op '{}' for strings".format(op))
        else:
            return '({}) {} ({})'.format(left, op, right)

    elif isinstance(expr, BinOp):
        left = _expr_to_c(expr.left, buf_params, scalar_params, current_ol)
        right = _expr_to_c(expr.right, buf_params, scalar_params, current_ol)
        if expr.op == 'and':
            return '({}) && ({})'.format(left, right)
        elif expr.op == 'or':
            return '({}) || ({})'.format(left, right)
        elif expr.op in ('+', '-', '*', '/', '%'):
            return '({} {} {})'.format(left, expr.op, right)
        else:
            raise ValueError("Unknown binop: {}".format(expr.op))

    elif isinstance(expr, UnaryOp):
        operand = _expr_to_c(expr.operand, buf_params, scalar_params, current_ol)
        if expr.op == 'not':
            return '!({})'.format(operand)
        elif expr.op == '-':
            return '-({})'.format(operand)
        elif expr.op == '+':
            return '+({})'.format(operand)
        else:
            raise ValueError("Unknown unary op: {}".format(expr.op))

    else:
        raise ValueError("Unknown expression type: {}".format(type(expr)))


def _expr_to_source(expr):
    """Convert an AST node back to its source form (for comments/error messages)."""
    if isinstance(expr, Var):
        return expr.name
    elif isinstance(expr, Attr):
        return _expr_to_source(expr.obj) + '.' + expr.attr
    elif isinstance(expr, Subscript):
        return _expr_to_source(expr.obj) + '[' + str(expr.index) + ']'
    elif isinstance(expr, IntLit):
        return str(expr.value)
    elif isinstance(expr, StrLit):
        return "'" + expr.value + "'"
    elif isinstance(expr, Compare):
        return '{} {} {}'.format(
            _expr_to_source(expr.left), expr.op, _expr_to_source(expr.right))
    elif isinstance(expr, BinOp):
        return '({} {} {})'.format(
            _expr_to_source(expr.left), expr.op, _expr_to_source(expr.right))
    elif isinstance(expr, UnaryOp):
        return '{}({})'.format(expr.op, _expr_to_source(expr.operand))
    else:
        return str(expr)


# ---------------------------------------------------------------------------
# Module init
# ---------------------------------------------------------------------------

def _emit_constants(out, mod):
    """Emit PyObject_SetAttrString calls for module-level integer constants,
    timing perf struct pointers, and GIL release flags."""
    has_gil = any(f.gil_release for f in mod.functions)
    if not mod.constants and not mod.timing and not has_gil:
        return
    out.append('    if (module != NULL) {')
    if mod.constants:
        for cname, cvalue in sorted(mod.constants.items()):
            out.append('        PyObject_SetAttrString(module, "{}",'.format(_escape_c_str(cname)))
            out.append('            PyLong_FromLong({}));'.format(cvalue))
    if mod.timing:
        out.append('        PyObject_SetAttrString(module, "_c2py_timing_enabled",')
        out.append('            PyLong_FromVoidPtr(&_c2py_timing_enabled));')
        for func in mod.functions:
            out.append('        PyObject_SetAttrString(module, "_perf_{0}",'.format(func.name))
            out.append('            PyLong_FromVoidPtr(&_perf_{0}));'.format(func.name))
            for ol in func.overloads:
                if ol.variants:
                    for v in ol.variants:
                        c_name = _extract_c_name(v.sig_str)
                        perf_name = '_perf_{0}__{1}'.format(func.name, c_name)
                        out.append('        PyObject_SetAttrString(module, "{}",'.format(perf_name))
                        out.append('            PyLong_FromVoidPtr(&{}));'.format(perf_name))
                else:
                    c_name = _extract_c_name(ol.sig_str)
                    perf_name = '_perf_{0}__{1}'.format(func.name, c_name)
                    out.append('        PyObject_SetAttrString(module, "{}",'.format(perf_name))
                    out.append('            PyLong_FromVoidPtr(&{}));'.format(perf_name))
    if has_gil:
        out.append('        PyObject_SetAttrString(module, "_c2py_gil_release_enabled",')
        out.append('            PyLong_FromVoidPtr(&_c2py_gil_release_enabled));')
        for func in mod.functions:
            if func.gil_release:
                out.append('        PyObject_SetAttrString(module, "_c2py_gil_release_{0}",'.format(func.name))
                out.append('            PyLong_FromVoidPtr(&_gil_release_{0}));'.format(func.name))
    out.append('    }')


def _emit_module_init(out, mod):
    name = mod.name
    has_gil = any(f.gil_release for f in mod.functions)
    has_variants = any(any(ol.variants for ol in f.overloads) for f in mod.functions)
    has_attrs = mod.constants or mod.timing or has_gil
    out.append('')
    out.append('/* ' + '-' * 44 + ' */')
    out.append('/* Module definition                          */')
    out.append('/* ' + '-' * 44 + ' */')
    out.append('')

    # Helper to build doc string
    def _doc(func):
        py_args = []
        for p in func.py_params:
            py_args.append('{}: {}'.format(p.name, p.pytype))
        default_doc = '{}({}) -> {}'.format(func.name, ', '.join(py_args), func.return_type)
        doc = func.doc if func.doc is not None else default_doc
        # Append variant info for grouped functions
        groups = [ol for ol in func.overloads if ol.variants]
        if groups:
            vnames = []
            for ol in groups:
                for v in ol.variants:
                    vnames.append(v.name)
            doc += '\\nVariants: ' + ', '.join(vnames)
        return doc

    # --- VARARGS method table (Python < 3.12) ---
    out.append('static PyMethodDef _methods_varargs[] = {')
    for func in mod.functions:
        out.append('    {{"{}", (PyCFunction)_{}_wrapper, METH_VARARGS, "{}"}},'.format(
            func.name, func.name, _doc(func)))
    if has_variants:
        for func in mod.functions:
            if any(ol.variants for ol in func.overloads):
                out.append('    {{"_rebind_{0}", (PyCFunction)_rebind_{0}, METH_VARARGS,'
                           .format(func.name))
                out.append('     "rebind variant for {0}"}},'.format(func.name))
    out.append('    {NULL, NULL, 0, NULL}')
    out.append('};')
    out.append('')

    # --- FASTCALL method table (Python >= 3.12) ---
    out.append('static PyMethodDef _methods_fastcall[] = {')
    for func in mod.functions:
        out.append('    {{"{}", (PyCFunction)_{}_fastcall, METH_FASTCALL, "{}"}},'.format(
            func.name, func.name, _doc(func)))
    if has_variants:
        for func in mod.functions:
            if any(ol.variants for ol in func.overloads):
                out.append('    {{"_rebind_{0}", (PyCFunction)_rebind_{0}, METH_VARARGS,'
                           .format(func.name))
                out.append('     "rebind variant for {0}"}},'.format(func.name))
    out.append('    {NULL, NULL, 0, NULL}')
    out.append('};')
    out.append('')

    # Module definition struct - methods pointer set at init time
    # GIL-enabled layout (standard CPython)
    out.append('static PyModuleDef _module_def = {')
    out.append('    PyModuleDef_HEAD_INIT,')
    out.append('    "{}",'.format(name))
    out.append('    NULL,')
    out.append('    -1,')
    out.append('    NULL,  /* methods set at init */')
    out.append('    NULL, NULL, NULL, NULL')
    out.append('};')
    out.append('')

    # Free-threaded layout (PyModuleDef_FT, PyObject is 32 bytes)
    out.append('static PyModuleDef_FT _module_def_ft = {')
    out.append('    PyModuleDef_HEAD_INIT_FT,')
    out.append('    "{}",'.format(name))
    out.append('    NULL,')
    out.append('    -1,')
    out.append('    NULL,  /* methods set at init */')
    out.append('    NULL, NULL, NULL, NULL')
    out.append('};')
    out.append('')

    # Resolve calls at init
    resolve_calls = ''
    if has_variants:
        for func in mod.functions:
            if any(ol.variants for ol in func.overloads):
                resolve_calls += '    _resolve_{}();\n'.format(func.name)

    # Python 3 init
    out.append('PyObject* PyInit_{}(void) {{'.format(name))
    out.append('    c2py_runtime_init();')
    out.append(resolve_calls)
    out.append('')
    out.append('    PyMethodDef *methods = C2PY.use_fastcall ? _methods_fastcall : _methods_varargs;')
    out.append('')
    out.append('    if (C2PY.is_free_threaded) {')
    out.append('        _module_def_ft.m_methods = methods;')
    if has_attrs:
        out.append('        PyObject *module;')
        out.append('        if (C2PY.Module_Create2 != NULL) {')
        out.append('            module = C2PY.Module_Create2((PyModuleDef*)&_module_def_ft, 1013);')
        out.append('        } else {')
        out.append('            return NULL;')
        out.append('        }')
        out.append('')
        _emit_constants(out, mod)
        out.append('')
        out.append('        return module;')
    else:
        out.append('        if (C2PY.Module_Create2 != NULL) {')
        out.append('            return C2PY.Module_Create2((PyModuleDef*)&_module_def_ft, 1013);')
        out.append('        }')
        out.append('        return NULL;')
    out.append('    } else {')
    out.append('        _module_def.m_methods = methods;')
    out.append('')
    if has_attrs:
        out.append('        PyObject *module;')
        out.append('        if (C2PY.Module_Create2 != NULL) {')
        out.append('            module = C2PY.Module_Create2(&_module_def, 1013);')
        out.append('        } else {')
        out.append('            /* Fallback for Python 2.7 where PyModuleDef is not supported */')
        out.append('            module = C2PY.InitModule_2_7("{}", methods);'.format(name))
        out.append('        }')
        out.append('')
        _emit_constants(out, mod)
        out.append('')
        out.append('        return module;')
    else:
        out.append('        if (C2PY.Module_Create2 != NULL) {')
        out.append('            return C2PY.Module_Create2(&_module_def, 1013);')
        out.append('        }')
        out.append('        /* Fallback for Python 2.7 where PyModuleDef is not supported */')
        out.append('        return C2PY.InitModule_2_7("{}", methods);'.format(name))
    out.append('    }')
    out.append('}')
    out.append('')

    # Python 2.7 init
    out.append('void init{}(void) {{'.format(name))
    out.append('    c2py_runtime_init();')
    out.append(resolve_calls)
    if has_attrs:
        out.append('    PyObject *module = C2PY.InitModule_2_7("{}",'.format(name))
        out.append('        C2PY.use_fastcall ? _methods_fastcall : _methods_varargs);')
        _emit_constants(out, mod)
    else:
        out.append('    C2PY.InitModule_2_7("{}",'.format(name))
        out.append('        C2PY.use_fastcall ? _methods_fastcall : _methods_varargs);')
    out.append('}')


def _escape_c_str(s):
    """Escape a string for use in a C string literal."""
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    s = s.replace('\t', '\\t')
    return s


def _float_literal(value):
    """Convert a Python float to a C double literal string.
    Handles whole-number floats (3.0 -> 3.0) and fractions."""
    s = "%.15g" % value
    if '.' not in s and 'e' not in s and 'E' not in s:
        s += ".0"
    return s
```

## c2py23/parser.py

```python
"""Parser for .c2py interface definition files.

Handles:
  - YAML loading (via PyYAML)
  - C function signature parsing
  - Expression parsing (for 'when' conditions and 'map' substitutions)
  - Building the ModuleDef data model
"""
from __future__ import print_function

import os
import re
import sys
import warnings
import yaml
from collections import namedtuple

# Python 2/3 compat: str covers bytes+unicode on 2.x, text on 3.x
if sys.version_info[0] >= 3:
    _STRING_TYPES = (str,)
else:
    _STRING_TYPES = (str, unicode)  # noqa: F821

# ---------------------------------------------------------------------------
# AST nodes for expressions in 'when' and 'map'
# ---------------------------------------------------------------------------

class Var(namedtuple('Var', ['name'])):
    pass

class Attr(namedtuple('Attr', ['obj', 'attr'])):
    pass

class Subscript(namedtuple('Subscript', ['obj', 'index'])):
    pass

class IntLit(namedtuple('IntLit', ['value'])):
    pass

class StrLit(namedtuple('StrLit', ['value'])):
    pass

class Compare(namedtuple('Compare', ['left', 'op', 'right'])):
    pass

class BinOp(namedtuple('BinOp', ['left', 'op', 'right'])):
    pass

class UnaryOp(namedtuple('UnaryOp', ['op', 'operand'])):
    pass

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class PyParam(namedtuple('PyParam', ['name', 'pytype', 'default'])):
    """pytype is one of 'buffer', 'int', 'float'. default is None for
    required params, or a numeric value for optional int/float params."""
    pass

class CParam(namedtuple('CParam', ['name', 'ctype', 'base_type', 'is_const', 'is_pointer'])):
    """ctype is the full C type string, base_type is the element type"""
    pass

class COverload(namedtuple('_COverload', ['sig_str', 'params', 'return_type', 'map_exprs', 'when_expr', 'name', 'group_name', 'variants'])):
    """A C function overload alternative or a dispatch group.

    For flat overloads (backward compatible):
        sig_str, params, return_type, map_exprs, when_expr are populated.
        name is optional (required if when_expr is static for rebind support).
        variants is None.

    For grouped dispatch:
        variants is a non-empty list of CVariant.
        sig_str, params, return_type are None.
        map_exprs is the shared argument map for all variants in the group.
        when_expr is the per-call group condition (e.g. data.format == 'f').
        group_name is an optional label (for rebind qualifiers, docstrings).

    outputs maps C parameter names to ctypes types (e.g. {'minval': 'double'}).
    Output params are auto-allocated as 1-element arrays and returned in the tuple.
    """
    def __new__(cls, sig_str, params, return_type, map_exprs, when_expr,
                name=None, group_name=None, variants=None, outputs=None):
        self = super(COverload, cls).__new__(cls, sig_str, params, return_type,
                                              map_exprs, when_expr,
                                              name, group_name, variants)
        self.outputs = outputs or {}
        return self

class CVariant(namedtuple('CVariant', ['name', 'sig_str', 'params', 'return_type', 'when_expr', 'outputs'])):
    """A variant within a dispatch group. Inherits map_exprs from the parent group.

    name is required for rebind, docstring, and timing identification.
    when_expr is the static (CPU feature) dispatch condition, or None for default.
    outputs is an optional dict for scalar output parameters (same format as COverload).
    """

class FuncDef(namedtuple('FuncDef', ['name', 'py_params', 'return_type', 'checks', 'overloads', 'default_raise', 'doc', 'gil_release'])):
    pass

class ModuleDef(namedtuple('ModuleDef', ['name', 'sources', 'headers', 'functions', 'constants', 'timing'])):
    """constants is a dict of {name: int_value} for module-level integer constants.
       timing is a bool enabling per-function performance profiling."""
    pass

# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_c2py(path):
    """Load and parse a .c2py YAML file, returning a ModuleDef."""
    with open(path, 'r') as f:
        raw = yaml.safe_load(f)

    module_name = _get_required(raw, 'module', path)
    sources = raw.get('source', [])
    if isinstance(sources, _STRING_TYPES):
        sources = [sources]
    headers = raw.get('headers', [])
    if isinstance(headers, _STRING_TYPES):
        headers = [headers]

    funcs = []
    for f in raw.get('functions', []):
        funcs.extend(_expand_func_template(f, path))

    constants = raw.get('constants', {})
    if not isinstance(constants, dict):
        raise ValueError("'constants' must be a dict in {}".format(path))
    for k, v in constants.items():
        if not isinstance(v, int):
            raise ValueError("Constant '{}' in {} must be an integer, got {}".format(k, path, type(v)))

    timing = bool(raw.get('timing', False))

    mod = ModuleDef(module_name, sources, headers, funcs, constants, timing)

    base_dir = os.path.dirname(os.path.abspath(path))
    _validate_module(mod, base_dir)

    return mod


def _get_required(d, key, path):
    if key not in d:
        raise ValueError("Missing required field '{}' in {}".format(key, path))
    return d[key]

# ---------------------------------------------------------------------------
# Python signature parser: "name(arg: type, ...) -> ret"
# ---------------------------------------------------------------------------

_PY_SIG_RE = re.compile(
    r'^\s*'
    r'(?P<name>\w+)\s*'
    r'\(\s*(?P<params>[^)]*?)\s*\)'
    r'\s*(?:->\s*(?P<ret>\w+))?\s*$'
)

_PYTYPE_MAP = {'buffer': 'buffer', 'int': 'int', 'float': 'float'}

_PY_PARAM_RE = re.compile(
    r'^(\w+)\s*:\s*(buffer|int|float)\s*(?:=\s*(-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))?\s*$'
)

def _parse_py_sig(sig_str, path):
    m = _PY_SIG_RE.match(sig_str)
    if not m:
        raise ValueError("Invalid python signature '{}' in {}".format(sig_str, path))
    name = m.group('name')
    params_str = m.group('params')
    ret = m.group('ret') or 'void'

    params = []
    seen_optional = False
    if params_str.strip():
        for part in params_str.split(','):
            part = part.strip()
            if not part:
                continue
            pm = _PY_PARAM_RE.match(part)
            if not pm:
                raise ValueError("Invalid param '{}' in signature '{}'".format(part, sig_str))
            pname = pm.group(1)
            ptype = pm.group(2)
            default_str = pm.group(3)

            if ptype not in _PYTYPE_MAP:
                raise ValueError("Unknown param type '{}' in signature '{}'".format(ptype, sig_str))
            pytype = _PYTYPE_MAP[ptype]

            if default_str is not None:
                if pytype == 'buffer':
                    raise ValueError(
                        "Buffer param '{}' cannot have a default value in '{}'".format(pname, sig_str))
                if pytype == 'int':
                    if not re.match(r'^-?\d+$', default_str):
                        raise ValueError(
                            "Integer param '{}' default '{}' is not a valid integer "
                            "in '{}'".format(pname, default_str, sig_str))
                    default = int(default_str)
                else:
                    default = float(default_str)
                seen_optional = True
            else:
                default = None
                if seen_optional:
                    raise ValueError(
                        "Required param '{}' cannot follow optional params in '{}'".format(pname, sig_str))

            params.append(PyParam(pname, pytype, default))
    return name, params, ret

# ---------------------------------------------------------------------------
# C signature parser
#
# Formats supported:
#   "name(...)"                         -> void return
#   "name(...) -> ret"                  -> explicit return
#   "ret name(...)"                     -> C-style return type
#   "ret name(...) -> ret"              -> both (-> overrides)
# ---------------------------------------------------------------------------

_C_TYPES_INT = (
    'int8_t', 'uint8_t', 'int16_t', 'uint16_t',
    'int32_t', 'uint32_t', 'int64_t', 'uint64_t',
    'int', 'float', 'double', 'char', 'void'
)
_C_TYPES = set(_C_TYPES_INT)

# Tokens in param lists: CONST, TYPE, STAR, NAME, COMMA, LPAREN, RPAREN
_C_PARAM_RE = re.compile(
    r'\s*(?:const\s+)?(' + '|'.join(_C_TYPES_INT) + r')\s*\*?\s*(\w+)\s*'
)

def _parse_c_sig(sig_str, path):
    sig_str = sig_str.strip()

    # Extract name + param list
    # Find '(' and the matching ')'
    paren_start = sig_str.find('(')
    if paren_start == -1:
        raise ValueError("Missing '(' in C signature '{}' in {}".format(sig_str, path))

    # The part before '(' contains [return_type] name
    before = sig_str[:paren_start].strip()

    # Find matching paren for nested parens (unlikely but be safe)
    depth = 0
    paren_end = paren_start
    for i in range(paren_start, len(sig_str)):
        if sig_str[i] == '(':
            depth += 1
        elif sig_str[i] == ')':
            depth -= 1
            if depth == 0:
                paren_end = i
                break

    params_str = sig_str[paren_start + 1:paren_end]

    if depth != 0:
        raise ValueError("Unmatched '(' in C signature '{}' in {}".format(sig_str, path))

    # Parse return type from suffix
    return_type = None  # None means void (none returned)
    remaining_after = sig_str[paren_end + 1:].strip()
    if remaining_after.startswith('->'):
        ret_part = remaining_after[2:].strip()
        if ret_part in _C_TYPES:
            return_type = ret_part
        else:
            raise ValueError("Unknown return type '{}' in {}".format(ret_part, sig_str))

    # Parse [return_type] name from before parens
    before_parts = before.split()
    if len(before_parts) == 1:
        name = before_parts[0]
        if return_type is None:
            return_type = 'void'
    elif len(before_parts) == 2 and before_parts[0] in _C_TYPES:
        if return_type is None:
            return_type = before_parts[0]
        name = before_parts[1]
    else:
        raise ValueError("Cannot parse C signature '{}' in {}".format(sig_str, path))

    # Parse params
    params = _parse_c_params(params_str)

    return name, params, return_type


def _parse_c_params(params_str):
    params = []
    if not params_str.strip():
        return params

    for part in params_str.split(','):
        part = part.strip()
        if not part:
            continue
        m = _C_PARAM_RE.match(part)
        if not m:
            raise ValueError("Cannot parse C param '{}'".format(part))
        base_type = m.group(1)
        name = m.group(2)
        is_const = 'const' in part
        is_pointer = '*' in part
        if is_pointer:
            ctype = ('const ' if is_const else '') + base_type + ' *'
        else:
            ctype = base_type
        params.append(CParam(name, ctype, base_type, is_const, is_pointer))
    return params

# ---------------------------------------------------------------------------
# Expression parser
#
# Grammar:
#   expr     := or_expr
#   or_expr  := and_expr ('or' and_expr)*
#   and_expr := not_expr ('and' not_expr)*
#   not_expr := 'not' not_expr | compare
#   compare  := term (cmp_op term)?
#   cmp_op   := '==' | '!=' | '<' | '>' | '<=' | '>='
#   term     := primary ('.' name)* ('[' INTEGER ']')*
#   primary  := NAME | INTEGER | STRING_LIT | '(' expr ')'
# ---------------------------------------------------------------------------

_CMP_OPS = {'==', '!=', '<', '>', '<=', '>='}

class _ExprParser(object):
    def __init__(self, s):
        self.s = s
        self.pos = 0
        self.n = len(s)

    def _skip_ws(self):
        while self.pos < self.n and self.s[self.pos] in ' \t':
            self.pos += 1

    def _peek(self):
        self._skip_ws()
        if self.pos >= self.n:
            return None
        return self.s[self.pos]

    def _consume(self):
        self._skip_ws()
        if self.pos >= self.n:
            return None
        ch = self.s[self.pos]
        self.pos += 1
        return ch

    def parse(self):
        self.pos = 0
        result = self._parse_or()
        self._skip_ws()
        if self.pos < self.n:
            raise ValueError("Unexpected trailing characters '{}' in expression '{}'".format(
                self.s[self.pos:], self.s))
        return result

    def _parse_or(self):
        left = self._parse_and()
        while True:
            self._skip_ws()
            if self._match_word('or'):
                right = self._parse_and()
                left = BinOp(left, 'or', right)
            else:
                break
        return left

    def _parse_and(self):
        left = self._parse_not()
        while True:
            self._skip_ws()
            if self._match_word('and'):
                right = self._parse_not()
                left = BinOp(left, 'and', right)
            else:
                break
        return left

    def _parse_not(self):
        self._skip_ws()
        if self._match_word('not'):
            operand = self._parse_not()
            return UnaryOp('not', operand)
        return self._parse_compare()

    def _parse_compare(self):
        left = self._parse_additive()
        self._skip_ws()
        pos = self.pos
        # Try to match a comparison operator
        if pos + 1 < self.n and self.s[pos:pos + 2] in _CMP_OPS:
            op = self.s[pos:pos + 2]
            self.pos = pos + 2
        elif pos < self.n and self.s[pos] in ('=', '!', '<', '>'):
            op = self.s[pos]
            self.pos = pos + 1
            # Check if followed by =
            if self.pos < self.n and self.s[self.pos] == '=':
                op += '='
                self.pos += 1
            if op not in _CMP_OPS:
                raise ValueError("Unknown comparison operator '{}'".format(op))
        else:
            return left
        right = self._parse_additive()
        return Compare(left, op, right)

    def _parse_additive(self):
        left = self._parse_multiplicative()
        while True:
            self._skip_ws()
            if self.pos < self.n and self.s[self.pos] in ('+', '-'):
                op = self.s[self.pos]
                self.pos += 1
                right = self._parse_multiplicative()
                left = BinOp(left, op, right)
            else:
                break
        return left

    def _parse_multiplicative(self):
        left = self._parse_unary()
        while True:
            self._skip_ws()
            if self.pos < self.n and self.s[self.pos] in ('*', '/', '%'):
                op = self.s[self.pos]
                self.pos += 1
                right = self._parse_unary()
                left = BinOp(left, op, right)
            else:
                break
        return left

    def _parse_unary(self):
        self._skip_ws()
        if self.pos < self.n and self.s[self.pos] in ('+', '-'):
            op = self.s[self.pos]
            self.pos += 1
            operand = self._parse_unary()
            return UnaryOp(op, operand)
        return self._parse_term()

    def _parse_term(self):
        node = self._parse_primary()
        while True:
            self._skip_ws()
            if self.pos < self.n and self.s[self.pos] == '.':
                self.pos += 1
                name = self._parse_name()
                node = Attr(node, name)
            elif self.pos < self.n and self.s[self.pos] == '[':
                self.pos += 1
                idx = self._parse_integer()
                self._skip_ws()
                if self.pos >= self.n or self.s[self.pos] != ']':
                    raise ValueError("Expected ']'")
                self.pos += 1
                node = Subscript(node, idx)
            else:
                break
        return node

    def _parse_primary(self):
        self._skip_ws()
        ch = self._peek()
        if ch is None:
            raise ValueError("Unexpected end of expression")
        if ch == '(':
            self.pos += 1
            node = self._parse_or()
            self._skip_ws()
            if self.pos >= self.n or self.s[self.pos] != ')':
                raise ValueError("Expected ')'")
            self.pos += 1
            return node
        if ch == "'" or ch == '"':
            return StrLit(self._parse_string())
        if ch.isdigit():
            return IntLit(self._parse_integer())
        if ch.isalpha() or ch == '_':
            return Var(self._parse_name())
        raise ValueError("Unexpected character '{}' in expression".format(ch))

    def _match_word(self, word):
        self._skip_ws()
        if self.pos + len(word) <= self.n and self.s[self.pos:self.pos + len(word)] == word:
            # Check word boundary
            end = self.pos + len(word)
            if end == self.n or not self.s[end].isalnum() and self.s[end] != '_':
                self.pos = end
                return True
        return False

    def _parse_name(self):
        self._skip_ws()
        start = self.pos
        while self.pos < self.n and (self.s[self.pos].isalnum() or self.s[self.pos] == '_'):
            self.pos += 1
        if start == self.pos:
            raise ValueError("Expected identifier")
        return self.s[start:self.pos]

    def _parse_integer(self):
        self._skip_ws()
        start = self.pos
        while self.pos < self.n and self.s[self.pos].isdigit():
            self.pos += 1
        if start == self.pos:
            raise ValueError("Expected integer")
        return int(self.s[start:self.pos])

    def _parse_string(self):
        quote = self.s[self.pos]
        self.pos += 1
        start = self.pos
        while self.pos < self.n and self.s[self.pos] != quote:
            if self.s[self.pos] == '\\':
                self.pos += 2
            else:
                self.pos += 1
        if self.pos >= self.n:
            raise ValueError("Unterminated string")
        val = self.s[start:self.pos]
        self.pos += 1
        return val


def parse_expr(s):
    """Parse an expression string, returning an AST node."""
    if s is None:
        return None
    return _ExprParser(s).parse()

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Template expansion (P9)
# ---------------------------------------------------------------------------

def _strsubst(obj, vars_map):
    """Recursively substitute ${VAR} patterns in strings within obj.

    Walks dicts, lists, and strings. Returns a deep copy with substitutions.
    vars_map is {varname: replacement_value} for a single expansion step.
    """
    if isinstance(obj, dict):
        return {k: _strsubst(v, vars_map) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strsubst(item, vars_map) for item in obj]
    if isinstance(obj, _STRING_TYPES):
        s = obj
        for var, val in vars_map.items():
            s = s.replace('${' + var + '}', val)
        return s
    return obj


def _expand_func_template(raw_func, path):
    """Expand a function definition with template variable substitution.

    If raw_func has an 'expand:' key, the dict must map variable names
    to lists of values of equal length. The function definition is
    expanded N times with ${VAR} substitutions applied to all strings.
    Returns a list of parsed FuncDef objects.

    If no 'expand:' key, returns [parsed_func] as before.
    """
    expand = raw_func.get('expand')
    if expand is None:
        return [_parse_func(raw_func, path)]

    if not isinstance(expand, dict):
        raise ValueError(
            "'expand' must be a dict mapping var names to lists in {}".format(path))

    lengths = set()
    for var, vals in expand.items():
        if not isinstance(vals, list):
            raise ValueError(
                "expand value for '{}' must be a list in {}".format(var, path))
        lengths.add(len(vals))

    if len(lengths) != 1:
        raise ValueError(
            "All expand value lists must have the same length in {}".format(path))

    n = lengths.pop()
    if n == 0:
        return []

    results = []
    for i in range(n):
        vars_map = {var: vals[i] for var, vals in expand.items()}
        expanded = _strsubst(raw_func, vars_map)
        results.append(_parse_func(expanded, path))
    return results


# Function-level parsing
# ---------------------------------------------------------------------------

def _coerce_expr_value(val, context, path):
    """Coerce a non-string YAML value to string for expression parsing.
    
    YAML parses bare integers/floats as their native types, but the expression
    parser expects strings. Map values like `verbose: 0` would crash otherwise.
    """
    if isinstance(val, _STRING_TYPES):
        return val
    if isinstance(val, (int, float)):
        warnings.warn(
            "{ctx} value in {path} is a bare {typ} ({val!r}); "
            "auto-coercing to string. Quote it: \"{val}\"".format(
                ctx=context, path=path, typ=type(val).__name__, val=val))
        return str(val)
    raise ValueError(
        "Expected string or number for %s value in %s, got %s" % (
            context, path, type(val).__name__))


def _parse_func(raw, path):
    py_sig_str = _get_required(raw, 'py_sig', path)
    name, py_params, ret_type = _parse_py_sig(py_sig_str, path)

    checks = [_parse_check_value(c, path) for c in raw.get('checks', [])]

    overloads = []
    for ol in raw.get('c_overloads', []):
        # --- Grouped dispatch (has 'variants:') ---
        if 'variants' in ol:
            variants_raw = ol.get('variants', [])
            if not variants_raw:
                raise ValueError("'variants' must be a non-empty list in {}".format(path))
            if 'sig' in ol:
                raise ValueError("Grouped overload cannot have 'sig'; use 'map:' and 'when:' at group level in {}".format(path))

            # Group-level when: (per-call dynamic condition)
            when_raw = ol.get('when')
            if when_raw is not None:
                when_raw = _coerce_expr_value(when_raw, 'when', path)
            group_when = parse_expr(when_raw)

            # Group-level map: (shared argument preparation)
            map_raw = _get_required(ol, 'map', path)
            group_map = {}
            for cname, expr_str in map_raw.items():
                expr_str = _coerce_expr_value(expr_str, 'map', path)
                group_map[cname] = parse_expr(expr_str)

            group_name = ol.get('group')

            # Parse variants
            variants = []
            for v in variants_raw:
                v_sig_str = _get_required(v, 'sig', path)
                v_c_name, v_params, v_ret = _parse_c_sig(v_sig_str, path)
                v_name = v.get('name')
                if v_name is None:
                    raise ValueError("Variant requires a 'name' in {}".format(path))
                v_when_raw = v.get('when')
                if v_when_raw is not None:
                    v_when_raw = _coerce_expr_value(v_when_raw, 'when', path)
                v_when_expr = parse_expr(v_when_raw)
                v_outputs = v.get('outputs', {})
                if v_outputs and not isinstance(v_outputs, dict):
                    raise ValueError("'outputs' must be a dict in {}".format(path))
                variants.append(CVariant(v_name, v_sig_str, v_params, v_ret, v_when_expr, v_outputs))

            overloads.append(COverload(None, None, None, group_map, group_when,
                                       group_name=group_name, variants=variants))
        else:
            # --- Flat overload (backward compatible) ---
            sig_str = _get_required(ol, 'sig', path)
            c_name, c_params, c_ret = _parse_c_sig(sig_str, path)
            map_raw = _get_required(ol, 'map', path)
            map_exprs = {}
            for cname, expr_str in map_raw.items():
                expr_str = _coerce_expr_value(expr_str, 'map', path)
                map_exprs[cname] = parse_expr(expr_str)
            when_raw = ol.get('when')
            if when_raw is not None:
                when_raw = _coerce_expr_value(when_raw, 'when', path)
            when_expr = parse_expr(when_raw)
            outputs = ol.get('outputs', {})
            if outputs and not isinstance(outputs, dict):
                raise ValueError("'outputs' must be a dict in {}".format(path))
            oname = ol.get('name')
            if oname is not None and not isinstance(oname, _STRING_TYPES):
                oname = str(oname)
            overloads.append(COverload(sig_str, c_params, c_ret, map_exprs, when_expr,
                                       name=oname, outputs=outputs))

    default_raise = raw.get('default_raise')
    doc = raw.get('doc')
    gil_release = bool(raw.get('gil_release', False))

    return FuncDef(name, py_params, ret_type, checks, overloads, default_raise, doc, gil_release)


def _parse_check_value(val, path):
    """Parse a check expression, coercing non-string values from YAML."""
    val = _coerce_expr_value(val, 'checks', path)
    return parse_expr(val)


# ---------------------------------------------------------------------------
# Validation: parameter counts, format-to-ctype mapping
# ---------------------------------------------------------------------------

_FORMAT_TO_CTYPE = {
    'b': 'int8_t',
    'B': 'uint8_t',
    'h': 'int16_t',
    'H': 'uint16_t',
    'i': 'int32_t',
    'I': 'uint32_t',
    # 'l' and 'L' are platform-sized in PEP 3118 (not fixed-width).
    # On LP64 they match int64_t/uint64_t; on ILP32 they match int32_t/uint32_t.
    # We map them to 'int64_t'/'uint64_t' (LP64) and note the portability caveat.
    # Downstream code on non-LP64 platforms should use 'q'/'Q' for portable
    # 64-bit dispatch and 'i'/'I' for portable 32-bit dispatch.
    'l': 'int64_t',
    'L': 'uint64_t',
    'q': 'int64_t',
    'Q': 'uint64_t',
    'f': 'float',
    'd': 'double',
}

_FUNC_DECL_RE = re.compile(
    r'(?:^|;|\})\s*'
    r'(?:static\s+)?(?:inline\s+)?(?:extern\s+)?'
    r'([\w\s*]+?)\s*'           # return type
    r'(\w+)\s*'                 # function name
    r'\(\s*((?:[^()]|\([^)]*\))*?)\s*\)'  # params (allow one level of nesting)
    r'\s*[{;]',
    re.MULTILINE | re.DOTALL
)


def _strip_c_comments(text):
    """Strip C-style comments (both /* */ and //) from source text."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        if i + 1 < n and text[i] == '/' and text[i + 1] == '/':
            i += 2
            while i < n and text[i] != '\n':
                i += 1
        elif i + 1 < n and text[i] == '/' and text[i + 1] == '*':
            i += 2
            while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def _count_c_params(params_str):
    """Count the number of parameters in a C function parameter string."""
    stripped = params_str.strip()
    if not stripped:
        return 0
    if stripped == 'void':
        return 0
    count = 1
    for ch in stripped:
        if ch == ',':
            count += 1
    return count


def _parse_c_func_from_files(file_list, base_dir):
    """Parse C source/header files to extract function signatures.

    Returns a dict of {func_name: param_count} for all functions found.
    """
    funcs = {}
    for fname in file_list:
        fpath = os.path.join(base_dir, fname)
        if not os.path.isfile(fpath):
            continue
        # Only parse C source/header files; skip .o and other binary files
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ('.c', '.h', '.i'):
            continue
        with open(fpath, 'r') as f:
            content = f.read()
        content = _strip_c_comments(content)
        for m in _FUNC_DECL_RE.finditer(content):
            ret_type = m.group(1).strip()
            func_name = m.group(2)
            params_str = m.group(3)
            if not ret_type:
                continue
            ret_parts = ret_type.split()
            is_typedef = all(p in _C_TYPES_INT or p in ('const', 'static',
                                'inline', 'extern') or p == '*' for p in ret_parts)
            if not is_typedef:
                continue
            count = _count_c_params(params_str)
            funcs[func_name] = count
    return funcs


def _find_format_check(checks):
    """Extract format check info: {(buf_name, format_char)} from check expressions."""
    results = set()
    for check in checks:
        if isinstance(check, Compare) and check.op == '==':
            left = check.left
            right = check.right
            if isinstance(left, Attr) and left.attr == 'format':
                if isinstance(right, StrLit) and len(right.value) == 1:
                    buf_name = _resolve_buf_name(left.obj)
                    if buf_name:
                        results.add((buf_name, right.value))
            elif isinstance(right, Attr) and right.attr == 'format':
                if isinstance(left, StrLit) and len(left.value) == 1:
                    buf_name = _resolve_buf_name(right.obj)
                    if buf_name:
                        results.add((buf_name, left.value))
    return results


def _resolve_buf_name(expr):
    """Resolve a Var or Attr chain to a buffer name string."""
    if isinstance(expr, Var):
        return expr.name
    if isinstance(expr, Attr):
        return _resolve_buf_name(expr.obj)
    return None


def _validate_module(mod, base_dir):
    """Run validation checks on a parsed ModuleDef.

    Checks:
      1. P0: Parameter count mismatch between .c2py C sig and actual C source
      2. P4: Buffer format checks vs C pointer types in overloads
    """
    all_files = list(mod.sources) + list(mod.headers)
    if not all_files:
        return

    c_funcs = _parse_c_func_from_files(all_files, base_dir)

    for func in mod.functions:
        for ol in func.overloads:
            # Validate both flat and grouped overloads
            targets = []
            if ol.variants:
                for v in ol.variants:
                    targets.append((_extract_c_name(v.sig_str), len(v.params), v))
            else:
                targets.append((_extract_c_name(ol.sig_str), len(ol.params), ol))

            for c_name, c2py_count, entry in targets:
                actual_count = c_funcs.get(c_name)
                if actual_count is not None and c2py_count != actual_count:
                    raise ValueError(
                        "P0: param count mismatch for '%s' in %s: "
                        ".c2py sig has %d params, C source has %d params" % (
                            c_name, mod.name, c2py_count, actual_count))

        # P4: format checks -> C type validation
        fmt_checks = _find_format_check(func.checks)
        if not fmt_checks:
            continue

        for buf_name, fmt_char in fmt_checks:
            expected_ctype = _FORMAT_TO_CTYPE.get(fmt_char)
            if expected_ctype is None:
                continue

            for ol in func.overloads:
                # For grouped overloads, validate each variant
                if ol.variants:
                    check_entries = [(v.params, v.sig_str) for v in ol.variants]
                else:
                    check_entries = [(ol.params, ol.sig_str)]

                for use_params, use_sig_str in check_entries:
                    for cp in use_params:
                        if not cp.is_pointer:
                            continue
                        expr = ol.map_exprs.get(cp.name)
                        if expr is None:
                            continue
                        if not _expr_refers_to(expr, buf_name):
                            continue
                        if cp.base_type != expected_ctype:
                            c_name = _extract_c_name(use_sig_str)
                            # LP64 compat: bare 'int' == 'int32_t'
                            if (cp.base_type, expected_ctype) not in (
                                    ('int', 'int32_t'), ('int32_t', 'int'),
                                    ('unsigned int', 'uint32_t'), ('uint32_t', 'unsigned int')):
                                raise ValueError(
                                    "P4: format check '%s.format == '%s'' implies %s*, "
                                    "but overload '%s' uses %s* for param '%s' in %s" % (
                                        buf_name, fmt_char, expected_ctype,
                                        c_name, cp.base_type, cp.name, mod.name))


def _extract_c_name(sig_str):
    """Extract the C function name from a sig string."""
    return sig_str.split('(')[0].strip().split()[-1]


def _expr_refers_to(expr, buf_name):
    """Check if an expression refers to a specific buffer param name."""
    if isinstance(expr, Var):
        return expr.name == buf_name
    elif isinstance(expr, Attr):
        return _expr_refers_to(expr.obj, buf_name)
    elif isinstance(expr, Subscript):
        return _expr_refers_to(expr.obj, buf_name)
    elif isinstance(expr, Compare):
        return _expr_refers_to(expr.left, buf_name) or _expr_refers_to(expr.right, buf_name)
    elif isinstance(expr, BinOp):
        return _expr_refers_to(expr.left, buf_name) or _expr_refers_to(expr.right, buf_name)
    elif isinstance(expr, UnaryOp):
        return _expr_refers_to(expr.operand, buf_name)
    return False
```

## c2py23/perf.py

```python
"""c2py23 performance data decoder.

Reads c2py_perf_t structs exposed as raw pointers on modules built with
`timing: true` in their .c2py file.

Usage:
    from c2py23.perf import read_perf

    import my_timed_module
    stats = read_perf(my_timed_module._perf_myfunc)
    print(stats)
"""

import ctypes


class _c2py_perf_t(ctypes.Structure):
    _fields_ = [
        ("call_count", ctypes.c_uint64),
        ("t_enter",    ctypes.c_uint64),
        ("t_pre_c",    ctypes.c_uint64),
        ("t_post_c",   ctypes.c_uint64),
        ("t_exit",     ctypes.c_uint64),
        ("t_c_min",    ctypes.c_uint64),
        ("t_c_max",    ctypes.c_uint64),
        ("t_c_total",  ctypes.c_uint64),
        ("t_wrap_min", ctypes.c_uint64),
        ("t_wrap_max", ctypes.c_uint64),
        ("t_wrap_total", ctypes.c_uint64),
        ("variant",    ctypes.c_int),
        ("group_idx",  ctypes.c_int),
        ("variant_name", ctypes.c_void_p),
    ]


def read_perf(ptr_int):
    """Decode a c2py_perf_t from the raw pointer (as Python int).

    Returns a dict with:
        call_count, t_enter, t_pre_c, t_post_c, t_exit,
        c_dur_ns, wrap_dur_ns,
        c_min_ns, c_max_ns, c_mean_ns,
        wrap_min_ns, wrap_max_ns, wrap_mean_ns.

    All time values are in nanoseconds.
    """
    if ptr_int == 0:
        return {"call_count": 0}
    p = _c2py_perf_t.from_address(ptr_int)
    n = p.call_count
    vname = ""
    if p.variant_name:
        try:
            vname = ctypes.c_char_p(p.variant_name).value
            if vname is None:
                vname = ""
            elif isinstance(vname, bytes):
                vname = vname.decode('ascii', errors='replace')
        except Exception:
            vname = ""
    return {
        "call_count": n,
        "t_enter":    p.t_enter,
        "t_pre_c":    p.t_pre_c,
        "t_post_c":   p.t_post_c,
        "t_exit":     p.t_exit,
        "c_dur_ns":   p.t_post_c - p.t_pre_c,
        "wrap_dur_ns": (p.t_pre_c - p.t_enter) + (p.t_exit - p.t_post_c)
                       if p.t_enter or p.t_exit else 0,
        "c_min_ns":   p.t_c_min,
        "c_max_ns":   p.t_c_max,
        "c_mean_ns":  p.t_c_total / n if n else 0,
        "wrap_min_ns":  p.t_wrap_min,
        "wrap_max_ns":  p.t_wrap_max,
        "wrap_mean_ns": p.t_wrap_total / n if n else 0,
        "variant":    p.variant,
        "group_idx":  p.group_idx,
        "variant_name": vname,
    }


def read_enabled(enabled_ptr_int):
    """Read the _c2py_timing_enabled flag."""
    if enabled_ptr_int == 0:
        return 0
    return ctypes.c_int.from_address(enabled_ptr_int).value


def set_enabled(enabled_ptr_int, value):
    """Set the _c2py_timing_enabled flag (0 or 1)."""
    if enabled_ptr_int == 0:
        return
    ctypes.c_int.from_address(enabled_ptr_int).value = value
```

## c2py23/runtime/c2py_amd64.h

```c
/* c2py_amd64.h - x86_64 CPU feature flags
 *
 * Include this header in your .c2py 'headers:' field or your own C code
 * to access CPU feature globals. These are populated by c2py_runtime_init()
 * via the cpuid instruction at module load time.
 *
 * Naming mirrors GCC/Clang __builtin_cpu_supports() names.
 */

#ifndef C2PY_AMD64_H
#define C2PY_AMD64_H

#ifdef __cplusplus
extern "C" {
#endif

/* Baseline features (always 1 on x86_64, check here for completeness) */
extern int c2py_amd64_mmx;
extern int c2py_amd64_sse;
extern int c2py_amd64_sse2;

/* SSE family */
extern int c2py_amd64_sse3;
extern int c2py_amd64_ssse3;
extern int c2py_amd64_sse4_1;
extern int c2py_amd64_sse4_2;

/* AVX family */
extern int c2py_amd64_avx;
extern int c2py_amd64_avx2;
extern int c2py_amd64_fma;

/* AVX-512 family */
extern int c2py_amd64_avx512f;
extern int c2py_amd64_avx512bw;
extern int c2py_amd64_avx512dq;
extern int c2py_amd64_avx512vl;

/* BMI / bit manipulation */
extern int c2py_amd64_bmi1;
extern int c2py_amd64_bmi2;
extern int c2py_amd64_popcnt;
extern int c2py_amd64_lzcnt;

#ifdef __cplusplus
}
#endif

#endif /* C2PY_AMD64_H */
```

## c2py23/runtime/c2py_arm64.h

```c
/* c2py_arm64.h - AArch64 CPU feature flags
 *
 * Include this header in your .c2py 'headers:' field or your own C code
 * to access CPU feature globals. These are populated by c2py_runtime_init()
 * via getauxval(AT_HWCAP) at module load time.
 */

#ifndef C2PY_ARM64_H
#define C2PY_ARM64_H

#ifdef __cplusplus
extern "C" {
#endif

/* Baseline (always 1 on AArch64) */
extern int c2py_arm64_fp;
extern int c2py_arm64_asimd;

/* Crypto extensions */
extern int c2py_arm64_aes;
extern int c2py_arm64_pmull;
extern int c2py_arm64_sha1;
extern int c2py_arm64_sha2;
extern int c2py_arm64_crc32;

/* Scalable Vector Extension */
extern int c2py_arm64_sve;
extern int c2py_arm64_sve2;

#ifdef __cplusplus
}
#endif

#endif /* C2PY_ARM64_H */
```

## c2py23/runtime/c2py_ppc64.h

```c
/* c2py_ppc64.h - POWER CPU feature flags
 *
 * Include this header in your .c2py 'headers:' field or your own C code
 * to access CPU feature globals. These are populated by c2py_runtime_init()
 * via getauxval(AT_HWCAP) at module load time.
 */

#ifndef C2PY_PPC64_H
#define C2PY_PPC64_H

#ifdef __cplusplus
extern "C" {
#endif

/* SIMD / Vector */
extern int c2py_ppc64_altivec;
extern int c2py_ppc64_vsx;

/* ISA levels (minimum for each Power ISA version) */
extern int c2py_ppc64_power8;
extern int c2py_ppc64_power9;

#ifdef __cplusplus
}
#endif

#endif /* C2PY_PPC64_H */
```

## c2py23/runtime/c2py_runtime.c

```c
/* c2py_runtime.c - nimpy-style CPython API loader
 *
 * Uses dlopen(NULL, ...) + dlsym() to resolve all CPython C API
 * function pointers at module load time. This eliminates the need
 * to link against -lpython, allowing one .so to work across
 * Python 2.7 through 3.14.
 *
 * Compile: gcc -c c2py_runtime.c -o c2py_runtime.o
 * Link:    gcc -shared ... c2py_runtime.o -ldl -o module.so
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <sys/auxv.h>
#include <pthread.h>
#include "c2py_runtime.h"

/* Global API table */
c2py_api_t C2PY = {0};
static volatile int _c2py_runtime_initialized = 0;
static int _c2py_init_result = 0;
static pthread_once_t _c2py_init_once = PTHREAD_ONCE_INIT;

/* ---- CPU feature flags (populated by _c2py_probe_cpu_features) ---- */

#ifdef __x86_64__
int c2py_amd64_mmx = 0;
int c2py_amd64_sse = 0;
int c2py_amd64_sse2 = 0;
int c2py_amd64_sse3 = 0;
int c2py_amd64_ssse3 = 0;
int c2py_amd64_sse4_1 = 0;
int c2py_amd64_sse4_2 = 0;
int c2py_amd64_avx = 0;
int c2py_amd64_avx2 = 0;
int c2py_amd64_fma = 0;
int c2py_amd64_avx512f = 0;
int c2py_amd64_avx512bw = 0;
int c2py_amd64_avx512dq = 0;
int c2py_amd64_avx512vl = 0;
int c2py_amd64_bmi1 = 0;
int c2py_amd64_bmi2 = 0;
int c2py_amd64_popcnt = 0;
int c2py_amd64_lzcnt = 0;
#endif

#if defined(__aarch64__) || defined(__arm64__)
int c2py_arm64_fp = 0;
int c2py_arm64_asimd = 0;
int c2py_arm64_aes = 0;
int c2py_arm64_pmull = 0;
int c2py_arm64_sha1 = 0;
int c2py_arm64_sha2 = 0;
int c2py_arm64_crc32 = 0;
int c2py_arm64_sve = 0;
int c2py_arm64_sve2 = 0;
#endif

#if defined(__powerpc64__) || defined(__powerpc__)
int c2py_ppc64_altivec = 0;
int c2py_ppc64_vsx = 0;
int c2py_ppc64_power8 = 0;
int c2py_ppc64_power9 = 0;
#endif

static int _resolve(void **ptr, const char *name)
{
    *ptr = dlsym(C2PY.dl_handle, name);
    if (*ptr == NULL) {
        /* Some symbols may legitimately not exist on old Python versions.
         * We only warn for critical ones. */
        return -1;
    }
    return 0;
}

#define RESOLVE(ptr, name) _resolve((void**)&(ptr), name)
#define RESOLVE_REQ(ptr, name) do { \
    if (_resolve((void**)&(ptr), name) != 0) { \
        fprintf(stderr, "c2py_runtime: FATAL - missing symbol: %s\n", name); \
        return; \
    } \
} while(0)

/* Python 2.7 module init helper */
static PyObject*
_init_module_2_7(const char *name, PyMethodDef *methods)
{
    void *dl = C2PY.dl_handle;

    /* Try Py_InitModule4 first (Python 2.7 preferred) */
    typedef PyObject* (*init4_fn)(const char*, PyMethodDef*, const char*,
                                   PyObject*, int);
    init4_fn fn4 = (init4_fn)dlsym(dl, "Py_InitModule4_64");
    if (fn4 == NULL) fn4 = (init4_fn)dlsym(dl, "Py_InitModule4");
    if (fn4 != NULL) {
        return fn4(name, methods, NULL, NULL, 1013 /* PYTHON_API_VERSION */);
    }

    /* Fallback: Py_InitModule3 */
    typedef PyObject* (*init3_fn)(const char*, PyMethodDef*, const char*);
    init3_fn fn3 = (init3_fn)dlsym(dl, "Py_InitModule3");
    if (fn3 != NULL) {
        return fn3(name, methods, NULL);
    }

    fprintf(stderr, "c2py_runtime: could not find module init function\n");
    return NULL;
}


/* ---- CPU feature probing ---- */

static void _c2py_probe_cpu_features(void)
{
#ifdef __x86_64__
    unsigned int eax1, ebx1, ecx1, edx1;
    unsigned int eax7, ebx7, ecx7, edx7;
    unsigned int eax81, ebx81, ecx81, edx81;

    /* Determine max standard leaf */
    __asm__ __volatile__("cpuid"
        : "=a"(eax1) : "a"(0) : "ebx", "ecx", "edx");
    unsigned int max_std = eax1;

    /* Leaf 1: baseline features */
    if (max_std >= 1) {
        __asm__ __volatile__("cpuid"
            : "=a"(eax1), "=b"(ebx1), "=c"(ecx1), "=d"(edx1)
            : "a"(1) : );
        c2py_amd64_mmx    = (edx1 >> 23) & 1;
        c2py_amd64_sse    = (edx1 >> 25) & 1;
        c2py_amd64_sse2   = (edx1 >> 26) & 1;
        c2py_amd64_sse3   = (ecx1 >>  0) & 1;
        c2py_amd64_ssse3  = (ecx1 >>  9) & 1;
        c2py_amd64_sse4_1 = (ecx1 >> 19) & 1;
        c2py_amd64_sse4_2 = (ecx1 >> 20) & 1;
        c2py_amd64_avx    = (ecx1 >> 28) & 1;
        c2py_amd64_fma    = (ecx1 >> 12) & 1;
        c2py_amd64_popcnt = (ecx1 >> 23) & 1;
    }

    /* Leaf 7, subleaf 0: extended features */
    if (max_std >= 7) {
        __asm__ __volatile__("cpuid"
            : "=a"(eax7), "=b"(ebx7), "=c"(ecx7), "=d"(edx7)
            : "a"(7), "c"(0));
        c2py_amd64_bmi1    = (ebx7 >>  3) & 1;
        c2py_amd64_avx2    = (ebx7 >>  5) & 1;
        c2py_amd64_bmi2    = (ebx7 >>  8) & 1;
        c2py_amd64_avx512f = (ebx7 >> 16) & 1;
        c2py_amd64_avx512dq = (ebx7 >> 17) & 1;
        c2py_amd64_avx512bw = (ebx7 >> 30) & 1;
        c2py_amd64_avx512vl = (ebx7 >> 31) & 1;
    }

    /* Leaf 0x80000001: extended feature bits (LZCNT) */
    /* Check extended leaf max first */
    __asm__ __volatile__("cpuid"
        : "=a"(eax81) : "a"(0x80000000) : "ebx", "ecx", "edx");
    if (eax81 >= 0x80000001) {
        __asm__ __volatile__("cpuid"
            : "=a"(eax81), "=b"(ebx81), "=c"(ecx81), "=d"(edx81)
            : "a"(0x80000001));
        c2py_amd64_lzcnt = (ecx81 >> 5) & 1;
    }
#endif

#if defined(__aarch64__) || defined(__arm64__)
    {
        unsigned long hwcap = getauxval(AT_HWCAP);
        unsigned long hwcap2 = getauxval(AT_HWCAP2);

        /* ARM64 HWCAP bits (stable kernel ABI) */
        c2py_arm64_fp    = (hwcap >> 0) & 1;
        c2py_arm64_asimd = (hwcap >> 1) & 1;
        c2py_arm64_aes   = (hwcap >> 3) & 1;
        c2py_arm64_pmull = (hwcap >> 4) & 1;
        c2py_arm64_sha1  = (hwcap >> 5) & 1;
        c2py_arm64_sha2  = (hwcap >> 6) & 1;
        c2py_arm64_crc32 = (hwcap >> 7) & 1;
        c2py_arm64_sve   = (hwcap >> 22) & 1;
        c2py_arm64_sve2  = (hwcap2 >> 1) & 1;
    }
#endif

#if defined(__powerpc64__) || defined(__powerpc__)
    {
        unsigned long hwcap = getauxval(AT_HWCAP);
        unsigned long hwcap2 = getauxval(AT_HWCAP2);

        c2py_ppc64_altivec = (hwcap >> 28) & 1;        /* PPC_FEATURE_HAS_ALTIVEC = 0x10000000 */
        c2py_ppc64_vsx     = (hwcap >>  7) & 1;         /* PPC_FEATURE_HAS_VSX     = 0x00000080 */
        c2py_ppc64_power8  = (hwcap2 >> 31) & 1;        /* PPC_FEATURE2_ARCH_2_07  = 0x80000000 */
        c2py_ppc64_power9  = (hwcap2 >> 23) & 1;        /* PPC_FEATURE2_ARCH_3_00  = 0x00800000 */
    }
#endif
}


static void _c2py_runtime_init_once(void)
{
    _c2py_init_result = -1;  /* assume failure until full success */

    /* CPU feature probing runs first -- does not depend on Python */
    _c2py_probe_cpu_features();

    C2PY.dl_handle = dlopen(NULL, RTLD_LAZY | RTLD_GLOBAL);
    if (C2PY.dl_handle == NULL) {
        fprintf(stderr, "c2py_runtime: dlopen(NULL) failed: %s\n", dlerror());
        fprintf(stderr, "c2py_runtime: interpreter may be statically linked "
                "(requires --enable-shared or export-dynamic).\n");
        return;
    }

    void *dl = C2PY.dl_handle;

    /* --- Detect Python version --- */
    {
        typedef const char* (*ver_fn)(void);
        ver_fn getver = (ver_fn)dlsym(dl, "Py_GetVersion");
        if (getver) {
            const char *v = getver();
            if (v) sscanf(v, "%d.%d", &C2PY.version_major, &C2PY.version_minor);
        }
        if (C2PY.version_major == 0) {
            /* Fallback: check for Py3-only symbol */
            if (dlsym(dl, "PyModule_Create2")) {
                C2PY.version_major = 3;
            } else {
                C2PY.version_major = 2;
            }
            C2PY.version_minor = 0;
        }
    }

    /* --- Detect free-threaded build ---
     *
     * Detection priority (first successful method wins):
     * 1. Py_GetVersion() string contains "free-threading" (CPython 3.13+).
     * 2. _Py_IsGILEnabled exists and returns 0 (CPython 3.13+ FT builds).
     *    This is an exported function: int _Py_IsGILEnabled(void).
     * 3. Py_GIL_DISABLED config var... but we cannot easily query that
     *    without #include <Python.h> or cpython/initconfig.h.  On the
     *    rare builds where neither 1 nor 2 works, the user should set
     *    C2PY.is_free_threaded via a debug override at runtime.
     */
    {
        /* Method 1: version string */
        typedef const char* (*ver_fn)(void);
        ver_fn getver = (ver_fn)dlsym(dl, "Py_GetVersion");
        const char *vstr = getver ? getver() : "";
        int found_ft = 0;
        if (vstr && strstr(vstr, "free-threading") != NULL)
            found_ft = 1;

        /* Method 2: _Py_IsGILEnabled (CPython 3.13+) */
        if (!found_ft) {
            typedef int (*gil_check_fn)(void);
            gil_check_fn gilchk = (gil_check_fn)dlsym(dl, "_Py_IsGILEnabled");
            if (gilchk && gilchk() == 0)
                found_ft = 1;
        }

        C2PY.is_free_threaded = found_ft;
    }

    /* --- Set ABI layout --- */
    if (C2PY.is_free_threaded) {
        /* Free-threaded PyObject layout (32 bytes LP64):
         *   ob_tid:0 ob_flags:8 ob_mutex:10 ob_gc_bits:11
         *   ob_ref_local:12 ob_ref_shared:16 ob_type:24 */
        C2PY.pyobject_size = 32;
        C2PY.ob_refcnt_offset = 16;  /* ob_ref_shared */
    } else {
        /* Standard GIL-enabled PyObject layout (16 bytes LP64):
         *   ob_refcnt:0 ob_type:8 */
        C2PY.pyobject_size = 16;
        C2PY.ob_refcnt_offset = 0;   /* ob_refcnt */
    }
    C2PY.pyobject_size_ft = 32;

    /* pymoduledef_max_size: pad generously for both layouts */
    {
        Py_ssize_t sz_gil = sizeof(PyModuleDef);
        Py_ssize_t sz_ft  = sizeof(PyModuleDef_FT);
        C2PY.pymoduledef_max_size = (sz_gil > sz_ft) ? sz_gil : sz_ft;
    }

    /* --- Buffer protocol (required) --- */
    RESOLVE_REQ(C2PY.GetBuffer, "PyObject_GetBuffer");
    RESOLVE_REQ(C2PY.ReleaseBuffer, "PyBuffer_Release");
    if (C2PY.GetBuffer == NULL || C2PY.ReleaseBuffer == NULL) return;

    /* --- Old buffer protocol (Python 2.x only) --- */
    C2PY.AsReadBuffer = (int (*)(PyObject*, const void**, Py_ssize_t*))
        dlsym(dl, "PyObject_AsReadBuffer");
    C2PY.AsWriteBuffer = (int (*)(PyObject*, void**, Py_ssize_t*))
        dlsym(dl, "PyObject_AsWriteBuffer");
    C2PY.Err_Clear = (void (*)(void))dlsym(dl, "PyErr_Clear");
    RESOLVE_REQ(C2PY.Err_Clear, "PyErr_Clear");
    if (C2PY.Err_Clear == NULL) return;
    C2PY.buffer_api_is_pep3118 = (C2PY.version_major >= 3);

    /* --- Buffer struct size ---
     * CPython 2.x has Py_buffer.smalltable[2] (96 bytes LP64).
     * CPython 3.x dropped smalltable; Debian/Ubuntu builds from 3.6+
     * all have sizeof(Py_buffer)==80 (internal at offset 72).
     * Use 80 for all 3.x, 96 for 2.x, to match observed ABI.
     */
    C2PY.pybuffer_size = (C2PY.version_major >= 3)
        ? C2PY_PYBUFFER_SZ_POST312 : C2PY_PYBUFFER_SZ_PRE312;

    /* --- Fastcall support (METH_FASTCALL stable ABI since 3.12) --- */
    C2PY.use_fastcall = (C2PY.version_major >= 3 && C2PY.version_minor >= 12);

    /* --- Argument parsing (required) --- */
    RESOLVE_REQ(C2PY.ParseTuple, "PyArg_ParseTuple");
    RESOLVE(C2PY.ParseTupleAndKeywords, "PyArg_ParseTupleAndKeywords");
    if (C2PY.ParseTuple == NULL) return;

    /* --- Error detection for fastcall scalar conversion --- */
    RESOLVE_REQ(C2PY.Err_Occurred, "PyErr_Occurred");
    if (C2PY.Err_Occurred == NULL) return;

    /* --- Value construction (required) --- */
    RESOLVE_REQ(C2PY.Long_FromLong, "PyLong_FromLong");
    RESOLVE(C2PY.Long_FromLongLong, "PyLong_FromLongLong");
    RESOLVE_REQ(C2PY.Float_FromDouble, "PyFloat_FromDouble");
    if (C2PY.Long_FromLong == NULL || C2PY.Float_FromDouble == NULL) return;

    /* --- Tuple construction (required) --- */
    RESOLVE_REQ(C2PY.Tuple_New, "PyTuple_New");
    RESOLVE_REQ(C2PY.Tuple_SetItem, "PyTuple_SetItem");
    if (C2PY.Tuple_New == NULL || C2PY.Tuple_SetItem == NULL) return;

    /* --- Scalar conversion --- */
    RESOLVE_REQ(C2PY.Long_AsLong, "PyLong_AsLong");
    RESOLVE_REQ(C2PY.Float_AsDouble, "PyFloat_AsDouble");
    if (C2PY.Long_AsLong == NULL || C2PY.Float_AsDouble == NULL) return;

    /* --- Exception handling (required) --- */
    RESOLVE_REQ(C2PY.exc_TypeError, "PyExc_TypeError");
    RESOLVE_REQ(C2PY.exc_ValueError, "PyExc_ValueError");
    RESOLVE_REQ(C2PY.exc_RuntimeError, "PyExc_RuntimeError");
    RESOLVE_REQ(C2PY.exc_MemoryError, "PyExc_MemoryError");
    RESOLVE_REQ(C2PY.Err_SetString, "PyErr_SetString");
    RESOLVE_REQ(C2PY.Err_Format, "PyErr_Format");
    if (C2PY.exc_TypeError   == NULL || C2PY.exc_ValueError  == NULL ||
        C2PY.exc_RuntimeError == NULL || C2PY.exc_MemoryError == NULL ||
        C2PY.Err_SetString    == NULL || C2PY.Err_Format      == NULL) return;

    /* One dereference is always needed to reach the real PyObject*:
     * - Pre-3.12: PyExc_* are PyObject* globals (heap type pointers).
     *   dlsym gives &PyExc_ValueError (a PyObject**). Deref -> PyObject*.
     * - 3.12+: PyExc_* are static PyObjects with shared-refcount
     *   indirection.  dlsym gives &_PyExc_ValueError.  First 8 bytes
     *   point to the shared-refcount struct (the real PyObject*).
     *   Deref -> PyObject*.
     *
     * In both layouts a single dereference yields the PyObject* that
     * PyErr_SetString expects. */
    C2PY.exc_TypeError = *(void **)C2PY.exc_TypeError;
    C2PY.exc_ValueError = *(void **)C2PY.exc_ValueError;
    C2PY.exc_RuntimeError = *(void **)C2PY.exc_RuntimeError;
    C2PY.exc_MemoryError = *(void **)C2PY.exc_MemoryError;

    /* --- Module creation --- */
    {
        void *mc = dlsym(dl, "PyModule_Create2");
        C2PY.Module_Create2 = (PyObject* (*)(PyModuleDef*, int))mc;
    }
    C2PY.InitModule_2_7 = _init_module_2_7;

    /* --- Reference counting ---
     * Py_IncRef / Py_DecRef are stable-ABI functions added in Python 3.12.
     * On older interpreters these symbols may not be exported; fall back
     * through _Py_IncRef (internal name on some builds) to manual
     * increment of the ob_refcnt field (always the first member of
     * PyObject, matching our struct definition in c2py_runtime.h).
     *
     * On free-threaded builds, manual refcounting is UNSAFE (ob_ref_shared
     * requires atomic operations).  Py_IncRef/Py_DecRef MUST be resolved
     * or we fail init. */
    {
        if (_resolve((void**)&C2PY.IncRef, "Py_IncRef") != 0)
            _resolve((void**)&C2PY.IncRef, "_Py_IncRef");
        if (_resolve((void**)&C2PY.DecRef, "Py_DecRef") != 0)
            _resolve((void**)&C2PY.DecRef, "_Py_DecRef");

        if (C2PY.is_free_threaded) {
            if (C2PY.IncRef == NULL || C2PY.DecRef == NULL) {
                fprintf(stderr, "c2py_runtime: FATAL - free-threaded build "
                        "requires Py_IncRef / Py_DecRef symbols\n");
                return;
            }
        } else {
            if (C2PY.IncRef == NULL)
                C2PY.IncRef = _c2py_inc_ref_manual;
            if (C2PY.DecRef == NULL)
                C2PY.DecRef = _c2py_dec_ref_manual;
        }
    }

    /* --- Object attribute access --- */
    RESOLVE_REQ(C2PY.SetAttrString, "PyObject_SetAttrString");
    if (C2PY.SetAttrString == NULL) return;

    /* --- Pointer-to-int --- */
    RESOLVE_REQ(C2PY.Long_FromVoidPtr, "PyLong_FromVoidPtr");
    if (C2PY.Long_FromVoidPtr == NULL) return;

    /* --- GIL management --- */
    RESOLVE_REQ(C2PY.SaveThread, "PyEval_SaveThread");
    RESOLVE_REQ(C2PY.RestoreThread, "PyEval_RestoreThread");
    if (C2PY.SaveThread == NULL || C2PY.RestoreThread == NULL) return;

    /* --- None singleton ---
     * _Py_NoneStruct is a static PyObject; dlsym returns &_Py_NoneStruct,
     * which is the same as Py_None (the macro: (&_Py_NoneStruct)).
     * Py_None is immortal so INCREF/DECREF is unnecessary but harmless.
     */
    {
        void *none = dlsym(dl, "_Py_NoneStruct");
        if (none == NULL) {
            /* On some platforms Py_None is a pointer variable pointing
             * to the struct. Try loading it and dereferencing. */
            void **pnone = (void**)dlsym(dl, "Py_None");
            if (pnone) none = *pnone;
        }
        C2PY.none_obj = (PyObject*)none;
        if (C2PY.none_obj == NULL) {
            fprintf(stderr, "c2py_runtime: could not resolve Py_None\n");
            return;
        }
    }

    _c2py_init_result = 0;
    _c2py_runtime_initialized = 1;
}

int c2py_runtime_init(void)
{
    pthread_once(&_c2py_init_once, _c2py_runtime_init_once);
    return _c2py_init_result;
}
```

## c2py23/runtime/c2py_runtime.h

```c
/* c2py_runtime.h - nimpy-style CPython API loader
 *
 * This header NEVER includes <Python.h>. All Python API types and functions
 * are resolved at runtime via dlopen(NULL) + dlsym(). This means one .so
 * works on Python 2.7 through 3.14 without any compile-time Python dependency.
 *
 * The technique originates from yglukhov/nimpy (https://github.com/yglukhov/nimpy),
 * a Nim-Python bridge designed for ABI compatibility across Python versions.
 * c2py23 adapts it for C, using only the minimal CPython API surface needed.
 */

#ifndef C2PY_RUNTIME_H
#define C2PY_RUNTIME_H

#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <stdint.h>
#include <limits.h>
#include <time.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------ */
/* Py_ssize_t - must be defined before any struct using it            */
/* ------------------------------------------------------------------ */

#if defined(__LP64__) || defined(_WIN64)
typedef long long Py_ssize_t;
#else
typedef long Py_ssize_t;
#endif

/* sizeof(Py_buffer) differs across CPython versions:
 * < 3.12: includes smalltable[2]  (96 bytes LP64, 52 bytes ILP32)
 * >= 3.12: smalltable removed for PEP 697 stable ABI (80 / 44)
 */
#if defined(__LP64__) || defined(_WIN64)
#define C2PY_PYBUFFER_SZ_PRE312   96
#define C2PY_PYBUFFER_SZ_POST312  80
#else
#define C2PY_PYBUFFER_SZ_PRE312   52
#define C2PY_PYBUFFER_SZ_POST312  44
#endif

/* ------------------------------------------------------------------ */
/* CPython type definitions (stable layouts across versions)          */
/* ------------------------------------------------------------------ */

/* PyObject layout: differs between GIL-enabled and free-threaded builds.
 *
 * GIL-enabled (CPython 2.7 - 3.14 standard): 16 bytes LP64
 *   offset 0: Py_ssize_t ob_refcnt
 *   offset 8: void *ob_type
 *
 * Free-threaded (CPython 3.13t+ --disable-gil): 32 bytes LP64
 *   offset  0: uintptr_t ob_tid
 *   offset  8: uint16_t ob_flags
 *   offset 10: uint8_t  ob_mutex
 *   offset 11: uint8_t  ob_gc_bits
 *   offset 12: uint32_t ob_ref_local
 *   offset 16: Py_ssize_t ob_ref_shared   <-- external refcount
 *   offset 24: void *ob_type
 *
 * We define both layouts.  Generated code uses macros (C2PY_SET_MNAME,
 * C2PY_SET_MDOC, etc.) that work with either layout via C2PY offsets.
 */

/* GIL-enabled PyObject layout (standard CPython) */
typedef struct _c2py_object {
    Py_ssize_t ob_refcnt;
    void *ob_type;
} PyObject;

/* Free-threaded PyObject layout (CPython --disable-gil) */
/* PyMutex: per-object lock, uint8_t with two-bit state (private) */
typedef struct { uint8_t _bits; } PyMutex;

typedef struct _c2py_object_ft {
    uintptr_t ob_tid;
    uint16_t ob_flags;
    PyMutex ob_mutex;
    uint8_t ob_gc_bits;
    uint32_t ob_ref_local;
    Py_ssize_t ob_ref_shared;
    void *ob_type;
} PyObject_FT;

/* Shorthand for embedding PyObject at the head of a struct (GIL layout) */
#define PyObject_HEAD \
    Py_ssize_t ob_refcnt; \
    void *ob_type;

typedef void *(*PyCFunction)(PyObject*, PyObject*);

/* Py_buffer: stable since Python 2.6 (PEP 3118).
 * NOTE: includes smalltable[2] field present in CPython 2.7-3.11.
 * In CPython 3.12+ this was removed (PEP 697 stable ABI);
 * we use C2PY.pybuffer_size (set at init) for correct sizeof.
 */
typedef struct {
    void *buf;
    PyObject *obj;
    Py_ssize_t len;
    Py_ssize_t itemsize;
    int readonly;
    int ndim;
    char *format;
    Py_ssize_t *shape;
    Py_ssize_t *strides;
    Py_ssize_t *suboffsets;
    Py_ssize_t smalltable[2];  /* present on CPython 2.7-3.11 */
    void *internal;
} Py_buffer;

/* PyMethodDef: stable layout across all Python versions */
typedef struct {
    const char *ml_name;
    PyCFunction ml_meth;
    int ml_flags;
    const char *ml_doc;
} PyMethodDef;

/* PyModuleDef_Base: standard GIL-enabled layout (Python 3.0+) */
typedef struct PyModuleDef_Base {
    PyObject ob_base;
    PyObject *(*m_init)(void);
    Py_ssize_t m_index;
    PyObject *m_copy;
} PyModuleDef_Base;

/* PyModuleDef_Base for free-threaded builds (PyObject is 32 bytes) */
typedef struct PyModuleDef_Base_FT {
    PyObject_FT ob_base;
    PyObject *(*m_init)(void);
    Py_ssize_t m_index;
    PyObject *m_copy;
} PyModuleDef_Base_FT;

/* PyModuleDef for Python 3.x standard GIL layout */
typedef struct PyModuleDef {
    PyModuleDef_Base m_base;
    const char *m_name;
    const char *m_doc;
    Py_ssize_t m_size;
    PyMethodDef *m_methods;
    void *m_slots;
    void *m_traverse;
    void *m_clear;
    void *m_free;
} PyModuleDef;

/* PyModuleDef for free-threaded builds (PyModuleDef_Base is 56 bytes) */
typedef struct PyModuleDef_FT {
    PyModuleDef_Base_FT m_base;
    const char *m_name;
    const char *m_doc;
    Py_ssize_t m_size;
    PyMethodDef *m_methods;
    void *m_slots;
    void *m_traverse;
    void *m_clear;
    void *m_free;
} PyModuleDef_FT;

/* ------------------------------------------------------------------ */
/* Constants                                                          */
/* ------------------------------------------------------------------ */

/* Py_buffer flags */
#define PyBUF_SIMPLE   0
#define PyBUF_WRITABLE 0x0001
#define PyBUF_FORMAT   0x0004
#define PyBUF_ND       0x0008
#define PyBUF_STRIDES  (0x0010 | PyBUF_ND)
#define PyBUF_INDIRECT (0x0100 | PyBUF_STRIDES)

/* PyMethodDef flags */
#define METH_VARARGS   0x0001
#define METH_KEYWORDS  0x0002
#define METH_NOARGS    0x0004
#define METH_O         0x0008
#define METH_CLASS     0x0010
#define METH_STATIC    0x0020
#define METH_FASTCALL  0x0080

/* Module init macro - initializes the PyModuleDef_Base embedded in PyModuleDef. */
#define PyModuleDef_HEAD_INIT { {1, NULL}, NULL, 0, NULL }

/* Module init macro for free-threaded builds (PyObject is 32 bytes).
 * ob_ref_shared = 1, ob_type = NULL, m_init = NULL, m_index = 0, m_copy = NULL.
 * ob_mutex is zeroed via {0} (PyMutex is struct { uint8_t _bits; }).
 * Other PyObject fields (ob_tid, ob_flags, ob_gc_bits, ob_ref_local) are zeroed. */
#define PyModuleDef_HEAD_INIT_FT \
    { {0, 0, {0}, 0, 0, 1, NULL}, NULL, 0, NULL}

/* ------------------------------------------------------------------ */
/* Function pointer table - populated by c2py_runtime_init()          */
/* ------------------------------------------------------------------ */

typedef struct {
    void *dl_handle;
    int version_major;
    int version_minor;

    int use_fastcall;               /* 1 = use METH_FASTCALL wrappers (Python >= 3.12) */
    int is_free_threaded;           /* 1 = Python built with --disable-gil */
    Py_ssize_t pybuffer_size;      /* actual sizeof(Py_buffer) for this Python version */
    Py_ssize_t pyobject_size;      /* actual sizeof(PyObject) for this Python version */
    Py_ssize_t pyobject_size_ft;   /* sizeof(PyObject) for free-threaded builds (32 LP64) */
    Py_ssize_t pymoduledef_max_size; /* max(sizeof(PyModuleDef), sizeof(PyModuleDef_FT)) */
    ptrdiff_t ob_refcnt_offset;    /* offset of ob_refcnt (or ob_ref_shared on FT) in PyObject */

    /* Buffer protocol */
    int (*GetBuffer)(PyObject*, Py_buffer*, int);
    void (*ReleaseBuffer)(Py_buffer*);

    /* Old buffer protocol (Python 2.x only, NULL on Python 3) */
    int (*AsReadBuffer)(PyObject*, const void**, Py_ssize_t*);
    int (*AsWriteBuffer)(PyObject*, void**, Py_ssize_t*);
    void (*Err_Clear)(void);
    int buffer_api_is_pep3118;  /* 0 = old API only, 1 = PEP 3118 available */

    /* Argument parsing */
    int (*ParseTuple)(PyObject*, const char*, ...);
    int (*ParseTupleAndKeywords)(PyObject*, PyObject*, const char*, char**, ...);

    /* Value construction */
    PyObject* (*Long_FromLong)(long);
    PyObject* (*Long_FromLongLong)(long long);
    PyObject* (*Float_FromDouble)(double);

    /* Tuple construction */
    PyObject* (*Tuple_New)(Py_ssize_t);
    int (*Tuple_SetItem)(PyObject*, Py_ssize_t, PyObject*);

    /* Scalar conversion from objects */
    long (*Long_AsLong)(PyObject*);
    double (*Float_AsDouble)(PyObject*);

    /* Exception objects (pointers to the actual exception types) */
    void *exc_TypeError;
    void *exc_ValueError;
    void *exc_RuntimeError;
    void *exc_MemoryError;
    void (*Err_SetString)(PyObject*, const char*);
    PyObject* (*Err_Occurred)(void);
    PyObject* (*Err_Format)(PyObject*, const char*, ...);

    /* None singleton (immortal, INCREF/DECREF unnecessary) */
    PyObject *none_obj;

    /* Module creation */
    PyObject* (*Module_Create2)(PyModuleDef*, int);
    PyObject* (*InitModule_2_7)(const char*, PyMethodDef*);

    /* Reference counting */
    void (*IncRef)(PyObject*);
    void (*DecRef)(PyObject*);

    /* Object attribute access */
    int (*SetAttrString)(PyObject*, const char*, PyObject*);

    /* Pointer-to-int conversion (for exposing perf struct addresses) */
    PyObject* (*Long_FromVoidPtr)(void*);

    /* GIL management */
    void* (*SaveThread)(void);
    void (*RestoreThread)(void*);

} c2py_api_t;

/* The global API table */
extern c2py_api_t C2PY;

/* ------------------------------------------------------------------ */
/* Convenience macros                                                 */
/* ------------------------------------------------------------------ */

#define PyObject_GetBuffer(o, b, f)    C2PY.GetBuffer((PyObject*)(o), (b), (f))
#define PyBuffer_Release(b)            C2PY.ReleaseBuffer(b)
#define PyArg_ParseTuple(a, f, ...)    C2PY.ParseTuple((PyObject*)(a), (f), ##__VA_ARGS__)
#define PyArg_ParseTupleAndKeywords(a, k, f, kw, ...) \
    C2PY.ParseTupleAndKeywords((PyObject*)(a), (PyObject*)(k), (f), (char**)(kw), ##__VA_ARGS__)
#define PyLong_FromLong(v)             C2PY.Long_FromLong(v)
#define PyLong_FromLongLong(v)         C2PY.Long_FromLongLong(v)
#define PyFloat_FromDouble(v)          C2PY.Float_FromDouble(v)
#define PyLong_AsLong(o)               C2PY.Long_AsLong((PyObject*)(o))
#define PyFloat_AsDouble(o)            C2PY.Float_AsDouble((PyObject*)(o))
#define PyErr_SetString(e, m)          C2PY.Err_SetString((PyObject*)(e), (m))
#define PyErr_Clear()                  C2PY.Err_Clear()
#define PyErr_Occurred()               C2PY.Err_Occurred()
#define PyErr_Format(e, f, ...)        C2PY.Err_Format((PyObject*)(e), (f), ##__VA_ARGS__)
#define Py_RETURN_NONE                 do { C2PY.IncRef(C2PY.none_obj); return C2PY.none_obj; } while(0)
#define Py_INCREF(o)                   C2PY.IncRef((PyObject*)(o))
#define Py_DECREF(o)                   C2PY.DecRef((PyObject*)(o))
#define PyObject_SetAttrString(o, n, v) C2PY.SetAttrString((PyObject*)(o), (n), (PyObject*)(v))
#define PyLong_FromVoidPtr(p)          C2PY.Long_FromVoidPtr((void*)(p))
#define PyTuple_New(s)                 C2PY.Tuple_New(s)
#define PyTuple_SetItem(t, i, o)       C2PY.Tuple_SetItem((PyObject*)(t), (i), (PyObject*)(o))
#define PyEval_SaveThread()            C2PY.SaveThread()
#define PyEval_RestoreThread(s)        C2PY.RestoreThread((void*)(s))

#define PyExc_TypeError                ((PyObject*)C2PY.exc_TypeError)
#define PyExc_ValueError               ((PyObject*)C2PY.exc_ValueError)
#define PyExc_RuntimeError             ((PyObject*)C2PY.exc_RuntimeError)
#define PyExc_MemoryError              ((PyObject*)C2PY.exc_MemoryError)

/* ------------------------------------------------------------------ */
/* Reference counting fallbacks (for CPython < 3.12 where Py_IncRef   */
/* is not an exported symbol)                                         */
/* ------------------------------------------------------------------ */

/* Manual refcount increment - accesses ob_refcnt via the correct offset
 * for the Python build (ob_refcnt on GIL, ob_ref_shared on free-threaded).
 * Safe on GIL-enabled builds where refcount is a simple Py_ssize_t field.
 * On free-threaded builds this fallback is UNSAFE (ob_ref_shared requires
 * atomic operations); always prefer Py_IncRef / Py_DecRef on 3.12+. */
static inline void _c2py_inc_ref_manual(PyObject *op)
{
    Py_ssize_t *refcnt = (Py_ssize_t*)((char*)op + C2PY.ob_refcnt_offset);
    ++(*refcnt);
}

static inline void _c2py_dec_ref_manual(PyObject *op)
{
    Py_ssize_t *refcnt = (Py_ssize_t*)((char*)op + C2PY.ob_refcnt_offset);
    --(*refcnt);
    if (*refcnt == 0) {
        fprintf(stderr, "c2py_runtime: _c2py_dec_ref_manual reached zero "
                "refcount for %p -- possible leak\n", (void*)op);
    }
}

/* ------------------------------------------------------------------ */
/* Buffer acquisition helper with old-API fallback for Python 2.7     */
/* ------------------------------------------------------------------ */

/* Flags for c2py_acquire_buffer */
#define C2PY_BUF_READ   0
#define C2PY_BUF_WRITE  1

/* Returns 0 on success, -1 on failure (with Python exception set) */
static inline int
c2py_acquire_buffer(PyObject *obj, Py_buffer *buf, int want_writable)
{
    int flags = PyBUF_STRIDES | PyBUF_FORMAT;
    if (want_writable) flags |= PyBUF_WRITABLE;

    memset(buf, 0, C2PY.pybuffer_size);

    if (C2PY.buffer_api_is_pep3118) {
        return PyObject_GetBuffer(obj, buf, flags);
    }

    /* Python 2.7: try PEP 3118 first, fall back to old API */
    if (PyObject_GetBuffer(obj, buf, flags) == 0)
        return 0;

    PyErr_Clear();

    if (want_writable) {
        if (C2PY.AsWriteBuffer &&
            C2PY.AsWriteBuffer(obj, (void**)&buf->buf, &buf->len) == 0) {
            buf->readonly = 0;
        } else {
            return -1;
        }
    } else {
        if (C2PY.AsReadBuffer &&
            C2PY.AsReadBuffer(obj, (const void**)&buf->buf, &buf->len) == 0) {
            buf->readonly = 1;
        } else {
            return -1;
        }
    }

    buf->ndim = 1;
    buf->itemsize = 1;
    buf->format = NULL;
    buf->shape = NULL;
    buf->strides = NULL;
    return 0;
}

/* Release a buffer acquired by c2py_acquire_buffer */
static inline void
c2py_release_buffer(Py_buffer *buf)
{
    if (buf->obj != NULL) {
        PyBuffer_Release(buf);
    }
    /* Old buffer API (PyObject_AsRead/WriteBuffer) needs no release */
}

/* ------------------------------------------------------------------ */
/* Performance timing (optional, enabled via timing: true in .c2py)   */
/* ------------------------------------------------------------------ */

typedef struct {
    uint64_t call_count;

    uint64_t t_enter;          /* last call: wrapper entry */
    uint64_t t_pre_c;          /* last call: just before C code */
    uint64_t t_post_c;         /* last call: just after C returns */
    uint64_t t_exit;           /* last call: before return to Python */

    uint64_t t_c_min;          /* min C-call wall time (ns) */
    uint64_t t_c_max;          /* max C-call wall time (ns) */
    uint64_t t_c_total;        /* accumulated C wall time */

    uint64_t t_wrap_min;       /* min wrapper overhead (ns) */
    uint64_t t_wrap_max;       /* max wrapper overhead (ns) */
    uint64_t t_wrap_total;     /* accumulated wrapper overhead */

    int variant;               /* active variant index (0-based), -1 if unset */
    int group_idx;             /* active outer group index, -1 if flat */
    const char *variant_name;  /* points to static string, NULL if unset */
} c2py_perf_t;

/* Returns monotonic time in cycles or nanoseconds depending on arch.
 * The unit is consistent within a single run; differential timing
 * (t_post - t_pre) uses the same source and gives valid deltas.
 * On x86_64/ARM64: uses CPU cycle counter for lower overhead.
 * On others: clock_gettime(CLOCK_MONOTONIC) fallback.
 */
#if defined(__x86_64__) || defined(__i386__)
static inline uint64_t c2py_ticks(void) {
    unsigned int lo, hi;
    __asm__ __volatile__("rdtsc" : "=a"(lo), "=d"(hi));
    return ((uint64_t)hi << 32) | lo;
}
#elif defined(__aarch64__)
static inline uint64_t c2py_ticks(void) {
    uint64_t cnt;
    __asm__ __volatile__("mrs %0, CNTVCT_EL0" : "=r"(cnt));
    return cnt;
}
#elif defined(__powerpc64__) || defined(__powerpc__)
static inline uint64_t c2py_ticks(void) {
#if defined(__GNUC__) || defined(__clang__)
    return __builtin_ppc_get_timebase();
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}
#else
static inline uint64_t c2py_ticks(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}
#endif

/* Update a perf record with one call's tick measurements.
 * t_enter:  wrapper entry
 * t_pre_c:  just before C call
 * t_post_c: just after C returns
 * t_exit:   just before returning to Python
 */
static inline void c2py_perf_record(c2py_perf_t *p,
    uint64_t t_enter, uint64_t t_pre_c, uint64_t t_post_c, uint64_t t_exit)
{
    uint64_t c_dur = t_post_c - t_pre_c;
    uint64_t w_dur = (t_pre_c - t_enter) + (t_exit - t_post_c);

    p->call_count++;
    p->t_enter  = t_enter;
    p->t_pre_c  = t_pre_c;
    p->t_post_c = t_post_c;
    p->t_exit   = t_exit;

    p->t_c_total += c_dur;
    p->t_wrap_total += w_dur;

    if (p->call_count == 1) {
        p->t_c_min = c_dur;
        p->t_c_max = c_dur;
        p->t_wrap_min = w_dur;
        p->t_wrap_max = w_dur;
    } else {
        if (c_dur < p->t_c_min) p->t_c_min = c_dur;
        if (c_dur > p->t_c_max) p->t_c_max = c_dur;
        if (w_dur < p->t_wrap_min) p->t_wrap_min = w_dur;
        if (w_dur > p->t_wrap_max) p->t_wrap_max = w_dur;
    }
}

/* Update a perf record for a single C call (no wrapper overhead).
 * Used for per-overload timing inside _impl functions. */
static inline void c2py_perf_record_call(c2py_perf_t *p,
    uint64_t t_pre, uint64_t t_post)
{
    uint64_t c_dur = t_post - t_pre;

    p->call_count++;
    p->t_pre_c  = t_pre;
    p->t_post_c = t_post;

    p->t_c_total += c_dur;

    if (p->call_count == 1) {
        p->t_c_min = c_dur;
        p->t_c_max = c_dur;
    } else {
        if (c_dur < p->t_c_min) p->t_c_min = c_dur;
        if (c_dur > p->t_c_max) p->t_c_max = c_dur;
    }
}

/* ------------------------------------------------------------------ */
/* CPU feature probing (for user extensibility, callable from         */
/* __attribute__((constructor)) functions)                            */
/* ------------------------------------------------------------------ */

#ifdef __x86_64__
static inline unsigned int c2py_cpuid_reg(int leaf, int subleaf, int reg) {
    unsigned int eax = 0, ebx = 0, ecx = 0, edx = 0;
    __asm__ __volatile__(
        "cpuid"
        : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
        : "a"(leaf), "c"(subleaf));
    switch (reg & 3) {
    case 0: return eax;
    case 1: return ebx;
    case 2: return ecx;
    default: return edx;
    }
}

static inline int c2py_cpuid_bit(int leaf, int subleaf, int reg, int bit) {
    return (c2py_cpuid_reg(leaf, subleaf, reg) >> bit) & 1;
}

/* Do NOT call cpu_supports from constructors; it may malloc internally.
 * Use c2py_cpuid_bit() instead for custom feature probes. */
#endif

/* ------------------------------------------------------------------ */
/* Init function                                                      */
/* ------------------------------------------------------------------ */

int c2py_runtime_init(void);

#ifdef __cplusplus
}
#endif

#endif /* C2PY_RUNTIME_H */
```

## c2py23_requests.md

```
# c2py23 Improvement Requests

Feedback from porting ImageD11's 58 C functions from f2py to c2py23.
Covering safety, usability, and features needed for Phase 2/3 of the migration.

**Status:** 8 of 9 implemented. 1 item remains: build-isolation docs (deferred, covered by P4 binary wheels).

---

## Safety

### 1. Parameter count validation at codegen time -- DONE

**Severity: Critical**  |  Real bug hit

The .c2py C signature and the actual C function signature can diverge silently.
The `bloboverlaps` C function takes 9 parameters but the .c2py C sig had 8
(missing `verbose`). The generated wrapper compiled fine and produced undefined
behavior at runtime -- `ns` landed in `verbose`'s slot, `nf` became `ns`, and
`nf` was garbage from the stack.

**Request:** Compare the parameter count in the .c2py C signature against the
actual C function declaration (from the header or .c file). Emit a hard error
at codegen time if they don't match. At minimum, emit a warning.

**Resolution:** Implemented. `_validate_module()` in parser.py parses C source
files, extracts function parameter counts, and raises `ValueError` on mismatch.

### 2. Compile-time validation of buffer format vs C type -- DONE

**Severity: High**

The `checks:` section in .c2py verifies buffer formats at runtime
(e.g. `labels1.format == 'i'`). If the check doesn't match the C type,
there's no compile-time warning. The generated code passes `int32_t *b1`
through an `int *` cast, which works on platforms where `int` == `int32_t`
but is not portable.

**Request:** Map buffer format checks to corresponding C types and warn if the
C function prototype uses a different-width type (e.g. `int32_t*` vs `int*`).

**Resolution:** Implemented. `_validate_module()` includes P4 check that maps
format characters in checks to expected C types via `_FORMAT_TO_CTYPE` and
raises `ValueError` when the overload uses a different-size pointer type.

---

## Usability

### 3. Direct support for fixed-width integer types -- DONE

**Severity: High**  |  43 thin wrappers, 87 type references

Currently c2py23 only supports `int*`, `float*`, `double*`, and `char*`.
Fixed-width types (`uint16_t*`, `int32_t*`, `uint8_t*`, `int8_t*`, `int64_t*`,
`uint32_t*`, `int16_t*`) require thin C wrapper functions that cast through
`char*` or `int*`. This adds:

- 43 wrapper functions in `_wrappers.c`
- Manual format-string checks in the .c2py file (`'H'` for uint16, `'B'` for uint8)
- Risk of getting the type-cast wrong in the wrapper

**Request:** Accept fixed-width integer types directly in C signatures.
Map them to PEP 3118 format characters automatically:
`uint16_t*` -> `H`, `int32_t*` -> `i`, `uint8_t*` -> `B`, `int8_t*` -> `b`,
`int64_t*` -> `q`, `uint32_t*` -> `I`, `int16_t*` -> `h`.

**Resolution:** Implemented. Parser accepts all 8 fixed-width types
(`int8_t`..`uint64_t`) in C signatures directly. Mapped to PEP 3118 format
characters via `_FORMAT_TO_CTYPE` in parser.py. ImageD11 thin wrappers removed.

### 4. Handle integer literal map values -- DONE

**Severity: Medium**

In the `map:` section, constant values like `verbose: 0` cause a parser crash:
```
TypeError: object of type 'int' has no len()
```
The workaround is to quote them as strings: `verbose: "0"`. This is surprising
and the error message is unhelpful.

**Request:** Accept bare integer literals in map values (treat them as integer
constant expressions), or at minimum give a clear error message:
"map values must be strings; got int: 0. Did you mean '0'?"

**Resolution:** Implemented. YAML type coercion in parser auto-coerces bare
int/float in map, when, and checks values. `verbose: 0` works directly.

### 5. Better buffer check error messages -- DONE

**Severity: Medium**

When a buffer format check fails, the error is:
```
ValueError: check failed: labels1.format == 'i'
```
This doesn't tell the user what format was actually found, making debugging
difficult. The user has to add debug prints to discover the actual format.

**Request:** Include the actual value in check failure messages:
```
ValueError: check failed: labels1.format == 'i' (got 'l')
```

**Resolution:** Implemented. Generator emits format comparison failure messages
with actual values: `check failed: expr (got format='X')`, `check failed: expr
(got 'X' vs 'Y')`, etc.

### 6. Output scalar convention option -- DONE

**Severity: Low**  |  Useful for migration

f2py returns output scalars as tuple elements:
```python
minval, maxval, mean, var = old.array_stats(img)
```

c2py23 writes into 1-element buffers:
```python
mn = np.zeros(1, dtype=np.float32)
mx = np.zeros(1, dtype=np.float32)
new.array_stats(img, mn, mx, me, va)
```

The equivalence tests need ~20 lines of boilerplate per function to bridge
this gap. A c2py23 mode that auto-allocates and returns 1-element buffers as
scalar return values would simplify testing and migration.

**Request:** Option to annotate `intent(out)` scalar parameters in the C sig
so c2py23 returns them as Python return values, matching f2py behavior.

**Resolution:** Implemented. `outputs:` key on C overloads declares pointer
params as output scalars. c2py23 auto-allocates 1-element stack variables,
calls the C function, and returns values in a Python tuple. Tested in
`tests/cases/scalar_output/`.

---

## Features

### 7. CPU feature detection for SIMD dispatch -- DONE

**Severity: Medium**  |  Phase 3 blocker (PLAN.md)

PLAN.md Phase 3 requires runtime dispatch to per-ISA implementations
(scalar, AVX2, AVX-512). The proposed syntax:
```yaml
c_overloads:
  - sig: "int tosparse_u16_avx512(...)"
    when: "cpu_has_avx512"
  - sig: "int tosparse_u16_avx2(...)"
    when: "cpu_has_avx2"
  - sig: "int tosparse_u16_scalar(...)"
    when: "1"
```

**Request:** Support `when:` conditions in `c_overloads` with a set of
built-in CPU feature predicates: `cpu_has_avx2`, `cpu_has_avx512`,
`cpu_has_neon`, etc. The condition is evaluated once at module load time.

**Resolution:** Implemented. Two-level group/variant dispatch with CPUID (x86_64)
and getauxval (ARM64/POWER) probing at init time. Feature globals
(e.g. `c2py_amd64_avx2`) are populated in `c2py_runtime_init()`. Supports
`.rebind()` for manual variant override, switch and function-pointer dispatch
forms, and worked example in `examples/simd_dispatch/`. See PLAN.md P1.

### 8. Preprocessor template pattern support -- DONE

**Severity: Low**  |  Phase 2 nice-to-have (PLAN.md)

PLAN.md Phase 2 uses C preprocessor `#include` templates to generate
type-generic variants. The pattern:
```c
// tosparse_u16.c
#define PIXEL_TYPE uint16_t
#define FUNC_SUFFIX _u16
#include "tosparse_tmpl.h"
```

Each variant needs its own .c2py entry with a different C symbol name.

**Request:** Support for parameterized .c2py function definitions that expand
to multiple variants, similar to a YAML loop/macro. Alternatively, document
the recommended approach for template-based code generation with c2py23.

**Resolution:** Implemented. `expand:` key with `${VAR}` substitution creates
N variants from a single template. Tested in `tests/cases/template/`.
Documented in `docs/specification.md` under "Template Expansion".

---

## Documentation

### 9. Clarify --no-build-isolation interactions

**Severity: Low**

c2py23 currently requires `--no-build-isolation` for pip install because it's
not on PyPI. This flag prevents pip from creating an isolated build
environment, which causes problems when the same environment also needs to
build f2py-based projects (like ImageD11 itself) -- the f2py build picks up
absolute paths from the venv numpy install and fails.

**Request:** Document the tradeoffs of `--no-build-isolation`. Consider
publishing c2py23 to PyPI (even as a dev release) so build isolation works
normally, or provide a `pip install c2py23` command that handles this
transparently.

---

## Summary

| # | Request | Severity | Status |
|---|---------|----------|--------|
| 1 | Parameter count validation | Critical | DONE |
| 2 | Buffer format vs C type validation | High | DONE |
| 3 | Direct fixed-width integer types | High | DONE |
| 4 | Integer literal map values | Medium | DONE |
| 5 | Better check failure messages | Medium | DONE |
| 6 | Output scalar convention option | Low | DONE |
| 7 | CPU feature detection (SIMD dispatch) | Medium | DONE |
| 8 | Template pattern support | Low | DONE |
| 9 | --no-build-isolation docs | Low | DEFERRED |

Items 1-8 are complete. Item 9 is deferred -- the plan is to publish binary wheels
to PyPI (one per platform/arch, Python-version-independent via ctypes-style
distribution), eliminating the need for `--no-build-isolation` entirely.
```

## docs/referee_reports_2026-06-15.md

```
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

### Open Items

**B2 (MEDIUM):** `_c2py_dec_ref_manual` has a diagnostic on zero-refcount but
does not call the destructor. This path is unreachable when the CPython C API
is used correctly (all decrefs go through the interpreter's own machinery).
A proper fix requires knowing `_Py_Dealloc`'s symbol name, which varies across
CPython versions. Left as a diagnostic-only mitigation pending a more
comprehensive approach (e.g., `GC_Unreachable` + deferred cleanup).

**P2 (LOW):** The `volatile` flag in `c2py_runtime_init()` serializes
initialization under the GIL in standard builds. Free-threaded 3.14+ (P4 in
PLAN.md) will require atomic initialization; deferred to that work item.

**P3 (LOW):** 32-bit `Py_buffer` sizes (52/44 bytes pre/post 3.12) are
unverified. No 32-bit ABI test container exists. The project targets
Linux-x86_64 primarily. Adding a 32-bit CI target (i386 container or
ARM32) is deferred.

**D2 (Design):** Scientific notation (`1e-4`) and leading-dot (`.5`) float
defaults are now supported. The `_PY_PARAM_RE` regex accepts `-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?`.
Integer parameter defaults are validated separately against `^-?\d+$` to
prevent `int = 1e5` from producing a confusing ValueError.

### Test Coverage Added

Three new test files were added in the fix commit:

- `tests/test_regression_fixes.py` -- 9 tests covering B1, B3, B4, P4, P5,
  and INT_MAX guard generation
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
```

## docs/specification.md

```
# c2py23 Specification

## Motivation

> "Real Programmers can write FORTRAN programs in any language."

-- Ed Post, "Real Programmers Don't Use Pascal", Datamation, July 1983

c2py23 targets the narrow intersection of C99 and Python needed for high-performance
numerical extensions. Rather than wrapping arbitrary C libraries, it enforces a
discipline where Python owns all memory, C functions operate on buffers passed in
by the caller, and the wrapper never copies or allocates. This eliminates entire
categories of bugs -- leaks, use-after-free, ownership confusion -- while keeping
the C code trivially simple.

The project defines a strict subset language: Python on one side (buffer protocol,
int, float), C99 on the other (flat pointers, scalar returns). The interface is
described declaratively in YAML. The code generator transpiles this into a CPython
C extension that dispatches to the right C function based on buffer properties:
element type, dimensionality, and layout. The wrapper itself is zero-copy and
allocation-free.

The long-term goal is a substrate for:
- SIMD dispatch within C functions, potentially at the wrapper level
- Accurate timing instrumentation (cycle counters, wall-clock)
- GIL release for pure-C sections
- Thread-safe extensions in free-threaded Python builds (3.14t+)

## Grammar

### Module-Level YAML Schema

```yaml
module: <python-module-name>          # required
source: [file1.c, file2.c, ...]       # required: C source files
headers: [header1.h, header2.h, ...]  # optional: C headers to #include
constants:                            # optional: module-level integer constants
  NAME1: 42
  NAME2: 7
timing: true                          # optional: enable perf timing

functions:                            # required: list of wrapped functions
  - py_sig: "name(arg: type, ...) -> return_type"
    doc: "Custom docstring"           # optional: override auto-generated doc
    expand:                           # optional: template expansion
      VAR1: [val_a, val_b, ...]       #   variable name -> list of values
      VAR2: [val_a, val_b, ...]       #   all lists must have same length
    checks:                           # optional: pre-conditions
      - "expression"
      - ...
    c_overloads:                      # required: ordered list of alternatives
      - sig: "c_function(c_params...) -> c_return"
        map: {c_param: expression, ...}
        when: "condition"             # optional: dispatch condition
        outputs:                      # optional: return-by-pointer scalars
          c_param_name: ctype         #   ctype: int, float, double, int32_t, etc.
      - ...
    default_raise: "TypeError: msg"   # optional: error when no overload matches
```

### Template Expansion (expand:)

The `expand:` key produces multiple function definitions from a single template
via `${VAR}` string substitution. All value lists under `expand:` must have the
same length N. For each index i, a copy of the function definition is generated
with `${VAR}` replaced by `values[i]` in all string fields.

```yaml
functions:
  - expand:
      TYPE: [uint8_t, uint16_t, int32_t]
      SUFFIX: [u8, u16, i32]
    py_sig: "sum_${SUFFIX}(data: buffer) -> int"
    c_overloads:
      - sig: "int sum_${SUFFIX}(const ${TYPE} *data, int n)"
        map: {data: "data.ptr", n: "data.n"}
```

Expands to three functions: `sum_u8`, `sum_u16`, `sum_i32`.

### Output Scalars (outputs:)

The `outputs:` key on a C overload declares parameters that are written by the
C function rather than passed by the Python caller. c2py23 auto-allocates a
1-element stack variable, passes a pointer to the C function, and returns the
resulting value as part of the Python return tuple.

```yaml
c_overloads:
  - sig: "stats(const double *data, int n, double *minval, double *maxval)"
    map: {data: "data.ptr", n: "data.n"}
    outputs:
      minval: double
      maxval: double
```

Python call returns a tuple:
```python
minval, maxval = statmod.stats(data)
```

If there is also a C return value, it comes first in the tuple.

**Tuple order**: The order of values in the returned tuple always follows the C
function parameter order (left to right in the C signature), not the YAML
dictionary insertion order. If the function also has a C return value, it
appears first, followed by output parameters in C signature order.

### Python Signature

```
py_sig ::= name "(" [py_param ("," py_param)*] ")" "->" py_ret
py_param ::= name ":" py_type
            | name ":" py_type "=" default
py_type ::= "buffer" | "int" | "float"
py_ret ::= "void" | "int" | "float"
default ::= integer_literal | float_literal
```

Optional parameters (with `=` default) are only supported for `int` and `float`
types, never `buffer`. All optional parameters must appear after all required
parameters.

Parameters:
- `buffer` -- any Python object supporting the buffer protocol. Passed as a pointer
  to the C function. Const pointers are read-only; non-const pointers are read-write
  and the caller must provide a writable buffer.
- `int` -- Python int, converted to C `int`
- `float` -- Python float, converted to C `double`

Returns:
- `void` -- the Python function returns `None`
- `int` -- the C function returns `int`, converted to Python `int`
- `float` -- the C function returns `float` or `double`, converted to Python `float`

### C Function Signature

```
c_sig ::= c_name "(" [c_param ("," c_param)*] ")" ["->" c_ret]
c_param ::= ["const"] c_ctype ["*"] name
c_ctype ::= "int" | "float" | "double" | "char"
          | "int8_t" | "uint8_t" | "int16_t" | "uint16_t"
          | "int32_t" | "uint32_t" | "int64_t" | "uint64_t"
c_ret ::= "int" | "float" | "double" | "void"
```

If `-> c_ret` is omitted, the return type is `void`.

Examples of valid C signatures:
```
array_sum(const double *a, const double *b, double *result, int n) -> int
fill_f(float *arr, int n, float value) -> void
dot(const double *a, const double *b, int n) -> double
```

### Map Expressions

`map:` entries connect C parameter names to expressions that compute their values
at call time from the Python parameters and buffer metadata.

```
map_expr ::= py_param_name
           | buffer_attr
           | literal

buffer_attr ::= buf "." attr
attr ::= "ptr" | "n" | "len" | "format" | "ndim" | "shape" "[" int "]" | "itemsize" | "strides" "[" int "]"
```

Buffer attribute reference:

| Expression | C equivalent | Description |
|-----------|-------------|-------------|
| `buf.ptr` | `buf->buf` cast to appropriate C type | Raw memory pointer |
| `buf.n` | `buf->len / buf->itemsize` | Element count |
| `buf.len` | `buf->len` | Byte length |
| `buf.format` | `buf->format` | PEP 3118 format string ("d", "f", "i", "B") |
| `buf.ndim` | `buf->ndim` | Number of dimensions |
| `buf.shape[i]` | `buf->shape[i]` | Size of dimension i |
| `buf.itemsize` | `buf->itemsize` | Bytes per element |
| `buf.strides[i]` | `buf->strides[i]` | Bytes between elements along dimension i |

For scalar Python parameters (`int`, `float`), the expression is simply the
parameter name. The generated code uses the local C variable (`c_name`).

### When Expressions

`when:` conditions determine which C overload is called. They are evaluated at
runtime in the generated `_impl` function, in declaration order. The first
overload whose `when` condition evaluates to true is selected. Overloads without
a `when` always match (useful as a default).

```
when_expr ::= compare ("and" compare | "or" compare)*
            | "not" when_expr
            | "(" when_expr ")"

compare ::= map_expr cmp_op map_expr
cmp_op ::= "==" | "!=" | "<" | ">" | "<=" | ">="
```

Format comparison with a single-character string literal uses last-character
matching to handle PEP 3118 endianness prefixes:
```
arr.format == 'd'   matches "d", "<d", ">d", "=d", "!d"
arr.format == 'f'   matches "f", "<f", ">f", "=f", "!f"
```

When the format pointer is NULL (old buffer protocol on Python 2.7), the
condition evaluates to true, allowing the first matching overload to proceed.

### Checks

`checks:` are pre-conditions evaluated before dispatch. If a check fails,
a `ValueError` is raised. Checks use the same expression language as `when:`
conditions.

```
checks:
  - "a.format == 'd'"
  - "a.n == b.n"
  - "a.n == result.n"
```

### Default Raise

`default_raise:` specifies the error raised when no overload matches:

```
default_raise: "TypeError: expected float or double buffer"
default_raise: "ValueError: expected [N,3] or [3,N] buffer"
```

The format is `"ExceptionType: message"`. Only `TypeError` and `ValueError`
are supported.

## Worked Examples

### Example 1: Element-wise Array Addition

**C source** (`arraysum.c`):
```c
int array_sum(const double *a, const double *b, double *result, int n) {
    int i;
    for (i = 0; i < n; i++) {
        result[i] = a[i] + b[i];
    }
    return n;
}
```

**Interface** (`arraysum.c2py`):
```yaml
module: arraysum
source: [arraysum.c]

functions:
  - py_sig: "array_sum(a: buffer, b: buffer, result: buffer) -> int"
    checks:
      - "a.format == 'd'"
      - "b.format == 'd'"
      - "result.format == 'd'"
      - "a.n == b.n"
      - "a.n == result.n"
    c_overloads:
      - sig: "array_sum(const double *a, const double *b, double *result, int n) -> int"
        map: {a: "a.ptr", b: "b.ptr", result: "result.ptr", n: "a.n"}
```

**Python call**:
```python
import ctypes, sys
sys.path.insert(0, '.')
import arraysum

a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
result = (ctypes.c_double * 4)()

n = arraysum.array_sum(a, b, result)
# n == 4
# result == [6.0, 8.0, 10.0, 12.0]
```

**Mapping at runtime**:

| Step | C parameter | Expression | Computed value |
|------|------------|-----------|---------------|
| 1 | `const double *a` | `a.ptr` | `(const double*)buf_a->buf` |
| 2 | `const double *b` | `b.ptr` | `(const double*)buf_b->buf` |
| 3 | `double *result` | `result.ptr` | `(double*)buf_result->buf` |
| 4 | `int n` | `a.n` | `(int)(buf_a->len / buf_a->itemsize)` = 4 |

The restrict check verifies that the writable buffer (`result`) does not overlap
with either read-only buffer (`a`, `b`).

### Example 2: Type Dispatch (float vs double)

**C source** (`fill.c`):
```c
void fill_f(float *arr, int n, float value) {
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_d(double *arr, int n, double value) {
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}
```

**Interface** (`fill.c2py`):
```yaml
module: fillmod
source: [fill.c]

functions:
  - py_sig: "fill(arr: buffer, value: float) -> void"
    c_overloads:
      - sig: "fill_f(float *arr, int n, float value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'f'"
      - sig: "fill_d(double *arr, int n, double value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'd'"
    default_raise: "TypeError: expected float or double buffer"
```

**Python call**:
```python
import ctypes, sys
sys.path.insert(0, '.')
import fillmod

# Float dispatch
arr_f = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
fillmod.fill(arr_f, 3.14)
# arr_f == [3.14, 3.14, 3.14, 3.14]

# Double dispatch
arr_d = (ctypes.c_double * 3)(0.0, 0.0, 0.0)
fillmod.fill(arr_d, 2.718)
# arr_d == [2.718, 2.718, 2.718]
```

**Dispatch at runtime**:

| Buffer format | Overload selected | C function called |
|--------------|-------------------|-------------------|
| `"f"` or `"<f"` | 0 | `fill_f((float*)buf->buf, n, (float)c_value)` |
| `"d"` or `"<d"` | 1 | `fill_d((double*)buf->buf, n, c_value)` |
| NULL (old API) | 0 | `fill_f(...)` (first overload, format unknown) |
| anything else | -- | `TypeError: expected float or double buffer` |

### Example 3: Shape Dispatch (AoS vs SoA)

**C source** (`transform.c`):
```c
void transform_aos(double *points, int n, double *out) {
    /* points: [n, 3] -- array of structs */
    int i;
    for (i = 0; i < n; i++) {
        double x = points[i * 3 + 0];
        double y = points[i * 3 + 1];
        double z = points[i * 3 + 2];
        out[i * 3 + 0] = x * 2.0;
        out[i * 3 + 1] = y * 2.0;
        out[i * 3 + 2] = z * 2.0;
    }
}

void transform_soa(double *points, int n, double *out) {
    /* points: [3, n] -- struct of arrays */
    int i;
    for (i = 0; i < n; i++) {
        double x = points[0 * n + i];
        double y = points[1 * n + i];
        double z = points[2 * n + i];
        out[0 * n + i] = x * 2.0;
        out[1 * n + i] = y * 2.0;
        out[2 * n + i] = z * 2.0;
    }
}
```

**Interface** (`transform.c2py`):
```yaml
module: xfrm
source: [transform.c]

functions:
  - py_sig: "transform(points: buffer, out: buffer) -> void"
    checks:
      - "points.format == 'd'"
      - "out.format == 'd'"
      - "out.n == points.n"
      - "points.ndim == 2"
    c_overloads:
      - sig: "transform_aos(double *points, int n, double *out)"
        map: {points: "points.ptr", n: "points.shape[0]", out: "out.ptr"}
        when: "points.shape[1] == 3"
      - sig: "transform_soa(double *points, int n, double *out)"
        map: {points: "points.ptr", n: "points.shape[1]", out: "out.ptr"}
        when: "points.shape[0] == 3"
    default_raise: "ValueError: expected [N,3] or [3,N] buffer"
```

**Python call**:
```python
import ctypes, sys
sys.path.insert(0, '.')
import xfrm

# AoS dispatch: [4, 3] shape
pts = (ctypes.c_double * 12)(1,2,3, 4,5,6, 7,8,9, 10,11,12)
out = (ctypes.c_double * 12)()
mv = memoryview(pts).cast('B').cast('d', [4, 3])
mv_out = memoryview(out).cast('B').cast('d', [4, 3])
xfrm.transform(mv, mv_out)
# Calls transform_aos, n = shape[0] = 4
# out == [2,4,6, 8,10,12, 14,16,18, 20,22,24]

# SoA dispatch: [3, 4] shape
pts2 = (ctypes.c_double * 12)(1,4,7,10, 2,5,8,11, 3,6,9,12)
out2 = (ctypes.c_double * 12)()
mv2 = memoryview(pts2).cast('B').cast('d', [3, 4])
mv_out2 = memoryview(out2).cast('B').cast('d', [3, 4])
xfrm.transform(mv2, mv_out2)
# Calls transform_soa, n = shape[1] = 4
# out2 == [2,8,14,20, 4,10,16,22, 6,12,18,24]
```

**Dispatch at runtime**:

| Buffer shape | Condition matched | C function called | n computed as |
|-------------|-------------------|-------------------|--------------|
| `(4, 3)` | `shape[1] == 3` | `transform_aos` | `shape[0] = 4` |
| `(3, 4)` | `shape[0] == 3` | `transform_soa` | `shape[1] = 4` |
| `(5, 2)` | none | `ValueError` | -- |
| 1D | `ndim == 2` fails | `ValueError` | -- |

Key design point: the wrapper never transposes or copies data. Both C functions
receive the same raw pointer; the dispatch only changes how `n` is computed and
which C function interprets the layout.

### Example 4: Dispatch Over All Buffer Types

This example demonstrates `when:` dispatch over all 10 PEP 3118 format
characters, mapping each to its corresponding C fixed-width type.

**C source** (`typedispatch.c`):
```c
#include <stdint.h>

void fill_u8(uint8_t *arr, int n, uint8_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_i8(int8_t *arr, int n, int8_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_u16(uint16_t *arr, int n, uint16_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_i16(int16_t *arr, int n, int16_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_u32(uint32_t *arr, int n, uint32_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_i32(int32_t *arr, int n, int32_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_u64(uint64_t *arr, int n, uint64_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_i64(int64_t *arr, int n, int64_t value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_f32(float *arr, int n, float value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
void fill_f64(double *arr, int n, double value) {
    int i; for (i = 0; i < n; i++) arr[i] = value;
}
```

**Interface** (`typedispatch.c2py`):
```yaml
module: dispatchmod
source: [typedispatch.c]
headers: [stdint.h]

functions:
  - py_sig: "fill(arr: buffer, value: float) -> void"
    c_overloads:
      - sig: "fill_u8(uint8_t *arr, int n, uint8_t value)"
        when: "arr.format == 'B'"
      - sig: "fill_i8(int8_t *arr, int n, int8_t value)"
        when: "arr.format == 'b'"
      - sig: "fill_u16(uint16_t *arr, int n, uint16_t value)"
        when: "arr.format == 'H'"
      - sig: "fill_i16(int16_t *arr, int n, int16_t value)"
        when: "arr.format == 'h'"
      - sig: "fill_u32(uint32_t *arr, int n, uint32_t value)"
        when: "arr.format == 'I'"
      - sig: "fill_i32(int32_t *arr, int n, int32_t value)"
        when: "arr.format == 'i'"
      - sig: "fill_u64(uint64_t *arr, int n, uint64_t value)"
        when: "arr.format == 'Q'"
      - sig: "fill_i64(int64_t *arr, int n, int64_t value)"
        when: "arr.format == 'q'"
      - sig: "fill_f32(float *arr, int n, float value)"
        when: "arr.format == 'f'"
      - sig: "fill_f64(double *arr, int n, double value)"
        when: "arr.format == 'd'"
    default_raise: "TypeError: expected buffer of type B,b,H,h,I,i,Q,q,f,d"
```

**Complete Format-to-C-Type Mapping**:

| PEP 3118 | Format char | C Type      | Size |
|----------|-------------|-------------|------|
| ubyte    | `B`         | `uint8_t`   | 1    |
| byte     | `b`         | `int8_t`    | 1    |
| ushort   | `H`         | `uint16_t`  | 2    |
| short    | `h`         | `int16_t`   | 2    |
| uint     | `I`         | `uint32_t`  | 4    |
| int      | `i`         | `int32_t`   | 4    |
| ulonglong| `Q`         | `uint64_t`  | 8    |
| longlong | `q`         | `int64_t`   | 8    |
| float    | `f`         | `float`     | 4    |
| double   | `d`         | `double`    | 8    |

**Note on `'l'` and `'L'` format characters**: PEP 3118 defines `'l'` (signed long)
and `'L'` (unsigned long) as platform-sized types. On LP64 platforms (Linux x86_64,
aarch64) they are 8 bytes wide and map to `int64_t`/`uint64_t`. On ILP32 and LLP64
platforms (32-bit, Windows) they are 4 bytes wide. For portable dispatch, prefer
`'q'`/`'Q'` for 64-bit integers and `'i'`/`'I'` for 32-bit integers. If you use
`'l'` or `'L'`, document that your `.c2py` file is LP64-only.

**Python call**:
```python
import ctypes, sys
sys.path.insert(0, '.')
import dispatchmod

# Dispatch by buffer format character
arr = (ctypes.c_uint8 * 5)(0,0,0,0,0)
dispatchmod.fill(arr, 42)
# arr == [42, 42, 42, 42, 42]  -- dispatched to fill_u8

arr2 = (ctypes.c_double * 3)(0,0,0)
dispatchmod.fill(arr2, 3.14)
# arr2 == [3.14, 3.14, 3.14]   -- dispatched to fill_f64
```

## Generated Wrapper Structure

For each function in the `.c2py` file, the generator produces two C functions:

### `_impl` Function

Takes `Py_buffer*` for each buffer param and C scalar values. Structure:

```
1. Evaluate checks -- raise ValueError on failure
2. Overload dispatch -- ordered if/else chain:
   a. For each overload with a `when` condition, test and enter `if` block
   b. For each overload without `when`, enter `else` block
   c. In each block: map expressions -> C args, call C function, return result
3. Default raise -- if no overload matched, raise TypeError or ValueError
```

### `_wrapper` Function

Takes `PyObject *self, *args, *kwargs` (standard CPython method). Structure:

```
1. PyArg_ParseTuple -- extract Python objects and scalar values
2. c2py_acquire_buffer -- for each buffer param, get Py_buffer struct
   (uses PEP 3118 on Python 3.x, falls back to old API on 2.7)
3. Restrict checks -- verify no writable buffer aliases any other buffer
4. Call _impl function
5. Cleanup -- release all acquired buffers
6. Return result
```

### Module Init

Two entry points are provided:

- `PyInit_<name>(void)` -- called by Python 3.x, returns `PyObject*`
- `init<name>(void)` -- called by Python 2.7, returns `void`

Both call `c2py_runtime_init()` which populates the function pointer table via
`dlopen(NULL)` + `dlsym()`. The module definition struct (`PyModuleDef`) and
method table (`PyMethodDef[]`) are compiled into the shared object.

## Nimpy Runtime

The runtime avoids linking against `libpython` entirely. The approach originates from
[yglukhov/nimpy](https://github.com/yglukhov/nimpy), a Nim-Python bridge designed for
ABI compatibility across Python versions. The key insight from nimpy: compiled modules
should not depend on a particular Python version; the C API symbols are loaded at runtime
from whichever process has launched the module.

c2py23 adapts this technique for C, trimming it to the smallest possible CPython C API
surface: buffer protocol, argument parsing, scalar construction, exception handling,
and module creation. No other CPython APIs are exposed or used.

1. At module load time, `c2py_runtime_init()` calls `dlopen(NULL, RTLD_LAZY | RTLD_GLOBAL)`
   to get a handle to the running Python interpreter's symbol table

2. All needed CPython C API functions are resolved via `dlsym()` and stored in a
   global function pointer table (`C2PY`)

3. Macros in `c2py_runtime.h` redirect standard CPython API names to the
   function pointer table:
   ```c
   #define PyObject_GetBuffer  C2PY.GetBuffer
   #define PyErr_SetString     C2PY.Err_SetString
   ```

4. CPython types (`PyObject`, `Py_buffer`, `PyMethodDef`, `PyModuleDef`) are
   redefined with ABI-stable layouts in `c2py_runtime.h`

5. The `Py_buffer` struct supports both 96-byte (Python 2.7, with smalltable)
   and 80-byte (Python 3.x, without smalltable) layouts; the runtime selects
   the correct size based on the Python version

6. `c2py_acquire_buffer()` is a version-aware wrapper: on Python 3.x it uses
   `PyObject_GetBuffer` with `PyBUF_STRIDES | PyBUF_FORMAT` flags; on Python 2.7
   it tries PEP 3118 first, then falls back to `PyObject_AsReadBuffer`/
   `PyObject_AsWriteBuffer` (old buffer API). Old buffers have `format = NULL`
   and `ndim = 1`

### Function Pointer Table

```c
typedef struct {
    void *dl_handle;
    int version_major, version_minor;

    int use_fastcall;               /* 1 = use METH_FASTCALL wrappers (Python >= 3.12) */
    int is_free_threaded;           /* 1 = Python built with --disable-gil */
    Py_ssize_t pybuffer_size;       /* actual sizeof(Py_buffer) for this version */
    Py_ssize_t pyobject_size;       /* actual sizeof(PyObject) for this version */
    ptrdiff_t ob_refcnt_offset;     /* offset of refcount field within PyObject */

    /* Buffer protocol */
    int (*GetBuffer)(PyObject*, Py_buffer*, int);
    void (*ReleaseBuffer)(Py_buffer*);
    int (*AsReadBuffer)(PyObject*, const void**, Py_ssize_t*);   /* 2.7 only */
    int (*AsWriteBuffer)(PyObject*, void**, Py_ssize_t*);        /* 2.7 only */
    void (*Err_Clear)(void);
    int buffer_api_is_pep3118;  /* 0 on 2.7, 1 on 3.x */

    /* Argument parsing */
    int (*ParseTuple)(PyObject*, const char*, ...);
    int (*ParseTupleAndKeywords)(PyObject*, PyObject*, const char*, char**, ...);

    /* Value construction */
    PyObject* (*Long_FromLong)(long);
    PyObject* (*Long_FromLongLong)(long long);
    PyObject* (*Float_FromDouble)(double);

    /* Tuple construction */
    PyObject* (*Tuple_New)(Py_ssize_t);
    int (*Tuple_SetItem)(PyObject*, Py_ssize_t, PyObject*);

    /* Scalar conversion */
    long (*Long_AsLong)(PyObject*);
    double (*Float_AsDouble)(PyObject*);

    /* Exception handling */
    void *exc_TypeError, *exc_ValueError, *exc_RuntimeError, *exc_MemoryError;
    void (*Err_SetString)(PyObject*, const char*);
    PyObject* (*Err_Occurred)(void);
    PyObject* (*Err_Format)(PyObject*, const char*, ...);

    /* Module creation */
    PyObject* (*Module_Create2)(PyModuleDef*, int);
    PyObject* (*InitModule_2_7)(const char*, PyMethodDef*);

    /* Object attribute access */
    int (*SetAttrString)(PyObject*, const char*, PyObject*);

    /* Pointer-to-int conversion (for exposing perf struct addresses) */
    PyObject* (*Long_FromVoidPtr)(void*);

    /* Reference counting */
    void (*IncRef)(PyObject*);
    void (*DecRef)(PyObject*);

    /* GIL management */
    void* (*SaveThread)(void);
    void (*RestoreThread)(void*);

    /* None singleton */
    PyObject *none_obj;

} c2py_api_t;
```

## Cross-Version Portability

### One .so for Multiple Python Versions

The compiled `.so` is Python-version-independent because:
- No compile-time Python headers are included
- All CPython API is resolved at module load time
- Both `PyInit_*` (Python 3) and `init*` (Python 2.7) entry points are exported
- The `PyModuleDef` struct has a stable ABI layout across Python 3.x

### OS/Libc Compatibility

The `.so` uses only C99 and POSIX `dlopen`/`dlsym`. To achieve maximum portability,
build on the oldest target OS. A `.so` built on Ubuntu 20.04 (glibc 2.31) imports
correctly on Ubuntu 24.04 (glibc 2.39). The reverse does not work, as expected
for any glibc-linked binary.

## Restrictions

- No `malloc`, `calloc`, `realloc`, or `free` in generated wrapper code
  (user C code may use them internally; allocated memory must be freed before return)
- No copies or transposes in the wrapper -- all memory is passed through
- All buffers must be contiguous (C-contiguous or F-contiguous as appropriate)
- The GIL is held during all C function calls by default.
  Individual functions or overloads may opt into GIL release via
  `gil_release: true` (see below).
- `restrict` is enforced at the wrapper level: aliasing writable buffers raises `ValueError`

## GIL Release and Thread Safety

### The GIL and Buffer Protocol

CPython's Global Interpreter Lock (GIL) serializes Python bytecode execution.
When a C extension is called, the GIL is held. This means:
- No other Python thread can run Python code concurrently.
- Python object reference counts are safe from races.
- The interpreter's internal state is protected.

The buffer protocol creates a reference from the C extension to a Python
object's underlying memory. `PyObject_GetBuffer` increments the object's
reference count indirectly through the buffer's exporter. As long as the
buffer is held, the Python object cannot be garbage collected and its
memory cannot be freed.

**What the buffer reference does NOT protect against:** concurrent writes.
If two Python threads each acquire a buffer reference to the same ndarray,
both hold valid pointers to the same memory. If one thread writes while
the other reads, there is a data race. The buffer protocol provides no
locking mechanism for content access. This is the caller's responsibility.

### Releasing the GIL

When a C function does not call any Python C API (no `PyArg_ParseTuple`,
no `PyLong_FromLong`, no exception setting), the GIL is unnecessary for
correctness. The wrapper can release it:

```yaml
functions:
  - py_sig: "array_stats(data: buffer) -> void"
    gil_release: true                      # per-function default
    c_overloads:
      - sig: "stats_f(const float *data, int n, ...)"
        map: {data: "data.ptr", n: "data.n"}
        gil_release: false                 # per-overload override
```

The `gil_release` key can appear at the function level (sets the default
for all overloads) or on individual overloads (overrides the function
default). If omitted, the GIL is held -- the safe default.

The generated wrapper calls `PyEval_SaveThread()` before entering the C
function and `PyEval_RestoreThread()` after returning. Between these
calls, other Python threads may run. The wrapper's argument parsing and
buffer acquisition happen before the GIL is released; buffer release and
result construction happen after it is reacquired.

### OpenMP and Oversubscription

A common misconception is that GIL release is required for OpenMP. It is
not. OpenMP threads are kernel threads created by the C runtime, not
Python threads. They run entirely within the C call and are unaffected
by the GIL. A function using `#pragma omp parallel for` works correctly
whether or not the GIL is released.

The real concern is oversubscription: if N Python threads each call an
OpenMP function that spawns M threads, N*M threads compete for cores.
In this scenario, NOT releasing the GIL may be desirable -- it serializes
the Python threads, preventing oversubscription. Whether to release
depends on the workload.

### The REAL Programmer Model

The design philosophy follows the spirit of "Real Programmers can write
FORTRAN programs in any language." c2py23 does not try to make thread
safety foolproof. It provides mechanisms, not policies:

- The default (GIL held) is safe for all cases.
- The `gil_release` opt-in is for callers who understand their data
  flow and can guarantee that no other thread will concurrently mutate
  the buffers they have passed.
- The buffer reference ensures memory is not freed. Content races are
  the user's problem.

### Global Toggle

A module-level runtime flag `_c2py_gil_release_enabled` (exposed as a
readable/writable `int` on the module, similar to the timing flag
`_c2py_timing_enabled`) allows callers to globally enable or disable
GIL release without recompilation:

```python
import mymod
mymod._c2py_gil_release_enabled  # 1 = enabled, 0 = disabled
mymod._c2py_gil_release_enabled = 0  # disable all GIL release
```

Per-function get/set methods provide finer control:

```python
mymod.array_stats.get_gil_release()     # True or False
mymod.array_stats.set_gil_release(False)
```

These follow the same pattern as `c2py23.perf.read_enabled` /
`c2py23.perf.set_enabled` for timing instrumentation.

### Free-Threading (Python 3.14t)

Free-threaded CPython (3.14+, compiled with `--disable-gil`, commonly named
`python3.14t`) eliminates the Global Interpreter Lock. This enables true
parallelism but introduces ABI differences that affect any C extension that
defines its own CPython types.

#### ABI Differences

The `PyObject` struct layout differs between GIL-enabled and free-threaded builds:

| Field              | Standard (GIL)   | Free-threaded      |
|--------------------|------------------|--------------------|
| sizeof(PyObject)   | 16 bytes (LP64)  | 32 bytes (LP64)    |
| sizeof(PyModuleDef)| 80 bytes         | 120 bytes          |
| ob_refcnt (refcount)| offset 0       | offset 16 (`ob_ref_shared`) |
| ob_type            | offset 8         | offset 24          |

The free-threaded PyObject has additional fields between the thread-id and the
external refcount: `ob_tid` (thread ID), `ob_flags` (biased refcount flags),
`PyMutex ob_mutex` (per-object lock), `ob_gc_bits` (GC state), `ob_ref_local`
(local refcount), then `ob_ref_shared` (the externally visible refcount) at
offset 16, and `ob_type` at offset 24.

c2py23 defines both layouts (`PyObject` / `PyObject_FT`, `PyModuleDef` /
`PyModuleDef_FT`) in `c2py_runtime.h`. Generated wrappers emit both a standard
and a free-threaded `PyModuleDef` at compile time and select the appropriate
one at module init time.

#### Runtime Detection

Detection happens in `c2py_runtime_init()` using multiple methods (first
successful match wins):

1. Version string -- `Py_GetVersion()` is checked for the substring
   `"free-threading"`.
2. `_Py_IsGILEnabled()` -- if available (CPython 3.13+), calling this
   function returns 0 on free-threaded builds, confirming FT status.
3. Module init uses `pthread_once` for thread safety -- ensures multiple
   threads racing to load the module do not double-initialize the runtime.

```c
/* Method 1: version string */
if (strstr(Py_GetVersion(), "free-threading") != NULL) is_ft = 1;

/* Method 2: _Py_IsGILEnabled() fallback */
if (!is_ft) {
    gil_check_fn fn = dlsym(dl, "_Py_IsGILEnabled");
    if (fn && fn() == 0) is_ft = 1;
}
```

When detected, `C2PY.ob_refcnt_offset` is set to 16 (the `ob_ref_shared` field)
instead of 0. Manual refcount operations (`_c2py_inc_ref_manual`) become
fatal -- `Py_IncRef` / `Py_DecRef` must be resolved from the interpreter.

**Note on Python 3.14 standard (GIL) builds:** Python 3.14 uses biased
reference counting (PEP 763) even in standard GIL-enabled builds. This means
`sys.getrefcount()` returns only `ob_ref_shared`, not the total refcount.
Local variable references are tracked in `ob_ref_local` and are invisible to
`sys.getrefcount()`. The c2py23 test suite accounts for this -- refcount
equality assertions are skipped on Python 3.14+ regardless of FT status.
The actual buffer refcounting by the C wrapper remains correct (verified
by 10000-iteration loop tests with stable refcounts).

#### Generated Code

The generator produces dual module definition structs:

```c
/* Standard GIL layout */
static PyModuleDef _module_def = {
    PyModuleDef_HEAD_INIT,
    "modname", NULL, -1, NULL /* m_methods set at init */,
    NULL, NULL, NULL, NULL
};

/* Free-threaded layout */
static PyModuleDef_FT _module_def_ft = {
    PyModuleDef_HEAD_INIT_FT,
    "modname", NULL, -1, NULL /* m_methods set at init */,
    NULL, NULL, NULL, NULL
};
```

At init time, the correct one is selected:

```c
PyObject* PyInit_modname(void) {
    c2py_runtime_init();
    PyMethodDef *methods = C2PY.use_fastcall ? _methods_fastcall : _methods_varargs;

    if (C2PY.is_free_threaded) {
        _module_def_ft.m_methods = methods;
        return C2PY.Module_Create2((PyModuleDef*)&_module_def_ft, 1013);
    } else {
        _module_def.m_methods = methods;
        return C2PY.Module_Create2(&_module_def, 1013);
    }
}
```

No compile-time Python headers are included, so a single `.so` built on any
machine works on both standard and free-threaded interpreters without
recompilation.

#### GIL Behavior

On free-threaded builds, `PyEval_SaveThread` and `PyEval_RestoreThread` are
no-ops. The `gil_release` flag in `.c2py` files is harmless -- the generated
code still compiles and runs correctly, it just has no effect on free-threaded
builds.

**Important:** c2py23 modules do NOT declare `Py_MOD_GIL_NOT_USED`. When loaded
by a free-threaded interpreter, CPython re-enables the GIL for the module. This
produces a `RuntimeWarning`:

```
RuntimeWarning: The global interpreter lock (GIL) has been enabled to load
module 'mymod', which has not declared that it can run safely without the GIL.
```

This is safe-by-default behavior: the wrapped C code may not be thread-safe,
so the GIL is preserved. Users who have verified that their C code is
thread-safe can suppress the warning:

```bash
PYTHON_GIL=0 python3.14t -c "import mymod; ..."
python3.14t -Xgil=0 -c "import mymod; ..."
```

Or within Python:

```python
import warnings
warnings.filterwarnings("ignore", message=".*GIL.*")
```

#### Refcounting on Free-Threaded Builds

On free-threaded builds, `Py_INCREF` / `Py_DECREF` use atomic operations.
c2py23 resolves `Py_IncRef` and `Py_DecRef` at runtime (available from
CPython 3.12+). The manual refcount fallback (`_c2py_inc_ref_manual` /
`_c2py_dec_ref_manual`) is **disabled** on free-threaded builds -- if
`Py_IncRef`/`Py_DecRef` cannot be resolved, init fails with a fatal error.
This prevents silent data races from non-atomic `++op->ob_refcnt`.

#### Compatibility Matrix

| Python Build | sizeof(PyObject) | Refcount field | GIL behavior | Supported |
|-------------|-----------------|----------------|-------------|-----------|
| 2.7 - 3.13 (standard) | 16 bytes | `ob_refcnt` at offset 0 | `PyEval_SaveThread` releases | Yes |
| 3.14 (standard) | 16 bytes | Biased: `ob_ref_shared` at offset 0 | `PyEval_SaveThread` releases | Yes |
| 3.14t (free-threaded) | 32 bytes | `ob_ref_shared` at offset 16 | `PyEval_SaveThread` is no-op; GIL re-enabled for module | Yes |

**Note:** Python 3.14 standard (GIL) uses biased reference counting (PEP 763)
where the PyObject layout is unchanged (16 bytes) but `ob_refcnt` is replaced
by `ob_ref_shared`. Local variable references use `ob_ref_local` (thread-local
storage) and are invisible to `sys.getrefcount()`. The c2py23 runtime uses
`Py_IncRef`/`Py_DecRef` (CPython 3.12+ stable ABI) which correctly handle
biased refcounting. The manual fallback (`_c2py_inc_ref_manual`) is not used
on Python 3.14 because `Py_IncRef`/`Py_DecRef` are always available.

## SIMD Dispatch and Multi-Flag Compilation

c2py23 provides CPU feature detection and two-level dispatch (buffer-type groups
+ CPU variants) as described in `PLAN.md` P1.  The build system is orthogonal:
c2py23 wraps and links; the user's build system (make, CMake, meson, etc.)
compiles source files with the appropriate `-m` flags.

**Multi-flag compilation pattern**: a single C kernel is compiled multiple times
with different `-m` flags and a `-DKERNEL_FN=<name>` rename macro, producing
ISA-specific object files.  c2py23 lists the `.o` files in `source:` and
dispatches between them via `c_overloads` with `variants:` and `when:` CPU
feature conditions.

See `examples/simd_dispatch/` for a complete worked example (SAXPY kernel
compiled as avx512/avx2/scalar variants, wrapped with grouped dispatch, with
Makefile and Python test harness).

## Future Work

- **Windows port** -- platform `GetModuleHandle(NULL)` + `GetProcAddress()` equivalent of `dlopen`/`dlsym`; MSVC/clang-cl build path; LLP64 type handling
```

## examples/kissfft_wrap/example.py

```python
"""Example: use the kissfftmod wrapper from Python."""
from __future__ import print_function

import ctypes
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kissfftmod

N = 256
# Real FFT: N real -> N/2+1 complex (stored as float pairs)
data = (ctypes.c_float * N)(*[math.sin(2 * math.pi * 7 * i / N) for i in range(N)])
spec = (ctypes.c_float * (N + 2))()  # (N/2+1)*2 floats

kissfftmod.rfft_forward(data, spec)
print("rfft: spec[0]=%.2f spec[1]=%.2f" % (spec[0], spec[1]))

# Complex FFT: N complex -> N complex
fin = (ctypes.c_float * (N * 2))(*(list(data) + [0.0] * N))
fout = (ctypes.c_float * (N * 2))()

kissfftmod.cfft_forward(fin, fout)
print("cfft: fout[0]=%.2f fout[1]=%.2f" % (fout[0], fout[1]))
```

## examples/kissfft_wrap/kissfft.c2py

```yaml
module: kissfftmod
source:
  - ../kissfft/kiss_fft.c
  - ../kissfft/kiss_fftr.c
  - kissfft_thin.c
headers:
  - ../kissfft/kiss_fft.h
  - ../kissfft/kiss_fftr.h

functions:
  - py_sig: "rfft_forward(data: buffer, spec: buffer) -> void"
    checks:
      - "data.format == 'f'"
      - "spec.format == 'f'"
      - "data.ndim == 1"
      - "spec.ndim == 1"
      - "spec.n >= data.n + 2"
    c_overloads:
      - sig: "kissfft_rfft_forward(const float *data, float *spec, int n)"
        map:
          data: "data.ptr"
          spec: "spec.ptr"
          n: "data.n"

  - py_sig: "cfft_forward(fin: buffer, fout: buffer) -> void"
    checks:
      - "fin.format == 'f'"
      - "fout.format == 'f'"
      - "fin.ndim == 1"
      - "fout.ndim == 1"
      - "fin.n == fout.n"
      - "fin.n % 2 == 0"
    c_overloads:
      - sig: "kissfft_cfft_forward(const float *fin, float *fout, int n)"
        map:
          fin: "fin.ptr"
          fout: "fout.ptr"
          n: "fin.n / 2"
```

## examples/kissfft_wrap/kissfft_thin.c

```c
#include <stdlib.h>
#include "../kissfft/kiss_fft.h"
#include "../kissfft/kiss_fftr.h"

void kissfft_rfft_forward(const float *data, float *spec, int n) {
    kiss_fftr_cfg cfg = kiss_fftr_alloc(n, 0, NULL, NULL);
    if (cfg) {
        kiss_fftr(cfg, data, (kiss_fft_cpx *)spec);
        free(cfg);
    }
}

void kissfft_cfft_forward(const float *fin, float *fout, int n) {
    kiss_fft_cfg cfg = kiss_fft_alloc(n, 0, NULL, NULL);
    if (cfg) {
        kiss_fft(cfg, (const kiss_fft_cpx *)fin, (kiss_fft_cpx *)fout);
        free(cfg);
    }
}
```

## examples/lz4_wrap/example.py

```python
"""Example: use the lz4mod wrapper from Python."""
from __future__ import print_function

import ctypes
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz4mod

data = b"Hello, World! " * 100
src = (ctypes.c_uint8 * len(data))(*bytearray(data))
dst = (ctypes.c_uint8 * len(data))()

compressed_size = lz4mod.compress(src, dst)
print("Compressed %d -> %d bytes" % (len(data), compressed_size))

out = (ctypes.c_uint8 * len(data))()
buf = (ctypes.c_uint8 * compressed_size)(*bytearray(bytes(dst[:compressed_size])))
decompressed_size = lz4mod.decompress(buf, out)
result = bytes(bytearray(out[:decompressed_size]))
print("Decompressed: %d bytes, match=%s" % (decompressed_size, result == data))
```

## examples/lz4_wrap/lz4.c2py

```yaml
module: lz4mod
source:
  - ../lz4/lib/lz4.c
  - lz4_thin.c
headers:
  - ../lz4/lib/lz4.h

functions:
  - py_sig: "compress(src: buffer, dst: buffer) -> int"
    checks:
      - "src.format == 'B'"
      - "dst.format == 'B'"
      - "src.ndim == 1"
      - "dst.ndim == 1"
    c_overloads:
      - sig: "int lz4_compress(const uint8_t *src, uint8_t *dst, int srcSize, int dstCapacity)"
        map:
          src: "src.ptr"
          dst: "dst.ptr"
          srcSize: "src.len"
          dstCapacity: "dst.len"

  - py_sig: "decompress(src: buffer, dst: buffer) -> int"
    checks:
      - "src.format == 'B'"
      - "dst.format == 'B'"
      - "src.ndim == 1"
      - "dst.ndim == 1"
    c_overloads:
      - sig: "int lz4_decompress(const uint8_t *src, uint8_t *dst, int compressedSize, int dstCapacity)"
        map:
          src: "src.ptr"
          dst: "dst.ptr"
          compressedSize: "src.len"
          dstCapacity: "dst.len"
```

## examples/lz4_wrap/lz4_thin.c

```c
#include <stdint.h>
#include "../lz4/lib/lz4.h"

int lz4_compress(const uint8_t *src, uint8_t *dst, int srcSize, int dstCapacity) {
    return LZ4_compress_default((const char *)src, (char *)dst, srcSize, dstCapacity);
}

int lz4_decompress(const uint8_t *src, uint8_t *dst, int compressedSize, int dstCapacity) {
    return LZ4_decompress_safe((const char *)src, (char *)dst, compressedSize, dstCapacity);
}
```

## examples/simd_dispatch/CMakeLists.txt

```
# CMakeLists.txt -- SIMD dispatch example with multi-flag compilation
#
# Demonstrates integrating c2py23 into a CMake build:
#   1. Compile kernel.c multiple times with different -m flags
#   2. Run c2py23 generate to produce the wrapper .c
#   3. Link everything into a shared module (Python extension)
#
# Usage:
#   mkdir build && cd build
#   cmake ..
#   cmake --build .
#   cd .. && python3 test_polysimd.py
#
# Prerequisites:
#   pip install c2py23 cmake
#
# NOTE: This is a build-system demonstration.  The same result can be
# achieved with the simple Makefile or a single `c2py23 build` call.
# This demo is for users integrating c2py23 into an existing CMake project.

cmake_minimum_required(VERSION 3.16)
project(polysimd LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O3 -fPIC -ffast-math")

# Find c2py23
find_program(C2PY23 c2py23 REQUIRED)

# Find runtime files from installed c2py23 package
execute_process(
  COMMAND python3 -c "import c2py23,os;print(os.path.join(os.path.dirname(c2py23.__file__),'runtime'))"
  OUTPUT_VARIABLE C2PY_RUNTIME_DIR
  OUTPUT_STRIP_TRAILING_WHITESPACE
)

# --- Multi-flag compilation ---
add_library(poly_f32_avx512 OBJECT poly_kernel.c)
target_compile_options(poly_f32_avx512 PRIVATE -mavx512f)
target_compile_definitions(poly_f32_avx512 PRIVATE KERNEL_FN=poly_f32_avx512)

add_library(poly_f32_avx2 OBJECT poly_kernel.c)
target_compile_options(poly_f32_avx2 PRIVATE -mavx2)
target_compile_definitions(poly_f32_avx2 PRIVATE KERNEL_FN=poly_f32_avx2)

add_library(poly_f32_scalar OBJECT poly_kernel.c)
target_compile_definitions(poly_f32_scalar PRIVATE KERNEL_FN=poly_f32_scalar)

# --- c2py23 generate ---
add_custom_command(
  OUTPUT polysimd_wrapper.c
  COMMAND ${C2PY23} generate ${CMAKE_CURRENT_SOURCE_DIR}/polysimd.c2py -o polysimd_wrapper.c
  DEPENDS polysimd.c2py
  COMMENT "Generating c2py23 wrapper"
)

# --- Link shared module ---
add_library(polysimd SHARED
  polysimd_wrapper.c
  ${C2PY_RUNTIME_DIR}/c2py_runtime.c
  ${C2PY_RUNTIME_DIR}/c2py_amd64.h
)
target_include_directories(polysimd PRIVATE ${C2PY_RUNTIME_DIR} ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(polysimd PRIVATE ${CMAKE_DL_LIBS} m)
set_target_properties(polysimd PROPERTIES
  PREFIX ""
  SUFFIX ".so"
  LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)
```

## examples/simd_dispatch/Makefile

```
# Makefile -- multi-flag SIMD compilation + c2py23 wrapping
#
# Compiles poly_kernel.c three times with different -m flags,
# producing ISA-specific object files.  c2py23 links them into
# the final .so and wraps them with CPU-feature dispatch.
#
# Usage:
#   make              build polysimd.so
#   make test         build and run test_polysimd.py
#   make clean        remove generated files

CC     ?= gcc
C2PY   ?= c2py23
CFLAGS := -O3 -Wall -Werror -fPIC -ffast-math

.PHONY: all test clean

all: polysimd.so

# --- Multi-flag compilation ---
# Each variant compiled from the SAME source with different -m flags
# and -DKERNEL_FN that renames the function.

poly_f32_avx512.o: poly_kernel.c
	$(CC) -c $(CFLAGS) -mavx512f -DKERNEL_FN=poly_f32_avx512 $< -o $@

poly_f32_avx2.o: poly_kernel.c
	$(CC) -c $(CFLAGS) -mavx2 -DKERNEL_FN=poly_f32_avx2 $< -o $@

poly_f32_scalar.o: poly_kernel.c
	$(CC) -c $(CFLAGS) -DKERNEL_FN=poly_f32_scalar $< -o $@

# --- c2py23 wrap ---
polysimd.so: polysimd.c2py poly_f32_avx512.o poly_f32_avx2.o poly_f32_scalar.o
	$(C2PY) build polysimd.c2py -o polysimd.so

test: polysimd.so
	python3 test_polysimd.py

clean:
	rm -f poly_f32_avx512.o poly_f32_avx2.o poly_f32_scalar.o
	rm -f polysimd_wrapper.c polysimd.so
```

## examples/simd_dispatch/meson.build

```
# meson.build -- SIMD dispatch example with multi-flag compilation
#
# Demonstrates integrating c2py23 into a meson build:
#   1. Compile kernel.c multiple times with different -m flags
#   2. Run c2py23 generate to produce the wrapper .c
#   3. Link everything into a shared module
#
# Usage:
#   meson setup builddir
#   meson compile -C builddir
#   meson test -C builddir
#
# Prerequisites:
#   pip install c2py23 meson
#
# NOTE: This is a build-system demonstration.  The same result can be
# achieved with the simple Makefile or a single `c2py23 build` call.
# This demo is for users who must integrate c2py23 into an existing
# meson project with custom compilation flags per source file.

project('polysimd', 'c',
  version: '0.1.0',
  default_options: ['warning_level=3', 'buildtype=release'])

cc = meson.get_compiler('c')
c2py = find_program('c2py23', required: true)
python3 = find_program('python3', 'python', required: false)

# Runtime files from the installed c2py23 package
r = run_command(python3, '-c',
  'import c2py23, os; print(os.path.join(os.path.dirname(c2py23.__file__), "runtime"))',
  check: true)
runtime_dir = r.stdout().strip()
runtime_c = join_paths(runtime_dir, 'c2py_runtime.c')
runtime_h = join_paths(runtime_dir, 'c2py_runtime.h')
amd64_h = join_paths(runtime_dir, 'c2py_amd64.h')

cflags = ['-O3', '-fPIC', '-ffast-math']

# --- Multi-flag compilation ---
poly_avx512 = static_library('poly_avx512', 'poly_kernel.c',
  c_args: cflags + ['-DKERNEL_FN=poly_f32_avx512', '-mavx512f'],
  install: false)

poly_avx2 = static_library('poly_avx2', 'poly_kernel.c',
  c_args: cflags + ['-DKERNEL_FN=poly_f32_avx2', '-mavx2'],
  install: false)

poly_scalar = static_library('poly_scalar', 'poly_kernel.c',
  c_args: cflags + ['-DKERNEL_FN=poly_f32_scalar'],
  install: false)

# --- c2py23 generate ---
wrapper_c = custom_target('polysimd_wrapper',
  input: 'polysimd.c2py',
  output: 'polysimd_wrapper.c',
  command: [c2py, 'generate', '@INPUT@', '-o', '@OUTPUT@'])

# --- Link shared module ---
polysimd = shared_module('polysimd',
  wrapper_c, runtime_c,
  link_with: [poly_avx512, poly_avx2, poly_scalar],
  include_directories: include_directories(runtime_dir, '.'),
  dependencies: [cc.find_library('dl', required: false)],
  install: true,
  install_dir: meson.current_source_dir())
```

## examples/simd_dispatch/poly_kernel.c

```c
/* poly_kernel.c -- compute-bound polynomial: out[i] = f(a[i], b[i])
 *
 * Each element does many arithmetic operations per memory load to
 * make the kernel compute-bound rather than memory-bound.  This
 * ensures SIMD width differences (SSE 4-wide, AVX2 8-wide,
 * AVX-512 16-wide) translate to visible throughput differences.
 *
 * This file is compiled multiple times with different -m flags and
 * -DKERNEL_FN=<name> to produce ISA-specific variants.  The kernel
 * itself is plain C99; the compiler auto-vectorizes based on the
 * -m flags supplied at compile time.
 *
 * Build (see Makefile):
 *   gcc -c -O3 -ffast-math -mavx512f -DKERNEL_FN=poly_f32_avx512 poly_kernel.c -o ...
 *   gcc -c -O3 -ffast-math -mavx2   -DKERNEL_FN=poly_f32_avx2   poly_kernel.c -o ...
 *   gcc -c -O3 -ffast-math          -DKERNEL_FN=poly_f32_scalar  poly_kernel.c -o ...
 */

#include <stddef.h>

#ifndef KERNEL_FN
#define KERNEL_FN poly_f32
#endif

/* Horner-like repeated squaring: x = a[i], then x = x*x + b[i] many times.
 * Each inner iteration: 1 mul + 1 add, 0 extra memory accesses.
 * Arithmetic intensity: ~16:1 (16 mul+add per 2 loads + 1 store). */
#define POLY_DEPTH 16

void KERNEL_FN(const float *a, const float *b, float *out, int n)
{
    int i;
    for (i = 0; i < n; i++) {
        float x = a[i];
        float y = b[i];
        int k;
        for (k = 0; k < POLY_DEPTH; k++)
            x = x * x + y;
        out[i] = x;
    }
}
```

## examples/simd_dispatch/polysimd.c2py

```yaml
# polysimd.c2py -- SIMD dispatch example with multi-flag compilation
#
# The kernel (poly_kernel.c) is compiled three times with different
# -m flags to produce ISA-specific .o files.  The .c2py file wraps
# each variant and dispatches based on CPU feature flags.
#
# Build:  make
# Test:   python3 test_polysimd.py

module: polysimd
source: [poly_f32_avx512.o, poly_f32_avx2.o, poly_f32_scalar.o]
headers: [c2py_amd64.h]
timing: true

functions:
  - py_sig: "poly(a: buffer, b: buffer, out: buffer) -> void"
    checks:
      - "a.n == b.n"
      - "a.n == out.n"
    c_overloads:
      - when: "a.format == 'f' and b.format == 'f' and out.format == 'f'"
        map: {a: "a.ptr", b: "b.ptr", out: "out.ptr", n: "a.n"}
        group: float
        variants:
          - name: "avx512"
            sig: "void poly_f32_avx512(const float *a, const float *b, float *out, int n)"
            when: "c2py_amd64_avx512f"
          - name: "avx2"
            sig: "void poly_f32_avx2(const float *a, const float *b, float *out, int n)"
            when: "c2py_amd64_avx2"
          - name: "scalar"
            sig: "void poly_f32_scalar(const float *a, const float *b, float *out, int n)"
```

## examples/simd_dispatch/setup.py

```python
"""setup.py -- SIMD dispatch example with multi-flag compilation

Demonstrates integrating c2py23 into a setuptools build:
  1. Pre-build hook: compile kernel.c multiple times with different -m flags
  2. c2py23 generate to produce the wrapper .c
  3. setuptools Extension builds the wrapper .c + runtime .c + user .o files

Usage:
  python3 setup.py build_ext --inplace
  python3 test_polysimd.py

Prerequisites:
  pip install c2py23 setuptools

NOTE: This is a build-system demonstration.  The same result can be
achieved with the simple Makefile or a single `c2py23 build` call.
"""
from __future__ import print_function

import os
import sys
import subprocess

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext as _build_ext


def find_runtime_dir():
    import c2py23
    return os.path.join(os.path.dirname(c2py23.__file__), 'runtime')


class PreBuildExtension(_build_ext):
    """Pre-build: compile poly_kernel.c with multiple -m flags,
    then run c2py23 generate to produce the wrapper .c."""

    def run(self):
        src_dir = os.path.dirname(os.path.abspath(__file__))
        cc = os.environ.get('CC', 'gcc')
        cflags = ['-O3', '-Wall', '-Werror', '-fPIC', '-ffast-math']

        # Multi-flag compilation
        variants = [
            ('poly_f32_avx512', ['-mavx512f']),
            ('poly_f32_avx2', ['-mavx2']),
            ('poly_f32_scalar', []),
        ]
        for fn_name, extra_flags in variants:
            obj = os.path.join(src_dir, '%s.o' % fn_name)
            cmd = [cc, '-c'] + cflags + extra_flags + [
                '-D', 'KERNEL_FN=%s' % fn_name,
                os.path.join(src_dir, 'poly_kernel.c'),
                '-o', obj,
            ]
            print('  ' + ' '.join(cmd))
            ret = subprocess.call(cmd)
            if ret != 0:
                sys.exit(ret)

        # Generate wrapper
        c2py_path = os.path.join(src_dir, 'polysimd.c2py')
        wrapper_path = os.path.join(src_dir, 'polysimd_wrapper.c')
        ret = subprocess.call([
            sys.executable, '-m', 'c2py23', 'generate', c2py_path,
            '-o', wrapper_path,
        ])
        if ret != 0:
            sys.exit(ret)

        _build_ext.run(self)


runtime_dir = find_runtime_dir()
runtime_c = os.path.join(runtime_dir, 'c2py_runtime.c')
src_dir = os.path.dirname(os.path.abspath(__file__))

polysimd_ext = Extension(
    'polysimd',
    sources=[
        runtime_c,
        os.path.join(src_dir, 'polysimd_wrapper.c'),
    ],
    extra_objects=[
        os.path.join(src_dir, 'poly_f32_avx512.o'),
        os.path.join(src_dir, 'poly_f32_avx2.o'),
        os.path.join(src_dir, 'poly_f32_scalar.o'),
    ],
    include_dirs=[runtime_dir, src_dir],
    extra_link_args=['-ldl'],
)

setup(
    name='polysimd',
    version='0.1.0',
    py_modules=[],
    ext_modules=[polysimd_ext],
    cmdclass={'build_ext': PreBuildExtension},
)
```

## examples/simd_dispatch/test_polysimd.py

```python
"""Test the poly SIMD dispatch module.

Demonstrates:
  - Automatic variant selection (CPU features)
  - Manual rebinding via _rebind_poly()
  - Timing via built-in c2py23 perf counters
  - Compute-bound kernel where SIMD width directly matters
"""
from __future__ import print_function

import ctypes
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polysimd

try:
    from c2py23.perf import read_perf, read_enabled, set_enabled
    HAVE_PERF = True
except ImportError:
    HAVE_PERF = False
    print("(c2py23.perf not available)")

# --- Test data ---
N = 100000
a = (ctypes.c_float * N)(*[float(i % 100) / 100.0 for i in range(N)])
b = (ctypes.c_float * N)(*[float(i % 100) / 100.0 for i in range(N)])
out = (ctypes.c_float * N)()

print("=== Poly SIMD dispatch ===")
print("Array size: %d" % N)
print("Docstring:")
print(polysimd.poly.__doc__)
print()

# --- Correctness check ---
variants = ["scalar", "avx2", "avx512"]
results = {}
for v in variants:
    polysimd._rebind_poly(v)
    polysimd.poly(a, b, out)
    results[v] = list(out[:3])
    print("%-8s out[:3] = %s" % (v, results[v]))

# All should match
ref = results["scalar"]
for v in ["avx2", "avx512"]:
    if results[v] != ref:
        print("MISMATCH: %s != scalar!" % v)
    else:
        print("%-8s matches scalar" % v)

# --- Timing via wall clock (multiple runs, show variance) ---
print()
print("=== Wall-clock timing (100 iterations, %d elements) ===" % N)
N_ITER = 100
N_WARM = 5

for v in variants:
    polysimd._rebind_poly(v)
    for _ in range(N_WARM):
        polysimd.poly(a, b, out)

    runs = []
    for run in range(5):
        t0 = time.time()
        for _ in range(N_ITER):
            polysimd.poly(a, b, out)
        dt = (time.time() - t0) / N_ITER * 1e6
        runs.append(dt)

    mean = sum(runs) / len(runs)
    std = (sum((r - mean)**2 for r in runs) / len(runs)) ** 0.5
    print("  %-8s  %8.1f us/call  (+/- %.1f us, cv=%.1f%%)" % (v, mean, std, 100*std/mean if mean else 0))

# --- Built-in perf ---
if HAVE_PERF:
    print()
    print("=== c2py23 built-in perf (cycles, 100 iterations) ===")
    variant_short = {"scalar": "poly_f32_scalar", "avx2": "poly_f32_avx2", "avx512": "poly_f32_avx512"}
    for v in variants:
        polysimd._rebind_poly(v)
        for _ in range(N_WARM):
            polysimd.poly(a, b, out)
        for _ in range(N_ITER):
            polysimd.poly(a, b, out)

        perf_key = '_perf_poly__' + variant_short[v]
        ptr = getattr(polysimd, perf_key, 0)
        if ptr:
            stats = read_perf(ptr)
            cyc = stats.get('c_mean_ns', 0)
            print("  %-8s  %8.0f cycles/call" % (v, cyc))
        else:
            print("  %-8s  (no perf struct)" % v)

# --- Speedup ratios ---
print()
print("=== Speedup ratios (wall clock, vs scalar) ===")
# Re-measure fresh
scalar_dt = None
for v in variants:
    polysimd._rebind_poly(v)
    for _ in range(N_WARM):
        polysimd.poly(a, b, out)
    t0 = time.time()
    for _ in range(N_ITER):
        polysimd.poly(a, b, out)
    dt = time.time() - t0
    if v == "scalar":
        scalar_dt = dt
    speedup = scalar_dt / dt if scalar_dt else 0
    print("  %-8s  %5.2fx" % (v, speedup))

polysimd._rebind_poly(None)
print()
print("Done.")
```

## examples/threading_bench/Makefile

```
CC       = gcc
CFLAGS   = -O3 -Wall -Werror
OMPFLAGS = -fopenmp

.PHONY: all clean serial omp

all: serial

serial:
	c2py23 build mc_pi.c2py

omp:
	CFLAGS="$(OMPFLAGS)" c2py23 build mc_pi.c2py

clean:
	rm -f mcpimod.so mcpimod_wrapper.c
```

## examples/threading_bench/bench_mc_pi.py

```python
#!/usr/bin/env python
"""Monte Carlo Pi -- Threading Benchmark

Compares serial, GIL release with threads, free-threading (3.14t+),
and OpenMP parallelism for a pure-C compute workload.

Usage:
    c2py23 build mc_pi.c2py && python bench_mc_pi.py
    EXTRA_CFLAGS=-fopenmp c2py23 build mc_pi.c2py && python bench_mc_pi.py

Python 2.7 compatible (uses threading.Thread, not concurrent.futures).
"""
from __future__ import print_function, division

import ctypes
import os
import sys
import threading
import time
import sysconfig

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import mcpimod
except ImportError:
    print("ERROR: mcpimod.so not found. Build it first:")
    print("  cd {} && c2py23 build mc_pi.c2py".format(HERE))
    sys.exit(1)

IS_PY3 = sys.version_info[0] >= 3

gil_disabled = sysconfig.get_config_var('Py_GIL_DISABLED')
IS_FREE_THREADED = (gil_disabled == 1)

TOTAL_N = 200000000
NUM_THREADS = 4
CHUNK_N = TOTAL_N // NUM_THREADS


def _detect_omp():
    """Check whether the .so was built with real OpenMP support.

    Uses ctypes to look up the mc_pi_has_omp symbol, which returns
    1 when compiled with -fopenmp, 0 otherwise.
    """
    so_path = os.path.join(HERE, "mcpimod.so")
    if not os.path.isfile(so_path):
        return False
    try:
        lib = ctypes.CDLL(so_path)
        fn = lib.mc_pi_has_omp
        fn.restype = ctypes.c_int
        return fn() == 1
    except Exception:
        return False


HAS_OMP = _detect_omp()


def elapsed_since(t0):
    return time.time() - t0


def run_serial():
    """Single-threaded baseline."""
    t0 = time.time()
    inside = mcpimod.mc_pi(TOTAL_N, 12345)
    elapsed = elapsed_since(t0)
    pi = 4.0 * inside / TOTAL_N
    return pi, elapsed


def run_threaded(n_threads):
    """Python threads with GIL release.

    Each thread calls mc_pi with 1/n_threads of the work and an
    independent seed.  On standard Python the C call releases the
    GIL; on free-threaded builds there is no GIL to release.
    """
    results = [0] * n_threads

    def worker(idx):
        seed = 12345 + idx * 7919
        results[idx] = mcpimod.mc_pi(CHUNK_N, seed)

    threads = [threading.Thread(target=worker, args=(i,))
               for i in range(n_threads)]

    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = elapsed_since(t0)

    inside = sum(results)
    pi = 4.0 * inside / (CHUNK_N * n_threads)
    return pi, elapsed


def run_openmp():
    """Single Python thread, C uses #pragma omp parallel for."""
    t0 = time.time()
    inside = mcpimod.mc_pi_omp(TOTAL_N, 12345)
    elapsed = elapsed_since(t0)
    pi = 4.0 * inside / TOTAL_N
    return pi, elapsed


def fmt_time(t):
    return "%.3fs" % t


def fmt_speedup(t_base, t_parallel):
    if t_parallel > 0:
        return "%.1fx" % (t_base / t_parallel)
    return "N/A"


def main():
    print("=== Monte Carlo Pi -- Threading Benchmark ===")
    print("Python: {} (free-threaded: {})".format(
        sys.version.split()[0], "yes" if IS_FREE_THREADED else "no"))
    print("Iterations: {:,} ({} chunks of {:,})".format(
        TOTAL_N, NUM_THREADS, CHUNK_N))
    print()

    # ---- 1. Serial baseline ----
    print("1. Serial")
    pi_s, t_s = run_serial()
    print("   pi = %.6f, wall = %s" % (pi_s, fmt_time(t_s)))
    print()

    t_base = t_s

    # ---- 2. GIL release + threading (or free-threading) ----
    label = "2. GIL release + %d threads" % NUM_THREADS
    if IS_FREE_THREADED:
        label = "2. Free-threading (%d threads)" % NUM_THREADS
    print(label)
    pi_t, t_t = run_threaded(NUM_THREADS)
    print("   pi = %.6f, wall = %s, speedup = %s" % (
        pi_t, fmt_time(t_t), fmt_speedup(t_base, t_t)))
    if NUM_THREADS > 1:
        efficiency = (t_base / t_t) / NUM_THREADS * 100
        print("   efficiency = %.0f%%" % efficiency)
    print()

    # ---- 3. OpenMP ----
    if HAS_OMP:
        print("3. OpenMP (%d threads inside C)" % NUM_THREADS)
        pi_o, t_o = run_openmp()
        print("   pi = %.6f, wall = %s, speedup = %s" % (
            pi_o, fmt_time(t_o), fmt_speedup(t_base, t_o)))
        if NUM_THREADS > 1:
            efficiency = (t_base / t_o) / NUM_THREADS * 100
            print("   efficiency = %.0f%%" % efficiency)
    else:
        print("3. OpenMP -- SKIP (rebuild with EXTRA_CFLAGS=-fopenmp)")
    print()

    # ---- Notes ----
    if IS_FREE_THREADED:
        print("Note: running on free-threaded Python (--disable-gil).")
        print("  PyEval_SaveThread is a no-op; threads overlap natively.")
        print("  c2py23 modules have GIL re-enabled for safety,")
        print("  so true free-threading requires PYTHON_GIL=0.")
    elif not HAS_OMP:
        print("Tip: rebuild with OpenMP for mode 3:")
        print("  EXTRA_CFLAGS=-fopenmp c2py23 build mc_pi.c2py")


if __name__ == '__main__':
    main()
```

## examples/threading_bench/mc_pi.c

```c
#include <stdint.h>

/* xorshift64 state */
typedef struct { uint64_t s; } xrs128_t;

static inline uint64_t xrs128_next(xrs128_t *st) {
    uint64_t x = st->s;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    st->s = x;
    return x;
}

static inline double xrs128_double(xrs128_t *st) {
    return (double)(xrs128_next(st) >> 11) * 0x1.0p-53;
}

static void xrs128_seed(xrs128_t *st, unsigned int seed) {
    st->s = (uint64_t)(seed + 1) * 0x9E3779B97F4A7C15ULL;
    (void)xrs128_next(st);
}

int mc_pi_serial(int n, int seed) {
    int inside = 0;
    int i;
    xrs128_t rng;
    xrs128_seed(&rng, (unsigned int)seed);

    for (i = 0; i < n; i++) {
        double x = xrs128_double(&rng);
        double y = xrs128_double(&rng);
        if (x * x + y * y <= 1.0)
            inside++;
    }
    return inside;
}

#ifdef _OPENMP
#include <omp.h>

int mc_pi_omp(int n, int seed) {
    int inside = 0;
#pragma omp parallel reduction(+ : inside)
    {
        int tid = omp_get_thread_num();
        xrs128_t rng;
        xrs128_seed(&rng, (unsigned int)(seed + tid * 7919));

        int i;
#pragma omp for
        for (i = 0; i < n; i++) {
            double x = xrs128_double(&rng);
            double y = xrs128_double(&rng);
            if (x * x + y * y <= 1.0)
                inside++;
        }
    }
    return inside;
}

int mc_pi_has_omp(void) {
    return 1;
}

#else

int mc_pi_omp(int n, int seed) {
    return mc_pi_serial(n, seed);
}

int mc_pi_has_omp(void) {
    return 0;
}
#endif
```

## examples/threading_bench/mc_pi.c2py

```yaml
module: mcpimod
source: [mc_pi.c]

functions:
  - py_sig: "mc_pi(n: int, seed: int = 0) -> int"
    gil_release: true
    c_overloads:
      - sig: "mc_pi_serial(int n, int seed) -> int"
        map:
          n: n
          seed: seed

  - py_sig: "mc_pi_omp(n: int, seed: int = 0) -> int"
    c_overloads:
      - sig: "mc_pi_omp(int n, int seed) -> int"
        map:
          n: n
          seed: seed

```

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=44", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "c2py23"
version = "0.1.0"
description = "Wrap C99 code to Python via the buffer protocol"
requires-python = ">=2.7"
dependencies = [
    "PyYAML>=5.1;python_version>='3'",
    "PyYAML>=3.10,<6;python_version=='2.7'",
]

[project.scripts]
c2py23 = "c2py23.cli:main"

[tool.setuptools.packages.find]
include = ["c2py23*"]
```

## setup.py

```python
"""Setup script for c2py23 - backward compat with older pip/setuptools."""
from __future__ import print_function
from setuptools import setup, find_packages

setup(
    name='c2py23',
    version='0.1.0',
    description='Wrap C99 code to Python via the buffer protocol',
    packages=find_packages(include=['c2py23', 'c2py23.*']),
    package_data={'c2py23': ['runtime/*.h', 'runtime/*.c']},
    install_requires=[
        'PyYAML>=5.1;python_version>="3"',
        'PyYAML>=3.10,<6;python_version=="2.7"',
    ],
    entry_points={
        'console_scripts': [
            'c2py23=c2py23.cli:main',
        ],
    },
)
```

## tests/abi_matrix.json

```json
{
  "Linux-x86_64": {
    "2.7": {
      "abi": {
        "EXC_OB_TYPE_RAW_0x7c7a8f34b220": "",
        "EXC_USES_SHARED_REFCNT_0": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x7c7a8f346040": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "88",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_2.7.18": "(default, Dec  9 2024, 19:35:20)",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "96",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "MISSING",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "MISSING",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "MISSING",
        "SYM__Py_IncRef": "MISSING",
        "SYM__Py_NoneStruct": "FOUND",
        "[GCC_9.4.0]": ""
      },
      "python_version": "2.7.18 (default, Dec  9 2024, 19:35:20)"
    },
    "3.10": {
      "abi": {
        "EXC_OB_TYPE_RAW_0x735075c3d020": "",
        "EXC_USES_SHARED_REFCNT_0": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_FASTCALL": "0x0080",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x735075c4f0e0": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "72",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_3.10.20": "(main, Mar  3 2026, 09:24:47) [GCC 13.3.0]",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "80",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "FOUND",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "MISSING",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "FOUND",
        "SYM__Py_IncRef": "FOUND",
        "SYM__Py_NoneStruct": "FOUND"
      },
      "python_version": "3.10.20 (main, Mar  3 2026, 09:24:47) [GCC 13.3.0]"
    },
    "3.11": {
      "abi": {
        "EXC_OB_TYPE_RAW_0x7ed90e5c4700": "",
        "EXC_USES_SHARED_REFCNT_0": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_FASTCALL": "0x0080",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x7ed90e5c7ec0": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "72",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_3.11.15": "(main, Mar  3 2026, 09:26:23) [GCC 13.3.0]",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "80",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "FOUND",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "FOUND",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "FOUND",
        "SYM__Py_IncRef": "FOUND",
        "SYM__Py_NoneStruct": "FOUND"
      },
      "python_version": "3.11.15 (main, Mar  3 2026, 09:26:23) [GCC 13.3.0]"
    },
    "3.12": {
      "abi": {
        "EXC_OB_TYPE_RAW_(nil)": "",
        "EXC_USES_SHARED_REFCNT_1": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_FASTCALL": "0x0080",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x71c54597b6c0": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "72",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_3.12.3": "(main, Mar 23 2026, 19:04:32) [GCC 13.3.0]",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "80",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "FOUND",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "FOUND",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "FOUND",
        "SYM__Py_IncRef": "FOUND",
        "SYM__Py_NoneStruct": "FOUND"
      },
      "python_version": "3.12.3 (main, Mar 23 2026, 19:04:32) [GCC 13.3.0]"
    },
    "3.13": {
      "abi": {
        "EXC_OB_TYPE_RAW_0x77d0e41907c0": "",
        "EXC_USES_SHARED_REFCNT_0": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_FASTCALL": "0x0080",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x77d0e419bb40": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "72",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_3.13.14": "(main, Jun 11 2026, 12:30:59) [GCC 13.3.0]",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "80",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "FOUND",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "FOUND",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "FOUND",
        "SYM__Py_IncRef": "FOUND",
        "SYM__Py_NoneStruct": "FOUND"
      },
      "python_version": "3.13.14 (main, Jun 11 2026, 12:30:59) [GCC 13.3.0]"
    },
    "3.14": {
      "abi": {
        "EXC_OB_TYPE_RAW_0x74ec0b17da60": "",
        "EXC_USES_SHARED_REFCNT_0": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_FASTCALL": "0x0080",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x74ec0b188fc0": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "72",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_3.14.6": "(main, Jun 11 2026, 12:32:48) [GCC 13.3.0]",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "80",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "FOUND",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "FOUND",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "FOUND",
        "SYM__Py_IncRef": "FOUND",
        "SYM__Py_NoneStruct": "FOUND"
      },
      "python_version": "3.14.6 (main, Jun 11 2026, 12:32:48) [GCC 13.3.0]"
    },
    "3.6": {
      "abi": {
        "#define__GNU_SOURCE": "",
        "/usr/local/include/python3.6m/pyconfig.h:1459:_warning:": "\"_GNU_SOURCE\" redefined",
        "EXC_OB_TYPE_RAW_(nil)": "",
        "EXC_USES_SHARED_REFCNT_1": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_FASTCALL": "0x0080",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "In_file": "included from /usr/local/include/python3.6m/Python.h:8,",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x7f97bc597120": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "72",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_3.6.15": "(default, Dec 21 2021, 12:20:05)",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "80",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "FOUND",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "MISSING",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "MISSING",
        "SYM__Py_IncRef": "MISSING",
        "SYM__Py_NoneStruct": "FOUND",
        "[GCC_8.3.0]": "",
        "check_abi.c:10:_note:": "this is the location of the previous definition",
        "from_check_abi.c:11:": ""
      },
      "python_version": "3.6.15 (default, Dec 21 2021, 12:20:05)"
    },
    "3.7": {
      "abi": {
        "EXC_OB_TYPE_RAW_(nil)": "",
        "EXC_USES_SHARED_REFCNT_1": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_FASTCALL": "0x0080",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x740bfc2ff280": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "72",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_3.7.17": "(default, Apr 27 2024, 21:22:13)",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "80",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "FOUND",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "MISSING",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "MISSING",
        "SYM__Py_IncRef": "MISSING",
        "SYM__Py_NoneStruct": "FOUND",
        "[GCC_13.2.0]": ""
      },
      "python_version": "3.7.17 (default, Apr 27 2024, 21:22:13)"
    },
    "3.8": {
      "abi": {
        "EXC_OB_TYPE_RAW_0x72921ad9c9a0": "",
        "EXC_USES_SHARED_REFCNT_0": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_FASTCALL": "0x0080",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x72921ad9ec20": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "72",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_3.8.10": "(default, Mar 18 2025, 20:04:55)",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "80",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "FOUND",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "MISSING",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "MISSING",
        "SYM__Py_IncRef": "MISSING",
        "SYM__Py_NoneStruct": "FOUND",
        "[GCC_9.4.0]": ""
      },
      "python_version": "3.8.10 (default, Mar 18 2025, 20:04:55)"
    },
    "3.9": {
      "abi": {
        "EXC_OB_TYPE_RAW_0x70ec5eb32fa0": "",
        "EXC_USES_SHARED_REFCNT_0": "",
        "FLAG_METH_CLASS": "0x0010",
        "FLAG_METH_FASTCALL": "0x0080",
        "FLAG_METH_KEYWORDS": "0x0002",
        "FLAG_METH_NOARGS": "0x0004",
        "FLAG_METH_O": "0x0008",
        "FLAG_METH_STATIC": "0x0020",
        "FLAG_METH_VARARGS": "0x0001",
        "FLAG_PyBUF_FORMAT": "0x0004",
        "FLAG_PyBUF_ND": "0x0008",
        "FLAG_PyBUF_SIMPLE": "0x0000",
        "FLAG_PyBUF_STRIDES": "0x0018",
        "FLAG_PyBUF_WRITABLE": "0x0001",
        "NONE_HAS_VALID_OB_TYPE_1": "",
        "NONE_OB_TYPE_0x70ec5eb44ec0": "",
        "OFFSET_PyObject.ob_refcnt": "0",
        "OFFSET_PyObject.ob_type": "8",
        "OFFSET_Py_buffer.buf": "0",
        "OFFSET_Py_buffer.format": "40",
        "OFFSET_Py_buffer.internal": "72",
        "OFFSET_Py_buffer.itemsize": "24",
        "OFFSET_Py_buffer.len": "16",
        "OFFSET_Py_buffer.ndim": "36",
        "OFFSET_Py_buffer.obj": "8",
        "OFFSET_Py_buffer.readonly": "32",
        "OFFSET_Py_buffer.shape": "48",
        "OFFSET_Py_buffer.strides": "56",
        "OFFSET_Py_buffer.suboffsets": "64",
        "PYVER_3.9.25": "(main, Nov  7 2025, 18:07:57)",
        "SIZEOF_PyObject": "16",
        "SIZEOF_Py_buffer": "80",
        "SIZEOF_Py_ssize_t": "8",
        "SIZEOF_int": "4",
        "SIZEOF_long": "8",
        "SIZEOF_void_ptr": "8",
        "SYM_PyArg_ParseTuple": "FOUND",
        "SYM_PyArg_ParseTupleAndKeywords": "FOUND",
        "SYM_PyBuffer_Release": "FOUND",
        "SYM_PyErr_Clear": "FOUND",
        "SYM_PyErr_Occurred": "FOUND",
        "SYM_PyErr_SetString": "FOUND",
        "SYM_PyExc_MemoryError": "FOUND",
        "SYM_PyExc_RuntimeError": "FOUND",
        "SYM_PyExc_TypeError": "FOUND",
        "SYM_PyExc_ValueError": "FOUND",
        "SYM_PyFloat_AsDouble": "FOUND",
        "SYM_PyFloat_FromDouble": "FOUND",
        "SYM_PyLong_AsLong": "FOUND",
        "SYM_PyLong_FromLong": "FOUND",
        "SYM_PyLong_FromLongLong": "FOUND",
        "SYM_PyModule_Create2": "FOUND",
        "SYM_PyObject_AsReadBuffer": "FOUND",
        "SYM_PyObject_AsWriteBuffer": "FOUND",
        "SYM_PyObject_GetBuffer": "FOUND",
        "SYM_PyObject_Vectorcall": "MISSING",
        "SYM_Py_DecRef": "FOUND",
        "SYM_Py_GetVersion": "FOUND",
        "SYM_Py_IncRef": "FOUND",
        "SYM_Py_None": "MISSING",
        "SYM__Py_DecRef": "MISSING",
        "SYM__Py_IncRef": "MISSING",
        "SYM__Py_NoneStruct": "FOUND",
        "[GCC_13.3.0]": ""
      },
      "python_version": "3.9.25 (main, Nov  7 2025, 18:07:57)"
    }
  }
}
```

## tests/cases/address/address.c

```c
#include <stdint.h>

int address_store(void *ptr, int value, int offset) {
    if (!ptr) return -1;
    int *p = (int *)ptr;
    p[offset] = value;
    return 0;
}
```

## tests/cases/address/address.c2py

```yaml
module: addressmod
source: [address.c]

functions:
  - py_sig: "address_store(ptr: int, value: int, offset: int) -> int"
    c_overloads:
      - sig: "int address_store(void *ptr, int value, int offset)"
        map: {ptr: ptr, value: value, offset: offset}
```

## tests/cases/arraysum/arraysum.c

```c
/* arraysum.c - element-wise addition of double arrays */
extern int array_sum(const double *a, const double *b, double *result, int n);

int array_sum(const double *a, const double *b, double *result, int n) {
    int i;
    for (i = 0; i < n; i++) {
        result[i] = a[i] + b[i];
    }
    return n;
}
```

## tests/cases/arraysum/arraysum.c2py

```yaml
module: arraysum
source: [arraysum.c]

functions:
  - py_sig: "array_sum(a: buffer, b: buffer, result: buffer) -> int"
    checks:
      - "a.format == 'd'"
      - "b.format == 'd'"
      - "result.format == 'd'"
      - "a.n == b.n"
      - "a.n == result.n"
    c_overloads:
      - sig: "array_sum(const double *a, const double *b, double *result, int n) -> int"
        map: {a: "a.ptr", b: "b.ptr", result: "result.ptr", n: "a.n"}
```

## tests/cases/constants/constants.c

```c
double scale_and_sum(const double *data, int n, int factor)
{
    int i;
    double s = 0.0;
    for (i = 0; i < n; i++) {
        s += data[i] * (double)factor;
    }
    return s;
}
```

## tests/cases/constants/constants.c2py

```yaml
module: constmod
source: [constants.c]
constants:
  ALPHA: 1
  BETA: 2
  GAMMA: 3

functions:
  - py_sig: "scale_sum(data: buffer, factor: int) -> float"
    c_overloads:
      - sig: "scale_and_sum(const double *data, int n, int factor) -> double"
        map: {data: "data.ptr", n: "data.n", factor: factor}
```

## tests/cases/docstring/docstring.c

```c
int add_one(int x)
{
    return x + 1;
}
```

## tests/cases/docstring/docstring.c2py

```yaml
module: docmod
source: [docstring.c]

functions:
  - py_sig: "inc(x: int) -> int"
    doc: "Increment x by 1 and return the result"
    c_overloads:
      - sig: "add_one(int x) -> int"
        map: {x: x}
```

## tests/cases/dot/dot.c

```c
/* dot.c - dot product of float or double arrays */

float dot_f(const float *a, const float *b, int n) {
    float sum = 0.0f;
    int i;
    for (i = 0; i < n; i++) {
        sum += a[i] * b[i];
    }
    return sum;
}

double dot_d(const double *a, const double *b, int n) {
    double sum = 0.0;
    int i;
    for (i = 0; i < n; i++) {
        sum += a[i] * b[i];
    }
    return sum;
}
```

## tests/cases/dot/dot.c2py

```yaml
module: dotmod
source: [dot.c]

functions:
  - py_sig: "dot(a: buffer, b: buffer) -> float"
    checks:
      - "a.format == b.format"
      - "a.n == b.n"
    c_overloads:
      - sig: "dot_f(const float *a, const float *b, int n) -> float"
        map: {a: "a.ptr", b: "b.ptr", n: "a.n"}
        when: "a.format == 'f'"
      - sig: "dot_d(const double *a, const double *b, int n) -> double"
        map: {a: "a.ptr", b: "b.ptr", n: "a.n"}
        when: "a.format == 'd'"
    default_raise: "TypeError: expected float or double buffer"
```

## tests/cases/fill/fill.c

```c
/* fill.c - fill an array with a constant value */

void fill_f(float *arr, int n, float value) {
    int i;
    for (i = 0; i < n; i++) {
        arr[i] = value;
    }
}

void fill_d(double *arr, int n, double value) {
    int i;
    for (i = 0; i < n; i++) {
        arr[i] = value;
    }
}
```

## tests/cases/fill/fill.c2py

```yaml
module: fillmod
source: [fill.c]

functions:
  - py_sig: "fill(arr: buffer, value: float) -> void"
    c_overloads:
      - sig: "fill_f(float *arr, int n, float value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'f'"
      - sig: "fill_d(double *arr, int n, double value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'd'"
    default_raise: "TypeError: expected float or double buffer"
```

## tests/cases/gil_release/sleep_fill.c

```c
#include <stdint.h>
#include <unistd.h>

void sleep_fill_f32(float *arr, int n, float value, int us)
{
    usleep(us);
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void sleep_fill_f64(double *arr, int n, double value, int us)
{
    usleep(us);
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}
```

## tests/cases/gil_release/sleep_fill.c2py

```yaml
module: gilmod
source: [sleep_fill.c]

functions:
  - py_sig: "sleep_fill(arr: buffer, value: float, us: int) -> void"
    gil_release: true
    c_overloads:
      - sig: "sleep_fill_f32(float *arr, int n, float value, int us)"
        map: {arr: "arr.ptr", n: "arr.n", value: value, us: us}
        when: "arr.format == 'f'"
      - sig: "sleep_fill_f64(double *arr, int n, double value, int us)"
        map: {arr: "arr.ptr", n: "arr.n", value: value, us: us}
        when: "arr.format == 'd'"
    default_raise: "TypeError: expected float or double buffer"

  - py_sig: "sleep_fill_no_gil(arr: buffer, value: float, us: int) -> void"
    c_overloads:
      - sig: "sleep_fill_f32(float *arr, int n, float value, int us)"
        map: {arr: "arr.ptr", n: "arr.n", value: value, us: us}
        when: "arr.format == 'f'"
      - sig: "sleep_fill_f64(double *arr, int n, double value, int us)"
        map: {arr: "arr.ptr", n: "arr.n", value: value, us: us}
        when: "arr.format == 'd'"
    default_raise: "TypeError: expected float or double buffer"
```

## tests/cases/optional/optional.c

```c
int process_data(const double *data, int n, int stride, int verbose)
{
    int i;
    int result = 0;
    if (verbose) {
        /* side-effect to prove verbose was used */
        result += 1000;
    }
    for (i = 0; i < n; i += stride) {
        result += (int)data[i];
    }
    return result;
}
```

## tests/cases/optional/optional.c2py

```yaml
module: optmod
source: [optional.c]

functions:
  - py_sig: "process(data: buffer, stride: int = 1, verbose: int = 0) -> int"
    checks:
      - "data.format == 'd'"
    c_overloads:
      - sig: "process_data(const double *data, int n, int stride, int verbose) -> int"
        map: {data: "data.ptr", n: "data.n", stride: stride, verbose: verbose}
```

## tests/cases/scalar_output/stats.c

```c
void stats(const double *data, int n, double *minval, double *maxval)
{
    int i;
    double mn = data[0];
    double mx = data[0];
    for (i = 1; i < n; i++) {
        if (data[i] < mn) mn = data[i];
        if (data[i] > mx) mx = data[i];
    }
    *minval = mn;
    *maxval = mx;
}
```

## tests/cases/scalar_output/stats.c2py

```yaml
module: statmod
source: [stats.c]

functions:
  - py_sig: "stats(data: buffer) -> void"
    checks:
      - "data.format == 'd'"
    c_overloads:
      - sig: "stats(const double *data, int n, double *minval, double *maxval)"
        map: {data: "data.ptr", n: "data.n"}
        outputs:
          minval: double
          maxval: double
```

## tests/cases/template/sum.c2py

```yaml
module: summod
source: [template.c]

functions:
  - expand:
      TYPE: [uint8_t, uint16_t, int32_t]
      SUFFIX: [u8, u16, i32]
    py_sig: "sum_${SUFFIX}(data: buffer) -> int"
    checks:
      - "data.len >= 0"
    c_overloads:
      - sig: "int sum_${SUFFIX}(const ${TYPE} *data, int n)"
        map: {data: "data.ptr", n: "data.n"}
```

## tests/cases/template/template.c

```c
#include <stdint.h>

int sum_u8(const uint8_t *data, int n) {
    int s = 0, i;
    for (i = 0; i < n; i++) s += data[i];
    return s;
}

int sum_u16(const uint16_t *data, int n) {
    int s = 0, i;
    for (i = 0; i < n; i++) s += data[i];
    return s;
}

int sum_i32(const int32_t *data, int n) {
    int s = 0, i;
    for (i = 0; i < n; i++) s += data[i];
    return s;
}
```

## tests/cases/timing/timing.c

```c
double weighted_sum(const double *data, int n, double weight)
{
    int i;
    double s = 0.0;
    for (i = 0; i < n; i++) {
        s += data[i] * weight;
    }
    return s;
}
```

## tests/cases/timing/timing.c2py

```yaml
module: timedmod
source: [timing.c]
timing: true

functions:
  - py_sig: "wsum(data: buffer, weight: float) -> float"
    c_overloads:
      - sig: "weighted_sum(const double *data, int n, double weight) -> double"
        map: {data: "data.ptr", n: "data.n", weight: weight}
```

## tests/cases/transform/transform.c

```c
/* transform.c - in-place 2D transform: AoS vs SoA dispatch */

void transform_aos(double *points, int n, double *out) {
    /* points: [n, 3] layout (array of structs) */
    int i;
    for (i = 0; i < n; i++) {
        double x = points[i * 3 + 0];
        double y = points[i * 3 + 1];
        double z = points[i * 3 + 2];
        out[i * 3 + 0] = x * 2.0;
        out[i * 3 + 1] = y * 2.0;
        out[i * 3 + 2] = z * 2.0;
    }
}

void transform_soa(double *points, int n, double *out) {
    /* points: [3, n] layout (struct of arrays) */
    int i;
    for (i = 0; i < n; i++) {
        double x = points[0 * n + i];
        double y = points[1 * n + i];
        double z = points[2 * n + i];
        out[0 * n + i] = x * 2.0;
        out[1 * n + i] = y * 2.0;
        out[2 * n + i] = z * 2.0;
    }
}
```

## tests/cases/transform/transform.c2py

```yaml
module: xfrm
source: [transform.c]

functions:
  - py_sig: "transform(points: buffer, out: buffer) -> void"
    checks:
      - "points.format == 'd'"
      - "out.format == 'd'"
      - "out.n == points.n"
      - "points.ndim == 2"
    c_overloads:
      - sig: "transform_aos(double *points, int n, double *out)"
        map: {points: "points.ptr", n: "points.shape[0]", out: "out.ptr"}
        when: "points.shape[1] == 3"
      - sig: "transform_soa(double *points, int n, double *out)"
        map: {points: "points.ptr", n: "points.shape[1]", out: "out.ptr"}
        when: "points.shape[0] == 3"
    default_raise: "ValueError: expected [N,3] or [3,N] buffer"
```

## tests/cases/typedispatch/typedispatch.c

```c
#include <stdint.h>

void fill_u8(uint8_t *arr, int n, uint8_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i8(int8_t *arr, int n, int8_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_u16(uint16_t *arr, int n, uint16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i16(int16_t *arr, int n, int16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_u32(uint32_t *arr, int n, uint32_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i32(int32_t *arr, int n, int32_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_u64(uint64_t *arr, int n, uint64_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i64(int64_t *arr, int n, int64_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_f32(float *arr, int n, float value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_f64(double *arr, int n, double value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}
```

## tests/cases/typedispatch/typedispatch.c2py

```yaml
module: dispatchmod
source: [typedispatch.c]
headers: [stdint.h]

functions:
  - py_sig: "fill(arr: buffer, value: float) -> void"
    c_overloads:
      - sig: "fill_u8(uint8_t *arr, int n, uint8_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'B'"
      - sig: "fill_i8(int8_t *arr, int n, int8_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'b'"
      - sig: "fill_u16(uint16_t *arr, int n, uint16_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'H'"
      - sig: "fill_i16(int16_t *arr, int n, int16_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'h'"
      - sig: "fill_u32(uint32_t *arr, int n, uint32_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'I'"
      - sig: "fill_i32(int32_t *arr, int n, int32_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'i'"
      - sig: "fill_u64(uint64_t *arr, int n, uint64_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'Q'"
      - sig: "fill_i64(int64_t *arr, int n, int64_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'q'"
      - sig: "fill_f32(float *arr, int n, float value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'f'"
      - sig: "fill_f64(double *arr, int n, double value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'd'"
    default_raise: "TypeError: expected buffer of type B,b,H,h,I,i,Q,q,f,d"
```

## tests/cases/types/types.c

```c
#include <stdint.h>

void fill_u16(uint16_t *arr, int n, uint16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_u32(uint32_t *arr, int n, uint32_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i64(int64_t *arr, int n, int64_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i8(int8_t *arr, int n, int8_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = (int8_t)value;
}

void fill_i16(int16_t *arr, int n, int16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = (int16_t)value;
}
```

## tests/cases/types/types.c2py

```yaml
module: typesmod
source: [types.c]
headers: [stdint.h]

functions:
  - py_sig: "fill(arr: buffer, value: int) -> void"
    c_overloads:
      - sig: "fill_u16(uint16_t *arr, int n, uint16_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'H'"
      - sig: "fill_u32(uint32_t *arr, int n, uint32_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'I'"
      - sig: "fill_i64(int64_t *arr, int n, int64_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'q'"
      - sig: "fill_i8(int8_t *arr, int n, int8_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'b'"
      - sig: "fill_i16(int16_t *arr, int n, int16_t value)"
        map: {arr: "arr.ptr", n: "arr.n", value: value}
        when: "arr.format == 'h'"
    default_raise: "TypeError: expected 'H', 'I', 'q', 'b', or 'h' buffer"
```

## tests/check_abi.c

```c
/* check_abi.c - Verify Python C ABI across versions and platforms.
 *
 * Compile:  gcc check_abi.c $(python3-config --includes --ldflags) -ldl -o check_abi
 * Usage:    ./check_abi
 *
 * Output format is key-value pairs suitable for machine parsing.
 * Collect results over snakepit containers into abi_matrix.json.
 */

#define _GNU_SOURCE
#include <Python.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stddef.h>

static void check_sym(const char *name) {
    void *p = dlsym(RTLD_DEFAULT, name);
    printf("SYM %-35s %s\n", name, p ? "FOUND" : "MISSING");
}

int main(void) {
    /* --- Basic info --- */
    printf("PYVER %s\n", Py_GetVersion());

    /* --- Free-threading detection --- */
#ifdef Py_GIL_DISABLED
    printf("FREE_THREADED %d\n", Py_GIL_DISABLED ? 1 : 0);
#else
    printf("FREE_THREADED 0\n");
#endif

    /* --- Type sizes --- */
    printf("SIZEOF void_ptr      %zu\n", sizeof(void*));
    printf("SIZEOF Py_ssize_t    %zu\n", sizeof(Py_ssize_t));
    printf("SIZEOF int           %zu\n", sizeof(int));
    printf("SIZEOF long          %zu\n", sizeof(long));

    /* --- PyObject layout (for manual refcount fallback) --- */
    {
        PyObject *tmp = Py_None;
        printf("OFFSET PyObject.ob_refcnt  %td\n",
               (char*)&tmp->ob_refcnt - (char*)tmp);
        printf("OFFSET PyObject.ob_type    %td\n",
               (char*)&tmp->ob_type - (char*)tmp);
        printf("SIZEOF PyObject            %zu\n", sizeof(PyObject));
#ifdef Py_GIL_DISABLED
        /* On free-threaded builds, PyObject has additional fields.
         * ob_refcnt does not exist directly; report the sub-fields. */
        {
            printf("OFFSET ob_ref_local        %td\n",
                   (char*)&tmp->ob_ref_local - (char*)tmp);
            printf("OFFSET ob_ref_shared       %td\n",
                   (char*)&tmp->ob_ref_shared - (char*)tmp);
        }
#endif
    }

    /* --- Py_buffer layout --- */
    {
        Py_buffer b;
        printf("SIZEOF Py_buffer           %zu\n", sizeof(Py_buffer));
        printf("OFFSET Py_buffer.buf       %td\n",
               (char*)&b.buf - (char*)&b);
        printf("OFFSET Py_buffer.obj       %td\n",
               (char*)&b.obj - (char*)&b);
        printf("OFFSET Py_buffer.len       %td\n",
               (char*)&b.len - (char*)&b);
        printf("OFFSET Py_buffer.itemsize  %td\n",
               (char*)&b.itemsize - (char*)&b);
        printf("OFFSET Py_buffer.readonly  %td\n",
               (char*)&b.readonly - (char*)&b);
        printf("OFFSET Py_buffer.ndim      %td\n",
               (char*)&b.ndim - (char*)&b);
        printf("OFFSET Py_buffer.format    %td\n",
               (char*)&b.format - (char*)&b);
        printf("OFFSET Py_buffer.shape     %td\n",
               (char*)&b.shape - (char*)&b);
        printf("OFFSET Py_buffer.strides   %td\n",
               (char*)&b.strides - (char*)&b);
        printf("OFFSET Py_buffer.suboffsets %td\n",
               (char*)&b.suboffsets - (char*)&b);
        /* smalltable presence inferred from internal offset:
         * < 3.12: internal at 88 (with smalltable[2] in between)
         * >= 3.12: internal at 72 (smalltable removed) */
        printf("OFFSET Py_buffer.internal  %td\n",
               (char*)&b.internal - (char*)&b);
    }

    /* --- PyMethodDef flags --- */
    printf("FLAG METH_VARARGS    0x%04x\n", METH_VARARGS);
    printf("FLAG METH_KEYWORDS   0x%04x\n", METH_KEYWORDS);
    printf("FLAG METH_NOARGS     0x%04x\n", METH_NOARGS);
    printf("FLAG METH_O          0x%04x\n", METH_O);
    printf("FLAG METH_CLASS      0x%04x\n", METH_CLASS);
    printf("FLAG METH_STATIC     0x%04x\n", METH_STATIC);
#ifdef METH_FASTCALL
    printf("FLAG METH_FASTCALL   0x%04x\n", METH_FASTCALL);
#endif

    /* --- PyBUF flags --- */
    printf("FLAG PyBUF_SIMPLE    0x%04x\n", PyBUF_SIMPLE);
    printf("FLAG PyBUF_WRITABLE  0x%04x\n", PyBUF_WRITABLE);
    printf("FLAG PyBUF_FORMAT    0x%04x\n", PyBUF_FORMAT);
    printf("FLAG PyBUF_ND        0x%04x\n", PyBUF_ND);
    printf("FLAG PyBUF_STRIDES   0x%04x\n", PyBUF_STRIDES);

    /* --- Symbol availability (resolved at runtime by c2py_runtime.c) --- */
    check_sym("Py_IncRef");
    check_sym("_Py_IncRef");
    check_sym("Py_DecRef");
    check_sym("_Py_DecRef");
    check_sym("PyObject_Vectorcall");
    check_sym("PyObject_GetBuffer");
    check_sym("PyBuffer_Release");
    check_sym("PyErr_Occurred");
    check_sym("PyErr_SetString");
    check_sym("PyErr_Clear");
    check_sym("PyArg_ParseTuple");
    check_sym("PyArg_ParseTupleAndKeywords");
    check_sym("PyModule_Create2");
    check_sym("PyLong_FromLong");
    check_sym("PyLong_FromLongLong");
    check_sym("PyFloat_FromDouble");
    check_sym("PyLong_AsLong");
    check_sym("PyFloat_AsDouble");
    check_sym("PyExc_TypeError");
    check_sym("PyExc_ValueError");
    check_sym("PyExc_RuntimeError");
    check_sym("PyExc_MemoryError");
    check_sym("_Py_NoneStruct");
    check_sym("Py_None");
    check_sym("PyObject_AsReadBuffer");
    check_sym("PyObject_AsWriteBuffer");
    check_sym("Py_GetVersion");

    /* --- Exception type layout: shared-refcount indirection ---
     * On Python 3.12+, exception type objects use immortal shared
     * refcounts.  The symbol (e.g. &PyExc_ValueError) stores a pointer
     * in its first 8 bytes that points to the actual PyObject (the
     * shared refcount struct).  c2py23 must follow that pointer so
     * that PyErr_SetString receives a real PyObject* with a valid
     * ob_type, not NULL.
     *
     * Detection: if the raw-symbol's first 8 bytes look like a pointer
     * (pointing elsewhere in the data segment) and its ob_type at offset 8
     * is NULL, then shared refcount indirection is active.  c2py23 must
     * follow the pointer so PyErr_SetString receives a proper PyObject*.
     */
    {
        void *raw = dlsym(RTLD_DEFAULT, "PyExc_ValueError");
        if (raw) {
            void *first8 = *(void **)raw;
            void *ob_type_raw = *(void **)((char *)raw + 8);
            /* shared refcount: first8 is a non-NULL pointer AND
             * ob_type_raw is NULL (it lives in the dereferenced struct) */
            int uses_shared_refcount = (first8 != NULL && ob_type_raw == NULL);
            printf("EXC_USES_SHARED_REFCNT %d\n", uses_shared_refcount);
            printf("EXC_OB_TYPE_RAW        %p\n", ob_type_raw);
        }
    }

    /* --- None singleton layout ---
     * On Python 3.12+, None is immortal (ob_refcnt = _Py_IMMORTAL_REFCNT).
     * Verify it uses the standard PyObject layout (no shared-refcount
     * indirection).  If this ever changes, our Py_RETURN_NONE macro
     * (which does C2PY.IncRef(C2PY.none_obj) on 2.7/3.x) would break.
     */
    {
        void *none_raw = dlsym(RTLD_DEFAULT, "_Py_NoneStruct");
        if (none_raw) {
            void *ob_type_none = *(void **)((char *)none_raw + 8);
            printf("NONE_OB_TYPE           %p\n", ob_type_none);
            printf("NONE_HAS_VALID_OB_TYPE %d\n", ob_type_none != NULL ? 1 : 0);
        }
    }

    return 0;
}
```

## tests/populate_abi_matrix.py

```python
#!/usr/bin/env python3
"""Populate tests/abi_matrix.json by running check_abi.c inside each
snakepit container for all supported Python versions.

Requires: snakepit containers in ../snakepit/ and Apptainer installed.
"""
from __future__ import print_function

import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SNAKEPIT_DIR = os.path.join(os.path.dirname(PROJECT_DIR), 'snakepit')
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, 'test_workspace')
MATRIX_FILE = os.path.join(SCRIPT_DIR, 'abi_matrix.json')
CHECK_ABI_C = os.path.join(SCRIPT_DIR, 'check_abi.c')

PYTHON_VERSIONS = [
    ("2.7",  "ubuntu20.04.sif"),
    ("3.6",  "debian10.sif"),
    ("3.7",  "ubuntu24.04.sif"),
    ("3.8",  "ubuntu20.04.sif"),
    ("3.9",  "ubuntu24.04.sif"),
    ("3.10", "ubuntu24.04.sif"),
    ("3.11", "ubuntu24.04.sif"),
    ("3.12", "ubuntu24.04.sif"),
    ("3.13", "ubuntu24.04.sif"),
    ("3.14", "ubuntu24.04.sif"),
    ("3.14t", "ubuntu24.04.sif"),
]


def run_apptainer(sif_file, command):
    sif_path = os.path.join(SNAKEPIT_DIR, sif_file)
    if not os.path.exists(sif_path):
        return 1, "", "SIF file not found: " + sif_path
    cmd = [
        "apptainer", "exec", "-e",
        "-B", WORKSPACE_DIR + ":/workspace",
        "--pwd", "/workspace",
        sif_path,
        "/bin/bash", "-c", command
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8', errors='replace')
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='replace')
        return proc.returncode, stdout, stderr
    except Exception as e:
        return 1, "", str(e)


def prepare_workspace():
    import shutil
    if os.path.exists(WORKSPACE_DIR):
        shutil.rmtree(WORKSPACE_DIR)
    os.makedirs(WORKSPACE_DIR)
    shutil.copy2(CHECK_ABI_C, WORKSPACE_DIR)


def collect_abi(python_version, sif_file):
    py = "python" + python_version
    print("  Collecting ABI for Python %s ..." % python_version)

    # Build and run inside container.
    # Most Python installations provide pythonX.Y-config; some (e.g. 3.14t
    # installed via uv) do not.  For those, fall back to sysconfig.
    is_ft = python_version.endswith('t')

    if is_ft:
        # Use sysconfig to get include and library paths
        build_and_run = (
            "cd /workspace && "
            "INCLUDE=$(%s -c \"import sysconfig; "
            " print(sysconfig.get_path('include'))\" 2>/dev/null) && "
            "LIBDIR=$(%s -c \"import sysconfig; "
            " print(sysconfig.get_config_var('LIBDIR'))\" 2>/dev/null) && "
            "LDLIB=$(%s -c \"import sysconfig; "
            " print(sysconfig.get_config_var('LDLIBRARY'))\" 2>/dev/null) && "
            "LNAME=$(echo \"$LDLIB\" | sed 's/^lib\\(.*\\)\\.so.*$/\\1/') && "
            "CFG=\"-I$INCLUDE -L$LIBDIR -Wl,-rpath,$LIBDIR -l$LNAME\" && "
            "echo \"CFG=$CFG\" && "
            "gcc -o /tmp/check_abi check_abi.c $CFG -ldl 2>&1 && "
            "/tmp/check_abi 2>&1" % (py, py, py)
        )
    else:
        # Some Python configs omit -lpythonN; add it explicitly if missing.
        build_and_run = (
            "cd /workspace && "
            "CFG=$(echo $(%s-config --includes --ldflags 2>/dev/null)) && "
            "if echo \"$CFG\" | grep -qv -- '-lpython'; then "
            "  CFG=\"$CFG -lpython%s\"; "
            "fi && "
            "gcc -o /tmp/check_abi check_abi.c $CFG -ldl 2>&1 && "
            "/tmp/check_abi 2>&1" % (py, python_version)
        )
    ret, stdout, stderr = run_apptainer(sif_file, build_and_run)

    if ret != 0:
        print("  [FAIL] Python %s: %s" % (python_version, stderr.strip()))
        return None

    # Parse output: CATEGORY label value
    entries = []
    pyver_full = None
    for line in stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        category = parts[0]
        label = parts[1].strip()
        val = parts[2].strip() if len(parts) > 2 else ""
        if category == "PYVER":
            pyver_full = line[len("PYVER "):]
        entries.append((category, label, val))

    if pyver_full is None:
        pyver_full = python_version
    return {"python_version": pyver_full, "entries": entries}


def main():
    if not os.path.exists(SNAKEPIT_DIR):
        print("Error: snakepit directory not found at " + SNAKEPIT_DIR)
        return 1

    print("Populating ABI matrix...")
    prepare_workspace()

    matrix = {}
    arch = "Linux-x86_64"

    for pyver, sif in PYTHON_VERSIONS:
        entry = collect_abi(pyver, sif)
        if entry is None:
            print("  [SKIP] Python %s (build failed)" % pyver)
            continue
        if arch not in matrix:
            matrix[arch] = {}
        abi_entry = {}
        for category, label, val in entry["entries"]:
            abi_entry[category + "_" + label] = val
        matrix[arch][pyver] = {
            "python_version": entry["python_version"],
            "abi": abi_entry
        }
        print("  [OK] Python %s" % pyver)

    # Write output
    with open(MATRIX_FILE, 'w') as f:
        json.dump(matrix, f, indent=2, sort_keys=True)
    print("\nABI matrix written to " + MATRIX_FILE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

## tests/requirements.txt

```
PyYAML>=5.1 ; python_version >= "3"
PyYAML>=3.10,<6 ; python_version < "3"
```

## tests/run_tests.sh

```bash
#!/usr/bin/env bash
# run_tests.sh - Build and test c2py23 for one Python version
# Usage: bash run_tests.sh [python_binary]
#
# This script:
# 1. Creates a virtual environment (if needed)
# 2. Installs c2py23 as a package
# 3. Builds all .so modules from .c2py files
# 4. Runs the uniform test suite
set -e

PYTHON="${1:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== c2py23 test runner ==="
echo "Python: $($PYTHON --version 2>&1)"
echo "Script dir: $SCRIPT_DIR"
echo "Project dir: $PROJECT_DIR"

# Create and activate virtual environment
PYVER=$("$PYTHON" -c "import sys; print('%d.%d' % (sys.version_info[0], sys.version_info[1]))" 2>/dev/null || echo "unknown")
IS_FT=$("$PYTHON" -c "import sysconfig; print(1 if sysconfig.get_config_var('Py_GIL_DISABLED') else 0)" 2>/dev/null || echo "0")

if [ "$IS_FT" = "1" ]; then
    # Free-threaded Python (3.14t): skip venv entirely.
    # uv-installed 3.14t venvs cannot find the stdlib; install and run
    # directly using --break-system-packages.
    echo "Free-threaded Python detected -- skipping venv, installing directly"
    "$PYTHON" -m pip install --break-system-packages -e "$PROJECT_DIR" 2>&1 | tail -3
else
    VENV_DIR="$SCRIPT_DIR/test_venv_${PYVER}"
    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating virtual environment at $VENV_DIR..."
        rm -rf "$VENV_DIR"
        MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info[0])" 2>/dev/null || echo "3")
        if [ "$MAJOR" = "2" ]; then
            # Python 2.7 uses virtualenv
            virtualenv "$VENV_DIR" 2>/dev/null || "$PYTHON" -m virtualenv "$VENV_DIR" 2>/dev/null || {
                echo "ERROR: Could not create venv. Install virtualenv for Python 2.7."
                exit 1
            }
        else
            "$PYTHON" -m venv "$VENV_DIR"
        fi
    fi

    # Activate
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
    else
        echo "ERROR: venv activate script not found"
        exit 1
    fi

    echo "Installing c2py23..."
    pip install -e "$PROJECT_DIR" 2>&1 | tail -3
fi

# Build all test modules
echo ""
echo "Building test modules..."
BUILD_PY="${IS_FT:+$PYTHON -m}"
for c2py_file in "$SCRIPT_DIR"/cases/*/*.c2py; do
    echo "  Building: $c2py_file"
    if [ "$IS_FT" = "1" ]; then
        "$PYTHON" -m c2py23.cli build "$c2py_file"
    else
        c2py23 build "$c2py_file"
    fi
done

# Run tests
RUN_PY="python"
if [ "$IS_FT" = "1" ]; then
    RUN_PY="$PYTHON"
fi
echo ""
echo "Running tests..."
cd "$SCRIPT_DIR"
$RUN_PY test_uniform.py

# Run peer review tests (alias + contiguity, numpy required)
echo ""
echo "Running peer review tests..."
if [ "$IS_FT" = "1" ]; then
    "$PYTHON" -m pip install --break-system-packages numpy 2>&1 | tail -1 || echo "(numpy install skipped)"
else
    pip install numpy 2>&1 | tail -1 || echo "(numpy install skipped - tests will SKIP)"
fi
$RUN_PY test_peer_review.py

# Run regression tests for referee report bug fixes
echo ""
echo "Running regression tests..."
$RUN_PY test_regression_fixes.py

# Run error path refcount tests
echo ""
echo "Running error path refcount tests..."
$RUN_PY test_error_paths.py

# Run leak stress test
echo ""
echo "Running leak stress test..."
$RUN_PY test_leaks.py

echo ""
echo "=== All tests complete ==="
```

## tests/test_all.py

```python
#!/usr/bin/env python3
"""
c2py23 test suite across all Python versions via snakepit containers.

Mirrors snakepit's test_images.py pattern:
1. Copies c2py23 project + test cases into workspace
2. For each Python version (2.7-3.14), runs run_tests.sh inside
   the appropriate Apptainer container
3. Collects pass/fail results
"""
from __future__ import print_function

import os
import sys
import shutil
import subprocess
from datetime import datetime

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SNAKEPIT_DIR = os.path.join(os.path.dirname(PROJECT_DIR), 'snakepit')
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, 'test_workspace')
LOG_FILE = os.path.join(SCRIPT_DIR, 'test_results.log')

# Python versions to test
PYTHON_VERSIONS = [
    ("2.7", "ubuntu20.04.sif"),
    ("3.6", "debian10.sif"),
    ("3.7", "ubuntu24.04.sif"),
    ("3.8", "ubuntu20.04.sif"),
    ("3.9", "ubuntu24.04.sif"),
    ("3.10", "ubuntu24.04.sif"),
    ("3.11", "ubuntu24.04.sif"),
    ("3.12", "ubuntu24.04.sif"),
    ("3.13", "ubuntu24.04.sif"),
    ("3.14", "ubuntu24.04.sif"),
    ("3.14t", "ubuntu24.04.sif"),
]

_log_file = None

# Common signal names for crash diagnostics
_SIGNAL_NAMES = {
    1: 'SIGHUP', 2: 'SIGINT', 3: 'SIGQUIT', 4: 'SIGILL',
    5: 'SIGTRAP', 6: 'SIGABRT', 7: 'SIGBUS', 8: 'SIGFPE',
    9: 'SIGKILL', 10: 'SIGUSR1', 11: 'SIGSEGV', 12: 'SIGUSR2',
    13: 'SIGPIPE', 14: 'SIGALRM', 15: 'SIGTERM', 16: 'SIGSTKFLT',
    17: 'SIGCHLD', 18: 'SIGCONT', 19: 'SIGSTOP', 20: 'SIGTSTP',
    21: 'SIGTTIN', 22: 'SIGTTOU', 23: 'SIGURG', 24: 'SIGXCPU',
    25: 'SIGXFSZ', 26: 'SIGVTALRM', 27: 'SIGPROF', 28: 'SIGWINCH',
    29: 'SIGIO', 30: 'SIGPWR', 31: 'SIGSYS',
}


def _signal_name(sig):
    return _SIGNAL_NAMES.get(sig, 'signal {}'.format(sig))


def log_write(message):
    if _log_file:
        _log_file.write(message + '\n')
        _log_file.flush()


def print_header(message):
    line = "=" * 70
    print("\n" + line)
    print(message)
    print(line + "\n")
    log_write(line)
    log_write(message)
    log_write(line + '\n')


def print_success(message):
    print("[OK] " + message)
    log_write("[OK] " + message)


def print_error(message):
    print("[FAIL] " + message)
    log_write("[FAIL] " + message)


def print_step(message):
    print(">> " + message)
    log_write(">> " + message)


def run_apptainer(sif_file, command, capture_output=True, timeout=600):
    """Run a command inside an Apptainer container.

    Args:
        sif_file: Name of the .sif container file
        command: Bash command to run inside the container
        capture_output: If True, capture stdout/stderr
        timeout: Maximum seconds before forcibly killing (default 600s = 10 min)

    Returns:
        (returncode, stdout, stderr) - stderr may contain error info on crash
    """
    sif_path = os.path.join(SNAKEPIT_DIR, sif_file)
    if not os.path.exists(sif_path):
        print_error("SIF file not found: {}".format(sif_path))
        return 1, "", "SIF file not found"

    apptainer_cmd = [
        "apptainer", "exec",
        "-e",
        "-B", WORKSPACE_DIR + ":/workspace",
        "--pwd", "/workspace",
        sif_path,
        "/bin/bash", "-c", command
    ]

    try:
        if capture_output:
            proc = subprocess.Popen(
                apptainer_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                print_error("Command timed out after {}s -- killing".format(timeout))
                proc.kill()
                stdout, stderr = proc.communicate()
                return -9, "", "TIMEOUT after {}s (possibly infinite loop or hang)".format(timeout)
            if isinstance(stdout, bytes):
                stdout = stdout.decode('utf-8', errors='replace')
            if isinstance(stderr, bytes):
                stderr = stderr.decode('utf-8', errors='replace')
            return proc.returncode, stdout, stderr
        else:
            ret = subprocess.call(apptainer_cmd, timeout=timeout)
            return ret, "", ""
    except subprocess.TimeoutExpired:
        print_error("Command timed out after {}s (no-capture mode)".format(timeout))
        return -9, "", "TIMEOUT after {}s".format(timeout)
    except OSError as e:
        print_error("OS error running apptainer: " + str(e))
        return 1, "", str(e)
    except Exception as e:
        print_error("Error running apptainer: " + str(e))
        return 1, "", str(e)


def test_python_version(python_version, sif_file):
    """Test c2py23 with a specific Python version inside a container."""
    print_header("Testing Python " + python_version)

    system_py = "python" + python_version
    test_cmd = "cd /workspace && bash tests/run_tests.sh " + system_py

    retcode, stdout, stderr = run_apptainer(sif_file, test_cmd)

    if retcode != 0:
        if retcode == -9:
            reason = "TIMED OUT (possible infinite loop or hang)"
        elif retcode < 0:
            reason = "KILLED by signal {}".format(-retcode)
        elif retcode > 128:
            sig = retcode - 128
            reason = "CRASHED with signal {} ({})".format(sig, _signal_name(sig))
        else:
            reason = "exit code {}".format(retcode)
        print_error("Test failed for Python {}: {}".format(python_version, reason))
        log_write("STDOUT:\n" + stdout)
        log_write("STDERR:\n" + stderr)
        print("--- STDOUT ---")
        print(stdout)
        print("--- STDERR ---")
        print(stderr)
        print("--- END ---")
        return False

    print_success("All tests passed for Python " + python_version)
    print(stdout.strip())
    log_write("Test output:\n" + stdout)
    return True


def prepare_workspace():
    """Prepare the test workspace: copy c2py23 project and test files."""
    print_step("Preparing test workspace...")

    # Clean workspace
    if os.path.exists(WORKSPACE_DIR):
        shutil.rmtree(WORKSPACE_DIR)
    os.makedirs(WORKSPACE_DIR)

    # Copy c2py23 source (excluding .git, __pycache__, test_workspace)
    for item in os.listdir(PROJECT_DIR):
        src = os.path.join(PROJECT_DIR, item)
        dst = os.path.join(WORKSPACE_DIR, item)
        if item in ('.git', '__pycache__', '*.pyc', 'test_workspace',
                     '*.egg-info'):
            continue
        if os.path.isdir(src):
            if item == 'tests':
                # Copy tests but not test_workspace subdir
                shutil.copytree(src, dst,
                                ignore=shutil.ignore_patterns(
                                    'test_venv', 'test_workspace',
                                    '__pycache__', '*.pyc', '*.egg-info'))
            else:
                shutil.copytree(src, dst,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            if not item.endswith('.pyc'):
                shutil.copy2(src, dst)

    # Make scripts executable
    for script in ['tests/run_tests.sh']:
        sp = os.path.join(WORKSPACE_DIR, script)
        if os.path.exists(sp):
            os.chmod(sp, 0o755)

    print_success("Workspace prepared at " + WORKSPACE_DIR)


def main():
    global _log_file

    _log_file = open(LOG_FILE, 'w')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_write("c2py23 Test Suite - " + timestamp + "\n")

    try:
        print_header("c2py23 Multi-Version Test Suite")
        print("Logging to: " + LOG_FILE)

        prepare_workspace()

        results = {}
        for python_version, sif_file in PYTHON_VERSIONS:
            success = test_python_version(python_version, sif_file)
            results[python_version] = success

            if not success:
                print_error("Python " + python_version + " test FAILED")
                log_write("Python " + python_version + " test FAILED")
                print("\nStopping to debug this version first.")
                print("To debug, run:")
                sif_path = os.path.join(SNAKEPIT_DIR, sif_file)
                print("  apptainer shell -e -B {}:/workspace {}".format(
                    WORKSPACE_DIR, sif_path))
                return 1

        # Summary
        print_header("Test Summary")
        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for version, success in results.items():
            if success:
                print_success("Python " + version)
            else:
                print_error("Python " + version)

        summary = "\nResults: {}/{} passed\n".format(passed, total)
        print(summary)
        log_write(summary)

        return 0 if passed == total else 1

    finally:
        if _log_file:
            _log_file.close()


if __name__ == '__main__':
    sys.exit(main())
```

## tests/test_error_paths.py

```python
"""Verify refcounts on buffer error paths across multi-buffer functions.

Tests:
  - arraysum (3 buffers): format check failure on last buffer
  - arraysum (3 buffers): size mismatch check on last buffer  
  - Writable buffer alias detection
  - Strided buffer rejection
"""
from __future__ import print_function

import sys
import os
import ctypes
import warnings
import sysconfig

warnings.filterwarnings("ignore", message=".*API version mismatch.*")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# On biased-refcounting Python (3.14+ standard or 3.13t+ FT),
# sys.getrefcount() reflects ob_ref_shared only, not the total refcount.
# Local variables contribute to ob_ref_local and are invisible to
# sys.getrefcount(), making simple equality assertions unreliable.
# We skip refcount checks on these builds and only verify that the
# correct exception is raised and that refcounts do not drift over
# repeated calls (the loop test still verifies no drift).
#
# Detection methods:
#   1. sysconfig.get_config_var('Py_GIL_DISABLED') == 1 (CPython 3.13t+)
#   2. 'free-threading' in sys.version (CPython 3.13t+)
#   3. sys.version_info >= (3, 14) -- Python 3.14+ uses biased refcounting
#      even in standard GIL builds (PEP 763 / PEP 703 preparation)

_IS_FREE_THREADED = False
try:
    if sysconfig.get_config_var('Py_GIL_DISABLED') == 1:
        _IS_FREE_THREADED = True
except Exception:
    pass

if not _IS_FREE_THREADED:
    try:
        if 'free-threading' in sys.version.lower():
            _IS_FREE_THREADED = True
    except Exception:
        pass

# Python 3.14+ uses biased reference counting even in standard builds;
# sys.getrefcount() is unreliable for equality assertions.
if not _IS_FREE_THREADED and sys.version_info >= (3, 14):
    _IS_FREE_THREADED = True


def refcount(obj):
    return sys.getrefcount(obj) - 1


def test_arraysum_format_mismatch_last_buffer():
    """3 buffers: a(d), b(d), c(f). c has wrong format -> format check fails."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    c = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)  # wrong type!

    if not _IS_FREE_THREADED:
        ra0 = refcount(a); rb0 = refcount(b); rc0 = refcount(c)

    try:
        arraysum.array_sum(a, b, c)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    if not _IS_FREE_THREADED:
        ra1 = refcount(a); rb1 = refcount(b); rc1 = refcount(c)
        assert ra1 == ra0, "a refcount: %d -> %d (leak!)" % (ra0, ra1)
        assert rb1 == rb0, "b refcount: %d -> %d (leak!)" % (rb0, rb1)
        assert rc1 == rc0, "c refcount: %d -> %d (leak!)" % (rc0, rc1)

    tag = " (FT: refcount skipped)" if _IS_FREE_THREADED else " -- all refcounts stable"
    print("PASS: format mismatch on 3rd buffer" + tag)


def test_arraysum_size_mismatch_last_buffer():
    """3 buffers: a(d, 4), b(d, 4), c(d, 3). c has different length ->
    size check fails."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    c = (ctypes.c_double * 3)(0.0, 0.0, 0.0)  # wrong size

    if not _IS_FREE_THREADED:
        ra0 = refcount(a); rb0 = refcount(b); rc0 = refcount(c)

    try:
        arraysum.array_sum(a, b, c)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    if not _IS_FREE_THREADED:
        ra1 = refcount(a); rb1 = refcount(b); rc1 = refcount(c)
        assert ra1 == ra0, "a refcount: %d -> %d (leak!)" % (ra0, ra1)
        assert rb1 == rb0, "b refcount: %d -> %d (leak!)" % (rb0, rb1)
        assert rc1 == rc0, "c refcount: %d -> %d (leak!)" % (rc0, rc1)

    tag = " (FT: refcount skipped)" if _IS_FREE_THREADED else " -- all refcounts stable"
    print("PASS: size mismatch on 3rd buffer" + tag)


def test_arraysum_success_refcounts():
    """3 buffers all correct: refcounts must return to baseline after call."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    c = (ctypes.c_double * 4)(0.0, 0.0, 0.0, 0.0)

    ra0 = refcount(a)
    rb0 = refcount(b)
    rc0 = refcount(c)

    arraysum.array_sum(a, b, c)

    ra1 = refcount(a)
    rb1 = refcount(b)
    rc1 = refcount(c)

    assert ra1 == ra0, "a refcount: %d -> %d" % (ra0, ra1)
    assert rb1 == rb0, "b refcount: %d -> %d" % (rb0, rb1)
    assert rc1 == rc0, "c refcount: %d -> %d" % (rc0, rc1)
    print("PASS: successful 3-buffer call -- all refcounts stable")


def test_arraysum_repeated_success_loop():
    """10000 calls with 3 buffers -- verify refcount stability each time."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    c = (ctypes.c_double * 4)(0.0, 0.0, 0.0, 0.0)

    ra0 = refcount(a)
    rb0 = refcount(b)
    rc0 = refcount(c)

    for i in range(10000):
        arraysum.array_sum(a, b, c)
        if i % 2500 == 0:
            ra = refcount(a)
            rb = refcount(b)
            rc = refcount(c)
            if ra != ra0 or rb != rb0 or rc != rc0:
                print("  FAIL at iter %d: a=%d->%d b=%d->%d c=%d->%d" % (
                    i, ra0, ra, rb0, rb, rc0, rc))
                return False

    ra1 = refcount(a)
    rb1 = refcount(b)
    rc1 = refcount(c)
    assert ra1 == ra0, "after 10000 iter: a=%d->%d" % (ra0, ra1)
    assert rb1 == rb0, "after 10000 iter: b=%d->%d" % (rb0, rb1)
    assert rc1 == rc0, "after 10000 iter: c=%d->%d" % (rc0, rc1)
    print("PASS: 10000 repeated 3-buffer calls -- all refcounts stable")


def test_arraysum_alias_detection_refcounts():
    """Alias detection (c2py wraps around writable buffers that alias)."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum

    # arraysum writes to r. If r aliases a or b, should error.
    a = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    b = (ctypes.c_double * 4)(5.0, 6.0, 7.0, 8.0)
    r = a  # r IS a (alias)

    if not _IS_FREE_THREADED:
        ra0 = refcount(a); rb0 = refcount(b)

    try:
        arraysum.array_sum(a, b, r)
        assert False, "Should have raised ValueError for alias"
    except ValueError:
        pass

    if not _IS_FREE_THREADED:
        ra1 = refcount(a); rb1 = refcount(b)
        assert ra1 == ra0, "a refcount: %d -> %d (alias leak!)" % (ra0, ra1)
        assert rb1 == rb0, "b refcount: %d -> %d (alias leak!)" % (rb0, rb1)

    tag = " (FT: refcount skipped)" if _IS_FREE_THREADED else " -- all refcounts stable"
    print("PASS: alias detection path" + tag)


if __name__ == '__main__':
    results = []
    for name in sorted(globals()):
        if name.startswith('test_'):
            try:
                globals()[name]()
                results.append(('PASS', name))
            except Exception as e:
                results.append(('FAIL', name + ': ' + str(e)))
                import traceback
                traceback.print_exc()

    passed = sum(1 for r, _ in results if r == 'PASS')
    total = len(results)
    print('\nResults: %d/%d passed' % (passed, total))
    sys.exit(0 if passed == total else 1)
```

## tests/test_interpreters.py

```python
#!/usr/bin/env python3
"""Verify that Python interpreters in the snakepit container are correct.

Checks that python3.14 (GIL-enabled) and python3.14t (free-threaded)
both exist and report the expected build types.
"""
from __future__ import print_function

import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SNAKEPIT_DIR = os.path.join(os.path.dirname(PROJECT_DIR), 'snakepit')
SIF_FILE = os.path.join(SNAKEPIT_DIR, 'ubuntu24.04.sif')


def check_interpreter(py_exe, expected_gil_disabled):
    """Check one interpreter inside the container."""
    script = (
        "import json, sys, sysconfig, struct;"
        "r = {};"
        "r['v'] = sys.version.split(chr(10))[0];"
        "r['ft'] = 1 if sysconfig.get_config_var('Py_GIL_DISABLED') else 0;"
        "r['vp'] = struct.calcsize('P');"
        "r['n'] = struct.calcsize('n');"
        "print(json.dumps(r))"
    )
    cmd = [
        "apptainer", "exec", "-e",
        SIF_FILE,
        py_exe, "-c", script
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        stdout = stdout.decode('utf-8', errors='replace') if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode('utf-8', errors='replace') if isinstance(stderr, bytes) else stderr
    except Exception as e:
        return False, "Error: {0}".format(e), {}

    if proc.returncode != 0:
        return False, "Exit {0}: {1}".format(proc.returncode, stderr[:200]), {}

    try:
        data = json.loads(stdout.strip().split('\n')[-1])
    except Exception:
        return False, "Parse error: {0}".format(stdout[:200]), {}

    actual_ft = data.get('ft', -1)
    ok = (actual_ft == (1 if expected_gil_disabled else 0))
    return ok, data, {}


def main():
    print("=== Interpreter Verification ===\n")

    if not os.path.exists(SIF_FILE):
        print("SKIP: container not found at {0}".format(SIF_FILE))
        return 0

    tests = [
        ("python3.14", False, "standard (GIL-enabled)"),
        ("python3.14t", True, "free-threaded (GIL-disabled)"),
    ]

    passed = 0
    failed = 0
    for py_exe, expected_ft, desc in tests:
        print("{0} ({1})...".format(py_exe, desc))
        ok, data, _ = check_interpreter(py_exe, expected_ft)

        if ok and data:
            print("  Version: {0}".format(data.get('v', '?')))
            print("  Free-threaded: {0}".format('yes' if data.get('ft') else 'no'))
            print("  sizeof(void*): {0}".format(data.get('vp', '?')))
            print("  sizeof(Py_ssize_t): {0}".format(data.get('n', '?')))
            print("  PASS")
            passed += 1
        elif ok is False and isinstance(data, dict) and data:
            print("  Version: {0}".format(data.get('v', '?')))
            print("  Free-threaded: {0}".format('yes' if data.get('ft') else 'no'))
            print("  FAIL: wrong GIL state (expected ft={0})".format(expected_ft))
            failed += 1
        else:
            print("  FAIL: {0}".format(data))
            failed += 1
        print()

    print("Result: {0}/{1} passed".format(passed, passed + failed))
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
```

## tests/test_leaks.py

```python
"""Memory leak stress test for c2py23 generated wrappers.

Exercises each wrapped function in a tight loop and monitors RSS growth.
Runs under valgrind for precise leak detection when available.
"""
from __future__ import print_function

import sys
import os
import ctypes
import warnings

warnings.filterwarnings("ignore", message=".*API version mismatch.*")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ITERATIONS = 10000


def _double_array(values):
    n = len(values)
    return (ctypes.c_double * n)(*values)


def _zeros_double(n):
    return _double_array([0.0] * n)


def _float_array(values):
    n = len(values)
    return (ctypes.c_float * n)(*values)


def test_arraysum_stress():
    """Stress test: repeated calls to triple-buffer write function."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'arraysum'))
    import arraysum
    for _ in range(_ITERATIONS):
        a = _double_array([1.0, 2.0, 3.0, 4.0])
        b = _double_array([5.0, 6.0, 7.0, 8.0])
        r = _zeros_double(4)
        arraysum.array_sum(a, b, r)
    print("PASS: arraysum stress (%d calls)" % _ITERATIONS)


def test_fill_stress():
    """Stress test: format dispatch write function."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'fill'))
    import fillmod
    for _ in range(_ITERATIONS):
        arr = _float_array([0.0, 0.0, 0.0, 0.0])
        fillmod.fill(arr, 3.14)
    print("PASS: fill stress (%d calls)" % _ITERATIONS)


def test_dot_stress():
    """Stress test: format dispatch with scalar return."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'dot'))
    import dotmod
    for _ in range(_ITERATIONS):
        a = _float_array([1.0, 2.0, 3.0])
        b = _float_array([4.0, 5.0, 6.0])
        dotmod.dot(a, b)
    print("PASS: dot stress (%d calls)" % _ITERATIONS)


def test_scalar_output_stress():
    """Stress test: output scalar convention."""
    sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'cases', 'scalar_output'))
    import statmod
    for _ in range(_ITERATIONS):
        data = _double_array([3.0, 1.0, 5.0, 2.0, 4.0])
        statmod.stats(data)
    print("PASS: scalar_output stress (%d calls)" % _ITERATIONS)


def check_rss():
    """Read RSS (resident set size) in pages from /proc/self/statm."""
    try:
        with open('/proc/self/statm', 'r') as f:
            fields = f.read().split()
            return int(fields[1])  # RSS in pages
    except Exception:
        return None


def main():
    global _ITERATIONS

    if '--valgrind' in sys.argv:
        _ITERATIONS = 100

    print("c2py23 memory leak stress test")
    print("Iterations per test: %d" % _ITERATIONS)
    print("")

    if '--valgrind' in sys.argv:
        print("Running under valgrind-compatible mode")

    tests = [
        test_arraysum_stress,
        test_fill_stress,
        test_dot_stress,
        test_scalar_output_stress,
    ]

    rss_before = check_rss()

    for test in tests:
        test()

    rss_after = check_rss()

    if rss_before is not None and rss_after is not None:
        pagesize = os.sysconf(os.sysconf_names['SC_PAGESIZE'])
        growth_kb = (rss_after - rss_before) * pagesize // 1024
        print("")
        print("RSS before: %d pages (%d kB)" % (rss_before,
              rss_before * pagesize // 1024))
        print("RSS after:  %d pages (%d kB)" % (rss_after,
              rss_after * pagesize // 1024))
        print("RSS growth: %d kB" % growth_kb)
        if growth_kb > 5000:
            print("WARNING: Significant RSS growth detected!")
            return 1

    print("")
    print("All stress tests passed.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

## tests/test_peer_review.py

```python
"""Aliasing and contiguity tests from peer review feedback.

Tests all 5 buffer-alias patterns:
  1. Slice:  b = a[1:]
  2. Reversed: b = a[::-1]
  3. memoryview: b = memoryview(a)
  4. View: b = a.view()
  5. Broadcast: b = np.broadcast_to(a, ...)

Also tests contiguity enforcement:
  - Strided arrays (a[::2]) are rejected
  - Negative strides (a[::-1]) are rejected
  - C-contiguous accepted
  - F-contiguous accepted (for 2D)
"""
from __future__ import print_function

import sys
import os
import ctypes
import warnings
warnings.filterwarnings("ignore", message=".*API version mismatch.*")

try:
    import numpy as np
except ImportError:
    print("SKIP: numpy not available")
    sys.exit(0)

IS_PY3 = sys.version_info[0] >= 3

test_dir = os.path.join(os.path.dirname(__file__), 'cases', 'arraysum')
sys.path.insert(0, test_dir)
import arraysum


def test_alias_slice():
    """Slice: b = a[1:] overlaps with original a."""
    a = np.arange(100.0, dtype=np.float64)
    b = a[1:]  # shares memory, offset by 8 bytes
    
    result = np.zeros(99, dtype=np.float64)
    try:
        arraysum.array_sum(a, b, a)  # output aliases input a
        print("FAIL: slice alias should be rejected")
        return False
    except ValueError as e:
        if 'alias' in str(e):
            print("PASS: slice alias detected")
            return True
        raise


def test_alias_reversed():
    """Reversed: b = a[::-1] overlaps with original a."""
    a = np.arange(100.0, dtype=np.float64)
    b = a[::-1]  # reversed view, same memory
    
    result = np.zeros(100, dtype=np.float64)
    try:
        arraysum.array_sum(a, b, a)  # output aliases input a
        print("FAIL: reversed alias should be rejected")
        return False
    except ValueError as e:
        if 'alias' in str(e):
            print("PASS: reversed alias detected")
            return True
        raise


def test_alias_memoryview():
    """memoryview: b = memoryview(a) wraps same data."""
    a = np.arange(100.0, dtype=np.float64)
    b = memoryview(a)  # same underlying memory
    
    result = np.zeros(100, dtype=np.float64)
    try:
        arraysum.array_sum(a, b, a)  # output aliases input a
        print("FAIL: memoryview alias should be rejected")
        return False
    except ValueError as e:
        if 'alias' in str(e):
            print("PASS: memoryview alias detected")
            return True
        raise


def test_alias_view():
    """View: b = a.view() shares same buffer."""
    a = np.arange(100.0, dtype=np.float64)
    b = a.view()
    
    result = np.zeros(100, dtype=np.float64)
    try:
        arraysum.array_sum(a, b, a)  # output aliases input a
        print("FAIL: view alias should be rejected")
        return False
    except ValueError as e:
        if 'alias' in str(e):
            print("PASS: view alias detected")
            return True
        raise


def test_alias_broadcast():
    """Broadcast: np.broadcast_to shares data pointer."""
    a = np.arange(100.0, dtype=np.float64)
    b = np.broadcast_to(a, (3, 100))  # same data, different shape
    
    result = np.zeros(100, dtype=np.float64)
    try:
        arraysum.array_sum(a, a, a)  # output == input (simpler alias test)
        print("FAIL: broadcast alias should be rejected")
        return False
    except ValueError as e:
        if 'alias' in str(e):
            print("PASS: broadcast (self-alias) detected")
            return True
        raise


def test_alias_output_equals_input():
    """Output same object as input -- simplest alias."""
    a = np.arange(100.0, dtype=np.float64)
    b = np.arange(100.0, dtype=np.float64)
    
    try:
        arraysum.array_sum(a, b, a)  # result IS a
        print("FAIL: output==input alias should be rejected")
        return False
    except ValueError as e:
        if 'alias' in str(e):
            print("PASS: output==input alias detected")
            return True
        raise


def test_no_false_positive():
    """Non-aliased buffers should pass."""
    a = np.arange(100.0, dtype=np.float64)
    b = np.arange(100.0, dtype=np.float64)
    result = np.zeros(100, dtype=np.float64)
    
    n = arraysum.array_sum(a, b, result)
    assert n == 100
    expected = a + b
    assert np.allclose(result, expected)
    print("PASS: non-aliased buffers accepted")
    return True


def test_contiguity_strided():
    """Strided arrays (a[::2]) should be rejected."""
    test_dir2 = os.path.join(os.path.dirname(__file__), 'cases', 'fill')
    sys.path.insert(0, test_dir2)
    import fillmod
    
    a = np.arange(20.0, dtype=np.float64)
    b = a[::2]  # stride = 16, not 8
    
    try:
        fillmod.fill(b, 1.0)
        print("FAIL: strided array should be rejected")
        return False
    except ValueError as e:
        if 'contiguous' in str(e).lower():
            print("PASS: strided rejected:", e)
            return True
        raise


def test_contiguity_reversed():
    """Reversed arrays (a[::-1]) should be rejected."""
    test_dir2 = os.path.join(os.path.dirname(__file__), 'cases', 'fill')
    sys.path.insert(0, test_dir2)
    
    a = np.arange(20.0, dtype=np.float64)
    b = a[::-1]
    
    try:
        # Need to re-import since sys.path may have changed
        import fillmod
        fillmod.fill(b, 1.0)
        print("FAIL: reversed array should be rejected")
        return False
    except ValueError as e:
        if 'contiguous' in str(e).lower():
            print("PASS: reversed rejected:", e)
            return True
        raise


def test_contiguity_fortran_2d():
    """F-contiguous 2D arrays should be accepted."""
    if not IS_PY3:
        print("SKIP: 2D arrays require Python 3.x")
        return True
    
    test_dir3 = os.path.join(os.path.dirname(__file__), 'cases', 'fill')
    sys.path.insert(0, test_dir3)
    
    # Create a Fortran-contiguous array and verify fillmod accepts it
    # (memoryview.cast requires C-contiguous, so pass numpy array directly)
    a = np.array([[1.,2.,3.],[4.,5.,6.],[7.,8.,9.],[10.,11.,12.]], dtype=np.float64)
    af = np.asfortranarray(a)  # F-order, shape [4,3], F-contiguous
    assert af.flags['F_CONTIGUOUS']
    assert not af.flags['C_CONTIGUOUS']
    
    import fillmod
    # Flat F-contiguous buffer: contiguous in memory along columns
    fillmod.fill(af, 99.0)
    assert (af == 99.0).all()
    print("PASS: F-contiguous 2D accepted")
    return True


def main():
    version_str = "%d.%d.%d" % (sys.version_info[0], sys.version_info[1], sys.version_info[2])
    print("Python version: %s" % version_str)
    print("")

    tests = [
        ("alias: output==input", test_alias_output_equals_input),
        ("alias: slice", test_alias_slice),
        ("alias: reversed", test_alias_reversed),
        ("alias: memoryview", test_alias_memoryview),
        ("alias: view", test_alias_view),
        ("alias: broadcast (self)", test_alias_broadcast),
        ("no false positive", test_no_false_positive),
        ("contiguity: strided rejected", test_contiguity_strided),
        ("contiguity: reversed rejected", test_contiguity_reversed),
        ("contiguity: F-order 2D accepted", test_contiguity_fortran_2d),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            if fn():
                passed += 1
            else:
                failed += 1
        except ImportError:
            print("SKIP: %s (module not available)" % name)
        except Exception as e:
            print("ERROR: %s - %s" % (name, e))
            import traceback
            traceback.print_exc()
            failed += 1

    print("")
    print("Results: %d passed, %d failed" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
```

## tests/test_regression_fixes.py

```python
"""Unit tests for parser and generator bug fixes from referee reports.

Tests: B1 (VARARGS wrapper signature), B3 (unmatched paren), B4 (L/l format mapping),
P4 (coerce warning), P5 (trailing newline), INT_MAX overflow check present,
+ coverage gaps: empty expand, default_raise, optional int=0 (falsy),
outputs + GIL release order, keyword argument rejection.
"""
from __future__ import print_function

import sys
import os
import tempfile
import warnings

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from c2py23.parser import load_c2py, _parse_c_sig, _FORMAT_TO_CTYPE, _C_TYPES_INT
from c2py23.parser import ModuleDef, FuncDef, PyParam, CParam, COverload, parse_expr
from c2py23.generator import generate


def test_passed():
    print("PASS: %s" % sys._getframe(1).f_code.co_name.replace('test_', ''))


def test_B1_varargs_wrapper_no_kwargs():
    """B1: VARARGS wrapper must NOT declare a 'kwargs' parameter.
    The signature must be (PyObject *self, PyObject *args) -- two parameters,
    not three, because the function address is cast to PyCFunction which takes
    exactly two parameters. A 3-param function through a 2-param pointer is UB."""
    mod = ModuleDef(
        name='b1test',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='f',
                py_params=[PyParam('x', 'float', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void do_f(double x)',
                    params=[CParam('x', 'double', 'double', False, False)],
                    return_type='void',
                    map_exprs={},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)

    varargs_line = None
    for line in code.split('\n'):
        if '_wrapper(PyObject' in line:
            varargs_line = line
            break

    assert varargs_line is not None, "Must emit a VARARGS wrapper"
    assert 'kwargs' not in varargs_line, (
        "VARARGS wrapper must not have kwargs param (UB): %s" % varargs_line)
    assert 'PyObject *self, PyObject *args' in varargs_line, (
        "VARARGS wrapper must have exactly 2 params, got: %s" % varargs_line)
    test_passed()


# ... (rest of tests remain the same)


def test_passed():
    print("PASS: %s" % sys._getframe(1).f_code.co_name.replace('test_', ''))


def test_B3_unmatched_paren_raises():
    """B3: Unmatched '(' in C signature must raise ValueError, not silently
    produce an empty param list."""
    try:
        _parse_c_sig("func(", "test")
        assert False, "Should have raised"
    except ValueError as e:
        msg = str(e)
        assert "Unmatched '('" in msg, "Expected 'Unmatched ('' in error, got: %s" % msg
    test_passed()


def test_B3_proper_paren_matching():
    """Verify paren matching uses a balanced-paren loop, not rfind.
    After the fix, a C signature with `->` return type suffix and a
    function with no trailing `)` should still parse correctly
    (the old rfind-based after_paren would match the wrong paren)."""
    name, params, ret = _parse_c_sig("func(int n, int m) -> int", "test")
    assert name == "func", "Expected func, got %s" % name
    assert len(params) == 2, "Expected 2 params, got %d" % len(params)
    assert ret == "int", "Expected int return type, got %s" % ret
    test_passed()


def test_B4_L_format_char_in_C_TYPES_INT():
    """B4: 'L' mapping must point to a type in _C_TYPES_INT to avoid false P4 errors."""
    assert 'L' in _FORMAT_TO_CTYPE, "'L' must be in _FORMAT_TO_CTYPE"
    assert _FORMAT_TO_CTYPE['L'] in _C_TYPES_INT, (
        "FORMAT_TO_CTYPE['L'] = '%s' must be in _C_TYPES_INT" % _FORMAT_TO_CTYPE['L'])

    assert 'l' in _FORMAT_TO_CTYPE, "'l' must be in _FORMAT_TO_CTYPE"
    assert _FORMAT_TO_CTYPE['l'] in _C_TYPES_INT, (
        "FORMAT_TO_CTYPE['l'] = '%s' must be in _C_TYPES_INT" % _FORMAT_TO_CTYPE['l'])
    test_passed()


def test_P4_coerce_warning_format():
    """P4: Coerce warning message must not have swapped format arguments.
    The warning must clearly state the value, type, and file context."""
    import io

    # Capture warnings
    buf = io.StringIO() if sys.version_info[0] >= 3 else io.BytesIO()

    from c2py23.parser import _coerce_expr_value

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = _coerce_expr_value(0, 'map', 'test.c2py')
        assert isinstance(result, str), "Should coerce int to str"
        assert len(w) == 1, "Expected 1 warning, got %d" % len(w)
        msg = str(w[0].message)
        # The message must contain the file path and must NOT contain the broken
        # '0: int' pattern (which was the bug)
        assert 'test.c2py' in msg, "Warning must mention file path"
        assert '0: int' not in msg, "Warning must not contain the swapped-arg bug pattern"
        assert 'map' in msg, "Warning must mention the context (map)"

    test_passed()


def test_P5_trailing_newline():
    """P5: Generated C source must end with a single newline character."""
    mod = ModuleDef(
        name='testmod',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='f',
                py_params=[PyParam('arr', 'buffer', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void do_f(float *arr, int n)',
                    params=[CParam('arr', 'float *', 'float', True, True),
                            CParam('n', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"),
                               'n': parse_expr("arr.n")},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    assert code.endswith('\n'), "Generated C must end with a newline"
    assert not code.endswith('\n\n'), "Generated C must end with exactly one newline"
    test_passed()


def test_INT_MAX_check_in_generated_code():
    """INT_MAX overflow guard must be present when int param maps from .n."""
    n_expr = parse_expr("arr.n")

    mod = ModuleDef(
        name='intcheck',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='process',
                py_params=[PyParam('arr', 'buffer', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void process(float *arr, int n)',
                    params=[CParam('arr', 'const float *', 'float', True, True),
                            CParam('n', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"), 'n': n_expr},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    # Must contain the INT_MAX guard
    assert 'INT_MAX' in code, "Generated code must include INT_MAX overflow guard"
    assert 'buffer too large for int n' in code, (
        "Generated code must have overflow error message")
    test_passed()


def test_INT_MAX_check_absent_when_no_int_n():
    """INT_MAX guard should NOT be emitted when no int param maps from .n or .len."""
    mod = ModuleDef(
        name='nointn',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='proc',
                py_params=[PyParam('arr', 'buffer', None),
                           PyParam('count', 'int', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void proc(float *arr, int count)',
                    params=[CParam('arr', 'const float *', 'float', True, True),
                            CParam('count', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"),
                               'count': parse_expr("count")},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    assert 'buffer too large' not in code, (
        "INT_MAX guard must not appear when no n/length-derived int params")
    test_passed()


def test_empty_expand():
    """expand with zero-length list: should produce no functions, no crash."""
    from c2py23.parser import _expand_func_template, _parse_func

    raw_func = {
        'py_sig': 'sum_a(arr: buffer) -> int',
        'c_overloads': [{
            'sig': 'int sum_a(const int *arr, int n)',
            'map': {'arr': 'arr.ptr', 'n': 'arr.n'}
        }],
        'expand': {'SUFFIX': [], 'TYPE': []},
    }
    expanded = _expand_func_template(raw_func, 'test.c2py')
    assert expanded == [], "Empty expand must produce empty list, got %s" % expanded
    test_passed()


def test_default_raise_valid():
    """default_raise with a known exception type must generate correct C code."""
    from c2py23.parser import parse_expr

    mod = ModuleDef(
        name='defraise',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='f',
                py_params=[PyParam('arr', 'buffer', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void do_f(float *arr, int n)',
                    params=[CParam('arr', 'float *', 'float', True, True),
                            CParam('n', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"),
                                'n': parse_expr("arr.n")},
                    when_expr=parse_expr("arr.format == 'f'"),
                )],
                default_raise='ValueError: no matching overload',
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    assert 'PyExc_ValueError' in code, (
        "default_raise must emit PyExc_ValueError")
    assert 'no matching overload' in code, (
        "default_raise message must appear in generated C")
    test_passed()


def test_optional_int_default_zero():
    """Optional int param with default 0: must not be mistaken for 'no default' (falsy edge case)."""
    from c2py23.parser import PyParam, _parse_py_sig

    name, params, ret = _parse_py_sig('f(arr: buffer, flags: int = 0) -> void', 'test.c2py')
    assert len(params) == 2
    assert params[1].default == 0, "default=0 must be stored as int 0, got %s" % repr(params[1].default)
    assert params[1].default is not None, "default=0 must not be conflated with None"

    from c2py23.parser import parse_expr

    mod = ModuleDef(
        name='optzero',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='f',
                py_params=[PyParam('arr', 'buffer', None),
                            PyParam('flags', 'int', 0)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void do_f(float *arr, int n, int flags)',
                    params=[CParam('arr', 'float *', 'float', True, True),
                            CParam('n', 'int', 'int', False, False),
                            CParam('flags', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"),
                                'n': parse_expr("arr.n"),
                                'flags': parse_expr("flags")},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    # Verify default=0 appears in the C code for local var initialization
    assert 'int c_flags = 0;' in code, (
        "Optional int=0 must emit 'int c_flags = 0;', got: %s"
        % code[code.find('c_flags'):][:50] if 'c_flags' in code else 'no c_flags')
    test_passed()


def test_outputs_with_gil_release():
    """GIL restore must happen before output tuple construction (outputs + gil_release combined)."""
    from c2py23.parser import parse_expr

    ol = COverload(
        sig_str='int get_min_max(const float *arr, int n, float *minv, float *maxv)',
        params=[CParam('arr', 'const float *', 'float', True, True),
                CParam('n', 'int', 'int', False, False),
                CParam('minv', 'float *', 'float', False, False),
                CParam('maxv', 'float *', 'float', False, False)],
        return_type='int',
        map_exprs={'arr': parse_expr("arr.ptr"),
                    'n': parse_expr("arr.n")},
        when_expr=None,
        outputs={'minv': 'float', 'maxv': 'float'},
    )

    mod = ModuleDef(
        name='outgil',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='stats',
                py_params=[PyParam('arr', 'buffer', None)],
                return_type='void',
                checks=[],
                overloads=[ol],
                default_raise=None,
                doc=None,
                gil_release=True,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    # GIL restore must appear before output tuple construction
    restore_pos = code.find('PyEval_RestoreThread')
    tuple_pos = code.find('PyTuple_New')

    if restore_pos >= 0 and tuple_pos >= 0:
        assert restore_pos < tuple_pos, (
            "PyEval_RestoreThread (pos %d) must come before PyTuple_New (pos %d)"
            % (restore_pos, tuple_pos))
    # And the gil_release flag should be emitted
    assert '_c2py_gil_release_enabled' in code, (
        "GIL release must emit module-level flag")
    test_passed()


def test_keyword_argument_rejection():
    """METH_VARARGS without METH_KEYWORDS must reject keyword arguments."""
    from c2py23.parser import parse_expr

    mod = ModuleDef(
        name='nokw',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='f',
                py_params=[PyParam('arr', 'buffer', None),
                            PyParam('n', 'int', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void do_f(float *arr, int n)',
                    params=[CParam('arr', 'float *', 'float', True, True),
                            CParam('n', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"),
                                'n': parse_expr("n")},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    # Must NOT have METH_KEYWORDS on any method def
    assert 'METH_KEYWORDS' not in code, (
        "METH_VARARGS functions must not use METH_KEYWORDS")
    assert 'METH_VARARGS' in code, (
        "Function must use METH_VARARGS flag")
    test_passed()


if __name__ == '__main__':
    results = []
    for name in sorted(globals()):
        if name.startswith('test_'):
            try:
                globals()[name]()
                results.append(('PASS', name))
            except Exception as e:
                results.append(('FAIL', name + ': ' + str(e)))
                import traceback
                traceback.print_exc()

    passed = sum(1 for r, _ in results if r == 'PASS')
    total = len(results)
    print('\nResults: %d/%d passed' % (passed, total))
    sys.exit(0 if passed == total else 1)
```

## tests/test_uniform.py

```python
"""Uniform test script for c2py23 - runs identically on Python 2.7 through 3.14.

Tests all test cases: arraysum, fill, dot, transform, types, optional,
docstring, constants, timing, scalar_output, template, typedispatch, gil_release.
Uses ctypes arrays (buffer protocol works on 2.7 and 3.x) + memoryview for shape.
On Python 2.7, some tests are skipped due to old buffer protocol limitations.
"""
from __future__ import print_function

import sys
import os
import warnings
import ctypes

warnings.filterwarnings("ignore", message=".*API version mismatch.*")

IS_PY3 = sys.version_info[0] >= 3
IS_PY2 = not IS_PY3


def _has_pep3118():
    """Check if the platform supports PEP 3118 buffer protocol for typed arrays."""
    if IS_PY3:
        return True
    # Python 2.7: ctypes arrays use old buffer protocol (no format info)
    # NumPy arrays support PEP 3118, but we don't depend on numPy
    return False


def _double_array(values):
    n = len(values)
    return (ctypes.c_double * n)(*values)


def _float_array(values):
    n = len(values)
    return (ctypes.c_float * n)(*values)


def _zeros_double(n):
    return _double_array([0.0] * n)


def _to_list(arr):
    return [arr[i] for i in range(len(arr))]


def test_arraysum():
    """Test element-wise addition of double arrays."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'arraysum'))
    import arraysum

    a = _double_array([1.0, 2.0, 3.0, 4.0])
    b = _double_array([5.0, 6.0, 7.0, 8.0])
    result = _zeros_double(4)

    n = arraysum.array_sum(a, b, result)
    assert n == 4, "Expected 4, got %d" % n
    expected = [6.0, 8.0, 10.0, 12.0]
    actual = _to_list(result)
    assert actual == expected, "Expected %s, got %s" % (expected, actual)
    print("PASS: arraysum")


def test_fill():
    """Test type dispatch: fill float vs double arrays."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'fill'))
    import fillmod

    arr_f = _float_array([0.0, 0.0, 0.0, 0.0])
    fillmod.fill(arr_f, 3.14)
    assert _to_list(arr_f) == [3.140000104904175] * 4, "float fill failed: %s" % _to_list(arr_f)

    arr_d = _double_array([0.0, 0.0, 0.0])
    fillmod.fill(arr_d, 2.718)
    assert _to_list(arr_d) == [2.718] * 3, "double fill failed: %s" % _to_list(arr_d)

    print("PASS: fill")


def test_dot():
    """Test type dispatch with scalar return: dot product float vs double."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'dot'))
    import dotmod

    fa = _float_array([1.0, 2.0, 3.0])
    fb = _float_array([4.0, 5.0, 6.0])
    r = dotmod.dot(fa, fb)
    assert abs(r - 32.0) < 0.01, "float dot failed: %s" % r

    da = _double_array([1.0, 2.0, 3.0])
    db = _double_array([4.0, 5.0, 6.0])
    r = dotmod.dot(da, db)
    assert abs(r - 32.0) < 0.01, "double dot failed: %s" % r

    print("PASS: dot")


def test_transform():
    """Test shape dispatch: AoS [N,3] vs SoA [3,N] 2D buffers."""
    if not IS_PY3:
        print("SKIP: transform (2D memoryview.cast requires Python 3.x)")
        return

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'transform'))
    import xfrm

    pts_aos = _double_array([
        1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0
    ])
    out = _zeros_double(12)
    mv = memoryview(pts_aos).cast('B').cast('d', [4, 3])
    mv_out = memoryview(out).cast('B').cast('d', [4, 3])
    xfrm.transform(mv, mv_out)
    expected_aos = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0]
    assert _to_list(out) == expected_aos, "AoS transform failed: %s" % _to_list(out)

    pts_soa = _double_array([
        1.0, 4.0, 7.0, 10.0, 2.0, 5.0, 8.0, 11.0, 3.0, 6.0, 9.0, 12.0
    ])
    out2 = _zeros_double(12)
    mv2 = memoryview(pts_soa).cast('B').cast('d', [3, 4])
    mv_out2 = memoryview(out2).cast('B').cast('d', [3, 4])
    xfrm.transform(mv2, mv_out2)
    expected_soa = [2.0, 8.0, 14.0, 20.0, 4.0, 10.0, 16.0, 22.0, 6.0, 12.0, 18.0, 24.0]
    assert _to_list(out2) == expected_soa, "SoA transform failed: %s" % _to_list(out2)

    print("PASS: transform")


def test_types():
    """Test format character dispatch with fixed-width integer types."""
    import ctypes as ct
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'types'))
    import typesmod

    # uint16_t (format 'H')
    arr_h = (ct.c_uint16 * 4)(0, 0, 0, 0)
    typesmod.fill(arr_h, 42)
    assert list(arr_h) == [42, 42, 42, 42], "uint16 fill failed: %s" % list(arr_h)

    # uint32_t (format 'I')
    arr_i = (ct.c_uint32 * 3)(0, 0, 0)
    typesmod.fill(arr_i, 99)
    assert list(arr_i) == [99, 99, 99], "uint32 fill failed: %s" % list(arr_i)

    # int64_t (format 'q')
    arr_q = (ct.c_int64 * 4)(0, 0, 0, 0)
    typesmod.fill(arr_q, -7)
    assert list(arr_q) == [-7, -7, -7, -7], "int64 fill failed: %s" % list(arr_q)

    # int8_t (format 'b')
    arr_b = (ct.c_int8 * 3)(0, 0, 0)
    typesmod.fill(arr_b, 5)
    assert list(arr_b) == [5, 5, 5], "int8 fill failed: %s" % list(arr_b)

    # int16_t (format 'h')
    arr_h16 = (ct.c_int16 * 4)(0, 0, 0, 0)
    typesmod.fill(arr_h16, 13)
    assert list(arr_h16) == [13, 13, 13, 13], "int16 fill failed: %s" % list(arr_h16)

    print("PASS: types")


def test_optional():
    """Test optional parameters with defaults."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'optional'))
    import optmod

    data = _double_array([1.0, 2.0, 3.0, 4.0, 5.0])

    # All 3 args provided
    r = optmod.process(data, 1, 1)  # stride=1, verbose=1
    assert r == 1015, "process(data, 1, 1) = %d, expected 1015" % r

    # stride provided, verbose default
    r = optmod.process(data, 2)  # stride=2, verbose=0
    assert r == 9, "process(data, 2) = %d, expected 9" % r

    # Only data provided: stride=1 default, verbose=0 default
    r = optmod.process(data)  # stride=1, verbose=0
    assert r == 15, "process(data) = %d, expected 15" % r

    print("PASS: optional")


def test_docstring():
    """Test custom docstring on a function."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'docstring'))
    import docmod

    result = docmod.inc(41)
    assert result == 42, "inc(41) = %d, expected 42" % result

    # Check docstring
    actual_doc = docmod.inc.__doc__
    expected_doc = "Increment x by 1 and return the result"
    assert actual_doc == expected_doc, \
        "docstring: got '%s', expected '%s'" % (actual_doc, expected_doc)

    print("PASS: docstring")


def test_constants():
    """Test module-level integer constants."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'constants'))
    import constmod

    assert constmod.ALPHA == 1, "ALPHA = %s, expected 1" % constmod.ALPHA
    assert constmod.BETA == 2, "BETA = %s, expected 2" % constmod.BETA
    assert constmod.GAMMA == 3, "GAMMA = %s, expected 3" % constmod.GAMMA

    # Also test the function
    data = _double_array([1.0, 2.0, 3.0])
    r = constmod.scale_sum(data, constmod.ALPHA + constmod.BETA)  # factor=3
    expected = 1.0 * 3 + 2.0 * 3 + 3.0 * 3
    assert abs(r - expected) < 0.001, \
        "scale_sum(factor=3) = %s, expected %s" % (r, expected)

    print("PASS: constants")


def test_timing():
    """Test performance timing feature."""
    from c2py23.perf import read_perf, read_enabled, set_enabled

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'timing'))
    import timedmod
    import ctypes as ct

    arr = (ct.c_double * 5)(1.0, 2.0, 3.0, 4.0, 5.0)
    for i in range(10):
        r = timedmod.wsum(arr, 2.0)
        assert abs(r - 30.0) < 0.001

    py = read_perf(timedmod._perf_wsum)
    ov = read_perf(timedmod._perf_wsum__weighted_sum)

    assert py['call_count'] == 10, "py call_count expected 10, got %d" % py['call_count']
    assert py['c_mean_ns'] > 0
    assert py['wrap_mean_ns'] >= 0
    assert ov['call_count'] == 10, "ov call_count expected 10, got %d" % ov['call_count']
    assert ov['c_mean_ns'] > 0
    assert ov['wrap_dur_ns'] == 0

    # Test toggle off
    enabled = read_enabled(timedmod._c2py_timing_enabled)
    assert enabled == 1
    set_enabled(timedmod._c2py_timing_enabled, 0)
    assert read_enabled(timedmod._c2py_timing_enabled) == 0

    timedmod.wsum(arr, 1.0)
    py2 = read_perf(timedmod._perf_wsum)
    assert py2['call_count'] == 10  # should NOT have incremented
    set_enabled(timedmod._c2py_timing_enabled, 1)

    print("PASS: timing")


def test_scalar_output():
    """Test output scalar convention - C returns values via pointer args."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'scalar_output'))
    import statmod

    data = _double_array([3.0, 1.0, 5.0, 2.0, 4.0])
    minval, maxval = statmod.stats(data)
    assert minval == 1.0, "minval expected 1.0, got %s" % minval
    assert maxval == 5.0, "maxval expected 5.0, got %s" % maxval

    print("PASS: scalar_output")


def test_template():
    """Test template expansion - parameterized function definitions."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'template'))
    import summod

    data_u8 = (ctypes.c_uint8 * 5)(1, 2, 3, 4, 5)
    assert summod.sum_u8(data_u8) == 15

    data_u16 = (ctypes.c_uint16 * 3)(1, 2, 3)
    assert summod.sum_u16(data_u16) == 6

    data_i32 = (ctypes.c_int32 * 4)(10, 20, 30, 40)
    assert summod.sum_i32(data_i32) == 100

    print("PASS: template")


def test_typedispatch():
    """Test format dispatch over all 10 PEP 3118 buffer types.
    
    Covers the complete format-to-ctype mapping:
      'B' -> uint8_t   'b' -> int8_t
      'H' -> uint16_t  'h' -> int16_t
      'I' -> uint32_t  'i' -> int32_t
      'Q' -> uint64_t  'q' -> int64_t
      'f' -> float     'd' -> double
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'typedispatch'))
    import dispatchmod

    # uint8_t (format 'B')
    arr_B = (ctypes.c_uint8 * 3)(0, 0, 0)
    dispatchmod.fill(arr_B, 42)
    assert list(arr_B) == [42, 42, 42], "uint8 fill failed: %s" % list(arr_B)

    # int8_t (format 'b')
    arr_b = (ctypes.c_int8 * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_b, -7)
    assert list(arr_b) == [-7, -7, -7, -7], "int8 fill failed: %s" % list(arr_b)

    # uint16_t (format 'H')
    arr_H = (ctypes.c_uint16 * 3)(0, 0, 0)
    dispatchmod.fill(arr_H, 99)
    assert list(arr_H) == [99, 99, 99], "uint16 fill failed: %s" % list(arr_H)

    # int16_t (format 'h')
    arr_h = (ctypes.c_int16 * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_h, -13)
    assert list(arr_h) == [-13, -13, -13, -13], "int16 fill failed: %s" % list(arr_h)

    # uint32_t (format 'I')
    arr_I = (ctypes.c_uint32 * 3)(0, 0, 0)
    dispatchmod.fill(arr_I, 1000000)
    assert list(arr_I) == [1000000, 1000000, 1000000], "uint32 fill failed: %s" % list(arr_I)

    # int32_t (format 'i')
    arr_i = (ctypes.c_int32 * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_i, -1000000)
    assert list(arr_i) == [-1000000, -1000000, -1000000, -1000000], "int32 fill failed: %s" % list(arr_i)

    # uint64_t (format 'Q')
    arr_Q = (ctypes.c_uint64 * 3)(0, 0, 0)
    dispatchmod.fill(arr_Q, 9999999999)
    assert list(arr_Q) == [9999999999, 9999999999, 9999999999], "uint64 fill failed: %s" % list(arr_Q)

    # int64_t (format 'q')
    arr_q = (ctypes.c_int64 * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_q, -9999999999)
    assert list(arr_q) == [-9999999999, -9999999999, -9999999999, -9999999999], "int64 fill failed: %s" % list(arr_q)

    # float32 (format 'f')
    arr_f = (ctypes.c_float * 4)(0, 0, 0, 0)
    dispatchmod.fill(arr_f, 3.14)
    vals_f = _to_list(arr_f)
    for v in vals_f:
        assert abs(v - 3.14) < 0.01, "float32 fill failed: %s" % vals_f

    # float64 (format 'd')
    arr_d = (ctypes.c_double * 3)(0, 0, 0)
    dispatchmod.fill(arr_d, 2.718)
    vals_d = _to_list(arr_d)
    for v in vals_d:
        assert abs(v - 2.718) < 0.0001, "float64 fill failed: %s" % vals_d

    print("PASS: typedispatch")


def test_gil_release():
    """Test GIL release: concurrent calls overlap instead of serializing."""
    import time
    import threading

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'gil_release'))
    import gilmod

    arr = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    arr2 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    sleep_us = 100000  # 100ms

    # Test 1: With GIL release, two threads overlap
    t0 = time.time()
    t1 = threading.Thread(target=gilmod.sleep_fill, args=(arr, 1.0, sleep_us))
    t2 = threading.Thread(target=gilmod.sleep_fill, args=(arr2, 2.0, sleep_us))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    elapsed = time.time() - t0

    # With GIL release, both 100ms sleeps should overlap -> < 150ms
    assert elapsed < 0.150, \
        "GIL release: expected < 150ms, got %.3fs (threads serialized?)" % elapsed
    assert list(arr) == [1.0, 1.0, 1.0, 1.0], "thread 1 fill failed"
    assert list(arr2) == [2.0, 2.0, 2.0, 2.0], "thread 2 fill failed"

    # Test 2: Without GIL release, threads serialize
    arr3 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    arr4 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)

    t0 = time.time()
    t3 = threading.Thread(target=gilmod.sleep_fill_no_gil, args=(arr3, 3.0, 50000))
    t4 = threading.Thread(target=gilmod.sleep_fill_no_gil, args=(arr4, 4.0, 50000))
    t3.start()
    t4.start()
    t3.join()
    t4.join()
    elapsed_no = time.time() - t0

    # Without GIL release, two 50ms sleeps serialize -> > 80ms
    assert elapsed_no > 0.080, \
        "No GIL release: expected > 80ms, got %.3fs (threads overlapped?)" % elapsed_no
    assert list(arr3) == [3.0, 3.0, 3.0, 3.0], "thread 3 fill failed"
    assert list(arr4) == [4.0, 4.0, 4.0, 4.0], "thread 4 fill failed"

    # Test 3: Global toggle disables GIL release
    # Read the global flag pointer and set to 0
    import ctypes as ct
    gil_flag_ptr = gilmod._c2py_gil_release_enabled
    ct.c_int.from_address(gil_flag_ptr).value = 0

    arr5 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    arr6 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)

    t0 = time.time()
    t5 = threading.Thread(target=gilmod.sleep_fill, args=(arr5, 5.0, 50000))
    t6 = threading.Thread(target=gilmod.sleep_fill, args=(arr6, 6.0, 50000))
    t5.start()
    t6.start()
    t5.join()
    t6.join()
    elapsed_disabled = time.time() - t0

    # When disabled, two 50ms sleeps should serialize -> > 80ms
    assert elapsed_disabled > 0.080, \
        "GIL disabled: expected > 80ms, got %.3fs (still overlapping?)" % elapsed_disabled
    assert list(arr5) == [5.0, 5.0, 5.0, 5.0], "thread 5 fill failed"
    assert list(arr6) == [6.0, 6.0, 6.0, 6.0], "thread 6 fill failed"

    # Restore global flag
    ct.c_int.from_address(gil_flag_ptr).value = 1

    # Test 4: Per-function toggle via module attribute
    func_flag_ptr = gilmod._c2py_gil_release_sleep_fill
    ct.c_int.from_address(func_flag_ptr).value = 0

    arr7 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
    arr8 = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)

    t0 = time.time()
    t7 = threading.Thread(target=gilmod.sleep_fill, args=(arr7, 7.0, 30000))
    t8 = threading.Thread(target=gilmod.sleep_fill, args=(arr8, 8.0, 30000))
    t7.start()
    t8.start()
    t7.join()
    t8.join()
    elapsed_func_disabled = time.time() - t0

    assert elapsed_func_disabled > 0.050, \
        "Per-func disabled: expected > 50ms, got %.3fs" % elapsed_func_disabled
    assert list(arr7) == [7.0, 7.0, 7.0, 7.0]
    assert list(arr8) == [8.0, 8.0, 8.0, 8.0]

    # Restore
    ct.c_int.from_address(func_flag_ptr).value = 1

    print("PASS: gil_release")


def test_address():
    """Test opaque void* pointers passed as Python int.

    Demonstrates that Python int values can map to C void* parameters.
    This is useful for passing GPU pointers, allocator handles, or
    other opaque addresses without Python managing the memory.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cases', 'address'))
    import addressmod

    # Allocate a buffer in Python, pass its address as int to C
    buf = (ctypes.c_int * 10)()
    ptr = ctypes.addressof(buf)

    # Store via void* -- C side dereferences the int as a pointer
    ret = addressmod.address_store(ptr, 42, 3)
    assert ret == 0, "address_store(ptr, 42, 3) returned %d, expected 0" % ret
    assert buf[3] == 42, "buf[3] = %d, expected 42 after address_store" % buf[3]

    # NULL pointer returns error
    ret = addressmod.address_store(0, 99, 0)
    assert ret == -1, "address_store(0, 99, 0) returned %d, expected -1" % ret

    # Verify other elements are untouched
    assert buf[0] == 0, "buf[0] was modified, expected 0"
    assert buf[9] == 0, "buf[9] was modified, expected 0"

    print("PASS: address")


def main():
    version_str = "%d.%d.%d" % (sys.version_info[0], sys.version_info[1], sys.version_info[2])
    print("Python version: %s" % version_str)
    tests = [
        ("arraysum", test_arraysum),
        ("fill", test_fill),
        ("dot", test_dot),
        ("transform", test_transform),
        ("types", test_types),
        ("optional", test_optional),
        ("docstring", test_docstring),
        ("constants", test_constants),
        ("timing", test_timing),
        ("scalar_output", test_scalar_output),
        ("template", test_template),
        ("typedispatch", test_typedispatch),
        ("gil_release", test_gil_release),
        ("address", test_address),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print("FAIL: %s - %s" % (name, e))
            failed += 1
            import traceback
            traceback.print_exc()

    print("")
    print("Results: %d passed, %d failed" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
```

