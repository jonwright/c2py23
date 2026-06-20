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
from c2py23 import generator as g_builder

RUNTIME_DIR = 'c2py23/runtime'
CASES_DIR = 'tests/cases'

GENERATORS = [
    ('original', g_orig),
    ('builder', g_builder),
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

        o = hashes.get('original')
        b = hashes.get('builder')

        if o is None or b is None:
            print('  FAIL on %s: orig=%s builder=%s' % (
                case_name, o, b))
            continue

        match_str = 'MATCH' if o == b else 'DIFFER'

        o_str = o[:12]
        b_str = b[:12]
        print('%-20s original=%-14s builder=%-14s [%s]' % (
            case_name, o_str, b_str, match_str))

    # Summary
    print()
    compiled = {'original': 0, 'builder': 0}
    for case_name, hs in results.items():
        for k in compiled:
            if hs.get(k) is not None:
                compiled[k] += 1
    matches = sum(1 for hs in results.values()
                  if hs.get('original') is not None
                  and hs.get('builder') is not None
                  and hs['original'] == hs['builder'])
    total = len(results)
    print('Cases compiled: original=%d builder=%d' % (
        compiled['original'], compiled['builder']))
    print('Object file matches: %d/%d' % (matches, total))


if __name__ == '__main__':
    main()
