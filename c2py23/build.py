"""c2py23.build -- setuptools helpers for building dlsym and pythonh modules.

A DlsymExt module produces a plain .so with no libpython link,
suitable for Python 2.7 through 3.15 with zero recompilation.
A PythonhExt module produces a version-specific .so linked to libpython.

Usage (dlsym):
    from c2py23.build import DlsymCmdclass
    setup(..., cmdclass=DlsymCmdclass)

Usage (pythonh):
    from c2py23.build import PythonhCmdclass
    setup(..., cmdclass=PythonhCmdclass)

Environment variables honoured by both:
    CC, CFLAGS, LDFLAGS, LIBS, LDSHARED
"""

from __future__ import print_function

from setuptools import Extension
from distutils.command.build_ext import build_ext


class _BaseBuildExt(build_ext):
    """Base class with shared helper: get_ext_modules."""

    def initialize_options(self):
        build_ext.initialize_options(self)
        self.ext_map = {}  # may be overridden

    def run(self):
        # Ensure wrapper .c files exist before building.
        mods = self.distribution.ext_modules
        if mods:
            print("[c2py23 build_ext] %d extension(s)" % len(mods))
        build_ext.run(self)


class _BenchmarkRouting(object):
    """Mixin: route benchmark extensions to build/ (dlsym) or build_ph/ (pythonh)."""

    _benchmark_build_subdir = "build"

    def get_ext_fullpath(self, ext_name):
        import os

        base = self.get_ext_filename(ext_name)
        ext = self.ext_map.get(ext_name)
        if ext and ext.sources:
            wrapper_dir = os.path.dirname(ext.sources[0])
            if "benchmarks" + os.sep + "src" in wrapper_dir.replace("/", os.sep):
                build_dir = os.path.join(os.path.dirname(wrapper_dir), self._benchmark_build_subdir)
                return os.path.join(build_dir, base)
            return os.path.join(wrapper_dir, base)
        return build_ext.get_ext_fullpath(self, ext_name)

    def run(self):
        self.ext_map = {ext.name: ext for ext in self.extensions}
        build_ext.run(self)
        import os
        import shutil

        for ext in self.extensions:
            built = os.path.join(self.build_lib, self.get_ext_filename(ext.name))
            dest = self.get_ext_fullpath(ext.name)
            if os.path.isfile(built) and built != dest:
                d = os.path.dirname(dest)
                if not os.path.isdir(d):
                    os.makedirs(d)
                shutil.copy2(built, dest)


class DlsymBuildExt(_BenchmarkRouting, _BaseBuildExt):
    """Build extensions in dlsym mode: plain .so, no libpython link.

    Strips the ABI-tagged filename suffix so the .so loads on any
    Python version without recompilation.

    Users should set LIBS="-ldl -lm" to override any python libs that
    setuptools may inject from sysconfig.
    """

    def get_ext_filename(self, ext_name):
        return ext_name.split(".")[0] + ".so"


class PythonhBuildExt(_BenchmarkRouting, _BaseBuildExt):
    """Build extensions in pythonh mode: #include <Python.h>, link libpython.

    Standard setuptools behaviour -- ABI-tagged filename, libpython linked.
    Adds -DC2PY_USE_PYTHON_H to every extension.

    Benchmarks go to build_ph/ (matching dlsym's build/ convention).
    Other modules go alongside source with ABI-tagged filenames.
    """

    _benchmark_build_subdir = "build_ph"

    def build_extensions(self):
        for ext in self.extensions:
            if not hasattr(ext, "extra_compile_args") or ext.extra_compile_args is None:
                ext.extra_compile_args = []
            if "-DC2PY_USE_PYTHON_H" not in ext.extra_compile_args:
                ext.extra_compile_args.append("-DC2PY_USE_PYTHON_H")
        build_ext.build_extensions(self)


# Convenience: cmdclass dicts for argument to setup()
DlsymCmdclass = {"build_ext": DlsymBuildExt}
PythonhCmdclass = {"build_ext": PythonhBuildExt}


def discover_modules(scan_dir, runtime_dir):
    """Return a list of setuptools Extension objects for all .c2py modules.

    Walks scan_dir recursively, finds .c2py files (excluding .c2py.py
    sidecars), parses their module name and source list, and builds
    Extension objects including the generated wrapper .c and the
    c2py23 runtime.

    Args:
        scan_dir: Directory to scan for .c2py files.
        runtime_dir: Path to c2py23/runtime/.

    Returns:
        List of setuptools.Extension objects.
    """
    import os
    import ast

    extensions = []
    runtime_c = os.path.join(runtime_dir, "c2py_runtime.c")
    runtime_include = runtime_dir

    for root, dirs, files in os.walk(scan_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in sorted(files):
            if not fn.endswith(".c2py"):
                continue
            if fn.endswith(".c2py.py"):
                continue
            c2py_path = os.path.join(root, fn)

            try:
                module, sources, includes = _parse_c2py(c2py_path)
            except Exception:
                continue

            if module is None:
                continue

            wrapper_c = os.path.join(os.path.dirname(c2py_path), module + "_wrapper.c")
            if not os.path.exists(wrapper_c):
                # Wrapper not generated yet -- skip (own build system like cmake/meson)
                continue

            # Skip modules with non-C source files (e.g., .o objects from separate build)
            skip = False
            c_sources = []
            for src in sources:
                if src.endswith(".c"):
                    c_sources.append(src)
                elif src.endswith(".o") or src.endswith(".obj"):
                    skip = True
            if skip:
                continue
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

    with open(c2py_path) as f:
        text = f.read()

    # Try Python dict format first
    import ast

    data = None
    try:
        import re

        stripped = re.sub(r"(?m)^\s*#.*$", "", text)
        data = ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        pass

    # Fall back to YAML
    if not isinstance(data, dict):
        try:
            import yaml as _yaml

            data = _yaml.safe_load(text)
        except Exception:
            pass

    if not isinstance(data, dict):
        return None, [], []

    module = data.get("module")
    if not module:
        return None, [], []

    raw_sources = data.get("source", [])
    if not raw_sources:
        return None, [], []

    base_dir = os.path.dirname(os.path.abspath(c2py_path))
    sources = []
    include_dirs = [base_dir]
    seen_dirs = set([base_dir])

    for src in raw_sources:
        src_path = os.path.normpath(os.path.join(base_dir, src))
        sources.append(src_path)
        d = os.path.dirname(src_path)
        if d not in seen_dirs:
            seen_dirs.add(d)
            include_dirs.append(d)

    # Also add header directories as includes
    for hdr in data.get("headers", []):
        hdr_path = os.path.normpath(os.path.join(base_dir, hdr))
        d = os.path.dirname(hdr_path)
        if d not in seen_dirs:
            include_dirs.append(d)

    return module, sources, include_dirs
