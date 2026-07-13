# Meson Build Demo

Packages a c2py23 module as a `py3-none-any` wheel using the Meson build system.

--8<-- "examples/meson_demo/README.md"

## Meson Configuration

```meson
--8<-- "examples/meson_demo/meson.build"
```

## Build Script

```bash
--8<-- "examples/meson_demo/build.sh"
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
