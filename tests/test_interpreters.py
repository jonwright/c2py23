#!/usr/bin/env python3
"""Verify that Python interpreters in the snakepit container are correct.

Checks that python3.14 (GIL-enabled) and python3.14t (free-threaded)
both exist and report the expected build types.
"""
from __future__ import print_function

import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SNAKEPIT_DIR = os.path.join(os.path.dirname(PROJECT_DIR), 'snakepit')
SIF_FILE = os.path.join(SNAKEPIT_DIR, 'ubuntu24.04.sif')


def check_interpreter(py_exe, expected_gil_disabled):
    """Check one interpreter inside the container."""
    script = (
        "import json, sys, sysconfig, struct;"
        "r = {};"
        "r['v'] = sys.version.split(chr(10))[0];"
        "r['ft'] = 1 if sysconfig.get_config_var('Py_GIL_DISABLED') else 0;"
        "r['vp'] = struct.calcsize('P');"
        "r['n'] = struct.calcsize('n');"
        "print(json.dumps(r))"
    )
    cmd = [
        "apptainer", "exec", "-e",
        SIF_FILE,
        py_exe, "-c", script
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        stdout = stdout.decode('utf-8', errors='replace') if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode('utf-8', errors='replace') if isinstance(stderr, bytes) else stderr
    except Exception as e:
        return False, "Error: {0}".format(e), {}

    if proc.returncode != 0:
        return False, "Exit {0}: {1}".format(proc.returncode, stderr[:200]), {}

    try:
        data = json.loads(stdout.strip().split('\n')[-1])
    except Exception:
        return False, "Parse error: {0}".format(stdout[:200]), {}

    actual_ft = data.get('ft', -1)
    ok = (actual_ft == (1 if expected_gil_disabled else 0))
    return ok, data, {}


def main():
    print("=== Interpreter Verification ===\n")

    if not os.path.exists(SIF_FILE):
        print("SKIP: container not found at {0}".format(SIF_FILE))
        return 0

    tests = [
        ("python3.14", False, "standard (GIL-enabled)"),
        ("python3.14t", True, "free-threaded (GIL-disabled)"),
    ]

    passed = 0
    failed = 0
    for py_exe, expected_ft, desc in tests:
        print("{0} ({1})...".format(py_exe, desc))
        ok, data, _ = check_interpreter(py_exe, expected_ft)

        if ok and data:
            print("  Version: {0}".format(data.get('v', '?')))
            print("  Free-threaded: {0}".format('yes' if data.get('ft') else 'no'))
            print("  sizeof(void*): {0}".format(data.get('vp', '?')))
            print("  sizeof(Py_ssize_t): {0}".format(data.get('n', '?')))
            print("  PASS")
            passed += 1
        elif ok is False and isinstance(data, dict) and data:
            print("  Version: {0}".format(data.get('v', '?')))
            print("  Free-threaded: {0}".format('yes' if data.get('ft') else 'no'))
            print("  FAIL: wrong GIL state (expected ft={0})".format(expected_ft))
            failed += 1
        else:
            print("  FAIL: {0}".format(data))
            failed += 1
        print()

    print("Result: {0}/{1} passed".format(passed, passed + failed))
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
