#!/usr/bin/env python
"""Convert all .c2py YAML files in tests/cases/ to Python dict format.
The resulting files remain valid .c2py (same extension), auto-detected by load_c2py()."""
from __future__ import print_function
import os, re, sys, json

CASES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests', 'cases')

def py_repr(obj, indent=0):
    """Render a Python object as a pretty-printed Python dict literal."""
    sp = "    "  # 4-space indent
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = []
        for k, v in obj.items():
            kr = json.dumps(k)  # safe string repr
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

def convert_file(c2py_path):
    with open(c2py_path) as f:
        text = f.read()
    
    # Try to parse as YAML
    try:
        import yaml
        data = yaml.safe_load(text)
    except Exception:
        print("  SKIP: cannot parse %s" % c2py_path)
        return False
    
    if not isinstance(data, dict):
        print("  SKIP: %s is not a dict" % c2py_path)
        return False
    
    # Generate Python dict format
    result = py_repr(data, 0)
    
    # Write back
    with open(c2py_path, 'w') as f:
        f.write(result)
        f.write('\n')
    return True

def main():
    count = 0
    for root, dirs, files in os.walk(CASES_DIR):
        for fn in sorted(files):
            if fn.endswith('.c2py'):
                path = os.path.join(root, fn)
                if convert_file(path):
                    count += 1
                    print("  CONVERTED: %s" % os.path.relpath(path, CASES_DIR))
    print("\nConverted %d file(s)" % count)

if __name__ == '__main__':
    main()
