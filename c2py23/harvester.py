"""Harvest c2py23 interface definitions from C source comment blocks.

C2PY_BEGIN/C2PY_END blocks embed Python dicts in C block comments:

    /* C2PY_BEGIN
    module: mymodule
    source: [mymodule.c]
    functions:
      - py_sig: "func(a: buffer) -> void"
        c_overloads:
          - sig: "func_impl(const double *a, int n)"
            map: {a: "a.ptr", n: "a.n"}
    C2PY_END */

Multiple blocks in one file are merged (dict.update).  This works for
both test modules (one block = full module definition) and multi-file
harvesting (one block = one function, assembled by the caller).

Compatible with c2ImageD11's harvester pattern.
"""

from __future__ import print_function

import ast
import os
import re
import sys


def _extract_blocks(text):
    """Yield (line_start, parsed_dict) for each C2PY_BEGIN..C2PY_END block."""
    begin_re = re.compile(r"C2PY_BEGIN")
    end_re = re.compile(r"C2PY_END")
    lines = text.splitlines(True)
    i = 0
    while i < len(lines):
        if begin_re.search(lines[i]):
            start_line = i + 1
            i += 1
            content_lines = []
            while i < len(lines) and not end_re.search(lines[i]):
                content_lines.append(lines[i])
                i += 1
            comment_prefix = re.compile(r"^\s*\*\s?")
            cleaned = []
            for ln in content_lines:
                s = ln.rstrip("\n\r")
                s = comment_prefix.sub("", s, count=1)
                cleaned.append(s)
            block_text = "\n".join(cleaned).strip()
            if block_text:
                block_text = re.sub(r"(?<=[\s,\[{:])true(?=\s*[\s,\]\}:])", "True", block_text)
                block_text = re.sub(r"(?<=[\s,\[{:])false(?=\s*[\s,\]\}:])", "False", block_text)
                try:
                    obj = ast.literal_eval(block_text)
                except (ValueError, SyntaxError) as e:
                    print("ERROR: %s in C2PY_BLOCK starting at line %d" % (e, start_line), file=sys.stderr)
                    raise
                if not isinstance(obj, dict):
                    print(
                        "ERROR: C2PY_BLOCK must be a dict (got %s) at line %d" % (type(obj).__name__, start_line),
                        file=sys.stderr,
                    )
                    continue
                yield start_line, obj
            if i < len(lines):
                i += 1
        else:
            i += 1


def extract_from_file(filepath):
    """Return merged dict from all C2PY_BEGIN blocks in a file.

    Multiple blocks are merged via dict.update() -- later blocks
    override earlier ones.  Per-function blocks (without 'module'
    key) are collected into a 'functions' list.
    """
    with open(filepath, "r") as f:
        text = f.read()

    merged = {}
    funcs = []
    for _lineno, block in _extract_blocks(text):
        if "module" in block or "functions" in block:
            # Full module definition block
            merged.update(block)
        elif "py_sig" in block:
            # Per-function block
            funcs.append(block)
        else:
            # Constants or other metadata block
            merged.update(block)

    if funcs and "functions" not in merged:
        merged["functions"] = funcs
    elif funcs:
        merged["functions"] = merged.get("functions", []) + funcs

    return merged


def extract_from_dir(dirpath):
    """Walk dirpath, merge blocks from all .c and .h files.

    Returns a single dict with all module definitions merged.
    Useful for multi-file harvesting (cImageD11 pattern).
    """
    merged = {}
    funcs = []
    for root, _dirs, files in os.walk(dirpath):
        for fn in sorted(files):
            if not (fn.endswith(".c") or fn.endswith(".h")):
                continue
            fp = os.path.join(root, fn)
            try:
                block = extract_from_file(fp)
            except Exception:
                continue
            if "module" in block:
                merged.update(block)
            for f in block.get("functions", []):
                funcs.append(f)
    if funcs and "functions" not in merged:
        merged["functions"] = funcs
    elif funcs:
        merged["functions"] = merged.get("functions", []) + funcs
    return merged
