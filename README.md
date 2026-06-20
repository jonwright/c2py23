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

> **Warning for Python 3.14t (free-threaded) users:** By default, c2py23 modules
> re-enable the GIL globally on load (safe default). Set `free_threading: true` in
> your `.c2py` file to opt into true free-threading -- but only after verifying
> your C code is thread-safe. See `docs/user_guide.md` for a guide to thread-safe
> C patterns.

## Features

The `.c2py` YAML interface defines Python signatures, C overloads, and dispatch conditions.
The generator emits a single-file C99 wrapper with no heap allocations.

- **Buffer protocol** with format dispatch (`float` vs `double` vs `int32_t`), arithmetic checks (`a.n >= b.n + 2`), and contiguity enforcement
- **Overload dispatch** by buffer type, shape, CPU features (AVX2/AVX-512/NEON), or arbitrary `when:` conditions; variants statically resolved at init
- **Template expansion** (`expand:` with `${VAR}` substitution) for generating typed variants
- **GIL release** (`gil_release: true`) per-function for parallel C calls
- **Output scalars** (`outputs:`) return-by-pointer parameters as Python tuple values
- **Optional parameters** with defaults, custom docstrings, `default_raise:` error messages
- **Opaque pointers** -- `void*` maps from Python `int` for user-managed memory (GPU, custom allocators)
- **Per-function timing** via `clock_gettime` (default, nanosecond resolution) or CPU cycle counters (`rdtsc`/`CNTVCT_EL0`/`mftb` with `-DC2PY_USE_CYCLE_COUNTER`), decoded via ctypes
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
| 3.14.0t | ubuntu24.04 | 14/14 pass (free-threaded build; loading c2py23 re-enables GIL globally -- serialized like standard CPython; `PYTHON_GIL=0` for true free-threading) |

Additional tests in `test_peer_review.py` (alias + contiguity, 10 tests, requires numpy),
`test_error_paths.py` (refcount stability, 5 tests), and
`test_regression_fixes.py` (codegen validation, 14 tests).

## Examples

The `examples/` directory contains four worked examples:

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
    test_interpreters.py      # Verify interpreters exist in container (3.14 + 3.14t)
    check_abi.c               # ABI introspection tool
    populate_abi_matrix.py    # Collect ABI data from all containers
    abi_matrix.json           # Py_buffer/PyObject layout across 11 versions
  docs/                       # Specification, grammar, and user guide
    specification.md          # Full grammar, architecture, runtime internals
    user_guide.md             # Thread safety guide and best practices
  PLAN.md                     # Future work and roadmap
```

## Documentation

- `AGENTS.md` -- guidelines for AI agents working on the codebase
- `docs/specification.md` -- full grammar, worked examples, architecture
- `docs/user_guide.md` -- thread safety guide and best practices
- `docs/referee_reports_2026-06-15.md` -- referee review reports with point-by-point response

## Limitations

- No structs, enums, or nested data types
- Flat memory only (contiguous buffers)
- On free-threaded 3.14t, CPython re-enables the GIL globally when a c2py23 module loads (no `Py_MOD_GIL_NOT_USED`). All Python threads are serialized; parallel C execution requires `gil_release: true` (same as standard CPython). Set `PYTHON_GIL=0` or `-Xgil=0` for true free-threading at your own risk (C code must be thread-safe). See `docs/specification.md` for details.
