# brainstorm/tests/setup_hpy.py -- build HPy test extension
# Based on HPy microbench setup.py
from setuptools import setup, Extension

setup(
    include_package_data=False,
    hpy_ext_modules=[
        Extension(
            "hpy_type_check",
            ["hpy_type_check.c"],
            extra_compile_args=["-O2"],
        ),
    ],
)
