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


def generate(c2py_path, output_path=None):
    """Parse a .c2py file and generate the wrapper C file.

    Args:
        c2py_path: Path to .c2py interface file.
        output_path: Optional output .c path.  If None, returns code.

    Returns:
        Generated C code as string.
    """
    if not os.path.exists(c2py_path):
        print("ERROR: file not found: {}".format(c2py_path), file=sys.stderr)
        sys.exit(1)

    print("Parsing {}...".format(c2py_path))
    module_def = load_c2py(c2py_path)

    from c2py23.generator import generate as _gen

    c_code = _gen(module_def)

    if output_path:
        try:
            with open(output_path, "w") as f:
                f.write(c_code)
        except IOError as e:
            sys.exit("Error writing {}: {}".format(output_path, e))
        print("Wrapper written to: {}".format(output_path))

    return c_code


def main():
    import argparse

    parser = argparse.ArgumentParser(prog="c2py23", description="Wrap C99 code to Python via the buffer protocol")
    parser.add_argument("file", nargs="?", help="Path to .c2py interface file")
    parser.add_argument("-o", "--output", help="Output wrapper .c path (default: stdout)")
    parser.add_argument("--version", action="store_true", help="Print c2py23 version and exit")
    args = parser.parse_args()

    if args.version:
        from c2py23 import __version__

        print(__version__)
        return

    if not args.file:
        parser.print_help()
        sys.exit(1)

    c_code = generate(args.file, args.output)
    if args.output is None:
        sys.stdout.write(c_code)


if __name__ == "__main__":
    main()
