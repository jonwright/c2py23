# CMake Build Demo

Packages a c2py23 module as a `py3-none-any` wheel using CMake.

## Interface

```yaml
--8<-- "examples/cmake_demo/arraysum.c2py"
```

## C Source

```c
--8<-- "examples/cmake_demo/arraysum.c"
```

## CMake Configuration

```cmake
--8<-- "examples/cmake_demo/CMakeLists.txt"
```

## Build Script

```bash
--8<-- "examples/cmake_demo/build.sh"
```

## Build & Run

```bash
pip install c2py23
cd examples/cmake_demo
bash build.sh
# Produces dist/arraysum_cmake-*.whl
pip install dist/arraysum_cmake-*.whl
python -c "from arraysum import add_arrays; help(add_arrays)"
```

## How It Works

`build.sh`:
1. Runs `c2py23 generate` to produce the wrapper C file
2. Uses CMake to build `_arraysum.c2py23-{os}_{arch}.so`
3. Copies the `.so` into the `arraysum/` package directory
4. Builds the wheel with `python3 -m build`

`CMakeLists.txt` calls `c2py23 generate` via `execute_process()` and
compiles the wrapper + runtime + user C source with `add_library()`.

The package `arraysum/__init__.py` uses `c2py_loader.load_native()` to
find and load the correct `.so` at import time.
