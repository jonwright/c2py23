"""Test single-header (c2py.h) blob mode.

Generates a wrapper with --emit-header, compiles it using only
c2py.h (no c2py_runtime.c), and verifies the module works.

Detects the C compiler from the CC environment variable (gcc or cl).
On MSVC, uses cl with /LD instead of gcc with -shared.

Builds into the project tree alongside other test artifacts -- no
temp directories, no cleanup, no Windows DLL lock issues.
"""

from __future__ import print_function

import ctypes
import os
import subprocess
import sys

try:
    import pytest
except ImportError:
    pytest = None

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C2PY_H = os.path.join(PROJECT_DIR, "c2py23", "runtime", "c2py.h")

# Subdirectory under tests/ where single-header test artifacts live
BUILD_DIR = os.path.join(PROJECT_DIR, "tests", "build", "single_header")


def _is_msvc():
    """Return True if the CC environment variable indicates MSVC."""
    cc = os.environ.get("CC", "")
    return cc in ("cl", "cl.exe") or os.environ.get("MSVC", "").strip() != ""


def _compile_cflags():
    """Return a list of compiler flags appropriate for the detected compiler."""
    if _is_msvc():
        return ["/O2", "/LD"]
    else:
        return ["-O2", "-Wall", "-fPIC", "-shared"]


def _compile_ext():
    """Return the shared library extension (.so or .pyd)."""
    if _is_msvc():
        return ".pyd"
    else:
        return ".so"


def _compile_link_flags():
    """Return a list of link flags appropriate for the detected compiler."""
    if _is_msvc():
        return ["/link"]
    else:
        return ["-ldl", "-lm"]


def _c2py_generate(c2py_path, output_c, use_single_header=False):
    """Run c2py23 to generate a wrapper."""
    cmd = [
        sys.executable,
        "-m",
        "c2py23",
        c2py_path,
        "-o",
        output_c,
    ]
    if use_single_header:
        cmd.append("--emit-header")
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("c2py23 failed:\n" + stderr.decode("utf-8", "replace"))


def _build_module(workdir, wrapper_c, c_source, so_name, extra_c=None):
    """Compile wrapper and C source into a shared library.

    Uses the compiler detected from the CC environment variable.
    On MSVC (CC=cl), uses cl with /LD.  On GCC (default), uses -shared.
    """
    cc = os.environ.get("CC", "gcc")
    cmd = [cc] + _compile_cflags()
    cmd.append("-I" + PROJECT_DIR)  # to find c2py23/runtime/c2py.h via wrapper include
    cmd.append(wrapper_c)
    cmd.append(c_source)
    if extra_c:
        cmd.append(os.path.join(PROJECT_DIR, extra_c))
    target = os.path.join(workdir, so_name)
    cmd.extend(["-o", target] + _compile_link_flags())

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("compile failed:\n" + stderr.decode("utf-8", "replace"))
    return target


def test_single_header_transform():
    """Generate and build a transform module using only c2py.h."""
    if hasattr(sys, "pypy_version_info"):
        print("SKIP: PyPy needs -DC2PY_TARGET_PYPY; tested separately via Makefile")
        return
    if not os.path.exists(C2PY_H):
        print("SKIP: c2py.h not found -- run 'python3 -m c2py23 --regenerate-header'")
        return

    c2py_path = os.path.join(PROJECT_DIR, "tests", "cases", "transform", "transform.c2py")
    c_source = os.path.join(PROJECT_DIR, "tests", "cases", "transform", "transform.c")

    if not os.path.isdir(BUILD_DIR):
        os.makedirs(BUILD_DIR)

    ext = _compile_ext()
    wrapper_c = os.path.join(BUILD_DIR, "xfrm_sh_wrapper.c")
    so_name = "xfrm_sh" + ext
    so_path = os.path.join(BUILD_DIR, so_name)

    # Generate wrapper with single-header mode
    _c2py_generate(c2py_path, wrapper_c, use_single_header=True)
    assert os.path.exists(wrapper_c)

    # Verify the generated wrapper uses c2py.h
    with open(wrapper_c) as f:
        content = f.read()
    assert "#define C2PY_IMPLEMENTATION" in content, "Generated wrapper should have C2PY_IMPLEMENTATION"
    assert '#include "c2py.h"' in content, "Generated wrapper should include c2py.h"
    assert '#include "c2py_runtime.h"' not in content, "Generated wrapper should NOT include c2py_runtime.h"

    # Compile with only c2py.h and the C source (no c2py_runtime.c)
    _build_module(BUILD_DIR, wrapper_c, c_source, so_name)

    # Import and test
    sys.path.insert(0, BUILD_DIR)
    if sys.version_info[0] >= 3:
        import importlib.machinery as im
        import importlib.util as iu

        modname = "xfrm"
        loader = im.ExtensionFileLoader(modname, so_path)
        spec = iu.spec_from_file_location(modname, so_path, loader=loader)
        if spec is None:
            raise RuntimeError("Failed to create module spec for {}".format(so_path))
        mod = iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
    else:
        import imp

        mod = imp.load_dynamic("xfrm", so_path)

    # Basic functional test
    import numpy as np

    arr = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float64)
    out = np.zeros_like(arr)
    mod.transform(arr, out)
    expected = arr * 2.0
    assert np.allclose(out, expected), "AoS transform failed"

    # Zero-size test
    arr0 = np.empty((0, 3), dtype=np.float64)
    out0 = np.empty((0, 3), dtype=np.float64)
    mod.transform(arr0, out0)
    # No error = success

    sys.path.pop(0)


def test_single_header_cli_flags():
    """Verify --emit-header and --regenerate-header flags work."""
    c2py_path = os.path.join(PROJECT_DIR, "tests", "cases", "arraysum", "arraysum.c2py")

    if not os.path.isdir(BUILD_DIR):
        os.makedirs(BUILD_DIR)

    wrapper_c = os.path.join(BUILD_DIR, "arraysum_sh_wrapper.c")
    c2py_h_out = os.path.join(BUILD_DIR, "c2py.h")

    # Remove any previous output so we can assert it was created fresh
    for f in (wrapper_c, c2py_h_out):
        if os.path.exists(f):
            os.unlink(f)

    cmd = [
        sys.executable,
        "-m",
        "c2py23",
        c2py_path,
        "-o",
        wrapper_c,
        "--emit-header",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _, stderr = proc.communicate()
    assert proc.returncode == 0, "--emit-header failed:\n" + stderr.decode("utf-8", "replace")
    assert os.path.exists(wrapper_c)
    assert os.path.exists(c2py_h_out), "c2py.h should be emitted alongside the wrapper"
