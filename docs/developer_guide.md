# Developer Guide

This guide is for contributors to c2py23 itself (not users of the library).

## Repository Setup

```bash
git clone https://github.com/jonwright/c2py23.git
cd c2py23
pip install -e .
```

## Snakepit Containers

c2py23 tests across many Python versions using [snakepit](https://github.com/jonwright/snakepit)
Apptainer/Singularity containers.  These must be present at `../snakepit/`
relative to the project root.

| Container | Python versions |
|-----------|----------------|
| `debian10.sif` | 3.6 |
| `ubuntu20.04.sif` | 2.7, 3.8 |
| `ubuntu24.04.sif` | 3.7, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14 |
| `ubuntu26.04.sif` | 3.14, 3.15 |
| `manylinux2014.sif` | 3.9-3.14 |

## Running Tests

Quick local tests on one Python version:

```bash
# Build test modules and run
bash tests/run_tests.sh python3.12

# Run pre-built modules only (no rebuild)
bash tests/run_tests_only.sh python3.12
```

Cross-version validation using snakepit containers:

```bash
# Build and test across all versions
python3 tests/test_all.py

# Manylinux build-once cross-test
python3 tests/test_manylinux.py
```

Leak detection:

```bash
# Valgrind
valgrind --leak-check=full python3 tests/test_leaks.py

# ASan
CC=gcc CFLAGS="-fsanitize=address -g -O1" LDFLAGS="-fsanitize=address" python tests/runner.py
```

## Debug Builds

```bash
# With debug symbols
CC=gcc CFLAGS="-g -O0 -Wall -Werror" python tests/runner.py

# Under GDB
gdb --args python3 -c "import sys; sys.path.insert(0,'tests/cases/fill'); import fillmod; ..."
```

## Test Architecture

### Test cases

All in `tests/cases/`.  Each has a `.c2py` interface, a `.c` source, and a
generated `_wrapper.c`.  Pre-commit hook (`.githooks/pre-commit`) regenerates
`tests/cases/transform/xfrm_wrapper.c` when core sources change.

### Test files

| File | What it tests |
|------|---------------|
| `test_uniform.py` | Core functionality: arraysum, fill, dot, transform, types, optional, docstring, constants, timing, scalar_output, template, typedispatch, gil_release |
| `test_peer_review.py` | Alias/contiguity enforcement (requires numpy) |
| `test_error_paths.py` | Wrong format, wrong ndim, wrong sizes |
| `test_leaks.py` | Valgrind leak checking |
| `test_lifecycle.py` | Module init/deinit, reload |
| `test_interpreters.py` | Subinterpreter support (Python 3.12+) |
| `test_regression_fixes.py` | Edge cases and bug regression tests |
| `test_examples.py` | Tests that examples build and run |

### CI workflows

All in `.github/workflows/`:

- `linux.yml` -- Python 2.7-3.15 on Ubuntu
- `windows.yml` -- Python 2.7-3.15 on Windows
- `aarch64.yml` -- Python 3.12 on arm64
- `full_matrix.yml` -- combined matrix on push to main

## ABI Matrix

When changing the runtime (`c2py_runtime.h` or `c2py_runtime.c`), re-populate:

```bash
python3 tests/populate_abi_matrix.py
```

This records `sizeof(PyObject)`, `sizeof(Py_buffer)`, `PyModuleDef` layout,
and symbol availability across all supported Python versions.

## Adding a New Python Version

1. Get the container.  Add a snakepit image for the new version.
2. Compile `tests/check_abi.c` against the new headers inside the container.
   Compare `sizeof(PyObject)`, `sizeof(Py_buffer)`, `PyModuleDef`, and
   `PY_MOD_GIL` against the previous version.
3. Run the full matrix: `python3 tests/test_all.py`
4. Bump the version ceiling in `c2py_runtime.c`.
5. Add a row to the version table in `README.md`.
6. Update `tests/test_all.py` and `.github/workflows/full_matrix.yml`.

## Code Guidelines

- 7-bit ASCII only in all source files
- Python 2.7 compatibility (no f-strings, no type annotations, no `pathlib`,
  no `subprocess.run()`)
- No `#include <Python.h>` in any C file
- No `malloc`/`free` in generated wrapper code
- Generated C must compile with `gcc -Wall -Werror`
- Never guard a test with `pytest.skip()` / `@pytest.mark.skipif()` for
  platform/version issues -- fix the code instead
