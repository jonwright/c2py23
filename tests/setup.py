"""Build all c2py23 test modules and examples as C extensions.

Usage:
    # Dlsym mode (portable, no libpython, plain .so names):
    CC=gcc LIBS="-ldl -lm" python tests/setup.py build_ext --inplace

    # Pythonh mode (version-specific, ABI-tagged):
    python tests/setup.py build_ext --inplace --pythonh

    # ASan:
    CC=gcc CFLAGS="-fsanitize=address -g -O1" LDFLAGS="-fsanitize=address" \\
        LIBS="-ldl -lm" python tests/setup.py build_ext --inplace

    # PGO (generate profile):
    CC=gcc CFLAGS="-fprofile-generate" python tests/setup.py build_ext --inplace
    # (run tests to collect profiles)
    # PGO (use profile):
    CC=gcc CFLAGS="-fprofile-use" python tests/setup.py build_ext --inplace

Environment variables:
    CC, CFLAGS, LDFLAGS, LDSHARED, LIBS

--pythonh flag:
    Builds with -DC2PY_USE_PYTHON_H and ABI-tagged filenames.
    Without it: dlsym mode, plain .so names, no libpython.
"""

from __future__ import print_function
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)

sys.path.insert(0, _PROJECT)

from c2py23.build import discover_modules, DlsymCmdclass, PythonhCmdclass
from setuptools import setup

# Determine mode from --pythonh flag
_pythonh = "--pythonh" in sys.argv
if _pythonh:
    sys.argv.remove("--pythonh")

_cmdclass = PythonhCmdclass if _pythonh else DlsymCmdclass

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
    "[c2py23 tests/setup] Mode: %s  Extensions: %d (tests) + %d (examples)"
    " + %d (benchmarks) = %d"
    % ("pythonh" if _pythonh else "dlsym", len(_test_exts), len(_example_exts), len(_bench_exts), len(all_extensions))
)

setup(
    name="c2py23_test_modules",
    ext_modules=all_extensions,
    cmdclass=_cmdclass,
)
