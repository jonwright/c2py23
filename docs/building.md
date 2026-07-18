# Building c2py23 Extensions

c2py23 generates C code.  It does NOT compile it.  You choose the build
system.

## Two modes

| Mode | How to build | Result |
|------|-------------|--------|
| **dlsym** (default) | Any C99 compiler | One `.so`/`.pyd` for Python 2.7 through 3.15 |
| **pythonh** | setuptools + `<Python.h>` | Version-specific `.so`, links libpython |

dlsym is the portable mode.  pythonh is for GraalPy, debugging, or static
builds.  See [--pythonh mode](pythonh.md) for details.

## dlsym mode -- vanilla C compilation

```bash
# 1. Generate the wrapper C file
c2py23 mymod.c2py -o mymod_wrapper.c

# 2. Compile with any C99 compiler
cc -shared -fPIC \
    c2py23/runtime/c2py_runtime.c \
    mymod_wrapper.c mymod.c \
    -I c2py23/runtime \
    -o mymod.so -ldl -lm
```

On Windows with MSVC:
```bash
cl /LD /I c2py23/runtime \
    c2py23/runtime/c2py_runtime.c \
    mymod_wrapper.c mymod.c \
    /Fe:mymod.pyd
```

## pythonh mode -- setuptools

```bash
# 1. Generate the wrapper
c2py23 mymod.c2py -o mymod_wrapper.c

# 2. Build with setuptools
python -c "
from setuptools import setup, Extension
from c2py23.setuptools_helper import PythonhCmdclass
setup(name='mymod',
    ext_modules=[Extension('mymod',
        ['mymod_wrapper.c', 'mymod.c', 'c2py23/runtime/c2py_runtime.c'],
        include_dirs=['c2py23/runtime', '.'])],
    cmdclass=PythonhCmdclass,
    script_args=['build_ext', '--inplace'])
"
```

## Build system examples

c2py23 is build-system-agnostic.  These examples show how to integrate
with common build systems for dlsym-mode extensions:

| Example | Build system | Notes |
|---------|-------------|-------|
| `examples/cmake_demo/` | [CMake](examples/cmake_demo.md) | `FindPython`, `add_library(... SHARED)` |
| `examples/meson_demo/` | [Meson](examples/meson_demo.md) | `shared_library()`, `meson.build` |
| `examples/simd_dispatch/` | Makefile | Multi-ISA compilation (AVX-512/AVX2/scalar `.o` files linked into one `.so`) |
| `examples/threading_bench/` | Makefile | OpenMP variant (`CC=... make omp`) |
| `examples/wheel_demo/` | setuptools | Multi-platform wheel packaging with `py3-none-any` tag |

### Generating a POSIX Makefile snippet

Run this in the source checkout to emit POSIX make rules for all `.c2py` modules
in a directory:

```bash
python tools/generate_makefile_deps.py > my_project_deps.mk
```

Include it from your `Makefile`:

```makefile
RUNTIME_SRC  := c2py23/runtime/c2py_runtime.c
RUNTIME_INC  := c2py23/runtime
RUNTIME_HDRS := $(wildcard $(RUNTIME_INC)/*.h)
EXT          ?= .so

include my_project_deps.mk

all: mymod$(EXT)
```

The generated rules produce `_wrapper.c` from `.c2py`, then compile to `.so`.

### Building wheels

dlsym `.so` files go into `py3-none-any` wheels -- one binary for all
Python versions.  See `examples/wheel_demo/` for a complete `setup.py`
that packages dlsym and pythonh variants automatically.

## Our test Makefile

`tests/Makefile` builds 17 test modules + 2 examples (kissfft, lz4) with
vanilla C.  Type `make -f tests/Makefile all` from the project root.

## Migrating from YAML (pre-v0.4.0)

c2py23 originally used YAML for `.c2py` interface files.  This was removed
in v0.4.0 -- YAML's indentation rules and the PyYAML C-extension dependency
caused portability problems across Python 2.7-3.15, PyPy, and WASM.

To migrate a legacy YAML `.c2py` file:

```bash
# 1. Convert to Python dict format:
python tools/convert_c2py_to_dict.py mymodule.c2py

# 2. Replace the YAML file with the generated .c2py.py sidecar:
mv mymodule.c2py.py mymodule.c2py

# 3. The new .c2py is a Python dict literal -- same keys, same values.
#    c2py23 mymodule.c2py -o mymodule_wrapper.c  works as before.
```

`tools/convert_c2py_to_dict.py` requires PyYAML (for reading the old format
only).  Once converted, PyYAML is no longer needed anywhere.

## PyPy and .so imports

PyPy's import machinery only recognizes ABI-tagged extension suffixes
(e.g. `.pypy311-pp73-x86_64-linux-gnu.so`).  Our dlsym mode produces
plain `.so` files for cross-version portability.  On PyPy, `import
fillmod` fails because the file finder never looks for `fillmod.so`.

**Workaround for test suites (pytest):** `tests/conftest.py` preloads
modules via `importlib.machinery.ExtensionFileLoader` into `sys.modules`
before test collection.  Plain `import` then succeeds because the module
is found in `sys.modules`.

**Workaround for scripts:** use `importlib` directly:

```python
import importlib.util, importlib.machinery

loader = importlib.machinery.ExtensionFileLoader(
    "mymod", "mymod.so")
spec = importlib.util.spec_from_file_location(
    "mymod", "mymod.so", loader=loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)
# mod.my_function() works now
```
