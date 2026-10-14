"""Generated wrappers and the runtime stay inside the C89-style subset.

Our portability floor is MSVC 2008 (VC9, the Python 2.7 compiler), whose C
front end is C89: every declaration must precede the first statement of its
block.  gcc cannot see MSVC-only branches, but it can enforce this rule on
everything it does compile, so every interface under tests/cases and
examples is generated and syntax-checked with -Wdeclaration-after-statement.

Needs gcc (or clang) via the CC environment variable; defaults to gcc,
and also when CC is MSVC's cl (the check is a gcc-only warning).
Builds into tests/build/c89 -- nothing is written next to the sources.
"""

from __future__ import print_function

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
RUNTIME = os.path.join(PROJECT, "c2py23", "runtime")
BUILD_DIR = os.path.join(HERE, "build", "c89")

sys.path.insert(0, HERE)
import runner  # noqa: E402

WARNING = "declaration-after-statement"


def _checker():
    """gcc/clang for the check: CC unless it names MSVC, whose flags differ."""
    cc = os.environ.get("CC", "gcc")
    if os.path.basename(cc).lower() in ("cl", "cl.exe"):
        return "gcc"
    return cc


def _run(cmd, cwd=None):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)
    out = proc.communicate()[0]
    return proc.returncode, out.decode("utf-8", "replace")


def _interfaces():
    found = []
    for base in ("tests/cases", "examples"):
        found.extend(runner._find_c2py_files(os.path.join(PROJECT, base)))
    return found


def test_wrappers_are_c89_declarations():
    cc = _checker()
    if not os.path.isdir(BUILD_DIR):
        os.makedirs(BUILD_DIR)
    interfaces = _interfaces()
    assert interfaces, "no interface files found"

    problems = []
    checked = 0
    for path in interfaces:
        name = os.path.relpath(path, PROJECT).replace(os.sep, "_")
        wrapper = os.path.join(BUILD_DIR, name + "_wrapper.c")
        rc, out = _run([sys.executable, "-m", "c2py23", path, "-o", wrapper], cwd=PROJECT)
        assert rc == 0, "generator failed for %s:\n%s" % (path, out)

        cmd = [cc, "-std=c99", "-fsyntax-only", "-W", "-Wdeclaration-after-statement"]
        cmd += ["-I" + RUNTIME, "-I" + os.path.dirname(path), "-I" + PROJECT, wrapper]
        rc, out = _run(cmd)
        if WARNING in out:
            problems.append("%s:\n%s" % (os.path.relpath(path, PROJECT), out))
        elif rc == 0:
            checked += 1
        elif "No such file or directory" not in out:
            # A missing vendored header (kissfft, lz4) stops gcc before it
            # reads the body; anything else is a real compile error.
            problems.append("%s: compile error:\n%s" % (os.path.relpath(path, PROJECT), out))

    assert not problems, "\n".join(problems)
    assert checked >= 20, "only %d wrappers compiled cleanly" % checked
    print("PASS: c89 wrappers (%d interfaces checked)" % checked)


def test_runtime_is_c89_declarations():
    """c2py_runtime.c, which pulls in c2py_dlsym.c."""
    cc = _checker()
    src = "c2py_runtime.c"
    cmd = [cc, "-std=c99", "-fsyntax-only", "-Wdeclaration-after-statement", "-I" + RUNTIME]
    cmd.append(os.path.join(RUNTIME, src))
    rc, out = _run(cmd)
    assert WARNING not in out, "%s:\n%s" % (src, out)
    assert rc == 0, "%s failed to compile:\n%s" % (src, out)
    print("PASS: c89 runtime")


if __name__ == "__main__":
    test_wrappers_are_c89_declarations()
    test_runtime_is_c89_declarations()
