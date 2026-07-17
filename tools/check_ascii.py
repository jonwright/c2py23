#!/usr/bin/env python
"""Check that all given files are 7-bit ASCII clean.

Usage:
    python tools/check_ascii.py file1.py file2.c ...   # check specific files
    git ls-files | python tools/check_ascii.py          # check from stdin
    git diff --cached --name-only | python tools/check_ascii.py

Exit 0 if all files are ASCII; exit 1 with violations on stderr otherwise.

Third-party libraries (examples/lz4/, examples/kissfft_wrap/kissfft/) and
generated content (test_venv/, node_modules/, site/) are excluded.
"""

from __future__ import print_function

import os
import sys

SKIP_DIRS = ("/examples/lz4/", "/kissfft/", "/test_venv", "/node_modules", "/site/")
SKIP_EXTENSIONS = (".so", ".wasm", ".o", ".pyd", ".whl", ".png", ".jpg", ".gz", ".zip", ".pyc", ".pyo", ".bin")
TEXT_EXTENSIONS = (
    "py",
    "c",
    "h",
    "md",
    "yml",
    "yaml",
    "sh",
    "toml",
    "cfg",
    "ini",
    "c2py",
    "c2py.py",
    "js",
    "ts",
    "json",
    "html",
    "css",
    "txt",
    "cmake",
    "rst",
    "",
)


def _should_check(path):
    if any(d in path for d in SKIP_DIRS):
        return False
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    if ext in SKIP_EXTENSIONS:
        return False
    if ext not in TEXT_EXTENSIONS:
        return False
    return True


def check_files(paths):
    bad = []
    for f in paths:
        if not _should_check(f):
            continue
        try:
            with open(f, "rb") as fh:
                for ln, line in enumerate(fh, 1):
                    for byte in line:
                        if byte > 127:
                            bad.append("{}:{}".format(f, ln))
                            break
        except (IOError, OSError):
            pass
    return bad


def main():
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
    else:
        paths = [line.strip() for line in sys.stdin if line.strip()]

    if not paths:
        sys.exit(0)

    bad = check_files(paths)

    if bad:
        print("ERROR: Non-ASCII characters found in {} file(s):".format(len(bad)), file=sys.stderr)
        for b in bad:
            print("  " + b, file=sys.stderr)
        print(file=sys.stderr)
        print("All source files must use 7-bit ASCII only.", file=sys.stderr)
        print("Replace em dashes (--) with --, smart quotes with straight quotes, etc.", file=sys.stderr)
        sys.exit(1)

    print("7-bit ASCII: PASS ({} file(s))".format(len(paths)))


if __name__ == "__main__":
    main()
