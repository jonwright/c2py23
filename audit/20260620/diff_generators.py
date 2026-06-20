#!/usr/bin/env python3
"""Diff C output from generators at function-granularity to find structural differences."""
from __future__ import print_function

import sys
import os
import re
import subprocess
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from c2py23.parser import load_c2py
from c2py23 import generator as g_orig
from c2py23 import generator_builder as g_builder
from c2py23 import generator_ast as g_ast

CASES_DIR = 'tests/cases'

def strip_c_comments(code):
    code = re.sub(r'//.*', '', code)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    code = re.sub(r'\n\s*\n', '\n\n', code)
    return code.strip() + '\n'

def normalize_line(line):
    """Remove whitespace padding for comparison."""
    return line.strip()

def split_functions(code):
    """Split C code into individual functions by 'static PyObject*' or 'PyObject* PyInit'."""
    lines = code.split('\n')
    functions = []
    current = []
    in_fn = False
    for line in lines:
        stripped = line.strip()
        if (stripped.startswith('static PyObject*') or
            stripped.startswith('PyObject* PyInit') or
            stripped.startswith('void init') or
            stripped.startswith('static PyMethodDef') or
            stripped.startswith('static PyModuleDef') or
            stripped.startswith('static PyModuleDef_FT')):
            if current:
                functions.append('\n'.join(current))
            current = [line]
            in_fn = True
        elif stripped and not in_fn:
            # Global declarations before first function
            if not current:
                current = [line]
            else:
                current.append(line)
        elif in_fn:
            current.append(line)
    if current:
        functions.append('\n'.join(current))
    return functions

def main():
    for case_name in sorted(os.listdir(CASES_DIR)):
        case_dir = os.path.join(CASES_DIR, case_name)
        if not os.path.isdir(case_dir):
            continue
        c2py_files = [f for f in os.listdir(case_dir) if f.endswith('.c2py')]
        if not c2py_files:
            continue
        c2py_file = os.path.join(case_dir, c2py_files[0])
        mod = load_c2py(c2py_file)

        # Generate from original and builder
        orig_code = strip_c_comments(g_orig.generate(mod))
        build_code = strip_c_comments(g_builder.generate(mod))
        ast_code = strip_c_comments(g_ast.generate(mod))

        orig_funcs = split_functions(orig_code)
        build_funcs = split_functions(build_code)
        ast_funcs = split_functions(ast_code)

        if len(orig_funcs) != len(build_funcs):
            print('=== %s: FUNCTION COUNT MISMATCH orig=%d builder=%d ===' % (
                case_name, len(orig_funcs), len(build_funcs)))
            continue

        if len(orig_funcs) != len(ast_funcs):
            print('=== %s: FUNCTION COUNT MISMATCH orig=%d ast=%d ===' % (
                case_name, len(orig_funcs), len(ast_funcs)))
            continue

        diffs_orig_builder = 0
        diffs_orig_ast = 0

        for i, (of, bf, af) in enumerate(zip(orig_funcs, build_funcs, ast_funcs)):
            o_norm = '\n'.join(normalize_line(l) for l in of.split('\n') if normalize_line(l) and not l.strip().startswith('#include'))
            b_norm = '\n'.join(normalize_line(l) for l in bf.split('\n') if normalize_line(l) and not l.strip().startswith('#include'))
            a_norm = '\n'.join(normalize_line(l) for l in af.split('\n') if normalize_line(l) and not l.strip().startswith('#include'))

            if o_norm != b_norm:
                diffs_orig_builder += 1
            if o_norm != a_norm:
                diffs_orig_ast += 1

        if diffs_orig_builder == 0 and diffs_orig_ast == 0:
            print('%-20s IDENTICAL (all 3)' % case_name)
        elif diffs_orig_builder == 0:
            print('%-20s orig=builder OK, ast=%d diffs' % (case_name, diffs_orig_ast))
            # Show ast differences
            for i, (of, af) in enumerate(zip(orig_funcs, ast_funcs)):
                o_norm = '\n'.join(normalize_line(l) for l in of.split('\n') if normalize_line(l) and not l.strip().startswith('#include'))
                a_norm = '\n'.join(normalize_line(l) for l in af.split('\n') if normalize_line(l) and not l.strip().startswith('#include'))
                if o_norm != a_norm:
                    # Show first 3 differing lines
                    o_lines = o_norm.split('\n')
                    a_lines = a_norm.split('\n')
                    for j, (ol, al) in enumerate(zip(o_lines, a_lines)):
                        if ol != al:
                            print('  Func %d line %d:' % (i, j))
                            print('    orig: %s' % ol[:100])
                            print('    ast:  %s' % al[:100])
                            if j > 10:
                                break
                    break
        else:
            print('%-20s orig/builder=%d diffs, ast=%d diffs' % (
                case_name, diffs_orig_builder, diffs_orig_ast))
            # Show a sample diff for orig vs builder
            for i, (of, bf) in enumerate(zip(orig_funcs, build_funcs)):
                o_norm = '\n'.join(normalize_line(l) for l in of.split('\n') if normalize_line(l) and not l.strip().startswith('#include'))
                b_norm = '\n'.join(normalize_line(l) for l in bf.split('\n') if normalize_line(l) and not l.strip().startswith('#include'))
                if o_norm != b_norm:
                    o_lines = o_norm.split('\n')
                    b_lines = b_norm.split('\n')
                    for j, (ol, bl) in enumerate(zip(o_lines, b_lines)):
                        if ol != bl:
                            print('  Func %d line %d:' % (i, j))
                            print('    orig: %s' % ol[:120])
                            print('    bldr: %s' % bl[:120])
                            if j > 10:
                                break
                    break


if __name__ == '__main__':
    main()
