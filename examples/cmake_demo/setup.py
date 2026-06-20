"""Setup for arraysum-cmake demo.

The .so is pre-built via cmake and included as package_data.
"""
from __future__ import print_function

from setuptools import setup
from wheel.bdist_wheel import bdist_wheel as _bdist_wheel


class BdistWheel(_bdist_wheel):
    def finalize_options(self):
        _bdist_wheel.finalize_options(self)
        self.root_is_pure = True

    def get_tag(self):
        return ('py3', 'none', 'any')


setup(
    name='arraysum-cmake',
    version='0.1.0',
    description='arraysum built with cmake (c2py23 + c2py_loader)',
    packages=['arraysum'],
    package_data={
        'arraysum': [
            '*.c2py23-*.so',
            '*.c2py23-*.pyd',
        ],
    },
    install_requires=[
        'c2py23',
    ],
    cmdclass={'bdist_wheel': BdistWheel},
)
