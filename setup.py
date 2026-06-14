"""Setup script for c2py23 - backward compat with older pip/setuptools."""
from __future__ import print_function
from setuptools import setup, find_packages

setup(
    name='c2py23',
    version='0.1.0',
    description='Wrap C99 code to Python via the buffer protocol',
    packages=find_packages(include=['c2py23', 'c2py23.*']),
    package_data={'c2py23': ['runtime/*.h', 'runtime/*.c']},
    install_requires=[
        'PyYAML>=5.1;python_version>="3"',
        'PyYAML>=3.10,<6;python_version=="2.7"',
    ],
    entry_points={
        'console_scripts': [
            'c2py23=c2py23.cli:main',
        ],
    },
)
