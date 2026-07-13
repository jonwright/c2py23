# CMake Build Demo

Packages a c2py23 module as a `py3-none-any` wheel using CMake.
The `.so` follows the `c2py23-{os}_{arch}.so` naming convention and
the c2py_loader selects the right binary at import time.

## Interface

```yaml
--8<-- "examples/cmake_demo/arraysum.c2py"
```

## Build & Run

```bash
cd examples/cmake_demo
pip install -e ../..
bash build.sh
# Produces dist/arraysum_cmake-*.whl
pip install dist/arraysum_cmake-*.whl
python -c "from arraysum import add_arrays; help(add_arrays)"
```

## Key Design Decisions

- `CMakeLists.txt` calls `c2py23 generate` + `gcc -shared` separately
- .so placed in `arraysum/` with platform-tagged filename
- `pyproject.toml` and `setup.py` override `bdist_wheel.get_tag()` for `py3-none-any`
- `__init__.py` uses `c2py_loader.load_native()` for multi-platform loading
