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

## Supported Types

| Python type | C types |
|-------------|---------|
| `buffer` | `const T*` (read-only), `T*` (read-write) where T is `int`, `float`, `double`, `char` |
| `int` | `int` |
| `float` | `float`, `double` |
| Return `void` | C `void` function |
| Return `int` | C `int` return |
| Return `float` | C `float` or `double` return |

No structs, enums, nested pointers, or heap allocation. All memory is flat and owned by Python.

## Features

- **Format dispatch** -- call different C functions based on buffer element type (`float` vs `double`)
- **Shape dispatch** -- call different C functions based on buffer dimensionality ([N,3] vs [3,N])
- **restrict enforcement** -- the wrapper checks that writable buffers do not alias, so C code can always use `restrict`
- **PEP 3118 buffer protocol** -- accepts any object supporting the buffer interface (`bytes`, `bytearray`, `array.array`, `memoryview`, `ctypes` arrays, numpy arrays, etc.)
- **nimpy-style runtime** -- no `-lpython` link dependency; one `.so` works on Python 2.7 through 3.14 (build on the oldest target OS for forward libc compatibility). The approach originates from [yglukhov/nimpy](https://github.com/yglukhov/nimpy) (ABI-compatible Nim-Python bridge); c2py23 adapts it for C, using only the minimal CPython C API surface needed for buffer protocol operations.
- **Python 2.7 fallback** -- `PyObject_AsReadBuffer`/`PyObject_AsWriteBuffer` used when PEP 3118 is unavailable
- **Zero-copy** -- the wrapper never allocates, copies, or transposes memory

## Supported Python Versions

| Version | Container | Status |
|---------|-----------|--------|
| 2.7.18 | ubuntu20.04 | 3/4 tests pass (transform uses 3.3+ API) |
| 3.8.10 | ubuntu20.04 | 4/4 pass |
| 3.9.25 | ubuntu24.04 | 4/4 pass |
| 3.10.20 | ubuntu24.04 | 4/4 pass |
| 3.11.15 | ubuntu24.04 | 4/4 pass |
| 3.12.3 | ubuntu24.04 | 4/4 pass |
| 3.13.14 | ubuntu24.04 | 4/4 pass |
| 3.14.6 | ubuntu24.04 | 4/4 pass |

## Testing

```bash
# Test a specific Python version locally
bash tests/run_tests.sh python3.12

# Test across all versions via snakepit containers
python3 tests/test_all.py
```

Requires the snakepit SIF containers at `../snakepit/`.

## File Structure

```
c2py23/
  c2py23/          # Python package (parser, generator, CLI)
    runtime/       # C runtime (nimpy loader + API table)
  tests/
    cases/         # Test cases (C source + .c2py interface)
    run_tests.sh   # Build + test for one Python version
    test_uniform.py # 2.7-3.14 compatible test runner
    test_all.py    # Orchestrator across snakepit containers
  docs/            # Specification and grammar
```

## Documentation

- `AGENTS.md` -- guidelines for AI agents working on the codebase
- `docs/specification.md` -- full grammar, worked examples, architecture

## Limitations

- No structs, enums, or nested data types
- Flat memory only (contiguous buffers)
- All memory management is in Python
- The GIL is held during all C function calls
- No dynamic dispatch at runtime -- all dispatch is resolved at code generation time
- Thread safety not yet addressed (future work)
