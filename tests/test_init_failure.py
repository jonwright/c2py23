"""A failing c2py_runtime_init() surfaces as ImportError with the reason
(review finding B10), not as SystemError with the reason on stderr.

Builds its own copy of tests/cases/ptralign in a temporary directory with
-DC2PY_TEST_FORCE_INIT_FAIL, which makes the runtime fail early in
_c2py_runtime_init_once(), and imports it in a subprocess.  The normal
test modules are not affected: the macro is defined only here.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
RUNTIME = os.path.join(PROJECT, "c2py23", "runtime")
CASE = os.path.join(HERE, "cases", "ptralign")

_IMPORT = """
import sys
sys.path.insert(0, %r)
try:
    import ptralignmod
except ImportError as e:
    print("ImportError: %%s" %% e)
    sys.exit(0)
except BaseException as e:
    print("%%s: %%s" %% (type(e).__name__, e))
    sys.exit(2)
print("imported")
sys.exit(1)
"""


def _run(cmd, cwd=None, env=None):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env)
    out = proc.communicate()[0]
    return proc.returncode, out.decode("utf-8", "replace")


def _build(tmp):
    env = dict(os.environ)
    env["PYTHONPATH"] = PROJECT + os.pathsep + env.get("PYTHONPATH", "")
    wrapper = os.path.join(tmp, "ptralignmod_wrapper.c")
    rc, out = _run([sys.executable, "-m", "c2py23", os.path.join(CASE, "ptralign.c2py"), "-o", wrapper], env=env)
    assert rc == 0, out
    cc = os.environ.get("CC", "gcc")
    srcs = [wrapper, os.path.join(CASE, "ptralign.c"), os.path.join(RUNTIME, "c2py_runtime.c")]
    if os.path.basename(cc).lower() in ("cl", "cl.exe"):
        target = os.path.join(tmp, "ptralignmod.pyd")
        cmd = [cc, "/nologo", "/LD", "/DC2PY_TEST_FORCE_INIT_FAIL", "/I" + RUNTIME, "/I" + CASE]
        cmd += srcs + ["/Fe" + target]
    else:
        target = os.path.join(tmp, "ptralignmod.so")
        cmd = [cc, "-O1", "-Wall", "-fPIC", "-shared", "-DC2PY_TEST_FORCE_INIT_FAIL"]
        cmd += ["-I" + RUNTIME, "-I" + CASE] + srcs + ["-o", target, "-ldl", "-lm"]
    rc, out = _run(cmd, cwd=tmp)
    assert rc == 0 and os.path.exists(target), "build failed:\n" + out
    return target


def test_init_failure_raises_import_error_with_reason():
    tmp = tempfile.mkdtemp(prefix="c2py_initfail_")
    try:
        _build(tmp)
        rc, out = _run([sys.executable, "-c", _IMPORT % tmp])
        assert rc == 0, "expected ImportError, got rc=%d:\n%s" % (rc, out)
        assert out.startswith("ImportError: "), out
        assert "cannot import ptralignmod" in out, out
        assert "forced init failure" in out, out
    finally:
        shutil.rmtree(tmp, True)
    print("PASS: init failure raises ImportError with reason")


if __name__ == "__main__":
    test_init_failure_raises_import_error_with_reason()
