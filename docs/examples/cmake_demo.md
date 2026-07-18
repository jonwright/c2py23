# CMake Build Demo

Packages a c2py23 module as a `py3-none-any` wheel using CMake.

--8<-- "examples/cmake_demo/README.md"

## CMake Configuration

```cmake
--8<-- "examples/cmake_demo/CMakeLists.txt"
```

## Build Script

```bash
--8<-- "examples/cmake_demo/build.sh"
```

## How It Works

`build.sh`:
1. Runs `c2py23` to produce the wrapper C file
2. Uses CMake to build `_arraysum.c2py23-{os}_{arch}.so`
3. Copies the `.so` into the `arraysum/` package directory
4. Builds the wheel with `python3 -m build`

`CMakeLists.txt` calls `c2py23` via `execute_process()` and
compiles the wrapper + runtime + user C source with `add_library()`.

The package `arraysum/__init__.py` uses `c2py_loader.load_native()` to
find and load the correct `.so` at import time.
