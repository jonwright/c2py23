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

# Optional call-coverage instrumentation, enabled by C2PY_CALL_INVENTORY=1.
# Records which exposed module functions were actually invoked during the
# run, so tools/call_inventory.py can report exposed-but-never-called gaps.
_CALL_COVERAGE = {}  # modname -> set of attribute names called


def _call_coverage_enabled():
    return os.environ.get("C2PY_CALL_INVENTORY") == "1"


def _record_call(modname, attr):
    if _call_coverage_enabled():
        _CALL_COVERAGE.setdefault(modname, set()).add(attr)


def _wrap_callables(modname, module):
    """Wrap every exposed callable with a recorder that passes through."""
    for attr in dir(module):
        if attr.startswith("__"):
            continue
        try:
            obj = getattr(module, attr)
        except Exception:
            continue
        if not callable(obj):
            continue

        def make_wrapper(_attr=attr, _obj=obj, _mod=modname):
            def _w(*args, **kwargs):
                _record_call(_mod, _attr)
                return _obj(*args, **kwargs)

            # Preserve the metadata that c2py23.perf and docstring tests read
            # off the function object, so wrapping does not break them.
            for _k in ("__doc__", "__name__", "__module__", "__text_signature__", "__qualname__"):
                _v = getattr(_obj, _k, None)
                if _v is not None:
                    try:
                        setattr(_w, _k, _v)
                    except (TypeError, AttributeError):
                        pass
            for _k, _v in getattr(_obj, "__dict__", {}).items():
                try:
                    setattr(_w, _k, _v)
                except (TypeError, AttributeError):
                    pass
            return _w

        try:
            setattr(module, attr, make_wrapper())
        except (TypeError, AttributeError):
            pass


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
    loaded = []
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
                    loaded.append((modname, mod))
            else:
                import imp

                mod = imp.load_dynamic(modname, so_path)
                sys.modules[modname] = mod
                loaded.append((modname, mod))
        except Exception:
            pass
    return loaded


def _write_call_inventory():
    if not _call_coverage_enabled():
        return
    import json

    out = os.path.join(PROJECT_DIR, "tests", ".call_coverage.json")
    data = {}
    for modname, called in sorted(_CALL_COVERAGE.items()):
        data[modname] = sorted(called)
    with open(out, "w") as f:
        json.dump(data, f, indent=1)
    print("[call-inventory] wrote %s (%d modules)" % (out, len(data)))


def pytest_configure(config):
    """Build .so files then preload modules before test collection."""
    _build_all()
    loaded = _preload_modules()
    if _call_coverage_enabled():
        for modname, mod in loaded:
            _wrap_callables(modname, mod)


def pytest_sessionfinish(session, exitstatus):
    _write_call_inventory()
