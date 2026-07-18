"""CLI entry point for c2py23 -- generate C wrapper from .c2py interface.

Usage:
    c2py23 file.c2py -o wrapper.c        # generate wrapper to file
    c2py23 file.c2py                      # generate to stdout
    c2py23 --version                      # print version
"""

from __future__ import print_function

import sys
import os

from c2py23.parser import load_c2py


def generate(c2py_path, output_path=None, use_single_header=False):
    """Parse a .c2py file and generate the wrapper C file.

    Args:
        c2py_path: Path to .c2py interface file.
        output_path: Optional output .c path.  If None, returns code.
        use_single_header: If True, emit #include "c2py.h" (with C2PY_IMPLEMENTATION)
            instead of #include "c2py_runtime.h".

    Returns:
        Generated C code as string.
    """
    if not os.path.exists(c2py_path):
        print("ERROR: file not found: {}".format(c2py_path), file=sys.stderr)
        sys.exit(1)

    print("Parsing {}...".format(c2py_path))
    module_def = load_c2py(c2py_path)

    from c2py23.generator import generate as _gen

    c_code = _gen(module_def, use_single_header=use_single_header)

    if output_path:
        try:
            with open(output_path, "w") as f:
                f.write(c_code)
        except IOError as e:
            sys.exit("Error writing {}: {}".format(output_path, e))
        print("Wrapper written to: {}".format(output_path))

    return c_code


def _emit_header(dest_dir):
    """Copy the bundled c2py.h single-header to dest_dir."""
    src = os.path.join(os.path.dirname(__file__), "runtime", "c2py.h")
    if not os.path.exists(src):
        sys.exit("Error: c2py.h not found at {}".format(src))
    dest = os.path.join(dest_dir, "c2py.h")
    try:
        with open(src, "r") as f:
            content = f.read()
        with open(dest, "w") as f:
            f.write(content)
    except IOError as e:
        sys.exit("Error writing {}: {}".format(dest, e))
    print("Header written to: {}".format(dest))


def _regenerate_header():
    """Regenerate c2py.h from runtime source files (requires runtime sources)."""
    script = os.path.join(os.path.dirname(__file__), "runtime", "merge_single_header.py")
    if not os.path.exists(script):
        sys.exit("Error: merge_single_header.py not found at {}".format(script))
    sys.stdout.flush()
    import subprocess

    ret = subprocess.call([sys.executable, script])
    if ret != 0:
        sys.exit("Error: merge_single_header.py failed with exit code {}".format(ret))


def main():
    import argparse

    parser = argparse.ArgumentParser(prog="c2py23", description="Wrap C99 code to Python via the buffer protocol")
    parser.add_argument("file", nargs="?", help="Path to .c2py interface file")
    parser.add_argument("-o", "--output", help="Output wrapper .c path (default: stdout)")
    parser.add_argument("--emit-header", action="store_true", help="Emit c2py.h single-header alongside the wrapper")
    parser.add_argument("--regenerate-header", action="store_true", help="Regenerate c2py.h from runtime sources")
    parser.add_argument("--version", action="store_true", help="Print c2py23 version and exit")
    args = parser.parse_args()

    if args.version:
        from c2py23 import __version__

        print(__version__)
        return

    if args.regenerate_header:
        _regenerate_header()
        return

    if not args.file:
        parser.print_help()
        sys.exit(1)

    c_code = generate(args.file, args.output, use_single_header=args.emit_header)
    if args.output is None:
        sys.stdout.write(c_code)

    if args.emit_header:
        if args.output:
            dest = os.path.dirname(os.path.abspath(args.output))
        else:
            dest = os.getcwd()
        _emit_header(dest)


if __name__ == "__main__":
    main()
