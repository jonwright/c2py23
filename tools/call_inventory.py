#!/usr/bin/env python
"""Report exposed-but-never-called Python functions from a c2py23 test run.

Run the suite with call recording:

    C2PY_CALL_INVENTORY=1 python -m pytest tests/...

Then:

    python tools/call_inventory.py

It reads tests/.call_coverage.json (written by the tests/conftest.py hook)
and, for every built test-case module, prints which exposed callables were
actually invoked and which were never called on this platform.  The
exposed-but-never-called list is exactly the class of gap that let the
_variants_*() Python-2.7 segfault slip through CI: a generated function
can carry a latent runtime defect and pass every test if nothing calls it.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES = os.path.join(ROOT, "tests", "cases")
JSON = os.path.join(ROOT, "tests", ".call_coverage.json")

IS_PY3 = sys.version_info[0] >= 3


def _case_modules():
    """Yield (directory, module_name) for each built test-case extension."""
    for pattern in ("*.so", "*.pyd"):
        for so in sorted(glob.glob(os.path.join(CASES, "*", pattern))):
            name = os.path.splitext(os.path.basename(so))[0]
            yield os.path.dirname(so), name


def _load_module(name, d):
    if name in sys.modules:
        return sys.modules[name]
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        return __import__(name)
    except Exception:
        return None


def _exposed(module):
    out = []
    for attr in sorted(dir(module)):
        if attr.startswith("__"):
            continue
        try:
            if callable(getattr(module, attr)):
                out.append(attr)
        except Exception:
            pass
    return out


def main():
    if not os.path.exists(JSON):
        print(
            "No %s found.\n"
            "Run:  C2PY_CALL_INVENTORY=1 python -m pytest tests/ ...\n"
            "then re-run this script." % JSON,
            file=sys.stderr,
        )
        return 1

    with open(JSON) as f:
        called = json.load(f)

    total_exposed = 0
    total_called = 0
    gap_names = []
    print("=== exposed Python functions: called vs never-called (this run) ===")
    for d, name in _case_modules():
        module = _load_module(name, d)
        if module is None:
            continue
        exposed = _exposed(module)
        called_set = set(called.get(name, []))
        called_in_exposed = sorted(s for s in exposed if s in called_set)
        never = sorted(s for s in exposed if s not in called_set)
        total_exposed += len(exposed)
        total_called += len(called_in_exposed)
        status = "OK" if never == [] else "GAP"
        print("[%s] %-14s exposed=%-3d called=%-3d" % (status, name, len(exposed), len(called_in_exposed)))
        for s in called_in_exposed:
            print("        called      %s" % s)
        for s in never:
            print("        NEVER       %s" % s)
            gap_names.append("%s.%s" % (name, s))

    print("")
    print("exposed=%d called=%d never_called=%d" % (total_exposed, total_called, len(gap_names)))
    if gap_names:
        print("exposed-but-never-called:")
        for g in gap_names:
            print("  - %s" % g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
