"""Build c2py23 test modules in pythonh mode via setuptools.

Usage:
    python tests/setup.py build_ext --inplace --pythonh

For dlsym mode (portable, no libpython) use the Makefile:
    make -f tests/Makefile all

Environment variables:
    CC, CFLAGS, LDFLAGS, LIBS
"""

from __future__ import print_function
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)

sys.path.insert(0, _PROJECT)

from c2py23.setuptools_helper import discover_modules, PythonhCmdclass
from setuptools import setup

# Pythonh mode only -- --pythonh flag is required
if "--pythonh" not in sys.argv:
    print("[tests/setup] ERROR: --pythonh flag required (dlsym uses Makefile)", file=sys.stderr)
    sys.exit(1)
sys.argv.remove("--pythonh")

# Discover test case modules
_test_exts = discover_modules(
    os.path.join(_PROJECT, "tests", "cases"),
    os.path.join(_PROJECT, "c2py23", "runtime"),
)

# Discover example modules
_example_exts = discover_modules(
    os.path.join(_PROJECT, "examples"),
    os.path.join(_PROJECT, "c2py23", "runtime"),
)

# Discover benchmark modules
_bench_exts = discover_modules(
    os.path.join(_PROJECT, "benchmarks", "src"),
    os.path.join(_PROJECT, "c2py23", "runtime"),
)

all_extensions = _test_exts + _example_exts + _bench_exts

print(
    "[c2py23 tests/setup] Mode: pythonh  Extensions: %d (tests) + %d (examples)"
    " + %d (benchmarks) = %d" % (len(_test_exts), len(_example_exts), len(_bench_exts), len(all_extensions))
)

setup(
    name="c2py23_test_modules",
    ext_modules=all_extensions,
    cmdclass=PythonhCmdclass,
)
