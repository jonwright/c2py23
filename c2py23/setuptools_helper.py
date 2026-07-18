"""c2py23 setuptools helper -- for pythonh mode ONLY.

Dlsym mode uses vanilla C compilation (gcc/clang/cl).  See
tests/Makefile for a dlsym build example, or the cmake/meson
demos in examples/.

Usage (pythonh):
    from c2py23.setuptools_helper import PythonhCmdclass
    setup(..., cmdclass=PythonhCmdclass)
"""

from __future__ import print_function

from distutils.command.build_ext import build_ext

from setuptools import Extension


class PythonhBuildExt(build_ext):
    """Build extensions in pythonh mode: #include <Python.h>, link libpython.

    Adds -DC2PY_USE_PYTHON_H to every extension.
    Returns platform-native ABI-tagged filenames.
    """

    def build_extensions(self):
        for ext in self.extensions:
            if ext.extra_compile_args is None or "-DC2PY_USE_PYTHON_H" not in ext.extra_compile_args:
                if not ext.extra_compile_args:
                    ext.extra_compile_args = []
                ext.extra_compile_args.append("-DC2PY_USE_PYTHON_H")
        build_ext.build_extensions(self)


PythonhCmdclass = {"build_ext": PythonhBuildExt}


def discover_modules(scan_dir, runtime_dir):
    """Return setuptools Extension objects for all c2py23 modules.

    Walks scan_dir for interface definitions: .c files with embedded
    C2PY_BEGIN blocks, or .c2py files.  Builds Extension lists that
    include the generated _wrapper.c + runtime.c + user sources.
    """
    import os

    extensions = []
    runtime_c = os.path.join(runtime_dir, "c2py_runtime.c")
    runtime_include = runtime_dir

    for root, dirs, files in os.walk(scan_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        interface_paths = []
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            if fn.endswith(".c") and not fn.endswith("_wrapper.c"):
                try:
                    with open(fp) as f:
                        if "C2PY_BEGIN" in f.read():
                            interface_paths.append(fp)
                except Exception:
                    pass
            elif fn.endswith(".c2py") and not fn.endswith(".c2py.py"):
                interface_paths.append(fp)

        for interface_path in interface_paths:
            try:
                module, sources, includes = _parse_c2py(interface_path)
            except Exception:
                continue

            if module is None:
                continue

            wrapper_c = os.path.join(os.path.dirname(interface_path), module + "_wrapper.c")
            if not os.path.exists(wrapper_c):
                continue

            c_sources = [src for src in sources if src.endswith(".c")]
            if not c_sources:
                continue

            all_sources = [wrapper_c, runtime_c] + c_sources
            all_includes = [runtime_include] + includes

            ext = Extension(module, all_sources, include_dirs=all_includes)
            extensions.append(ext)

    return extensions


def _parse_c2py(c2py_path):
    """Parse a .c2py file and return (module_name, sources, include_dirs)."""
    import os

    try:
        from c2py23.parser import load_c2py

        m = load_c2py(c2py_path)
    except Exception:
        return None, [], []

    base_dir = os.path.dirname(os.path.abspath(c2py_path))
    sources = [os.path.normpath(os.path.join(base_dir, s)) for s in m.sources]

    include_dirs = [base_dir]
    seen = set([base_dir])
    for src in sources:
        d = os.path.dirname(src)
        if d not in seen:
            seen.add(d)
            include_dirs.append(d)
    for hdr in m.headers:
        d = os.path.dirname(os.path.normpath(os.path.join(base_dir, hdr)))
        if d not in seen:
            include_dirs.append(d)

    return m.name, sources, include_dirs
