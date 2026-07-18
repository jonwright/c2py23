"""pytest configuration for c2py23.  Generates wrapper .c files and
builds .so extensions before test collection.

Delegates to tests/runner.py for the heavy lifting.
Python 2.7 compatible.  Uses subprocess.Popen.
"""

from __future__ import print_function

import os
import sys
import subprocess

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(PROJECT_DIR, "tests", "runner.py")

# Exclude container orchestrators from test collection
collect_ignore = [
    "test_all.py",
    "test_manylinux.py",
    "runner.py",
]


def _build_all():
    """Generate wrappers and build .so files via runner."""
    if "--no-build" in sys.argv:
        return
    proc = subprocess.Popen(
        [sys.executable, RUNNER, "--no-test"],
        cwd=PROJECT_DIR,
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


def _preload_modules():
    """Preload all .so/.pyd modules via importlib for PyPy compatibility.

    PyPy's import system does not find .so files via sys.path the same
    way CPython does.  Pre-loading into sys.modules before collection
    ensures tests can use plain 'import modname'.
    """
    import glob

    cases_dir = os.path.join(PROJECT_DIR, "tests", "cases")
    examples_dir = os.path.join(PROJECT_DIR, "examples")
    so_files = glob.glob(os.path.join(cases_dir, "*", "*.so"))
    so_files.extend(glob.glob(os.path.join(examples_dir, "*", "*.so")))
    so_files.extend(glob.glob(os.path.join(PROJECT_DIR, "benchmarks", "build", "*.so")))
    for so_path in so_files:
        modname = os.path.basename(so_path)[:-3]
        if modname in sys.modules:
            continue
        try:
            if sys.version_info[0] >= 3:
                import importlib.util as iu
                import importlib.machinery as im

                loader = im.ExtensionFileLoader(modname, so_path)
                spec = iu.spec_from_file_location(modname, so_path, loader=loader)
                if spec:
                    mod = iu.module_from_spec(spec)
                    sys.modules[modname] = mod
                    loader.exec_module(mod)
            else:
                import imp

                mod = imp.load_dynamic(modname, so_path)
                sys.modules[modname] = mod
        except Exception:
            pass


def pytest_configure(config):
    """Build .so files then preload modules before test collection."""
    _build_all()
    _preload_modules()
