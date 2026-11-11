"""Prelude for subprocess snippets that load a c2py23 test extension module.

PyPy's import system does not find a non-ABI-tagged .so via a plain
`import modname` (it only recognises ABI-tagged suffixes).  The snippets
below run as `python -c` in a child process, so they cannot use the
parent's conftest.py preloader.  This module builds a small, self-contained
prelude that finds the extension file and loads it explicitly, using the
same code path on CPython and PyPy.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

_PRELUDE = """import glob, os, sys


def c2py_load(modname, dirname):
    '''Load a c2py23 test extension module named modname from directory dirname.

    Finds the extension file, accepting a plain .so/.pyd name or an ABI-tagged
    name (e.g. mod.cpython-312-x86_64-linux-gnu.so or mod.cp312-win_amd64.pyd),
    then loads it with importlib.machinery.ExtensionFileLoader on Python 3 or
    imp.load_dynamic on Python 2.  Works on CPython and PyPy alike; module init
    errors (for example a forced c2py runtime init failure) propagate unchanged.
    '''
    ext = ".pyd" if sys.platform == "win32" else ".so"
    plain = os.path.join(dirname, modname + ext)
    path = plain if os.path.exists(plain) else None
    if path is None:
        matches = [p for p in glob.glob(os.path.join(dirname, modname + ".*"))
                   if p.endswith((".so", ".pyd"))]
        if matches:
            matches.sort(key=lambda p: p.count("."), reverse=True)
            path = matches[0]
    if path is None:
        raise ImportError("cannot import " + modname)
    if sys.version_info[0] >= 3:
        import importlib.machinery as im
        import importlib.util as iu
        loader = im.ExtensionFileLoader(modname, path)
        spec = iu.spec_from_file_location(modname, path, loader=loader)
        mod = iu.module_from_spec(spec)
        sys.modules[modname] = mod
        loader.exec_module(mod)
        return mod
    import imp
    mod = imp.load_dynamic(modname, path)
    sys.modules[modname] = mod
    return mod
"""


def extload_prelude():
    """Return the source of a prelude defining c2py_load(), to splice into a
    subprocess snippet that runs as ``python -c``."""
    return _PRELUDE
