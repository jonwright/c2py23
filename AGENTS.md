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

## SIMD Dispatch / CPU Feature Detection (P1 - PLANNING)

**Status: Not started. Design discussion needed before implementation.**

### Open Questions

1. Which architectures to support?
   - x86_64: avx2, avx512f (CPUID leaf 7)
   - ARM64: neon (always present on arm64), asimd (MRS ID_AA64PFR0_EL1)
   - POWER: vsx? (not requested so far)

2. How should CPU detection work?
   - Option A: inline asm in c2py_runtime.c (__get_cpuid on x86, MRS on arm64)
   - Option B: read /proc/cpuinfo (portable, no asm, but slow and Linux-only)
   - Option C: dlopen libcpuid or similar (adds dependency)
   - Preferred: Option A for x86_64 and arm64, with /proc/cpuinfo fallback.

3. Grammar for `when:` conditions
   - `when: "cpu_has_avx2"` -- function-level dispatch
   - Should this be per-overload or per-function? (per-overload is natural since different C functions correspond to different SIMD paths)
   - What if no matching CPU feature is found? Fall back to a non-SIMD overload.

4. Where does the dispatch happen?
   - At `_impl` level: select the right C function pointer at module init, call through pointer
   - Static bool flag per feature, checked in the _impl dispatch chain
   - The feature check is done once at module init, not per call

### Proposed Grammar (tentative)

```yaml
functions:
  - py_sig: "process(arr: buffer) -> void"
    c_overloads:
      - sig: "process_avx2(double *arr, int n)"
        map: {arr: "arr.ptr", n: "arr.n"}
        when: "arr.format == 'd' and cpu_has_avx2"
      - sig: "process_scalar(double *arr, int n)"
        map: {arr: "arr.ptr", n: "arr.n"}
        when: "arr.format == 'd'"
    default_raise: "ValueError: unsupported format"
```

### Implementation Sketch

1. `parser.py`: Add `cpu_has_*` as valid identifiers in `when:` expressions
2. `generator.py`: At module init, emit calls to detect CPU features and store in static bools
3. `c2py_runtime.h/c`: Add `c2py_cpu_has(const char *feature)` function:
   - Returns 1/0 for known features
   - Uses __get_cpuid on x86, MRS on arm64, /proc/cpuinfo parsing as fallback
4. In `_impl` function: before the dispatch chain, evaluate cpu_has_* as pre-computed bools

### When to Start

Discuss with stakeholders which CPU features are needed for ImageD11.
The implementation depends on knowing the target architectures and
the specific SIMD functions that ImageD11 will provide.

## Contributing Guidelines

1. **Always use 7-bit ASCII encoding** -- no unicode characters
2. **Maintain Python 2.7 compatibility** in all Python files
3. **Never include `<Python.h>`** in any C file
4. **No memory allocation in wrappers** -- all memory from Python
5. Test across all supported Python versions before committing
6. Keep the `.c2py` YAML grammar minimal -- new features must be expressible in C without runtime overhead
7. Generated C code should compile with `gcc -Wall -Werror`
8. Run both `test_uniform.py` and `test_peer_review.py` before committing
9. Run `python3 tests/test_all.py` for multi-version validation
10. Re-populate the ABI matrix (`python3 tests/populate_abi_matrix.py`) when changing the runtime
