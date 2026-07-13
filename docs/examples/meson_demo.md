# Meson Build Demo

Packages a c2py23 module as a `py3-none-any` wheel using the Meson build system.

## Interface

```yaml
--8<-- "examples/meson_demo/arraysum.c2py"
```

## C Source

```c
--8<-- "examples/meson_demo/arraysum.c"
```

## Meson Configuration

```meson
--8<-- "examples/meson_demo/meson.build"
```

## Build Script

```bash
--8<-- "examples/meson_demo/build.sh"
```

## Build & Run

```bash
pip install c2py23 meson
cd examples/meson_demo
bash build.sh
# Produces dist/arraysum_meson-*.whl
pip install dist/arraysum_meson-*.whl
python -c "from arraysum import add_arrays; help(add_arrays)"
```

## How It Works

`build.sh`:
1. Generates the wrapper C file with `c2py23 generate`
2. Configures and builds with Meson
3. Copies the `.so` into the `arraysum/` package directory
4. Builds the wheel with `python3 -m build`

The `meson.build` file invokes `c2py23 generate` via `run_command()`,
then builds the `.so` with `shared_library()` using the generated wrapper,
runtime, and user source files.
