"""pytest configuration for c2py23.  Session-scoped fixture builds all test
modules once before any tests run.

Python 2.7 compatible (pytest 4.6.x).  Uses subprocess.call (not run).
"""
from __future__ import print_function

import os
import sys
import subprocess

import pytest

# Suppress PytestReturnNotNoneWarning from peer_review tests (legacy return-bool style)
pytestmark = pytest.mark.filterwarnings(
    "ignore::pytest.PytestReturnNotNoneWarning")

# Exclude container orchestrator and snakepit test scripts from test collection
collect_ignore = ["test_all.py", "test_manylinux.py"]

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_DIR = os.path.join(PROJECT_DIR, "tests", "cases")
EXAMPLES_DIR = os.path.join(PROJECT_DIR, "examples")

sys.path.insert(0, PROJECT_DIR)


def _module_name(c2py_path):
    """Read the module name from a .c2py file."""
    with open(c2py_path) as f:
        for line in f:
            if line.startswith("module:"):
                return line.split()[1]
    return None


def _dirty(c2py_path):
    """Return True if the .so for a .c2py module needs rebuilding."""
    module = _module_name(c2py_path)
    if module is None:
        return False
    case_dir = os.path.dirname(c2py_path)
    so_file = os.path.join(case_dir, module + ".so")

    if not os.path.exists(so_file):
        return True

    so_mtime = os.path.getmtime(so_file)
    if os.path.getmtime(c2py_path) > so_mtime:
        return True

    for name in sorted(os.listdir(case_dir)):
        fpath = os.path.join(case_dir, name)
        if name.endswith(".c") and os.path.isfile(fpath):
            if os.path.getmtime(fpath) > so_mtime:
                return True
    return False


def _build(c2py_path):
    """Build a .c2py module using c2py23 build."""
    ret = subprocess.call(
        [sys.executable, "-m", "c2py23.cli", "build", c2py_path],
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE if hasattr(subprocess, "DEVNULL") else None,
        stderr=subprocess.PIPE if hasattr(subprocess, "DEVNULL") else None,
    )
    if ret != 0:
        pytest.fail("Build failed for %s (exit %d)" % (c2py_path, ret))


def _collect_c2py_files(base_dir):
    """Yield all .c2py file paths under base_dir."""
    for root, dirs, files in os.walk(base_dir):
        # skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in sorted(files):
            if f.endswith(".c2py"):
                yield os.path.join(root, f)


@pytest.fixture(scope="session", autouse=True)
def build_all_modules():
    """Build all test-case and example .c2py modules once per session."""
    built = 0

    # Build test cases
    for c2py_path in _collect_c2py_files(CASES_DIR):
        if _dirty(c2py_path):
            _build(c2py_path)
            built += 1

    # Build examples
    for ex in ["kissfft_wrap", "lz4_wrap"]:
        ex_dir = os.path.join(EXAMPLES_DIR, ex)
        if os.path.isdir(ex_dir):
            for c2py_path in _collect_c2py_files(ex_dir):
                if _dirty(c2py_path):
                    _build(c2py_path)
                    built += 1

    if built:
        print("\n[c2py23 conftest] Built %d module(s)" % built)
