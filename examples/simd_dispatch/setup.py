"""setup.py -- SIMD dispatch example with multi-flag compilation

Demonstrates integrating c2py23 into a setuptools build:
  1. Pre-build hook: compile kernel.c multiple times with different -m flags
  2. c2py23 generate to produce the wrapper .c
  3. setuptools Extension builds the wrapper .c + runtime .c + user .o files

Usage:
  python3 setup.py build_ext --inplace
  python3 test_polysimd.py

Prerequisites:
  pip install c2py23 setuptools

NOTE: This is a build-system demonstration.  The same result can be
achieved with the simple Makefile or a single `c2py23 build` call.
"""
from __future__ import print_function

import os
import sys
import subprocess

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext as _build_ext


def find_runtime_dir():
    import c2py23
    return os.path.join(os.path.dirname(c2py23.__file__), 'runtime')


class PreBuildExtension(_build_ext):
    """Pre-build: compile poly_kernel.c with multiple -m flags,
    then run c2py23 generate to produce the wrapper .c."""

    def run(self):
        src_dir = os.path.dirname(os.path.abspath(__file__))
        cc = os.environ.get('CC', 'gcc')
        cflags = ['-O3', '-Wall', '-Werror', '-fPIC', '-ffast-math']

        # Multi-flag compilation
        variants = [
            ('poly_f32_avx512', ['-mavx512f']),
            ('poly_f32_avx2', ['-mavx2']),
            ('poly_f32_scalar', []),
        ]
        for fn_name, extra_flags in variants:
            obj = os.path.join(src_dir, '%s.o' % fn_name)
            cmd = [cc, '-c'] + cflags + extra_flags + [
                '-D', 'KERNEL_FN=%s' % fn_name,
                os.path.join(src_dir, 'poly_kernel.c'),
                '-o', obj,
            ]
            print('  ' + ' '.join(cmd))
            ret = subprocess.call(cmd)
            if ret != 0:
                sys.exit(ret)

        # Generate wrapper
        c2py_path = os.path.join(src_dir, 'polysimd.c2py')
        wrapper_path = os.path.join(src_dir, 'polysimd_wrapper.c')
        ret = subprocess.call([
            sys.executable, '-m', 'c2py23', 'generate', c2py_path,
            '-o', wrapper_path,
        ])
        if ret != 0:
            sys.exit(ret)

        _build_ext.run(self)


runtime_dir = find_runtime_dir()
runtime_c = os.path.join(runtime_dir, 'c2py_runtime.c')
src_dir = os.path.dirname(os.path.abspath(__file__))

polysimd_ext = Extension(
    'polysimd',
    sources=[
        runtime_c,
        os.path.join(src_dir, 'polysimd_wrapper.c'),
    ],
    extra_objects=[
        os.path.join(src_dir, 'poly_f32_avx512.o'),
        os.path.join(src_dir, 'poly_f32_avx2.o'),
        os.path.join(src_dir, 'poly_f32_scalar.o'),
    ],
    include_dirs=[runtime_dir, src_dir],
    extra_link_args=['-ldl'],
)

setup(
    name='polysimd',
    version='0.1.0',
    py_modules=[],
    ext_modules=[polysimd_ext],
    cmdclass={'build_ext': PreBuildExtension},
)
