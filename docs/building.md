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

Run this to emit POSIX make rules for all `.c2py` modules in a directory:

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
