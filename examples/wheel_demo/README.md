# arraysum wheel demo

Minimal example of packaging a c2py23-generated extension as a
`py3-none-any` wheel using the `c2py_loader` filename convention.

## Quick start

```bash
# Build and run (needs c2py23 installed)
bash build.sh
pip install dist/arraysum-0.1.0-py3-none-any.whl
python3 -c "import arraysum; print(arraysum.array_sum.__doc__)"
```

## Files

```
arraysum.c2py              c2py23 interface (module name: _arraysum)
arraysum.c                 C implementation
arraysum/__init__.py       package init, calls c2py_loader
pyproject.toml             build config, declares c2py23 dependency
setup.py                   setuptools with bdist_wheel -> py3-none-any
MANIFEST.in                sdist includes
build.sh                   one-step build script
```

## How it works

1. `c2py23 generate` produces `_arraysum_wrapper.c`
2. `gcc` compiles the wrapper + user C + c2py_runtime.c into
   `arraysum/_arraysum.c2py23-linux_x86_64.so`
3. `arraysum/__init__.py` calls `c2py23.c2py_loader.load_native()`
   which loads the .so by explicit filename (no sys.path hacking)
4. `setup.py bdist_wheel` packages everything as `py3-none-any`

## Adding more platforms

Build in each target container, naming each .so with the platform key:

```bash
# On x86_64:
bash build.sh  ->  arraysum/_arraysum.c2py23-linux_x86_64.so

# On aarch64 (cross-compile from manylinux2014):
CC=aarch64-linux-gnu-gcc bash build.sh --arch linux_aarch64
-> arraysum/_arraysum.c2py23-linux_aarch64.so

# On power9:
CC=powerpc64le-linux-gnu-gcc bash build.sh --arch linux_ppc64le
-> arraysum/_arraysum.c2py23-linux_ppc64le.so
```

Collect all the .so files into `arraysum/`, then run `bash build.sh --pack-only`
to assemble the multi-platform wheel.  All platforms in one `py3-none-any.whl`,
no per-architecture PyPI uploads needed.

## SIMD variants

For SIMD dispatch (like `examples/simd_dispatch/`), compile each variant
`.o` with the right `-m` flags (in your Makefile), link them together into
one .so per architecture.  c2py23's CPUID dispatch (in the `.c2py` file)
selects the right variant at runtime.  No extra flags in `pyproject.toml`.

## Runtime dependency

The wheel requires `c2py23` at runtime (for `c2py_loader.py`).  If you
want a zero-dependency wheel, copy the `load_native()` function body into
your own `__init__.py` -- it's ~30 lines and self-contained.
