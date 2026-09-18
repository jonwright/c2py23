#!/usr/bin/env python
"""Measure C coverage of c2py23 wrappers + runtime using gcov.

Setup (once, from the repo root):

    CC=gcc CFLAGS="--coverage -O0 -g -Wall" LDFLAGS="--coverage" \
        make -f tests/Makefile clean all        # instrumented build
    python tests/runner.py --no-build           # run the pytest suite

Then run this script to produce tests/coverage_report.md:

    python tools/measure_c_coverage.py

It runs `gcov -b -c` over every instrumented module, sums line-hit counts
across all modules for the SHARED runtime sources (c2py_runtime.c and
c2py_dlsym.c), and reports per-module wrapper coverage plus the merged
runtime coverage and its uncovered lines.

The shared runtime is compiled into every .so, so coverage of it must be
merged: a line executed by any module counts as covered.  Generated
wrapper .c files are unique per module, so each is reported individually.

Python 2.7 - 3.15 compatible.  Requires gcov on PATH.
"""

from __future__ import print_function

import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORT = os.path.join(ROOT, "tests", "coverage_report.md")

# Source files that are compiled into every module (aggregate across modules).
SHARED_RUNTIME = ("c2py_runtime.c", "c2py_dlsym.c", "c2py_runtime.h", "c2py_dlsym.h")


def _gcov_datas():
    """Yield every (module_dir_rel, gcda_path) under the test/build tree."""
    for pattern in (
        "tests/cases/*/*.gcda",
        "examples/kissfft_wrap/*.gcda",
        "examples/lz4_wrap/*.gcda",
        "benchmarks/build/*.gcda",
    ):
        for p in sorted(glob.glob(os.path.join(ROOT, pattern))):
            yield p


def _parse_gcov(path):
    """Return {line_no: count} for executable lines in a .gcov file.

    count == -1 means "not a code line" (skipped).  0 means code that never ran.
    """
    lines = {}
    with open(path) as f:
        for line in f:
            m = re.match(r"^\s*(\S+):\s*(\d+)(?:-\d+)?:\s", line)
            if not m:
                continue
            raw = m.group(1)
            lineno = int(m.group(2))
            if raw == "-":
                continue  # non-code
            # gcov suffixes an executed line with '*' when a branch on that
            # line is not fully taken (e.g. "2*").  The line IS executed.
            raw = raw.rstrip("*")
            if raw in ("#####", "=====", "$$$$$"):
                lines[lineno] = 0
            else:
                try:
                    lines[lineno] = int(raw)
                except ValueError:
                    pass
    return lines


def _run_gcov(gcda):
    """Run gcov for one .gcda and return list of created .gcov paths + stdout text."""
    out = subprocess.run(
        ["gcov", "-b", "-c", os.path.relpath(gcda, ROOT)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.decode("utf-8", errors="replace")
    created = []
    for m in re.finditer(r"Creating '([^']+\.gcov)'", out):
        created.append(m.group(1))
    return created, out


def main():
    gcov_datas = list(_gcov_datas())
    # per-source aggregation: {source_name: {line: total_hits}}
    agg = {}
    # per-module wrapper coverage: {module_label: (source, total, covered)}
    per_module = []
    # store runtime summary lines from each run for reference
    runtime_exit_order = []

    for gcda in gcov_datas:
        created, out = _run_gcov(gcda)
        for g in created:
            gpath = os.path.join(ROOT, g)
            if not os.path.exists(gpath):
                continue
            src = g[:-5]  # strip ".gcov"
            parsed = _parse_gcov(gpath)
            d = agg.setdefault(src, {})
            for lineno, cnt in parsed.items():
                d[lineno] = d.get(lineno, 0) + cnt
            os.remove(gpath)

    # Work out per-module wrappers (sources not in SHARED_RUNTIME and live in a case dir).
    for src, linehits in sorted(agg.items()):
        total = len(linehits)
        covered = sum(1 for v in linehits.values() if v > 0)
        is_shared = any(src.endswith(s) for s in SHARED_RUNTIME)
        # a source is a wrapper if it is not in the runtime dir and not a user .c we do not track
        if "c2py23/runtime/" in src or src.endswith("c2py_runtime.c") or src.endswith("c2py_dlsym.c"):
            is_shared = True
        if is_shared:
            continue
        pct = (100.0 * covered / total) if total else 0.0
        per_module.append((src, total, covered, pct))

    # Merged runtime coverage (sum across all modules).
    runtime_summary = {}
    for s in ("c2py_runtime.c", "c2py_dlsym.c"):
        linehits = agg.get(s, {})
        total = len(linehits)
        covered = sum(1 for v in linehits.values() if v > 0)
        pct = (100.0 * covered / total) if total else 0.0
        runtime_summary[s] = (total, covered, pct)

    # Uncovered runtime lines (merged): lines with sum == 0.
    uncovered = {}
    for s in ("c2py_runtime.c", "c2py_dlsym.c"):
        linehits = agg.get(s, {})
        zeros = sorted(l for l, v in linehits.items() if v == 0)
        uncovered[s] = zeros

    # ---- Write report ----
    mt = open(REPORT, "w")
    def w(*a):
        mt.write(" ".join(str(x) for x in a) + "\n")

    w("# c2py23 C coverage report")
    w("")
    w("Generated locally by tools/measure_c_coverage.py (gcov).")
    w("Merged across %d instrumented compilation units." % len(gcov_datas))
    w("")
    w("## Merged runtime coverage")
    w("")
    w("| source | lines | covered | % |")
    w("|--------|------:|--------:|-----:|")
    for s, (total, covered, pct) in sorted(runtime_summary.items()):
        w("| %s | %d | %d | %.1f%% |" % (s, total, covered, pct))
    w("")
    w("## Uncovered runtime lines (never executed by any module)")
    w("")
    w("These are the gaps for this platform/Python. Lines executed by *no*")
    w("module in the suite may hide a latent runtime bug (the _variants_*")
    w("Python-2.7 segfault lived in an unexercised code path).")
    w("")
    w("```")
    for s in ("c2py_runtime.c", "c2py_dlsym.c"):
        z = uncovered[s]
        w("%s uncovered: %d of %d" % (s, len(z), len(agg.get(s, {}))))
        for lineno in z[:120]:
            w("  %s:%d" % (s, lineno))
        if len(z) > 120:
            w("  ... (%d more)" % (len(z) - 120))
    w("```")
    w("")
    w("## Per-module wrapper coverage")
    w("")
    w("| module wrapper source | lines | covered | % |")
    w("|-----------------------|------:|--------:|-----:|")
    for src, total, covered, pct in sorted(per_module):
        w("| %s | %d | %d | %.1f%% |" % (src, total, covered, pct))
    w("")
    mt.close()

    print("Wrote %s" % REPORT)
    print("")
    print("Merged runtime coverage:")
    for s, (total, covered, pct) in sorted(runtime_summary.items()):
        print("  %-18s %5d/%-5d %6.1f%%" % (s, covered, total, pct))
    overall_lines = sum(len(v) for v in agg.values())
    overall_cov = sum(1 for v in agg.values() for x in v.values() if x > 0)
    print("  (all sources aggregated: %d/%d lines covered)" % (overall_cov, overall_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
