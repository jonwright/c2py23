"""pytest configuration for c2py23.  Builds all test .so files before
collection so that module-level imports in test files succeed.

Python 2.7 compatible (pytest 4.6.x).  Uses subprocess.Popen.
"""
from __future__ import print_function

import os
import sys
import subprocess

import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_DIR = os.path.join(PROJECT_DIR, "tests", "cases")
EXAMPLES_DIR = os.path.join(PROJECT_DIR, "examples")
RUNTIME_DIR = os.path.join(PROJECT_DIR, "c2py23", "runtime")

# Exclude container orchestrators from test collection
collect_ignore = ["test_all.py", "test_manylinux.py"]


def _module_name(c2py_path):
    """Extract module name from a .c2py file (YAML or Python dict format).
    
    Uses the same auto-detection order as load_c2py() in parser.py."""
    with open(c2py_path) as f:
        text = f.read()
    # Try Python dict format first (safe, no PyYAML needed)
    try:
        import ast
        data = ast.literal_eval(text)
        if isinstance(data, dict):
            return data.get('module')
    except (ValueError, SyntaxError):
        pass
    # Legacy YAML format fallback
    try:
        from c2py23.parser import _HAS_YAML
        if _HAS_YAML:
            import yaml as _yaml
            data = _yaml.safe_load(text)
            if isinstance(data, dict):
                return data.get('module')
    except Exception:
        pass
    return None


def _runtime_mtime():
    """Return the latest mtime of runtime source files (headers + runtime.c)."""
    latest = 0.0
    for name in os.listdir(RUNTIME_DIR):
        fpath = os.path.join(RUNTIME_DIR, name)
        if name.endswith((".h", ".c")) and os.path.isfile(fpath):
            m = os.path.getmtime(fpath)
            if m > latest:
                latest = m
    return latest


def _dirty(c2py_path):
    module = _module_name(c2py_path)
    if module is None:
        return False
    so_file = os.path.join(os.path.dirname(c2py_path), module + ".so")
    if not os.path.exists(so_file):
        return True
    so_mtime = os.path.getmtime(so_file)
    if os.path.getmtime(c2py_path) > so_mtime:
        return True
    if _runtime_mtime() > so_mtime:
        return True
    for name in sorted(os.listdir(os.path.dirname(c2py_path))):
        fpath = os.path.join(os.path.dirname(c2py_path), name)
        if name.endswith(".c") and os.path.isfile(fpath):
            if os.path.getmtime(fpath) > so_mtime:
                return True
    return False


def _build_one(c2py_path):
    proc = subprocess.Popen(
        [sys.executable, "-m", "c2py23.cli", "build", c2py_path],
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        msg = "Build failed for %s (exit %d)" % (c2py_path, proc.returncode)
        if stderr:
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            msg += "\n" + stderr
        print(msg, file=sys.stderr)
        sys.exit(1)


def _collect_c2py_files(base_dir):
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in sorted(files):
            if f.endswith(".c2py"):
                yield os.path.join(root, f)


def _build_all():
    """Build all .c2py modules (test cases + examples)."""
    built = 0
    for c2py_path in _collect_c2py_files(CASES_DIR):
        if _dirty(c2py_path):
            _build_one(c2py_path)
            built += 1
    for ex in ["kissfft_wrap", "lz4_wrap"]:
        ex_dir = os.path.join(EXAMPLES_DIR, ex)
        if os.path.isdir(ex_dir):
            for c2py_path in _collect_c2py_files(ex_dir):
                if _dirty(c2py_path):
                    _build_one(c2py_path)
                    built += 1
    if built:
        print("\n[c2py23 conftest] Built %d module(s)" % built)


def pytest_configure(config):
    """Build all .so files before pytest collects test modules.
    Module-level imports in test files need the .so files to exist.
    """
    _build_all()
