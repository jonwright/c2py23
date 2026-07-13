# Wheel Packaging Demo

The simplest possible wheel packaging demo.  Builds a single `.so` and
wraps it in a `py3-none-any` wheel using setuptools.

--8<-- "examples/wheel_demo/README.md"

## Build Script

```bash
--8<-- "examples/wheel_demo/build.sh"
```

## How It Works

`build.sh`:
1. runs `c2py23 generate` to produce the wrapper C file
2. Compiles the `.so` with `gcc -shared` (platform-tagged filename)
3. Copies it into the `arraysum/` package directory
4. Builds the wheel with `python3 -m build`

The `setup.py` overrides `bdist_wheel.get_tag()` to produce a
`py3-none-any` wheel.  `.so` files are listed as `package_data`, not
`ext_modules`, so `EXT_SUFFIX` is never applied.
