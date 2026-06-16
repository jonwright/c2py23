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
`uint32_t`, `int64_t`, `uint64_t`, `int`, `float`, `double`, `char`

**Output scalars** (`outputs:` key): supports `int8_t`, `int16_t`, `int32_t`,
`uint8_t`, `uint16_t`, `uint32_t`, `int64_t`, `uint64_t`, `float`, `double`,
`int` as return-by-pointer parameters.

No structs, enums, nested pointers, or heap allocation. All memory is flat and owned by Python.

## Features

- **Format dispatch** -- call different C functions based on buffer element type (`float` vs `double` vs `int32_t`)
- **Shape dispatch** -- call different C functions based on buffer dimensionality ([N,3] vs [3,N])
- **Template expansion** -- `expand:` key generates multiple function variants via `${VAR}` substitution
- **SIMD dispatch** -- `variants:` key dispatches to ISA-specific kernel variants based on CPU feature flags; static dispatch resolved at module init. Supports multi-flag compilation (same kernel compiled with `-mavx2`, `-mavx512f`, etc.)
- **CPU feature detection** -- runtime headers detect avx2, avx512f, neon, asimd, sve, and other CPU features via CPUID/MRS
- **GIL release** -- `gil_release: true` releases the GIL during C calls for parallelism; per-function and per-overload
- **Output scalars** -- `outputs:` key auto-allocates return-by-pointer params as Python tuple values (f2py compat)
- **Module constants** -- `constants:` key emits integer module-level constants
- **Optional parameters** -- `int` and `float` params support `= default_value`
- **Custom docstrings** -- `doc:` key overrides auto-generated docstrings
- **Default raise** -- `default_raise:` specifies exception type and message when no overload matches
- **restrict enforcement** -- the wrapper checks that writable buffers do not alias; C code can assume `restrict`
- **PEP 3118 buffer protocol** -- accepts any object supporting the buffer interface (`bytes`, `bytearray`, `array.array`, `memoryview`, `ctypes` arrays, numpy arrays, etc.)
- **nimpy-style runtime** -- no `-lpython` link dependency; one `.so` works on Python 2.7 through 3.14. Uses `dlopen(NULL)` + `dlsym()` to resolve CPython API at load time. Originates from [yglukhov/nimpy](https://github.com/yglukhov/nimpy).
- **Python 2.7 fallback** -- `PyObject_AsReadBuffer`/`PyObject_AsWriteBuffer` used when PEP 3118 is unavailable
- **Zero-copy** -- the wrapper never allocates, copies, or transposes memory; all buffers are owned and managed by Python
- **Contiguity enforcement** -- validates C and Fortran-order contiguity, rejects strided or indirect buffers
- **Per-function timing** -- `timing: true` enables cycle-count instrumentation of C call overhead
- **Arch-specific clocks** -- `rdtsc` (x86), `CNTVCT_EL0` (ARM64), `mftb` (POWER) for low-overhead timing
- **METH_FASTCALL** -- on Python 3.12+, the wrapper uses `METH_FASTCALL` for reduced call overhead
- **Codegen validation** -- parameter count mismatch between .c2py sig and C source emits a warning
- **Type validation** -- format checks (e.g. `buffer.format == 'i'`) are validated against C pointer types
- **Check diagnostics** -- check failures include actual runtime values (e.g. `got format='l'`)
- **ASan support** -- `c2py23 build --asan` links with `-fsanitize=address` for leak detection

## Supported Python Versions

| Version | Container | Tests |
|---------|-----------|-------|
| 2.7.18 | ubuntu20.04 | 12/13 pass, 1 skip (transform) |
| 3.6.15 | debian10 | 13/13 pass |
| 3.7.17 | ubuntu24.04 | 13/13 pass |
| 3.8.10 | ubuntu20.04 | 13/13 pass |
| 3.9.25 | ubuntu24.04 | 13/13 pass |
| 3.10.20 | ubuntu24.04 | 13/13 pass |
| 3.11.15 | ubuntu24.04 | 13/13 pass |
| 3.12.3 | ubuntu24.04 | 13/13 pass |
| 3.13.14 | ubuntu24.04 | 13/13 pass |
| 3.14.6 | ubuntu24.04 | 13/13 pass (GIL-enabled; free-threaded not yet supported) |

Additional tests in `test_peer_review.py` (alias + contiguity, 10 tests, requires numpy),
`test_error_paths.py` (refcount stability, 5 tests), and
`test_regression_fixes.py` (codegen validation, 9 tests).

## Examples

The `examples/` directory contains three worked examples:

- **KissFFT** (`examples/kissfft_wrap/`) -- real and complex FFT over float buffers
- **LZ4** (`examples/lz4_wrap/`) -- compress/decompress over byte buffers
- **SIMD Dispatch** (`examples/simd_dispatch/`) -- multi-flag compilation with CPU feature dispatch; includes meson.build, CMakeLists.txt, and setup.py build system integration demos

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
  tests/
    cases/                    # Test cases (C source + .c2py interface)
    run_tests.sh              # Build + test for one Python version
    test_uniform.py           # 2.7-3.14 compatible test runner (13 tests)
    test_all.py               # Orchestrator across snakepit containers
    test_leaks.py             # Memory stress test (valgrind compatible)
    test_peer_review.py       # Alias + contiguity enforcement tests (requires numpy)
    test_error_paths.py       # Refcount stability on error paths
    test_regression_fixes.py  # Parser/generator bug-fix unit tests
    check_abi.c               # ABI introspection tool
    populate_abi_matrix.py    # Collect ABI data from all containers
    abi_matrix.json           # Py_buffer/PyObject layout across 10 versions
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
- Thread safety for free-threaded 3.14+ not yet addressed
