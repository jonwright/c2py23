#!/usr/bin/env python3
"""Compare all 3 generators: strip C comments, compile, compare object files."""
from __future__ import print_function

import sys
import os
import re
import hashlib
import subprocess
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from c2py23.parser import load_c2py
from c2py23 import generator as g_orig
from c2py23 import generator_builder as g_builder
from c2py23 import generator_ast as g_ast

RUNTIME_DIR = 'c2py23/runtime'
CASES_DIR = 'tests/cases'

GENERATORS = [
    ('original', g_orig),
    ('builder', g_builder),
    ('ast', g_ast),
]

def strip_c_comments(code):
    """Remove C-style /* */ and // comments, preserving line numbers."""
    # Remove // line comments
    code = re.sub(r'//.*', '', code)
    # Remove /* */ block comments (non-greedy)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    # Collapse blank lines (multiple \n\n -> \n\n)
    code = re.sub(r'\n\s*\n', '\n\n', code)
    return code.strip() + '\n'

def compile_c(code, name_tag):
    """Compile C code to .o and return (retcode, stdout, stderr)."""
    with tempfile.NamedTemporaryFile(suffix='.c', mode='w', delete=False) as f:
        f.write(code)
        cpath = f.name
    opath = cpath + '.o'
    try:
        p = subprocess.run(
            ['gcc', '-Wall', '-Werror', '-c',
             '-I', RUNTIME_DIR,
             '-o', opath, cpath],
            capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        os.unlink(cpath)
        return (1, '', 'TIMEOUT')
    os.unlink(cpath)
    if p.returncode != 0:
        if os.path.exists(opath):
            os.unlink(opath)
        return (p.returncode, p.stdout, p.stderr)
    # Compute SHA256 hash
    with open(opath, 'rb') as f:
        h = hashlib.sha256(f.read()).hexdigest()
    os.unlink(opath)
    return (0, h, '')

def main():
    results = {}
    print('Found cases:', sorted(os.listdir(CASES_DIR)))
    sys.stdout.flush()
    # Find all test cases
    for case_name in sorted(os.listdir(CASES_DIR)):
        case_dir = os.path.join(CASES_DIR, case_name)
        if not os.path.isdir(case_dir):
            continue
        c2py_files = [f for f in os.listdir(case_dir) if f.endswith('.c2py')]
        if not c2py_files:
            continue
        c2py_file = os.path.join(case_dir, c2py_files[0])
        mod = load_c2py(c2py_file)

        codes = {}
        hashes = {}
        stripped_codes = {}

        for gen_name, gen_func in GENERATORS:
            try:
                code = gen_func.generate(mod)
                stripped = strip_c_comments(code)
                ret, h, err = compile_c(stripped, gen_name)
                if ret != 0:
                    print('  %s: COMPILE FAILED' % gen_name)
                    for line in err.split('\n')[:10]:
                        print('    ', line)
                    hashes[gen_name] = None
                else:
                    hashes[gen_name] = h
                    stripped_codes[gen_name] = stripped
                    codes[gen_name] = code
            except Exception as e:
                print('  %s: EXCEPTION: %s' % (gen_name, e))
                hashes[gen_name] = None

        results[case_name] = hashes

        # Check which match
        o = hashes.get('original')
        b = hashes.get('builder')
        a = hashes.get('ast')

        if o is None or b is None or a is None:
            print('  FAIL/ERROR on %s: o=%s b=%s a=%s' % (
                case_name, hashes.get('original'), hashes.get('builder'), hashes.get('ast')))
            continue

        match_str = ''
        if o == b:
            match_str += ' orig=builder'
        if o == a:
            match_str += ' orig=ast'
        if b == a:
            match_str += ' builder=ast'
        if not match_str:
            match_str = ' ALL DIFFER'

        o_str = hashes.get('original', '')[0:12] if hashes.get('original') else 'FAIL'
    b_str = hashes.get('builder', '')[0:12] if hashes.get('builder') else 'FAIL'
    a_str = hashes.get('ast', '')[0:12] if hashes.get('ast') else 'FAIL'
    print('%-20s original=%-14s builder=%-14s ast=%-14s [%s]' % (
        case_name, o_str, b_str, a_str, match_str))

    # Summary
    print()
    totals = {'original': 0, 'builder': 0, 'ast': 0}
    matches = {'orig_builder': 0, 'orig_ast': 0, 'builder_ast': 0}
    for case_name, hs in results.items():
        for k in totals:
            if hs.get(k) is not None:
                totals[k] += 1
        if hs.get('original') is not None and hs.get('builder') is not None \
           and hs['original'] == hs['builder']:
            matches['orig_builder'] += 1
        if hs.get('original') is not None and hs.get('ast') is not None \
           and hs['original'] == hs['ast']:
            matches['orig_ast'] += 1
        if hs.get('builder') is not None and hs.get('ast') is not None \
           and hs['builder'] == hs['ast']:
            matches['builder_ast'] += 1

    print('Cases compiled: original=%d builder=%d ast=%d' % (
        totals['original'], totals['builder'], totals['ast']))
    print('Object file matches: orig=builder=%d  orig=ast=%d  builder=ast=%d' % (
        matches['orig_builder'], matches['orig_ast'], matches['builder_ast']))


if __name__ == '__main__':
    main()
