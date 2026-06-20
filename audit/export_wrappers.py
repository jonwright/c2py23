#!/usr/bin/env python3
"""Export c2py23 generated wrapper modules as Markdown for audit/review.

Driven by ``git ls-files <dir>`` for each test case / example.
Generated ``_wrapper.c`` files (not tracked) are appended from disk.
Binary artifacts (``.so``, ``.o``) are excluded.

Pre-checks enforce clean git tree, build, and test pass before export.

Output:
    audit/wrappers_combined.md   -- all modules in one file, runtime once
    audit/wrappers/<module>.md   -- one self-contained file per module
                                   (runtime NOT repeated; see README for
                                    LLM review workflow)

Usage:
    python3 audit/export_wrappers.py [OPTIONS]

Options:
    --skip-build        Skip build verification
    --skip-tests        Skip test verification
    --combined-only     Only write wrappers_combined.md
    --individual-only   Only write per-module wrappers/*.md
    --output-dir DIR    Output directory (default: audit/)
    -h, --help          Show this help
"""
from __future__ import print_function

import os
import sys
import datetime
import subprocess
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)

# Submodule paths (excluded)
_SUBMODULE_PATHS = {'examples/kissfft', 'examples/lz4'}

_BINARY_EXTS = {'.so', '.o', '.a', '.dylib', '.dll', '.pyc', '.pyo'}

# Runtime files (from git) to include once in the combined file
_RUNTIME_PATHS = [
    'c2py23/runtime/c2py_runtime.h',
    'c2py23/runtime/c2py_runtime.c',
    'c2py23/runtime/c2py_amd64.h',
    'c2py23/runtime/c2py_arm64.h',
    'c2py23/runtime/c2py_ppc64.h',
]

# Modules that need free-threaded Python 3.14t+
try:
    import sysconfig
    _is_ft = bool(sysconfig.get_config_var('Py_GIL_DISABLED'))
except Exception:
    _is_ft = False
_SKIP_MODULES = set() if _is_ft else {'freethreading'}


# --- Git helpers -----------------------------------------------------------

def _git_clean_check():
    """Return True if working tree is clean."""
    try:
        out = subprocess.check_output(
            ['git', 'status', '--porcelain'],
            cwd=REPO_DIR, stderr=subprocess.STDOUT
        ).decode('utf-8', errors='replace')
    except subprocess.CalledProcessError:
        return True
    lines = [l for l in out.splitlines() if l.strip()
             and not l.startswith('?? audit/')]
    if lines:
        print('ERROR: git working tree is not clean:')
        for l in lines:
            print('  {}'.format(l))
        return False
    return True


def _git_ls(dir_path):
    """Return sorted list of git-tracked files under a directory."""
    try:
        out = subprocess.check_output(
            ['git', 'ls-files', dir_path],
            cwd=REPO_DIR, stderr=subprocess.STDOUT
        ).decode('utf-8', errors='replace')
    except subprocess.CalledProcessError:
        return []
    return sorted(line.strip() for line in out.splitlines() if line.strip())


def _is_text(path):
    ext = os.path.splitext(path)[1].lower()
    return ext not in _BINARY_EXTS


# --- Module discovery ------------------------------------------------------

def _find_modules():
    """Return list of (module_dir_rel, c2py_path_rel, module_name)."""
    modules = []

    for top_dir in ['tests/cases', 'examples']:
        top = os.path.join(REPO_DIR, top_dir)
        if not os.path.isdir(top):
            continue
        for entry in sorted(os.listdir(top)):
            mod_dir = os.path.join(top_dir, entry)
            mod_dir_full = os.path.join(REPO_DIR, mod_dir)
            if not os.path.isdir(mod_dir_full):
                continue
            if entry in _SUBMODULE_PATHS:
                continue

            c2py_files = [f for f in os.listdir(mod_dir_full)
                         if f.endswith('.c2py')]
            if not c2py_files:
                continue
            c2py_rel = os.path.join(mod_dir, c2py_files[0])

            # Read module name from YAML
            try:
                with open(os.path.join(REPO_DIR, c2py_rel), 'r') as f:
                    data = yaml.safe_load(f)
                name = data.get('module', entry)
            except Exception:
                name = entry

            modules.append((mod_dir, c2py_rel, name))

    return modules


def _module_files(mod_dir_rel):
    """Return git-tracked text files for a module directory, plus wrapper.

    Returns (tracked_files, wrapper_path_rel, wrapper_path_abs).
    wrapper_path may be None if not built.
    """
    tracked = _git_ls(mod_dir_rel)

    # Find the generated _wrapper.c (not tracked by git)
    mod_dir_abs = os.path.join(REPO_DIR, mod_dir_rel)
    wrappers = [f for f in os.listdir(mod_dir_abs)
                if f.endswith('_wrapper.c')]
    wrapper_rel = None
    wrapper_abs = None
    if wrappers:
        wrapper_rel = os.path.join(mod_dir_rel, wrappers[0])
        wrapper_abs = os.path.join(REPO_DIR, wrapper_rel)

    # Filter out binary
    tracked = [f for f in tracked if _is_text(f)
               and not f.endswith('_wrapper.c')]

    return tracked, wrapper_rel, wrapper_abs


# --- Build & Test pre-check ------------------------------------------------

def _run(cmd, cwd=None, env=None):
    try:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        return (proc.returncode,
                out.decode('utf-8', errors='replace'),
                err.decode('utf-8', errors='replace'))
    except Exception as e:
        return 1, '', str(e)


def _build_check(skip_build):
    mods = _find_modules()
    built = []
    failed = []
    skipped_build = []

    for mod_dir, c2py_rel, name in mods:
        entry = os.path.basename(mod_dir)
        if entry in _SKIP_MODULES:
            skipped_build.append((name, 'requires free-threaded Python'))
            continue

        _, wrapper_rel, wrapper_abs = _module_files(mod_dir)
        so_abs = os.path.join(REPO_DIR, mod_dir, name + '.so')
        if not os.path.isfile(so_abs):
            sos = [f for f in os.listdir(os.path.join(REPO_DIR, mod_dir))
                   if f.endswith('.so')]
            if sos:
                so_abs = os.path.join(REPO_DIR, mod_dir, sos[0])

        if wrapper_abs and os.path.isfile(so_abs):
            built.append((mod_dir, c2py_rel, name))
            continue

        if skip_build:
            skipped_build.append((name, 'build skipped, wrapper/so missing'))
            continue

        c2py_abs = os.path.join(REPO_DIR, c2py_rel)
        print('  Building: {}'.format(c2py_rel))
        ret, out, err = _run('c2py23 build "{}"'.format(c2py_abs))
        if ret != 0:
            print('  [FAIL] build failed:')
            if err:
                print('    ' + err.replace('\n', '\n    '))
            failed.append(name)
        else:
            built.append((mod_dir, c2py_rel, name))

    if failed:
        print('\nERROR: {} module(s) failed to build: {}'.format(
            len(failed), ', '.join(failed)))
        return False

    if skipped_build:
        print('Note: {} module(s) skipped:'.format(len(skipped_build)))
        for m, reason in skipped_build:
            print('  {} -- {}'.format(m, reason))

    print('Build OK: {} modules ready.'.format(len(built)))
    return True


def _test_check(skip_tests):
    if skip_tests:
        print('Test check skipped (--skip-tests).')
        return True

    test_dir = os.path.join(REPO_DIR, 'tests')
    py = sys.executable

    for label, script in [
        ('test_uniform.py', 'test_uniform.py'),
        ('test_error_paths.py', 'test_error_paths.py'),
        ('test_regression_fixes.py', 'test_regression_fixes.py'),
        ('test_leaks.py', 'test_leaks.py'),
    ]:
        print('Running {} ...'.format(script))
        ret, out, err = _run('{} "{}"'.format(
            py, os.path.join(test_dir, script)))
        if ret != 0:
            print('[FAIL] {} failed.'.format(script))
            if out:
                print(out[-1000:])
            return False
        print('[OK] {}'.format(script))

    # Snakepit: check log; run only if it doesn't exist
    snakepit_dir = os.path.join(os.path.dirname(REPO_DIR), 'snakepit')
    sif_files = [f for f in os.listdir(snakepit_dir) if f.endswith('.sif')] \
        if os.path.isdir(snakepit_dir) else []
    if sif_files:
        log_path = os.path.join(test_dir, 'test_results.log')
        print('\nSnakepit containers found ({})'.format(len(sif_files)))
        if os.path.isfile(log_path):
            with open(log_path, 'r') as f:
                log_text = f.read()
            fail_count = log_text.count('[FAIL]')
            if fail_count == 0:
                print('[OK] test_results.log shows no failures')
            else:
                print('[WARN] test_results.log has {} failure(s)'.format(fail_count))
        else:
            print('No test_results.log; run:  python3 tests/test_all.py')
    else:
        print('Snakepit not found -- skip multi-version check.')

    print('\nAll test phases complete.')
    return True


# --- Export ----------------------------------------------------------------

def _read_file(relpath):
    full = os.path.join(REPO_DIR, relpath)
    try:
        with open(full, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(full, 'r', encoding='latin-1') as f:
            return f.read()
    except Exception:
        return ''


def _lang_tag(path):
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        '.py': 'python', '.c': 'c', '.h': 'c', '.toml': 'toml',
        '.yaml': 'yaml', '.c2py': 'yaml', '.md': 'markdown',
        '.sh': 'bash', '.cfg': 'ini', '.json': 'json',
    }
    return mapping.get(ext, '')


def _emit_runtime_section():
    """Emit the runtime support code section (shared once)."""
    lines = ['## Runtime Support Code', '']
    lines.append('These files are compiled into every c2py23-generated .so.')
    lines.append('They implement the "nimpy trick" -- all CPython API is')
    lines.append('resolved at runtime via dlopen(NULL)/dlsym().')
    lines.append('')
    for rp in _RUNTIME_PATHS:
        lines.append('### `{}`'.format(rp))
        lines.append('')
        lines.append('```c')
        lines.append(_read_file(rp).rstrip())
        lines.append('```')
        lines.append('')
    return '\n'.join(lines)


def _emit_module_section(mod_dir, c2py_rel, name):
    """Emit a single module section (without runtime)."""
    tracked, wrapper_rel, wrapper_abs = _module_files(mod_dir)

    lines = ['## {}'.format(name)]
    lines.append('')
    lines.append('**Directory**: `{}`'.format(mod_dir))
    lines.append('')

    files_included = []

    for fpath in tracked:
        # Sort order: .c2py first, then .c, then .py, then rest
        lines.append('### `{}`'.format(fpath))
        lines.append('')
        lines.append('```{}'.format(_lang_tag(fpath)))
        lines.append(_read_file(fpath).rstrip())
        lines.append('```')
        lines.append('')
        files_included.append(fpath)

    if wrapper_rel and os.path.isfile(wrapper_abs):
        lines.append('### `{}` *(generated)*'.format(wrapper_rel))
        lines.append('')
        lines.append('```c')
        lines.append(_read_file(wrapper_rel).rstrip())
        lines.append('```')
        lines.append('')
        files_included.append(wrapper_rel)

    return '\n'.join(lines), files_included


def _export_combined(modules, output_dir):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    py_ver = '{}.{}.{}'.format(
        sys.version_info[0], sys.version_info[1], sys.version_info[2])

    lines = [
        '# c2py23 Generated Wrapper Modules Audit',
        '',
        '**Generated**: {}'.format(now),
        '**Python**: {}'.format(py_ver),
        '**Modules**: {}'.format(len(modules)),
        '',
        'This file contains every c2py23-generated CPython C extension module.',
        'For each: YAML interface, C implementation, and generated wrapper.',
        'The runtime support code appears once at the top.',
        '',
        '---',
        '',
        _emit_runtime_section(),
        '---',
        '',
        '# Wrapper Modules',
        '',
    ]

    # TOC
    lines.append('## Table of Contents')
    lines.append('')
    lines.append('1. [Runtime Support Code](#runtime-support-code)')
    for i, (mod_dir, c2py_rel, name) in enumerate(modules, 2):
        anchor = name.lower().replace('_', '-')
        lines.append('{}. [{}](#{})'.format(i, name, anchor))
    lines.append('')
    lines.append('---')
    lines.append('')

    for mod_dir, c2py_rel, name in modules:
        section, _ = _emit_module_section(mod_dir, c2py_rel, name)
        lines.append(section)
        lines.append('---')
        lines.append('')

    output_path = os.path.join(output_dir, 'wrappers_combined.md')
    output = '\n'.join(lines) + '\n'
    with open(output_path, 'w') as f:
        f.write(output)
    print('Wrote {}'.format(output_path))


def _export_individual(modules, output_dir):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    wrappers_dir = os.path.join(output_dir, 'wrappers')
    if not os.path.isdir(wrappers_dir):
        os.makedirs(wrappers_dir)

    for mod_dir, c2py_rel, name in modules:
        section_text, files_included = _emit_module_section(
            mod_dir, c2py_rel, name)

        lines = [
            '# c2py23 Wrapper Module: {}'.format(name),
            '',
            '**Generated**: {}'.format(now),
            '**Directory**: `{}`'.format(mod_dir),
            '**Files**: {}'.format(', '.join(files_included) if files_included else '(none)'),
            '',
            '> **Note:** This file does NOT include the runtime support code.',
            '> See `wrappers_combined.md` or the full repository audit for the',
            '> shared runtime (`c2py_runtime.h`, `c2py_runtime.c`, arch headers).',
            '> For LLM review: upload the runtime code first so the model',
            '> understands the CPython ABI types used throughout.',
            '',
            '---',
            '',
            section_text,
        ]

        output_path = os.path.join(wrappers_dir, '{}.md'.format(name))
        output = '\n'.join(lines) + '\n'
        with open(output_path, 'w') as f:
            f.write(output)
        print('  Wrote {}'.format(output_path))


# --- Main ------------------------------------------------------------------

def main():
    skip_build = False
    skip_tests = False
    combined_only = False
    individual_only = False
    output_dir = SCRIPT_DIR

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--skip-build':
            skip_build = True
        elif arg == '--skip-tests':
            skip_tests = True
        elif arg == '--combined-only':
            combined_only = True
        elif arg == '--individual-only':
            individual_only = True
        elif arg == '--output-dir' and i + 1 < len(args):
            i += 1
            output_dir = args[i]
        elif arg in ('-h', '--help'):
            print(__doc__)
            return 0
        else:
            print('Unknown option: {}'.format(arg))
            return 1
        i += 1

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    # Pre-check: clean git tree
    print('Checking git tree...')
    if not _git_clean_check():
        print('\nCommit or stash changes before exporting.')
        return 1
    print('[OK] git tree clean.\n')

    # Phase 1: Build
    print('--- Phase 1: Build Check ---')
    if not _build_check(skip_build):
        print('ERROR: Build pre-check failed.')
        return 1

    # Phase 2: Tests
    print('\n--- Phase 2: Test Check ---')
    if not _test_check(skip_tests):
        print('ERROR: Test pre-check failed.')
        return 1

    # Phase 3: Export
    print('\n--- Phase 3: Export ---')
    all_mods = _find_modules()
    modules = [(m, c, n) for m, c, n in all_mods
               if os.path.basename(m) not in _SKIP_MODULES]

    if not combined_only:
        print('Exporting individual module files...')
        _export_individual(modules, output_dir)

    if not individual_only:
        print('Exporting combined file...')
        _export_combined(modules, output_dir)

    print('\n=== Export complete ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())
