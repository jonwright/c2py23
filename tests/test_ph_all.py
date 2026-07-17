# -*- coding: utf-8 -*-
# tests/test_ph_all.py — run inside container: test dlsym + pythonh builds
"""Test that both dlsym (nimpy) and pythonh builds work for fill.c2py."""

from __future__ import print_function
import sys, os, subprocess, ctypes


def do_build(flag):
    cmd = [sys.executable, "-m", "c2py23.cli", "build"]
    if flag:
        cmd.append(flag)
    cmd.extend(["tests/cases/fill/fill.c2py", "-o", "/tmp/fill_%s.so" % (flag or "dlsym")])
    # Python 2.7 compat: use Popen instead of subprocess.run
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", "replace") if stderr else ""
        lines = err.strip().split("\n")
        raise RuntimeError(lines[-1] if lines else "build failed")


def load_and_test(path):
    sys.path.insert(0, "/tmp")
    v = sys.version_info
    if v[0] >= 3:
        import importlib.machinery, importlib.util

        l = importlib.machinery.ExtensionFileLoader("fillmod", path)
        s = importlib.util.spec_from_file_location("fillmod", path, loader=l)
        m = importlib.util.module_from_spec(s)
        l.exec_module(m)
    else:
        import imp

        m = imp.load_dynamic("fillmod", path)
    arr = (ctypes.c_float * 4)(0, 0, 0, 0)
    m.fill(arr, 42.0)
    if list(arr) != [42, 42, 42, 42]:
        raise RuntimeError("fill returned %s" % list(arr))


def main():
    ver = "%d.%d%s" % (
        sys.version_info.major,
        sys.version_info.minor,
        "t" if getattr(sys, "abiflags", "").startswith("t") else "",
    )
    results = []
    for mode, flag in [("dlsym", ""), ("pythonh", "--pythonh")]:
        try:
            do_build(flag)
            load_and_test("/tmp/fill_%s.so" % (flag or "dlsym"))
            results.append("%s:PASS" % mode)
        except Exception as e:
            msg = str(e).split("\n")[0][:80]
            results.append("%s:FAIL(%s)" % (mode, msg))
    print("  %-6s %s" % (ver, "  ".join(results)))


if __name__ == "__main__":
    main()
