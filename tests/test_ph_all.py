# -*- coding: utf-8 -*-
# tests/test_ph_all.py  --  test dlsym + pythonh builds for fill.c2py
"""Build and load fill.c2py in both dlsym and pythonh modes.

Verifies that each mode loads from the correct .so file.
Run inside snakepit containers or locally.
"""

from __future__ import print_function

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _generate():
    """Generate fill wrapper."""
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "c2py23",
            os.path.join(HERE, "cases", "fill", "fill.c2py"),
            "-o",
            "fill_wrapper.c",
        ]
    )


def _build_dlsym():
    """Build in dlsym mode via shared setup.py."""
    env = os.environ.copy()
    env.setdefault("CC", "gcc")
    env.setdefault("LIBS", "-ldl -lm")
    env.setdefault("LDSHARED", "gcc -shared")
    # Only build fillmod (not all modules)
    subprocess.check_call(
        [
            sys.executable,
            "-c",
            "\n".join(
                [
                    "from setuptools import setup, Extension",
                    "from c2py23.build import DlsymCmdclass",
                    "setup(name='fill_test',",
                    "      ext_modules=[Extension('fillmod',",
                    "          ['fill_wrapper.c', 'tests/cases/fill/fill.c',",
                    "           'c2py23/runtime/c2py_runtime.c'],",
                    "          include_dirs=['c2py23/runtime', 'tests/cases/fill'])],",
                    "      cmdclass=DlsymCmdclass,",
                    "      script_args=['build_ext'])",
                ]
            ),
        ],
        env=env,
    )


def _build_pythonh():
    """Build in pythonh mode."""
    subprocess.check_call(
        [
            sys.executable,
            "-c",
            "\n".join(
                [
                    "from setuptools import setup, Extension",
                    "from c2py23.build import PythonhCmdclass",
                    "setup(name='fill_ph_test',",
                    "      ext_modules=[Extension('fillmod',",
                    "          ['fill_wrapper.c', 'tests/cases/fill/fill.c',",
                    "           'c2py23/runtime/c2py_runtime.c'],",
                    "          include_dirs=['c2py23/runtime', 'tests/cases/fill'])],",
                    "      cmdclass=PythonhCmdclass,",
                    "      script_args=['build_ext'])",
                ]
            ),
        ]
    )


def load_and_check(path, expected_basename):
    """Load and test fill from path, verify correct .so file."""
    import ctypes

    v = sys.version_info
    if v[0] >= 3:
        import importlib.machinery
        import importlib.util

        loader = importlib.machinery.ExtensionFileLoader("fillmod", path)
        spec = importlib.util.spec_from_file_location("fillmod", path, loader=loader)
        if spec is None:
            raise RuntimeError("Could not create spec for %s" % path)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    else:
        import imp

        mod = imp.load_dynamic("fillmod", path)

    # Verify loading from the right .so
    actual = os.path.basename(mod.__file__)
    if actual != expected_basename:
        raise RuntimeError(
            "Wrong .so loaded: expected '%s', got '%s' (path: %s)" % (expected_basename, actual, mod.__file__)
        )

    arr = (ctypes.c_float * 4)(0, 0, 0, 0)
    mod.fill(arr, 42.0)
    if list(arr) != [42.0, 42.0, 42.0, 42.0]:
        raise RuntimeError("fill returned %s" % list(arr))
    return mod.__file__


def main():
    ver = "%d.%d%s" % (
        sys.version_info.major,
        sys.version_info.minor,
        "t" if getattr(sys, "abiflags", "").startswith("t") else "",
    )
    results = []

    # Generate wrapper once
    _generate()

    # ---- Dlsym build ----
    try:
        _build_dlsym()
        import glob

        candidates = glob.glob("build/lib.*/fillmod.so")
        dlsym_path = os.path.join(os.path.dirname(__file__), "cases", "fill", "fillmod.dlsym_test.so")
        if candidates:
            shutil.copy2(candidates[0], dlsym_path)
        load_and_check(dlsym_path, "fillmod.dlsym_test.so")
        results.append("dlsym:PASS")
    except Exception as e:
        msg = str(e).split("\n")[0][:80]
        results.append("dlsym:FAIL(%s)" % msg)

    # ---- Pythonh build ----
    try:
        _build_pythonh()
        import glob
        import sysconfig

        ext = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
        candidates = glob.glob("build/lib.*/fillmod" + ext)
        pythonh_path = os.path.join(os.path.dirname(__file__), "cases", "fill", "fillmod.pythonh_test" + ext)
        if candidates:
            shutil.copy2(candidates[0], pythonh_path)
        load_and_check(pythonh_path, "fillmod.pythonh_test" + ext)
        results.append("pythonh:PASS")
    except Exception as e:
        msg = str(e).split("\n")[0][:80]
        results.append("pythonh:FAIL(%s)" % msg)

    # Cleanup
    for f in ["fill_wrapper.c"]:
        if os.path.exists(f):
            os.unlink(f)

    print("  %-6s %s" % (ver, "  ".join(results)))
    if any("FAIL" in r for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
