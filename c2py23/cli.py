"""CLI entry point for c2py23.

Usage:
    c2py23 build foo.c2py [-o foo.so]
"""
from __future__ import print_function

import sys
import os
import subprocess
import argparse

from c2py23.parser import load_c2py
from c2py23.generator import generate


def cmd_build(args):
    """Parse a .c2py file and generate + compile a .so module."""
    c2py_path = args.file
    output = args.output

    if not os.path.exists(c2py_path):
        print("ERROR: file not found: {}".format(c2py_path), file=sys.stderr)
        sys.exit(1)

    # Parse
    print("Parsing {}...".format(c2py_path))
    module_def = load_c2py(c2py_path)
    mod_name = module_def.name

    # Generate wrapper C
    wrapper_c = mod_name + '_wrapper.c'
    wrapper_path = os.path.join(os.path.dirname(c2py_path) or '.', wrapper_c)
    print("Generating {}...".format(wrapper_path))
    c_code = generate(module_def)
    with open(wrapper_path, 'w') as f:
        f.write(c_code)

    # Find runtime files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    runtime_dir = os.path.join(script_dir, 'runtime')
    runtime_h = os.path.join(runtime_dir, 'c2py_runtime.h')
    runtime_c = os.path.join(runtime_dir, 'c2py_runtime.c')

    # Determine output .so path
    if output:
        so_path = output
    else:
        so_path = mod_name + '.so'
        base_dir = os.path.dirname(c2py_path) or '.'
        so_path = os.path.join(base_dir, so_path)

    # Collect source files
    source_files = [runtime_c, wrapper_path]
    base_dir = os.path.dirname(os.path.abspath(c2py_path))
    for src in module_def.sources:
        src_path = os.path.join(base_dir, src)
        if not os.path.exists(src_path):
            print("ERROR: source file not found: {}".format(src_path), file=sys.stderr)
            sys.exit(1)
        source_files.append(src_path)

    # Include paths
    include_dirs = [runtime_dir, base_dir]
    # Include paths - add source subdirectories
    src_dirs = set()
    for src in module_def.sources:
        d = os.path.dirname(os.path.join(base_dir, src))
        if d not in include_dirs:
            src_dirs.add(d)
    for d in sorted(src_dirs):
        include_dirs.append(d)
    include_flags = []
    for d in include_dirs:
        include_flags.extend(['-I', d])

    # Compiler selection
    cc = os.environ.get('CC', 'gcc')
    cflags = os.environ.get('CFLAGS', '').split()
    ldflags = os.environ.get('LDFLAGS', '').split()

    # Libraries
    libs = os.environ.get('LIBS', '-ldl -lm').split()

    # Compile
    print("Compiling {}...".format(so_path))
    cmd = [cc, '-shared', '-fPIC'] + include_flags + cflags + source_files + ldflags + libs + ['-o', so_path]
    print("  " + ' '.join(cmd))
    ret = subprocess.call(cmd)
    if ret != 0:
        print("ERROR: compilation failed", file=sys.stderr)
        sys.exit(1)

    print("Success: {}".format(so_path))


def main():
    parser = argparse.ArgumentParser(prog='c2py23',
                                      description='Wrap C99 code to Python via the buffer protocol')
    sub = parser.add_subparsers(dest='command', help='Commands')

    build_p = sub.add_parser('build', help='Build a .so from a .c2py file')
    build_p.add_argument('file', help='Path to .c2py interface file')
    build_p.add_argument('-o', '--output', help='Output .so path')
    build_p.set_defaults(func=cmd_build)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == '__main__':
    main()
