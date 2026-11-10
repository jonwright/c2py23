"""Runtime symbols must be hidden: no C2PY*, c2py_*, _c2py_* exported.

Under sys.setdlopenflags(RTLD_GLOBAL) an exported C2PY table would make a
second c2py23 module bind to the first module's table.  Checks both the
dynamic symbol table (nm) and the behaviour (two modules, RTLD_GLOBAL).

Windows: a DLL exports nothing without dllexport, so there is no symbol
table to inspect and no RTLD_GLOBAL; the tests below are written for
ELF/Mach-O platforms and are not run on win32 (see _on_windows()).  On
Linux/macOS a missing `nm` is an error, not a skip.
"""

from __future__ import print_function

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(HERE)
CASES = os.path.join(HERE, "cases")
BUILD_DIR = os.path.join(HERE, "build", "visibility")

PREFIXES = ("C2PY", "c2py_", "_c2py_")


def _on_windows():
    return sys.platform in ("win32", "cygwin")


def _module_path(case, name):
    return os.path.join(CASES, case, name + (".pyd" if _on_windows() else ".so"))


def _exported(path):
    """Return the set of symbols the shared object exports."""
    if sys.platform == "darwin":
        cmd = ["nm", "-gU", path]
    else:
        cmd = ["nm", "-D", "--defined-only", path]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("nm failed on %s: %s" % (path, err.decode("utf-8", "replace")))
    syms = set()
    for line in out.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            sym = parts[-1]
            if sys.platform == "darwin" and sym.startswith("_"):
                sym = sym[1:]
            syms.add(sym)
    return syms


def _leaks(path):
    return sorted(s for s in _exported(path) if s.startswith(PREFIXES))


def _check_module(case, name, expect_present):
    if _on_windows():
        return
    path = _module_path(case, name)
    assert os.path.exists(path), "build the test modules first: " + path
    syms = _exported(path)
    leaked = sorted(s for s in syms if s.startswith(PREFIXES))
    assert not leaked, "%s exports runtime symbols: %s" % (name, leaked)
    for sym in expect_present:
        assert sym in syms, "%s should still export %s" % (name, sym)


def test_timing_module_hides_runtime():
    # timing enabled: also exercises the tick-frequency / cycle-counter globals
    _check_module("timing", "timedmod", ["weighted_sum"])


def test_cpu_flag_module_hides_runtime():
    # uses c2py_amd64.h / c2py_arm64.h / c2py_ppc64.h flags
    _check_module("simd_dispatch", "simd_fillmod", ["fill_scalar", "simd_fill_amd64_flag"])


def test_plain_module_hides_runtime():
    _check_module("arraysum", "arraysum", ["array_sum"])


_GLOBAL_SCRIPT = r"""
import ctypes, os, sys
sys.setdlopenflags(getattr(os, "RTLD_NOW", 2) | getattr(os, "RTLD_GLOBAL", 0x100))
sys.path.insert(0, %(arraysum)r)
sys.path.insert(0, %(timing)r)
import arraysum
import timedmod
a = (ctypes.c_double * 3)(1.0, 2.0, 3.0)
b = (ctypes.c_double * 3)(10.0, 20.0, 30.0)
r = (ctypes.c_double * 3)()
arraysum.array_sum(a, b, r)
assert list(r) == [11.0, 22.0, 33.0], list(r)
w = timedmod.wsum(a, 2.0)
assert w == 12.0, w
print("OK")
"""


def test_two_modules_rtld_global():
    if _on_windows():
        return
    script = _GLOBAL_SCRIPT % {
        "arraysum": os.path.join(CASES, "arraysum"),
        "timing": os.path.join(CASES, "timing"),
    }
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = proc.communicate()
    assert proc.returncode == 0, err.decode("utf-8", "replace")
    assert out.decode("utf-8", "replace").strip() == "OK"


def test_single_header_hides_runtime():
    if _on_windows():
        return
    sys.path.insert(0, HERE)
    try:
        import test_single_header as sh
    finally:
        sys.path.pop(0)
    if not os.path.isdir(BUILD_DIR):
        os.makedirs(BUILD_DIR)
    case = os.path.join(CASES, "arraysum")
    wrapper_c = os.path.join(BUILD_DIR, "vis_sh_wrapper.c")
    sh._c2py_generate(os.path.join(case, "arraysum.c2py"), wrapper_c, use_single_header=True)
    # Header next to the wrapper is found via the wrapper's own directory.
    so = sh._build_module(BUILD_DIR, wrapper_c, os.path.join(case, "arraysum.c"), "vis_sh.so")
    leaked = _leaks(so)
    assert not leaked, "single-header build exports: %s" % leaked
    assert "array_sum" in _exported(so)


if __name__ == "__main__":
    test_timing_module_hides_runtime()
    test_cpu_flag_module_hides_runtime()
    test_plain_module_hides_runtime()
    test_two_modules_rtld_global()
    test_single_header_hides_runtime()
    print("PASS: visibility")
