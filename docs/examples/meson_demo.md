# Meson Build Demo

Packages a c2py23 module as a `py3-none-any` wheel using the Meson build system.
Equivalent to the CMake demo, using `meson.build` instead.

## Interface

```yaml
--8<-- "examples/meson_demo/arraysum.c2py"
```

## Build & Run

```bash
cd examples/meson_demo
pip install -e ../..
bash build.sh
# Produces dist/arraysum_meson-*.whl
pip install dist/arraysum_meson-*.whl
python -c "from arraysum import add_arrays; help(add_arrays)"
```

## Key Design Decisions

- `meson.build` calls `c2py23 generate` via `run_command()` and compiles with `shared_library()`
- Same `.so` filename convention and loader pattern as the CMake demo
- `pip install meson` required for the build
