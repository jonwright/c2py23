#!/usr/bin/env python3
"""Export c2py23 full source tree as a single Markdown file for audit/review.

Driven by ``git ls-files`` -- the repo is the source of truth.

- Requires a clean git working tree
- Excludes submodules (examples/kissfft, examples/lz4)
- Excludes binary files (.so, .o, .a, .sif, .png, etc.)

Usage:
    python3 tools/audit/export_full_repo.py [--output FILE.md]
"""
from __future__ import print_function

import os
import sys
import datetime
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

# Submodule paths in this repo (excluded from audit)
_SUBMODULE_PATHS = {
    'examples/kissfft',
    'examples/lz4',
}

# Extensions treated as binary (not rendered in markdown)
_BINARY_EXTS = {
    '.so', '.o', '.a', '.dylib', '.dll', '.lib', '.pyd',
    '.sif', '.def',
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.bmp',
    '.pdf', '.zip', '.gz', '.tar', '.xz', '.bz2',
    '.pyc', '.pyo',
}


def _is_text(path):
    ext = os.path.splitext(path)[1].lower()
    return ext not in _BINARY_EXTS


def _git_clean_check():
    """Return True if working tree is clean (no modified/staged files)."""
    try:
        out = subprocess.check_output(
            ['git', 'status', '--porcelain'],
            cwd=REPO_DIR, stderr=subprocess.STDOUT
        ).decode('utf-8', errors='replace')
    except subprocess.CalledProcessError:
        # Not a git repo? Proceed anyway.
        return True
    # Allow untracked audit/ directory
    lines = [l for l in out.splitlines() if l.strip()
             and not l.startswith('?? audit/')]
    if lines:
        print('ERROR: git working tree is not clean:')
        for l in lines:
            print('  {}'.format(l))
        print('Commit or stash changes before exporting.')
        return False
    return True


def _git_tracked_files():
    """Return sorted list of all tracked text files (excl submodules + binary)."""
    try:
        out = subprocess.check_output(
            ['git', 'ls-files'],
            cwd=REPO_DIR, stderr=subprocess.STDOUT
        ).decode('utf-8', errors='replace')
    except subprocess.CalledProcessError:
        print('ERROR: git ls-files failed. Is this a git repo?')
        sys.exit(1)

    files = []
    for line in out.splitlines():
        path = line.strip()
        if not path:
            continue
        # Exclude submodules
        if path in _SUBMODULE_PATHS:
            continue
        if any(path.startswith(s + '/') for s in _SUBMODULE_PATHS):
            continue
        # Exclude binary
        if not _is_text(path):
            continue
        files.append(path)

    return sorted(files)


def _generate_tree(files):
    """Generate an ASCII tree from a sorted list of relative paths."""
    tree_lines = ['.']
    prev_parts = []
    for path in files:
        parts = path.split('/')
        depth = 0
        for i, part in enumerate(parts):
            if i < len(prev_parts) and part == prev_parts[i]:
                depth = i + 1
                continue
            indent = ''.join('    ' for _ in range(depth))
            if i == len(parts) - 1:
                tree_lines.append('{}-- {}'.format(indent, part))
            else:
                tree_lines.append('{}-- {}/'.format(indent, part))
            depth += 1
        prev_parts = parts
    return '\n'.join(tree_lines)


def _lang_tag(path):
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        '.py': 'python', '.c': 'c', '.h': 'c', '.toml': 'toml',
        '.yaml': 'yaml', '.c2py': 'yaml', '.md': 'markdown',
        '.sh': 'bash', '.cfg': 'ini', '.txt': 'text',
        '.json': 'json', '.cmake': 'cmake', '.meson': 'ini',
        '.in': 'text',
    }
    return mapping.get(ext, '')


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


def _classify_sections(files):
    """Group files into sections by path prefix."""
    sections = [
        ('Build & Configuration', []),
        ('Project Context', []),
        ('Core Pipeline', []),
        ('C Runtime', []),
        ('Documentation', []),
        ('Test Suite', []),
        ('Test Cases', []),
        ('Examples', []),
    ]
    seen = set()

    def _place(prefixes, section_idx):
        for f in files:
            if f in seen:
                continue
            for pfx in prefixes:
                if f == pfx or f.startswith(pfx):
                    sections[section_idx][1].append(f)
                    seen.add(f)
                    break

    _place(['pyproject.toml', 'setup.py'], 0)
    _place(['AGENTS.md', 'README.md', 'LICENSE', 'PLAN.md'], 1)
    _place(['c2py23/__init__.py', 'c2py23/parser.py',
            'c2py23/generator.py', 'c2py23/cli.py', 'c2py23/perf.py'], 2)
    _place(['c2py23/runtime/'], 3)
    _place(['docs/'], 4)
    _place(['tests/test_', 'tests/populate_', 'tests/run_tests',
            'tests/requirements.txt', 'tests/abi_matrix.json',
            'tests/check_abi.c'], 5)
    _place(['tests/cases/'], 6)
    _place(['examples/'], 7)

    # Anything left unmatched goes to "Other"
    remaining = [f for f in files if f not in seen]
    if remaining:
        sections.append(('Other', remaining))

    return [(n, fl) for n, fl in sections if fl]


def _emit_toc(sections):
    lines = ['## Table of Contents', '']
    for section_name, files in sections:
        lines.append('- **{}**'.format(section_name))
        for fpath in files:
            anchor = fpath.replace('/', '-').replace('.', '-')
            lines.append('  - [`{}`](#{})'.format(fpath, anchor))
    lines.append('')
    return '\n'.join(lines)


def export_full_repo(output_path=None):
    if output_path is None:
        output_path = os.path.join(SCRIPT_DIR, 'full_repo_audit.md')

    if not _git_clean_check():
        sys.exit(1)

    files = _git_tracked_files()
    if not files:
        print('ERROR: no tracked files found')
        sys.exit(1)

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sections = _classify_sections(files)

    lines = [
        '# c2py23 Full Repository Audit',
        '',
        '**Generated**: {}'.format(now),
        '**Repository**: {}'.format(REPO_DIR),
        '**Tracked files**: {}'.format(len(files)),
        '',
        '## Directory Structure',
        '',
        '```',
        _generate_tree(files),
        '```',
        '',
        _emit_toc(sections),
        '',
        '# Source Files',
        '',
    ]

    for section_name, section_files in sections:
        lines.append('## {}'.format(section_name))
        lines.append('')
        for fpath in section_files:
            lines.append('### `{}`'.format(fpath))
            lines.append('')
            content = _read_file(fpath)
            lang = _lang_tag(fpath)
            lines.append('```{}'.format(lang))
            lines.append(content.rstrip())
            lines.append('```')
            lines.append('')

    output = '\n'.join(lines) + '\n'
    with open(output_path, 'w') as f:
        f.write(output)
    print('Wrote {} ({} files)'.format(output_path, len(files)))


if __name__ == '__main__':
    output_arg = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--output' and i + 1 < len(args):
            output_arg = args[i + 1]
            i += 2
        elif args[i] in ('-h', '--help'):
            print(__doc__)
            sys.exit(0)
        else:
            output_arg = args[i]
            i += 1
    export_full_repo(output_arg)
