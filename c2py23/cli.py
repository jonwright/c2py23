"""CLI entry point for c2py23.

Usage:
    c2py23 build foo.c2py [-o foo.so] [--asan] [--generate-only] [--compile-only [--source s.c ...] [--include d/ ...]]
    c2py23 generate foo.c2py [-o wrapper.c]
"""

from __future__ import print_function

import sys
import os
import subprocess
import argparse

from c2py23.parser import load_c2py


def _generate_wrapper(c2py_path, output_path=None):
    """Parse a .c2py file and generate the wrapper C file.

    Returns (wrapper_path, module_def).
    """
    if not os.path.exists(c2py_path):
        print("ERROR: file not found: {}".format(c2py_path), file=sys.stderr)
        sys.exit(1)

    print("Parsing {}...".format(c2py_path))
    module_def = load_c2py(c2py_path)
    mod_name = module_def.name

    if output_path:
        wrapper_path = output_path
    else:
        wrapper_c = mod_name + "_wrapper.c"
        wrapper_path = os.path.join(os.path.dirname(c2py_path) or ".", wrapper_c)

    from c2py23.generator import generate as _gen

    c_code = _gen(module_def)
    try:
        with open(wrapper_path, "w") as f:
            f.write(c_code)
    except IOError as e:
        sys.exit("Error writing {}: {}".format(wrapper_path, e))

    return wrapper_path, module_def


def _collect_user_sources(base_dir, module_def):
    """Collect user C source files, resolving relative paths against base_dir.

    Returns list of absolute paths.
    """
    source_files = []
    for src in module_def.sources:
        # Normalise: join(base_dir, src) handles both absolute and relative
        src_path = os.path.normpath(os.path.join(base_dir, src))
        if not os.path.exists(src_path):
            print("ERROR: source file not found: {}".format(src_path), file=sys.stderr)
            sys.exit(1)
        source_files.append(src_path)
    return source_files


def _collect_include_dirs(base_dir, module_def, extra_dirs=None):
    """Collect include directories from module_def sources plus extra dirs.

    Returns list of unique include directory paths.
    """
    include_dirs = [base_dir]
    src_dirs = set()
    for src in module_def.sources:
        d = os.path.dirname(os.path.join(base_dir, src))
        if d not in include_dirs:
            src_dirs.add(d)
    for d in sorted(src_dirs):
        include_dirs.append(d)
    if extra_dirs:
        for d in extra_dirs:
            if d not in include_dirs:
                include_dirs.append(d)
    return include_dirs


def _pythonh_libs(libs):
    """When --pythonh is set, drop -ldl (not needed) and add -lpythonX.Y if on CPython.
    PyPy and GraalPy provide cpyext symbols at load time, no -lpython needed.
    On Windows, uses the .lib import library directly (MSVC does not understand -l).
    Returns (libs, extra_linker_flags)."""
    libs = [l for l in libs if l != "-ldl"]
    extra_ldflags = []
    try:
        is_cpython = sys.implementation.name == "cpython"
    except AttributeError:
        # Python 2.7: sys.implementation does not exist.
        # Distinguish CPython 2.7 from PyPy 2.7.
        is_cpython = not hasattr(sys, "pypy_version_info")
    if is_cpython:
        try:
            import sysconfig as _sc

            if sys.platform == "win32":
                libdir = _sc.get_config_var("LIBDIR")
                if libdir:
                    ver = sys.version_info
                    # python312.lib, python27.lib, etc.
                    libname = "python%d%d.lib" % (ver.major, ver.minor)
                    libfile = os.path.join(libdir, libname)
                    if not os.path.exists(libfile):
                        # fallback: stable ABI name (python3.lib)
                        libfile = os.path.join(libdir, "python%d.lib" % ver.major)
                    if os.path.exists(libfile):
                        libs.append(libfile)
            else:
                ld_ver = _sc.get_config_var("LDVERSION") or _sc.get_config_var("VERSION")
                if ld_ver:
                    libs.append("-lpython" + ld_ver)
                    # For non-standard libpython locations (uv, static builds),
                    # add -L to the library directory
                    libdir = _sc.get_config_var("LIBDIR")
                    if libdir:
                        extra_ldflags.append("-L" + libdir)
        except Exception:
            pass
    return libs, extra_ldflags


def _compile_wrapper(wrapper_path, source_files, include_dirs, output_so, asan=False, target="cpython", pythonh=False):
    """Compile a wrapper .c file (plus runtime and user sources) to a .so/.pyd."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    runtime_dir = os.path.join(script_dir, "runtime")
    runtime_c = os.path.join(runtime_dir, "c2py_runtime.c")

    all_sources = [runtime_c, wrapper_path] + list(source_files)
    for src_path in all_sources:
        if not os.path.exists(src_path):
            print("ERROR: source file not found: {}".format(src_path), file=sys.stderr)
            sys.exit(1)

    all_includes = [runtime_dir] + list(include_dirs)

    if pythonh:
        if target != "cpython":
            print("ERROR: --pythonh is incompatible with --target {}".format(target), file=sys.stderr)
            sys.exit(1)
        try:
            import sysconfig as _sc

            py_inc = _sc.get_config_var("INCLUDEPY")
            if py_inc:
                all_includes.insert(0, py_inc)
        except Exception:
            pass

    if target == "wasm":
        py_include = os.environ.get("EMSCRIPTEN_PYTHON_INCLUDE")
        if py_include:
            all_includes.insert(0, py_include)
        else:
            print(
                "WARNING: EMSCRIPTEN_PYTHON_INCLUDE not set -- Python headers not found. "
                "Use -I or set EMSCRIPTEN_PYTHON_INCLUDE.",
                file=sys.stderr,
            )

    is_win = sys.platform == "win32"

    if target == "wasm":
        cc = os.environ.get("CC", "emcc")
        is_msvc = False
    elif is_win:
        cc = os.environ.get("CC", "gcc")
        if cc == "cl" or cc.endswith("cl.exe") or cc.endswith("cl"):
            is_msvc = True
        else:
            is_msvc = False
    else:
        cc = os.environ.get("CC", "gcc")
        is_msvc = False

    if is_msvc:
        _default_cflags = "/W4"
    else:
        _default_cflags = "-O2 -Wall -Werror -Wpointer-arith"
    cflags = [f for f in os.environ.get("CFLAGS", _default_cflags).split() if f]
    ldflags = [f for f in os.environ.get("LDFLAGS", "").split() if f]

    if target == "pypy":
        cflags.insert(0, "-DC2PY_TARGET_PYPY")
        # -O2 causes segfault on PyPy cpyext module import
        # (likely DSE removing needed initializations in static structs).
        # -O1 is safe; user can override via CFLAGS env var.
        if not os.environ.get("CFLAGS"):
            for j in range(len(cflags)):
                if cflags[j] == "-O2":
                    cflags[j] = "-O1"
                    break

    if pythonh:
        cflags.insert(0, "-DC2PY_USE_PYTHON_H")

    if asan:
        if is_msvc:
            cflags.append("/fsanitize=address")
        else:
            cflags.append("-fsanitize=address")
            cflags.append("-g")
            cflags.append("-O1")
            ldflags.append("-fsanitize=address")
        print("  [ASan enabled]")

    if is_win:
        default_libs = "-lkernel32" if not is_msvc else ""
        libs = os.environ.get("LIBS", default_libs).split()
        libs = [l for l in libs if l]
    else:
        libs = os.environ.get("LIBS", "-ldl -lm").split()

    if pythonh:
        libs, extra_ld = _pythonh_libs(libs)
        ldflags.extend(extra_ld)

    if is_msvc:
        include_flags = []
        for d in all_includes:
            include_flags.extend(["/I", d])
        cmd = [cc, "/nologo", "/LD"] + cflags + include_flags + all_sources
        cmd += libs + ["/Fe" + output_so]
    elif target == "wasm":
        include_flags = []
        for d in all_includes:
            include_flags.extend(["-I", d])
        # Emscripten side module: no -shared/-fPIC, no -ldl
        wasm_libs = [l for l in libs if l != "-ldl"]
        cmd = (
            [cc, "-s", "SIDE_MODULE=1"] + include_flags + cflags + all_sources + ldflags + wasm_libs + ["-o", output_so]
        )
    elif is_win:
        include_flags = []
        for d in all_includes:
            include_flags.extend(["-I", d])
        cmd = [cc, "-shared"] + include_flags + cflags + all_sources
        cmd += ldflags + libs + ["-o", output_so]
    else:
        include_flags = []
        for d in all_includes:
            include_flags.extend(["-I", d])
        cmd = [cc, "-shared", "-fPIC"] + include_flags + cflags + all_sources + ldflags + libs + ["-o", output_so]

    print("Compiling {}...".format(output_so))
    print("  " + " ".join(cmd))
    ret = subprocess.call(cmd)
    if ret != 0:
        print("ERROR: compilation failed", file=sys.stderr)
        sys.exit(1)

    print("Success: {}".format(output_so))


def _determine_so_path(output_arg, default_name, base_dir, target="cpython", pythonh=False):
    """Determine the .so/.pyd/.wasm output path."""
    if output_arg:
        return output_arg
    if target == "wasm":
        ext = ".wasm"
    elif sys.platform == "win32":
        ext = ".pyd"
    elif pythonh:
        try:
            import sysconfig as _sc

            ext_suffix = _sc.get_config_var("EXT_SUFFIX")
            if ext_suffix:
                return os.path.join(base_dir, default_name + ext_suffix)
        except Exception:
            pass
        ext = ".so"
    else:
        ext = ".so"
    return os.path.join(base_dir, default_name + ext)


def cmd_build(args):
    """Parse a .c2py file and generate + compile a .so module."""
    c2py_path = args.file

    # --generate-only: stop after writing wrapper .c
    if getattr(args, "generate_only", False):
        wrapper_path, _ = _generate_wrapper(c2py_path, args.output)
        print("Wrapper written to: {}".format(wrapper_path))
        return

    # --compile-only: skip parse+generate, compile existing wrapper.c
    if getattr(args, "compile_only", False):
        wrapper_path = c2py_path
        if not os.path.exists(wrapper_path):
            print(
                "ERROR: wrapper file not found: {}".format(wrapper_path),
                file=sys.stderr,
            )
            sys.exit(1)

        source_files = args.source or []
        source_files = [os.path.abspath(s) for s in source_files]

        include_dirs = args.include or []
        include_dirs = [os.path.abspath(d) for d in include_dirs]

        base = os.path.splitext(os.path.basename(wrapper_path))[0]
        so_base = base.replace("_wrapper", "")
        output_so = _determine_so_path(
            args.output,
            so_base,
            os.path.dirname(wrapper_path) or ".",
            target=getattr(args, "target", "cpython"),
            pythonh=getattr(args, "pythonh", False),
        )
        _compile_wrapper(
            wrapper_path,
            source_files,
            include_dirs,
            output_so,
            asan=getattr(args, "asan", False),
            target=getattr(args, "target", "cpython"),
            pythonh=getattr(args, "pythonh", False),
        )
        return

    # Normal build: parse + generate + compile
    base_dir = os.path.dirname(os.path.abspath(c2py_path))

    wrapper_path, module_def = _generate_wrapper(c2py_path)

    source_files = _collect_user_sources(base_dir, module_def)
    include_dirs = _collect_include_dirs(base_dir, module_def)

    output_so = _determine_so_path(
        args.output,
        module_def.name,
        base_dir,
        target=getattr(args, "target", "cpython"),
        pythonh=getattr(args, "pythonh", False),
    )

    _compile_wrapper(
        wrapper_path,
        source_files,
        include_dirs,
        output_so,
        asan=getattr(args, "asan", False),
        target=getattr(args, "target", "cpython"),
        pythonh=getattr(args, "pythonh", False),
    )


def cmd_generate(args):
    """Generate C wrapper from a .c2py file without compiling."""
    wrapper_path, _ = _generate_wrapper(args.file, args.output)
    print("Wrapper written to: %s" % wrapper_path)


def _add_build_parser(sub):
    build_p = sub.add_parser("build", help="Build a .so from a .c2py file")
    build_p.add_argument("file", help="Path to .c2py interface file")
    build_p.add_argument(
        "-o",
        "--output",
        help="Output .so path (or wrapper .c path with --generate-only)",
    )

    build_p.add_argument(
        "--asan",
        action="store_true",
        help="Compile with -fsanitize=address " "(detects buffer overflows, leaks, use-after-free)",
    )
    build_p.add_argument(
        "--generate-only",
        action="store_true",
        help="Generate wrapper .c only, do not compile",
    )
    build_p.add_argument(
        "--compile-only",
        action="store_true",
        help="Compile an existing wrapper .c file (skip parse+generate)",
    )
    build_p.add_argument(
        "--target",
        choices=["cpython", "pypy", "wasm"],
        default="cpython",
        help="Target Python runtime (default: cpython, for PyPy: pypy, for Pyodide/WASM: wasm)",
    )
    build_p.add_argument(
        "--pythonh",
        action="store_true",
        default=False,
        help="Compile with #include <Python.h> instead of dlsym "
        "(portable cross-version .so, for GraalPy, debugging, static builds)",
    )
    build_p.add_argument(
        "-s",
        "--source",
        action="append",
        help="User C source files (repeatable, for --compile-only)",
    )
    build_p.add_argument(
        "-I",
        "--include",
        action="append",
        help="Include directories (repeatable, for --compile-only)",
    )
    build_p.set_defaults(func=cmd_build)


def _add_generate_parser(sub):
    gen_p = sub.add_parser("generate", help="Generate wrapper .c from .c2py (no compilation)")
    gen_p.add_argument("file", help="Path to .c2py interface file")
    gen_p.add_argument("-o", "--output", help="Output wrapper .c path")
    gen_p.set_defaults(func=cmd_generate)


def main():
    parser = argparse.ArgumentParser(prog="c2py23", description="Wrap C99 code to Python via the buffer protocol")
    sub = parser.add_subparsers(dest="command", help="Commands")

    _add_build_parser(sub)
    _add_generate_parser(sub)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
