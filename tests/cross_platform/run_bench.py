#!/usr/bin/env python3
"""Cross-platform gold benchmark runner -- writes results.json."""

import sys, os, time, subprocess, json

HERE = os.path.dirname(os.path.abspath(__file__))
GRAALPY = os.path.join(HERE, "..", "graalpy-install", "bin", "graalpy")
RESULTS = os.path.join(HERE, "results.json")

results = {}


def bench(name, python, code, timeout=30):
    out = subprocess.check_output([python, "-c", code], stderr=subprocess.STDOUT, timeout=timeout, cwd=HERE).decode()
    ns = float(out.strip())
    results[name] = ns
    return ns


print("--- CPython 3.12 ---")
bench(
    "cpython_noargs",
    "python3",
    """
import gold_noargs, time
N=10_000_000
for _ in range(2000): gold_noargs.fastcall()
t0=time.perf_counter_ns()
for _ in range(N): gold_noargs.fastcall()
print((time.perf_counter_ns()-t0)/N)
""",
)
bench(
    "cpython_vnorm",
    "python3",
    """
import gold_vnorm, time, numpy as np
N=3; IT=200_000
vec=np.random.rand(N,3).astype(np.float64)
mods=np.zeros(N,np.float64)
for _ in range(500): gold_vnorm.fastcall(vec,mods)
t0=time.perf_counter_ns()
for _ in range(IT): gold_vnorm.fastcall(vec,mods)
print((time.perf_counter_ns()-t0)/IT)
""",
)

print("--- PyPy 7.3.15 ---")
bench(
    "pypy_noargs",
    "pypy3",
    """
import gold_noargs, time
N=2_000_000
for _ in range(1000): gold_noargs.noargs()
t0=time.perf_counter_ns()
for _ in range(N): gold_noargs.noargs()
print((time.perf_counter_ns()-t0)/N)
""",
)
bench(
    "pypy_vnorm",
    "pypy3",
    """
import gold_vnorm, time, numpy as np
N=3; IT=100_000
vec=np.random.rand(N,3).astype(np.float64)
mods=np.zeros(N,np.float64)
for _ in range(300): gold_vnorm.varargs(vec,mods)
t0=time.perf_counter_ns()
for _ in range(IT): gold_vnorm.varargs(vec,mods)
print((time.perf_counter_ns()-t0)/IT)
""",
)

print("--- GraalPy 25.1.3 ---")
try:
    bench(
        "graalpy_noargs",
        GRAALPY,
        """
import sys; sys.path.insert(0,'.')
import gold_noargs, time
N=2_000_000
for _ in range(1000): gold_noargs.noargs()
t0=time.perf_counter_ns()
for _ in range(N): gold_noargs.noargs()
print((time.perf_counter_ns()-t0)/N)
""",
    )
except Exception as e:
    results["graalpy_noargs"] = 0
    print("  noargs FAIL:", e)

try:
    bench(
        "graalpy_vnorm",
        GRAALPY,
        """
import sys; sys.path.insert(0,'.')
import gold_vnorm, time, numpy as np
N=3; IT=100_000
vec=np.random.rand(N,3).astype(np.float64)
mods=np.zeros(N,np.float64)
for _ in range(300): gold_vnorm.varargs(vec,mods)
t0=time.perf_counter_ns()
for _ in range(IT): gold_vnorm.varargs(vec,mods)
print((time.perf_counter_ns()-t0)/IT)
""",
        timeout=60,
    )
except Exception as e:
    results["graalpy_vnorm"] = 0
    print("  vnorm FAIL:", e)

with open(RESULTS, "w") as f:
    json.dump(results, f, indent=1)
print("Wrote", RESULTS)
