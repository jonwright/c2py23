"""Setup for arraysum -- c2py23 wheel demo.

Uses c2py_loader naming convention: _arraysum.c2py23-{os}_{arch}.so

The .so is pre-built and included as package_data.  No setuptools.Extension
is used, so EXT_SUFFIX is never applied and the .so filename is preserved
as-is.

For multi-platform wheels: build the .so inside each target container, name
each .so with the right platform key, place all of them in the arraysum/
package directory, then run `python -m build` once.  The resulting
py3-none-any wheel works on all supported platforms.
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
    name='arraysum',
    version='0.1.0',
    description='Element-wise addition of double arrays (c2py23 demo)',
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
