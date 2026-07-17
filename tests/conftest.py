"""pytest configuration for c2py23.  Generates wrapper .c files from .c2py
interfaces and builds .so extensions via setuptools before test collection.

Python 2.7 compatible (pytest 4.6.x).  Uses subprocess.Popen.
"""

from __future__ import print_function

import os
import sys
import subprocess

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_DIR = os.path.join(PROJECT_DIR, "tests", "cases")
EXAMPLES_DIR = os.path.join(PROJECT_DIR, "examples")
RUNTIME_DIR = os.path.join(PROJECT_DIR, "c2py23", "runtime")

# Exclude container orchestrators from test collection
collect_ignore = ["test_all.py", "test_manylinux.py", "test_ph_ci_27.py", "test_ph_ci_314t.py"]


def _runtime_mtime():
    """Return the latest mtime of runtime source files."""
    latest = 0.0
    for name in os.listdir(RUNTIME_DIR):
        fpath = os.path.join(RUNTIME_DIR, name)
        if name.endswith((".h", ".c")) and os.path.isfile(fpath):
            m = os.path.getmtime(fpath)
            if m > latest:
                latest = m
    return latest


def _find_module_name(c2py_path):
    """Extract module name from a .c2py file."""
    with open(c2py_path) as f:
        text = f.read()
    try:
        import ast
        import re

        stripped = re.sub(r"(?m)^\s*#.*$", "", text)
        data = ast.literal_eval(stripped)
        if isinstance(data, dict):
            return data.get("module")
    except (ValueError, SyntaxError):
        pass
    try:
        from c2py23.parser import _HAS_YAML

        if _HAS_YAML:
            import yaml as _yaml

            data = _yaml.safe_load(text)
            if isinstance(data, dict):
                return data.get("module")
    except Exception:
        pass
    return None


def _dirty(c2py_path):
    """Return True if the wrapper or .so needs rebuilding."""
    module = _find_module_name(c2py_path)
    if module is None:
        return False
    c2py_dir = os.path.dirname(c2py_path)
    wrapper_c = os.path.join(c2py_dir, module + "_wrapper.c")
    so_file = os.path.join(c2py_dir, module + ".so")
    if not os.path.exists(so_file) or not os.path.exists(wrapper_c):
        return True
    so_mtime = os.path.getmtime(so_file)
    if os.path.getmtime(c2py_path) > so_mtime:
        return True
    if _runtime_mtime() > so_mtime:
        return True
    for name in sorted(os.listdir(c2py_dir)):
        fpath = os.path.join(c2py_dir, name)
        if name.endswith(".c") and os.path.isfile(fpath):
            if os.path.getmtime(fpath) > so_mtime:
                return True
    return False


def _generate_one(c2py_path):
    """Generate wrapper .c from a .c2py file."""
    module = _find_module_name(c2py_path)
    if module is None:
        return
    wrapper_c = os.path.join(os.path.dirname(c2py_path), module + "_wrapper.c")
    proc = subprocess.Popen(
        [sys.executable, "-m", "c2py23.cli", c2py_path, "-o", wrapper_c],
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        msg = "Generate failed for %s (exit %d)" % (c2py_path, proc.returncode)
        if stderr:
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            msg += "\n" + stderr
        print(msg, file=sys.stderr)
        sys.exit(1)


def _build_all_dlsym():
    """Build all dirty .so files via setuptools in dlsym mode, then copy to source dirs."""
    import glob
    import shutil

    setup_py = os.path.join(PROJECT_DIR, "tests", "setup.py")
    env = os.environ.copy()
    env.setdefault("CC", "gcc")
    env.setdefault("LIBS", "-ldl -lm")
    env.setdefault("LDSHARED", env.get("CC", "gcc") + " -shared")

    proc = subprocess.Popen(
        [sys.executable, setup_py, "build_ext", "--inplace"],
        cwd=PROJECT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        msg = "Build failed (exit %d)" % proc.returncode
        if stderr:
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            msg += "\n" + stderr
        print(msg, file=sys.stderr)
        sys.exit(1)

    print("[c2py23 conftest] Build complete")


def _build_all():
    """Generate all wrappers, then build all .so files."""
    built = 0
    for root, dirs, files in os.walk(CASES_DIR):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in sorted(files):
            if f.endswith(".c2py") and not f.endswith(".c2py.py"):
                c2py_path = os.path.join(root, f)
                if _dirty(c2py_path):
                    _generate_one(c2py_path)
                    built += 1

    for ex in ["kissfft_wrap", "lz4_wrap"]:
        ex_dir = os.path.join(EXAMPLES_DIR, ex)
        if os.path.isdir(ex_dir):
            for root, dirs, files in os.walk(ex_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in sorted(files):
                    if f.endswith(".c2py") and not f.endswith(".c2py.py"):
                        c2py_path = os.path.join(root, f)
                        if _dirty(c2py_path):
                            _generate_one(c2py_path)
                            built += 1

    if built:
        print("\n[c2py23 conftest] Generated %d wrapper(s)" % built)
        _build_all_dlsym()


def pytest_configure(config):
    """Generate wrappers and build .so files before test collection."""
    _build_all()
