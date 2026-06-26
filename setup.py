"""Setup script for c2py23 - backward compat with older pip/setuptools."""
from __future__ import print_function
import os
from setuptools import setup, find_packages

_here = os.path.dirname(__file__)
_version = {}
with open(os.path.join(_here, 'c2py23', '__init__.py')) as f:
    exec(f.read(), _version)

with open(os.path.join(_here, 'README.md')) as f:
    long_description = f.read()

setup(
    name='c2py23',
    version=_version['__version__'],
    description='Wrap C99 code to Python via the buffer protocol',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(include=['c2py23', 'c2py23.*']),
    package_data={'c2py23': ['runtime/*.h', 'runtime/*.c']},
    install_requires=[],
    extras_require={
        'yaml': [
            'PyYAML>=5.1;python_version>="3"',
            'PyYAML>=3.10,<6;python_version=="2.7"',
        ],
    },
    entry_points={
        'console_scripts': [
            'c2py23=c2py23.cli:main',
        ],
    },
)
