# Wheel Packaging Demo

The simplest possible wheel packaging demo.  Builds a single `.so` and
wraps it in a `py3-none-any` wheel using setuptools.

## Interface

```yaml
--8<-- "examples/wheel_demo/arraysum.c2py"
```

## Build & Run

```bash
cd examples/wheel_demo
pip install -e ../..
bash build.sh
# Produces dist/arraysum_wheel-*.whl
pip install dist/arraysum_wheel-*.whl
python -c "from arraysum import add_arrays; help(add_arrays)"
```

## Key Design Decisions

- Simplest possible setup: `c2py23 generate` + `gcc -shared` + `python3 -m build`
- `setup.py` overrides `bdist_wheel.get_tag()` to produce `py3-none-any`
- `MANIFEST.in` ensures `.so` files are included in the wheel
- The wheel works on any platform that has the matching `.so` architecture
