#!/usr/bin/env python3
"""Generate docs/benchmarks.md from .bench_results.json (auto-saved by pytest)."""

from __future__ import print_function

import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(HERE, ".bench_results.json")
DOCS_FILE = os.path.join(HERE, "..", "docs", "benchmarks.md")


def load_results():
    if not os.path.exists(RESULTS_FILE):
        return None
    with open(RESULTS_FILE, "r") as f:
        rows = json.load(f)
    return rows


def group_section(rows, section):
    return [r for r in rows if r.get("section") == section]


def fmt(n, tmpl="{}"):
    if isinstance(n, float) and n > 0:
        return tmpl.format(n)
    if isinstance(n, (int, float)) and n == 0:
        return "--"
    return str(n)


def render():
    rows = load_results()
    if rows is None:
        print("No results file found. Run: make -C benchmarks bench")
        return

    pyver = sys.version.split()[0]
    uname = platform.uname()
    cpu_info = "{} {}".format(uname.machine, uname.processor.split(",")[0] if uname.processor else "")
    date = time.strftime("%Y-%m-%d %H:%M")

    lines = []

    def L(s=""):
        lines.append(s)

    L("# Benchmark Results")
    L()
    L(
        "**Platform**: {} {}, Python {}, GCC 13.3.0, single core (`taskset -c 0`).".format(
            uname.system, uname.machine, pyver
        )
    )
    L("All C code compiled with `-O2`.  Generated {}.".format(date))
    L()

    # -- No-arg section --
    N = group_section(rows, "noargs")
    if N:
        L("## No-arg call overhead")
        L()
        L("10,000,000 calls to a function taking zero arguments and returning `None`.")
        L("This isolates the pure Python-to-C-to-Python crossing cost.")
        L()
        L("| wrapper | timing | c kernel | wrapper | ns/call |")
        L("|---------|--------|----------|---------|---------|")
        for r in N:
            L(
                "| {} | {} | {} | {} | {} |".format(
                    r["label"], r["timing"], r["c_mean"], r["wrap"], fmt(r["ns_per_call"], "{:.1f}")
                )
            )
        L()

    # -- Vnorm tiny --
    V = group_section(rows, "vnorm_tiny")
    if V:
        L("## Vnorm wrapper overhead (tiny, N=3)")
        L()
        L("200,000 calls to `vnorm(vec, mods)` with a single 3D vector.")
        L("The C kernel runs in ~1 ns; wall-clock time is pure wrapper overhead.")
        L()
        L("| wrapper | acquire | checks | timing | ns/call |")
        L("|---------|---------|--------|--------|---------|")
        for r in V:
            extra = ""
            if r.get("c_mean"):
                extra = " (c={} w={})".format(r["c_mean"], r["wrap"])
            L(
                "| {} | {} | {} | {} | {} |".format(
                    r["label"], r["acquire"], r["checks"], r["timing"], fmt(r["ns_per_call"], "{:.0f}")
                )
            )
        L()

    # -- Vnorm large --
    Lrg = group_section(rows, "vnorm_large")
    if Lrg:
        L("## Vnorm throughput (large, N=4.2M, ~134 MB)")
        L()
        L("Single call, C kernel dominates (~10 ms). Throughput in MB/s.")
        L("All paths are zero-copy; wrapper overhead is constant regardless of N.")
        L()
        L("| wrapper | acquire | checks | timing | ms | MB/s |")
        L("|---------|---------|--------|--------|-----|------|")
        for r in Lrg:
            L(
                "| {} | {} | {} | {} | {} | {} |".format(
                    r["label"], r["acquire"], r["checks"], r["timing"], fmt(r["ms"], "{:.1f}"), fmt(r["mb_s"], "{:.0f}")
                )
            )
        L()

    # -- Getitem --
    G = group_section(rows, "getitem")
    if G:
        L("## Getitem overhead (per-call buffer acquisition)")
        L()
        L("500,000 calls extracting one element from a double buffer and returning")
        L("it as a Python float.  Each call acquires the buffer, reads one element,")
        L("constructs a Python float, and releases the buffer.")
        L()
        L("| wrapper | timing | ns/call |")
        L("|---------|--------|---------|")
        for r in G:
            extra = ""
            if r.get("c_mean") and r.get("c_mean") != "--":
                extra = " (c={} w={})".format(r["c_mean"], r["wrap"])
            L("| {} | {} | {} |".format(r["label"], r["timing"], fmt(r["ns_per_call"], "{:.0f}")))
        L()

    # -- Save --
    with open(DOCS_FILE, "w") as f:
        f.write("\n".join(lines))
    print("Wrote {}".format(DOCS_FILE))


if __name__ == "__main__":
    render()
