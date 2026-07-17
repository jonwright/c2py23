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
    "test_ph_ci_27.py",
    "test_ph_ci_314t.py",
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


def pytest_configure(config):
    """Build .so files before test collection."""
    _build_all()
