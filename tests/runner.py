#!/usr/bin/env python
"""c2py23 test runner -- generate, build, test.

Usage:
    python tests/runner.py              # Run all tests
    python tests/runner.py --no-build   # Skip build (use existing .so files)

Replaces tests/run_tests.sh, tests/build_all.sh, tests/run_tests_only.sh.
"""

from __future__ import print_function

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
RUNTIME = os.path.join(PROJECT, "c2py23", "runtime")


def _find_c2py_files(base_dir):
    """Yield all interface files (.c with C2PY_BEGIN, .c2py, .c2py.py)."""
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in sorted(files):
            if fn.endswith(".c2py") and not fn.endswith(".c2py.py"):
                yield os.path.join(root, fn)
            elif fn.endswith(".c") and not fn.endswith("_wrapper.c"):
                fp = os.path.join(root, fn)
                try:
                    with open(fp) as f:
                        if "C2PY_BEGIN" in f.read():
                            yield fp
                except Exception:
                    pass


def _module_name(c2py_path):
    """Parse interface to get module name -- try .c (C2PY_BEGIN), then .c2py."""
    with open(c2py_path) as f:
        text = f.read()

    # Check for embedded C2PY_BEGIN blocks in .c files
    if "C2PY_BEGIN" in text:
        try:
            from c2py23.harvester import extract_from_file

            data = extract_from_file(c2py_path)
            if isinstance(data, dict):
                name = data.get("module")
                if name:
                    return name
        except Exception:
            pass

    # Python dict format
    try:
        import ast
        import re

        data = ast.literal_eval(re.sub(r"(?m)^\s*#.*$", "", text))
        if isinstance(data, dict):
            name = data.get("module")
            if name:
                return name
    except Exception:
        pass

    # c2py parser (robust, handles all formats)
    try:
        from c2py23.parser import load_c2py

        return load_c2py(c2py_path).name
    except Exception:
        pass

    return None


def generate_all():
    """Generate wrapper .c files for all test modules and examples."""
    count = 0
    # Test cases
    cases_dir = os.path.join(HERE, "cases")
    for c2py_path in _find_c2py_files(cases_dir):
        mod = _module_name(c2py_path)
        if not mod:
            continue
        wrapper_c = os.path.join(os.path.dirname(c2py_path), mod + "_wrapper.c")
        if _needs_regen(c2py_path, wrapper_c):
            subprocess.check_call([sys.executable, "-m", "c2py23", c2py_path, "-o", wrapper_c])
            count += 1

    # Examples
    for ex_name in ("kissfft_wrap", "lz4_wrap"):
        ex_dir = os.path.join(PROJECT, "examples", ex_name)
        if os.path.isdir(ex_dir):
            for c2py_path in _find_c2py_files(ex_dir):
                mod = _module_name(c2py_path)
                if not mod:
                    continue
                wrapper_c = os.path.join(os.path.dirname(c2py_path), mod + "_wrapper.c")
                if _needs_regen(c2py_path, wrapper_c):
                    subprocess.check_call([sys.executable, "-m", "c2py23", c2py_path, "-o", wrapper_c])
                    count += 1

    if count:
        print("[runner] Generated %d wrapper(s)" % count)


def _needs_regen(c2py_path, wrapper_c):
    """Return True if wrapper needs (re)generation."""
    if not os.path.exists(wrapper_c):
        return True
    w_mtime = os.path.getmtime(wrapper_c)
    if os.path.getmtime(c2py_path) > w_mtime:
        return True
    # Check runtime headers
    for fn in os.listdir(RUNTIME):
        if fn.endswith((".h", ".c")):
            if os.path.getmtime(os.path.join(RUNTIME, fn)) > w_mtime:
                return True
    # Check source files in same directory
    case_dir = os.path.dirname(c2py_path)
    for fn in os.listdir(case_dir):
        if fn.endswith(".c"):
            if os.path.getmtime(os.path.join(case_dir, fn)) > w_mtime:
                return True
    return False


def build_all():
    """Build all dlsym .so files via vanilla C compilation (make)."""
    makefile = os.path.join(HERE, "Makefile")
    print("[runner] Building dlsym extensions (make)...")
    subprocess.check_call(["make", "-f", makefile, "all"], cwd=PROJECT)
    print("[runner] Build complete")


def build_pythonh():
    """Build all .so files via setuptools in pythonh mode."""
    setup_py = os.path.join(HERE, "setup.py")
    print("[runner] Building pythonh extensions...")
    subprocess.check_call(
        [sys.executable, setup_py, "build_ext", "--inplace", "--pythonh"],
        cwd=PROJECT,
    )
    print("[runner] Pythonh build complete")


def run_tests():
    """Run all pytest tests."""
    import pytest

    args = [
        "-v",
        "--durations=10",
        "--tb=short",
        "--ignore=" + os.path.join(HERE, "test_workspace"),
        HERE,
    ]
    if "--no-build" in sys.argv:
        args.append("--no-build")
    return pytest.main(args)


def main():
    no_build = "--no-build" in sys.argv
    no_test = "--no-test" in sys.argv
    pythonh = "--pythonh" in sys.argv

    print("=== c2py23 test runner ===")
    print("Python: %s" % sys.version.split()[0])

    if not no_build:
        generate_all()
        build_all()
        if pythonh:
            build_pythonh()

    if not no_test:
        sys.exit(run_tests())


if __name__ == "__main__":
    main()
