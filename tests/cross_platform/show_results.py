#!/usr/bin/env python3
"""Read results.json and print formatted table."""

import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results.json")

try:
    with open(RESULTS) as f:
        r = json.load(f)
except FileNotFoundError:
    print("No results.json found. Run: python3 run_bench.py && node pyodide_test.js")
    exit(1)


def ns(val, fmt=".0f"):
    if val and val > 0:
        return ("{:" + fmt + "}").format(val)
    return "      --"


print("=" * 60)
print("  CROSS-PLATFORM GOLD MICRO-BENCHMARKS")
print("=" * 60)
print()
print("  All C code compiled -O2.  Single-core, taskset -c 0.")
print("  noargs = f() -> None (10M calls CPython, 2M others)")
print("  vnorm  = vec[N,3] + mods[N] -> void, N=3 tiny")
print()
print(f"  {'Platform':20s} {'noargs (ns)':>12s} {'vnorm (ns)':>12s}")
print("  " + "-" * 46)

rows = [
    ("CPython 3.12", r.get("cpython_noargs"), r.get("cpython_vnorm")),
    ("PyPy 7.3.15", r.get("pypy_noargs"), r.get("pypy_vnorm")),
    ("GraalPy 25.1.3", r.get("graalpy_noargs"), r.get("graalpy_vnorm")),
    ("Pyodide 0.27.2", r.get("pyodide_noargs"), r.get("pyodide_vnorm")),
]

for label, noargs, vnorm in rows:
    print(f"  {label:20s} {ns(noargs):>12s} {ns(vnorm):>12s}")

print()
print("  Build artifacts: gold_noargs.{cpython,pypy,graalpy}.so, gold_noargs.wasm")
print("                    gold_vnorm.{cpython,pypy,graalpy}.so,  gold_vnorm.wasm")

# Ratios relative to CPython
c_noargs = r.get("cpython_noargs", 0)
c_vnorm = r.get("cpython_vnorm", 0)
if c_noargs and c_vnorm:
    print()
    print("  Ratios vs CPython:")
    for label, noargs, vnorm in rows[1:]:
        na = noargs / c_noargs if noargs and c_noargs else 0
        vn = vnorm / c_vnorm if vnorm and c_vnorm else 0
        parts = []
        if na:
            parts.append("noargs {:.1f}x".format(na))
        if vn:
            parts.append("vnorm {:.1f}x".format(vn))
        print(f"    {label:20s}  {', '.join(parts)}")
