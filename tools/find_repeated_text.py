#!/usr/bin/env python
"""Detect near-duplicate prose across the repository.

Scans all text source files, chunks by paragraph, and reports paragraphs
that appear with high similarity in different files.  Uses Jaccard
similarity on word sets for speed, with a fallback to cosine on TF
vectors for close candidates.

Outputs a list of near-duplicate paragraph pairs ordered by similarity.
Exit code 1 if duplicates found.  Use --whitelist for expected dupes.

Usage:
    python3 tools/find_repeated_text.py
    python3 tools/find_repeated_text.py --threshold 0.8    # sensitivity
    python3 tools/find_repeated_text.py --json              # machine output
    python3 tools/find_repeated_text.py --whitelist tools/dupe_whitelist.txt
"""

from __future__ import print_function

import collections
import json
import math
import os
import re
import sys

IS_PY3 = sys.version_info[0] >= 3

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCLUDE_GLOBS = [
    ".git",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.o",
    "*.out",
    "*.a",
    "*.dll",
    "*.pyd",
    "*.zip",
    "*.tar.gz",
    "*.whl",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.svg",
    "*.icc",
    "*.icm",
    "node_modules",
    "build",
    "dist",
    "*.egg-info",
    ".mypy_cache",
    ".pytest_cache",
    "*.sif",
    "*.ipynb_checkpoints",
]

EXCLUDE_DIRS = {"kissfft", "lz4"}

SKIP_FILES = {"LICENSE"}

DEFAULT_THRESHOLD = 0.65
WHITELIST_PATH = os.path.join(os.path.dirname(__file__), "dupe_whitelist.txt")


def _glob_match(path, pattern):
    import fnmatch

    return fnmatch.fnmatch(os.path.basename(path), pattern)


def _is_excluded(path):
    rel = os.path.relpath(path, PROJECT_DIR)
    parts = rel.replace("\\", "/").split("/")

    for part in parts:
        if part.startswith("."):
            return True
    for pattern in EXCLUDE_GLOBS:
        if pattern.startswith("*."):
            if _glob_match(path, pattern):
                return True
        else:
            for part in parts:
                if part == pattern:
                    return True
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
    return os.path.basename(path) in SKIP_FILES


def _paths():
    paths = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            if _is_excluded(fp):
                continue
            paths.append(fp)
    return paths


def _read_file(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if b"\x00" in raw[:1024]:
            return None
        if IS_PY3:
            return raw.decode("utf-8", errors="replace")
        else:
            return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


_RE_SPLIT = re.compile(r"\n\s*\n")
_RE_WS = re.compile(r"\s+")
_RE_WORD = re.compile(r"[a-zA-Z0-9]+")


def _paragraphs(text):
    paras = _RE_SPLIT.split(text)
    result = []
    for p in paras:
        cleaned = _RE_WS.sub(" ", p).strip()
        if not cleaned:
            continue
        if len(cleaned) < 30:
            continue
        result.append(cleaned)
    return result


def _tokenize(text):
    words = _RE_WORD.findall(text.lower())
    return collections.Counter(words), set(words)


def _jaccard(set_a, set_b):
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return float(intersection) / float(union)


def _cosine_tf(vec_a, vec_b):
    all_words = set(vec_a) | set(vec_b)
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for w in all_words:
        va = vec_a.get(w, 0)
        vb = vec_b.get(w, 0)
        dot += va * vb
        norm_a += va * va
        norm_b += vb * vb
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _load_whitelist(path):
    entries = set()
    if not os.path.isfile(path):
        return entries
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split("|||")
                if len(parts) >= 2:
                    entries.add((parts[0].strip(), parts[1].strip()))
    return entries


def _is_whitelisted(file_a, file_b, whitelist):
    ra = os.path.relpath(file_a, PROJECT_DIR)
    rb = os.path.relpath(file_b, PROJECT_DIR)
    return (ra, rb) in whitelist or (rb, ra) in whitelist


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Similarity threshold (default: %s)" % DEFAULT_THRESHOLD,
    )
    ap.add_argument("--json", action="store_true", help="Output JSON")
    ap.add_argument("--whitelist", type=str, default=WHITELIST_PATH, help="Whitelist file path")
    ap.add_argument("--ci", action="store_true", help="Fail if any dupes found")
    args = ap.parse_args()

    whitelist = _load_whitelist(args.whitelist)

    all_paths = _paths()
    file_data = {}
    for fp in all_paths:
        text = _read_file(fp)
        if text is not None:
            file_data[fp] = text

    all_paras = []
    para_info = []
    for fp, text in sorted(file_data.items()):
        paras = _paragraphs(text)
        for p in paras:
            word_ctr, word_set = _tokenize(p)
            all_paras.append(p)
            para_info.append((fp, word_ctr, word_set))

    results = []
    n = len(all_paras)

    for i in range(n):
        fi, ci, si = para_info[i]
        for j in range(i + 1, n):
            fj, cj, sj = para_info[j]

            if fi == fj:
                continue
            if _is_whitelisted(fi, fj, whitelist):
                continue

            jacc = _jaccard(si, sj)
            if jacc < args.threshold * 0.6:
                continue

            sim = _cosine_tf(ci, cj)
            if sim >= args.threshold:
                results.append((sim, fi, fj, all_paras[i], all_paras[j]))

    results.sort(reverse=True)

    if args.json:
        output = []
        for sim, fa, fb, pa, pb in results:
            output.append(
                {
                    "similarity": round(sim, 4),
                    "file_a": os.path.relpath(fa, PROJECT_DIR),
                    "file_b": os.path.relpath(fb, PROJECT_DIR),
                    "text_a": pa[:200],
                    "text_b": pb[:200],
                }
            )
        print(json.dumps(output, indent=2))
    else:
        if results:
            print("Near-duplicate paragraphs (threshold=%.2f):" % args.threshold)
            print()
            for sim, fa, fb, pa, pb in results:
                fa_r = os.path.relpath(fa, PROJECT_DIR)
                fb_r = os.path.relpath(fb, PROJECT_DIR)
                print("  sim=%.3f  %s <-> %s" % (sim, fa_r, fb_r))
                print("    A: %s..." % pa[:120])
                print("    B: %s..." % pb[:120])
                print()
            print("%d duplicate pair(s) found." % len(results))
        else:
            print("No near-duplicate paragraphs found (threshold=%.2f)." % args.threshold)

    if results:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
