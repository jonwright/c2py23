#!/usr/bin/env python
"""Convert YAML .c2py files to Python dict format sidecar (.c2py.py).

The .c2py.py file is written alongside the original .c2py file and
contains the equivalent interface as a Python dict literal.  It is
auto-detected by load_c2py() and can be loaded in place of the YAML.

Usage:
    python3 tools/convert_c2py_to_dict.py              # tests/cases/
    python3 tools/convert_c2py_to_dict.py --all         # tests/cases/ + examples/
    python3 tools/convert_c2py_to_dict.py path/file.c2py  # single file
    python3 tools/convert_c2py_to_dict.py --check          # validate symmetry only
"""
from __future__ import print_function
import os, sys, json

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_DIR = os.path.join(PROJECT_DIR, 'tests', 'cases')
EXAMPLES_DIR = os.path.join(PROJECT_DIR, 'examples')


def py_repr(obj, indent=0):
    """Render a Python object as a pretty-printed Python dict literal."""
    sp = "    "
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = []
        for k, v in obj.items():
            kr = json.dumps(k)
            vr = py_repr(v, indent + 1)
            items.append(sp * (indent + 1) + kr + ": " + vr)
        inner = ",\n".join(items)
        return "{\n" + inner + ",\n" + sp * indent + "}"
    elif isinstance(obj, list):
        if not obj:
            return "[]"
        if len(obj) == 1 and not isinstance(obj[0], (dict, list)):
            return "[" + py_repr(obj[0], indent) + "]"
        items = []
        for v in obj:
            items.append(sp * (indent + 1) + py_repr(v, indent + 1))
        inner = ",\n".join(items)
        return "[\n" + inner + ",\n" + sp * indent + "]"
    elif isinstance(obj, bool):
        return "True" if obj else "False"
    elif obj is None:
        return "None"
    elif isinstance(obj, str):
        return json.dumps(obj)
    elif isinstance(obj, (int, float)):
        return json.dumps(obj)
    else:
        return json.dumps(obj)


def convert_file(c2py_path, check_only=False):
    """Read YAML, write .c2py.py sidecar.  Returns True on success."""
    try:
        import yaml
    except ImportError:
        print("PyYAML required for conversion: pip install PyYAML", file=sys.stderr)
        return False

    with open(c2py_path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return False

    dict_path = c2py_path + '.py'
    result = py_repr(data, 0)
    if not check_only:
        with open(dict_path, 'w') as f:
            f.write('# Python dict format equivalent of %s\n' % os.path.basename(c2py_path))
            f.write(result)
            f.write('\n')
    return True


def find_c2py_files(root_dir):
    for root, dirs, files in os.walk(root_dir):
        for fn in sorted(files):
            if fn.endswith('.c2py') and not fn.endswith('.c2py.py'):
                yield os.path.join(root, fn)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('paths', nargs='*', help='.c2py files to convert (default: all in tests/cases/)')
    ap.add_argument('--all', action='store_true', help='Walk both tests/cases/ and examples/')
    ap.add_argument('--check', action='store_true', help='Check only (do not write files)')
    args = ap.parse_args()

    if args.paths:
        paths = args.paths
    else:
        paths = list(find_c2py_files(CASES_DIR))
        if args.all:
            paths.extend(find_c2py_files(EXAMPLES_DIR))

    count = 0
    for p in sorted(paths):
        if convert_file(p, check_only=args.check):
            rel = os.path.relpath(p, PROJECT_DIR)
            if args.check:
                print("  OK: %s" % rel)
            else:
                print("  WRITTEN: %s.py" % rel)
            count += 1

    print("\n%d file(s) processed" % count)
    return 0


if __name__ == '__main__':
    sys.exit(main())
