"""CLI entry point for c2py23.

Usage:
    c2py23 build foo.c2py [-o foo.so] [--asan] [--generate-only] [--compile-only [--source s.c ...] [--include d/ ...]]
    c2py23 generate foo.c2py [-o wrapper.c]
    c2py23 compile wrapper.c [-s user.c ...] [-I include/ ...] [-o output.so] [--asan]
"""
from __future__ import print_function

import sys
import os
import subprocess
import argparse

from c2py23.parser import load_c2py
from c2py23.generator import generate


def _generate_wrapper(c2py_path, output_path=None, generator='original'):
    """Parse a .c2py file and generate the wrapper C file.

    Args:
        c2py_path: Path to .c2py interface file
        output_path: Optional output wrapper .c path
        generator: Generator to use ('original' or 'builder')

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
        wrapper_c = mod_name + '_wrapper.c'
        wrapper_path = os.path.join(os.path.dirname(c2py_path) or '.', wrapper_c)

    if generator == 'builder':
        print("Generating {} (CBuilder)...".format(wrapper_path))
        from c2py23.generator_builder import generate as _gen
    else:
        print("Generating {}...".format(wrapper_path))
        from c2py23.generator import generate as _gen
    c_code = _gen(module_def)
    try:
        with open(wrapper_path, 'w') as f:
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


def _compile_wrapper(wrapper_path, source_files, include_dirs, output_so, asan=False):
    """Compile a wrapper .c file (plus runtime and user sources) to a .so."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    runtime_dir = os.path.join(script_dir, 'runtime')
    runtime_c = os.path.join(runtime_dir, 'c2py_runtime.c')

    all_sources = [runtime_c, wrapper_path] + list(source_files)
    for src_path in all_sources:
        if not os.path.exists(src_path):
            print("ERROR: source file not found: {}".format(src_path), file=sys.stderr)
            sys.exit(1)

    all_includes = [runtime_dir] + list(include_dirs)
    include_flags = []
    for d in all_includes:
        include_flags.extend(['-I', d])

    cc = os.environ.get('CC', 'gcc')
    cflags = os.environ.get('CFLAGS', '').split()
    ldflags = os.environ.get('LDFLAGS', '').split()

    if asan:
        cflags.append('-fsanitize=address')
        ldflags.append('-fsanitize=address')
        print("  [ASan enabled]")

    libs = os.environ.get('LIBS', '-ldl -lm').split()

    print("Compiling {}...".format(output_so))
    cmd = ([cc, '-shared', '-fPIC'] + include_flags + cflags +
           all_sources + ldflags + libs + ['-o', output_so])
    print("  " + ' '.join(cmd))
    ret = subprocess.call(cmd)
    if ret != 0:
        print("ERROR: compilation failed", file=sys.stderr)
        sys.exit(1)

    print("Success: {}".format(output_so))


def _determine_so_path(output_arg, default_name, base_dir):
    """Determine the .so output path."""
    if output_arg:
        return output_arg
    return os.path.join(base_dir, default_name + '.so')


def cmd_build(args):
    """Parse a .c2py file and generate + compile a .so module."""
    c2py_path = args.file
    generator = getattr(args, 'generator', 'original')

    # --generate-only: stop after writing wrapper .c
    if getattr(args, 'generate_only', False):
        wrapper_path, _ = _generate_wrapper(c2py_path, args.output, generator)
        print("Wrapper written to: {}".format(wrapper_path))
        return

    # --compile-only: skip parse+generate, compile existing wrapper.c
    if getattr(args, 'compile_only', False):
        wrapper_path = c2py_path
        if not os.path.exists(wrapper_path):
            print("ERROR: wrapper file not found: {}".format(wrapper_path), file=sys.stderr)
            sys.exit(1)

        source_files = args.source or []
        source_files = [os.path.abspath(s) for s in source_files]

        include_dirs = args.include or []
        include_dirs = [os.path.abspath(d) for d in include_dirs]

        base = os.path.splitext(os.path.basename(wrapper_path))[0]
        so_base = base.replace('_wrapper', '')
        output_so = _determine_so_path(args.output, so_base,
                                        os.path.dirname(wrapper_path) or '.')
        _compile_wrapper(wrapper_path, source_files, include_dirs, output_so,
                          asan=getattr(args, 'asan', False))
        return

    # Normal build: parse + generate + compile
    base_dir = os.path.dirname(os.path.abspath(c2py_path))

    wrapper_path, module_def = _generate_wrapper(c2py_path, generator=generator)

    source_files = _collect_user_sources(base_dir, module_def)
    include_dirs = _collect_include_dirs(base_dir, module_def)

    output_so = _determine_so_path(args.output, module_def.name, base_dir)

    _compile_wrapper(wrapper_path, source_files, include_dirs, output_so,
                      asan=getattr(args, 'asan', False))


def cmd_generate(args):
    """Generate C wrapper from a .c2py file without compiling."""
    generator = getattr(args, 'generator', 'original')
    wrapper_path, _ = _generate_wrapper(args.file, args.output, generator)
    print("Wrapper written to: {}".format(wrapper_path))


def cmd_compile(args):
    """Compile a wrapper .c file to a .so."""
    wrapper_path = args.file
    if not os.path.exists(wrapper_path):
        print("ERROR: wrapper file not found: {}".format(wrapper_path), file=sys.stderr)
        sys.exit(1)

    source_files = args.source or []
    source_files = [os.path.abspath(s) for s in source_files]

    include_dirs = args.include or []
    include_dirs = [os.path.abspath(d) for d in include_dirs]

    base = os.path.splitext(os.path.basename(wrapper_path))[0]
    so_base = base.replace('_wrapper', '')
    output_so = _determine_so_path(args.output, so_base,
                                    os.path.dirname(wrapper_path) or '.')
    _compile_wrapper(wrapper_path, source_files, include_dirs, output_so,
                      asan=getattr(args, 'asan', False))


def _add_build_parser(sub):
    build_p = sub.add_parser('build', help='Build a .so from a .c2py file')
    build_p.add_argument('file', help='Path to .c2py interface file')
    build_p.add_argument('-o', '--output', help='Output .so path (or wrapper .c path with --generate-only)')
    build_p.add_argument('--generator', choices=['original', 'builder'], default='original',
                          help='Generator to use (default: original)')
    build_p.add_argument('--asan', action='store_true',
                          help='Compile with -fsanitize=address for leak detection')
    build_p.add_argument('--generate-only', action='store_true',
                          help='Generate wrapper .c only, do not compile')
    build_p.add_argument('--compile-only', action='store_true',
                          help='Compile an existing wrapper .c file (skip parse+generate)')
    build_p.add_argument('-s', '--source', action='append',
                          help='User C source files (repeatable, for --compile-only)')
    build_p.add_argument('-I', '--include', action='append',
                          help='Include directories (repeatable, for --compile-only)')
    build_p.set_defaults(func=cmd_build)


def _add_generate_parser(sub):
    gen_p = sub.add_parser('generate', help='Generate wrapper .c from .c2py (no compilation)')
    gen_p.add_argument('file', help='Path to .c2py interface file')
    gen_p.add_argument('-o', '--output', help='Output wrapper .c path')
    gen_p.add_argument('--generator', choices=['original', 'builder'], default='original',
                          help='Generator to use (default: original)')
    gen_p.set_defaults(func=cmd_generate)


def _add_compile_parser(sub):
    comp_p = sub.add_parser('compile', help='Compile a wrapper .c file to .so')
    comp_p.add_argument('file', help='Path to wrapper .c file')
    comp_p.add_argument('-s', '--source', action='append',
                         help='User C source files (repeatable)')
    comp_p.add_argument('-I', '--include', action='append',
                         help='Include directories (repeatable)')
    comp_p.add_argument('-o', '--output', help='Output .so path')
    comp_p.add_argument('--asan', action='store_true',
                         help='Compile with -fsanitize=address for leak detection')
    comp_p.set_defaults(func=cmd_compile)


def main():
    parser = argparse.ArgumentParser(prog='c2py23',
                                      description='Wrap C99 code to Python via the buffer protocol')
    sub = parser.add_subparsers(dest='command', help='Commands')

    _add_build_parser(sub)
    _add_generate_parser(sub)
    _add_compile_parser(sub)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == '__main__':
    main()
