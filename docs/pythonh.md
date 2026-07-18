# `--pythonh`: Direct CPython Extension Mode

`c2py23 file.c2py -o wrapper.c` generates the wrapper.  Then compile with
setuptools and `-DC2PY_USE_PYTHON_H`:
No cross-version `.so` portability.  No C2PY function pointer table
indirection (when combined with LTO).

## What it does

Normally c2py23 generates "nimpy-style" wrappers: the runtime never
includes `<Python.h>`, instead resolving every CPython API symbol at
module load time via `dlopen(NULL)` + `dlsym()`.  This allows one `.so`
to load on Python 2.7 through 3.15 without recompilation.

`--pythonh` skips all of that:

| Aspect | Default (nimpy) | `--pythonh` |
|--------|----------------|-------------|
| Header | Never includes `<Python.h>` | `#include <Python.h>` |
| API calls | Through `C2PY.GetBuffer(...)` function pointer table | Direct CPython API calls |
| `.so` suffix | `_native.c2py23-...` or `.so` | Versioned: `.cpython-312-x86_64-linux-gnu.so` |
| Portability | One `.so` for Python 2.7-3.15 | Tied to one Python version |
| Dependencies | None (not even `-lpython`) | `-lpythonX.Y` (CPython only) |
| Debugging | dlsym adds indirection | Normal CPython debugger story |

## When to use

**Use `--pythonh` when:**

- **GraalPy**: Native Image `dlopen(NULL)` exports zero CPython symbols.
  The nimpy path segfaults.  `--pythonh` is the only viable mode.

- **Debugging**: When something breaks, isolate whether the bug is in the
  dlsym resolution path or in the wrapper logic.  Build with `--pythonh`
  and compare behavior.

- **Static/embedded builds**: For PyInstaller, embedded Python, or any
  context where `dlopen(NULL)` is restricted.

- **Maximum performance**: With `-flto`, the C2PY function pointer table
  devirtualizes to direct calls.  On `noargs()` this saves ~1-6 ns per
  call (see `docs/benchmarks.md`).

**Do NOT use `--pythonh` when:**

- You need one `.so` for multiple Python versions (the default nimpy mode
  is designed for this).
- You are targeting WASM/Pyodide (use `--target wasm`).
- You are targeting PyPy's cpyext with portable struct layouts (use
  `--target pypy`).

## Usage

```bash
# 1. Generate the wrapper (same as dlsym mode)
# CPython / PyPy / GraalPy
python3 -m c2py23 mymodule.c2py -o mymodule_wrapper.c

# 2. Build with setuptools (pythonh mode)
python -c "
from setuptools import setup, Extension
from c2py23.setuptools_helper import PythonhCmdclass
setup(name='mymodule',
    ext_modules=[Extension('mymodule',
        ['mymodule_wrapper.c', 'mymodule.c', 'c2py23/runtime/c2py_runtime.c'],
        include_dirs=['c2py23/runtime', '.'])],
    cmdclass=PythonhCmdclass,
    script_args=['build_ext', '--inplace'])
"
```

The running Python interpreter IS the target.  Setuptools auto-detects
include paths, the correct `.so` suffix, and linker flags.

`--pythonh` mode uses `-DC2PY_USE_PYTHON_H`.  It is incompatible with
WASM/Pyodide (which resolves symbols dynamically).  It can be combined
with `--target pypy` when building against PyPy's headers.

## Runtime support matrix

| Runtime | `--pythonh` | Nimpy (dlsym) | Notes |
|---------|------------|---------------|-------|
| CPython 2.7-3.15 | Yes | Yes | Default works everywhere |
| PyPy 3.9, 3.11 | Yes | Yes (`--target pypy`) | No `METH_FASTCALL` on cpyext |
| PyPy 2.7 | Untested | Partial | No fastcall either way |
| GraalPy 3.12 | **Yes (required)** | No (segfault) | `dlopen(NULL)` exports zero symbols |
| WASM/Pyodide | No | Yes (`--target wasm`) | Side modules resolve symbols dynamically |
| Free-threaded CPython (3.14t, 3.15t) | Yes | Yes | GIL re-enabled on load (module not declared FT-safe) |

## Performance

See `docs/benchmarks.md` for current numbers.  Summary:

- **CPython**: ~1 ns faster per `noargs()` call (under 1% of total
  call overhead).  The dlsym trick costs one load through the C2PY
  function pointer table.

- **PyPy**: ~6 ns faster per `noargs()` call (~3% of total).  PyPy's
  cpyext adds overhead that `--pythonh` eliminates.

- **GraalPy**: The nimpy path does not work at all.  `--pythonh` is
  the only option.

For buffer computations (vnorm, N=3 vectors), the delta is ~3 ns per
call  --  noise relative to the buffer acquisition and computation costs.

## LTO and devirtualization

With `-flto -O2`, the C2PY function pointer table devirtualizes to
direct CPython API calls.  See `tests/test_lto_devirt.sh` and
`tests/test_lto_devirt.md` for the proof.

In pythonh mode, the compiler can see that every C2PY function pointer
is set to a known CPython symbol at init time and never mutated.  The
result is zero C2PY indirect calls in the generated assembly.

## How it works internally

The `-DC2PY_USE_PYTHON_H` preprocessor flag gates two code paths:

1. **Header** (`c2py_runtime.h`): When set, includes `<Python.h>` and
   defines the C2PY struct using real CPython types.  Otherwise, uses
   the hand-declared types for cross-version ABI compatibility.

2. **Runtime** (`c2py_runtime.c`): When set, `c2py_runtime_init()`
   fills the C2PY struct from compile-time CPython symbols instead of
   `dlopen()` + `dlsym()`.  Nimpy-only code is guarded with `#ifndef
   C2PY_USE_PYTHON_H`.

3. **Generated wrappers**: Completely unchanged between modes.  The
   same `.c2py` source produces the same C wrapper; only the runtime
   resolution mechanism differs.

## Limitations

- **No cross-version portability**: The `.so` is tied to one Python version.
- **No free-threading**: `is_free_threaded` is hardcoded to 0.  Free-threaded
  CPython builds are not supported in `--pythonh` mode.
- **Not for WASM**: Use `--target wasm` for Pyodide/WASM targets.
- **PyPy needs `PYTHONPATH`**: The PyPy binary may need `PYTHONPATH` set
  to find c2py23's source when running `-m c2py23.cli`.
- **Linker flags vary**: CPython needs `-lpythonX.Y`; PyPy and GraalPy
  provide symbols through cpyext at load time and do not need it.
