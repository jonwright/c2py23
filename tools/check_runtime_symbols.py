#!/usr/bin/env python
"""Static self-check of the c2py23 runtime symbol-resolution table.

This scans the dlsym backend (c2py_dlsym.c), the pythonh backend
(c2py_pythonh.c), the ABI header (c2py_runtime.h), and the code generator
(c2py23/generator.py) to find latent "NULL function-pointer" hazards of
the class that took down _variants_*() on Python 2.7:

  * A C-API symbol that only exists under one Python line (e.g.
    PyBytes_* vs PyString_*, PyCapsule_* vs PyCObject_*) resolved with
    NO fallback to its sibling name, so the slot silently stays NULL on
    the other line.  If generated/runtime code then calls through that
    slot without a guard -> SIGSEGV.

  * A C-API symbol the generator emits that has no matching slot or no
    resolution at all.

  * A slot left NULL on a Python version even though that version exports
    the symbol.  Discovered example (the pythonh/2.7 long-long slots) is a
    FALSE POSITIVE: those slots are only consumed via dlsym-mode macros
    (inside `#ifndef C2PY_USE_PYTHON_H`), so pythonh generated code uses
    the real `<Python.h>` symbol and never dereferences the NULL slot.
    Slots whose macro mapping is dlsym-only are reported as informational,
    not as hazards.

It is a measurement tool, not a test: it prints a report and exits 0
unless a command-line gate requests otherwise.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RT = os.path.join(ROOT, "c2py23", "runtime")
DL = os.path.join(RT, "c2py_dlsym.c")
PH = os.path.join(RT, "c2py_pythonh.c")
RH = os.path.join(RT, "c2py_runtime.h")
GEN = os.path.join(ROOT, "c2py23", "generator.py")

# Version-sensitive C-API names: (py3 symbol, [py2 symbol(s)])
ALIASES = {
    "Bytes_FromStringAndSize": ("PyBytes_FromStringAndSize", ["PyString_FromStringAndSize"]),
    "Capsule_GetPointer": ("PyCapsule_GetPointer", ["PyCObject_AsVoidPtr"]),
}

# Slots whose C symbol exists only on Python 3 (or free-threaded builds), so
# leaving them NULL on Python 2 in the pythonh backend is correct, not a gap.
PY3_ONLY_SLOTS = frozenset([
    "Module_Create2",          # PyModule_Create2 is Python 3 only
    "exc_BufferError",         # PyExc_BufferError is Python 3 only
    "Capsule_GetPointer",      # PyCapsule_* is Python 3 only
    "Unstable_Module_SetGIL",  # PyUnstable_Module_SetGIL is 3.13t/FT only
])


def read(path):
    with open(path, "r") as f:
        return f.read()


def fnptr_slots(text):
    """Return the set of function-pointer slot names declared in the struct."""
    return set(re.findall(r"\(\*(\w+)\)\(", text))


def guarded_slots(text):
    """Return slots referenced in a NULL guard such as `!C2PY.Slot` or `C2PY.Slot == NULL`.

    A slot with a NULL guard at its use site will not deref NULL even if the
    underlying symbol is missing on some Python line, so it is not a hazard.
    """
    guards = set(re.findall(r"!C2PY\.(\w+)", text))
    guards |= set(re.findall(r"C2PY\.(\w+)\s*==\s*NULL", text))
    return guards


def dlsym_only_slots(text):
    """Return slots whose PyXxx macro -> C2PY slot mapping lives ONLY inside
    the `#ifndef C2PY_USE_PYTHON_H` block of c2py_runtime.h.

    In pythonh mode those macros are not defined, so generated code resolves
    the PyXxx name to the real `<Python.h>` symbol instead of the C2PY slot.
    Such a slot is therefore read only in dlsym mode; a NULL value in the
    pythonh backend is not a hazard.
    """
    slots = set()
    depth = 0
    for line in text.split("\n"):
        if re.match(r"^\s*#ifndef\s+C2PY_USE_PYTHON_H\b", line):
            depth = 1
            continue
        if depth == 0:
            continue
        if re.match(r"^\s*#(?:if|ifdef|ifndef)\b", line):
            depth += 1
            continue
        if re.match(r"^\s*#endif\b", line):
            depth -= 1
            continue
        m = re.match(r"^\s*#define\s+(Py\w+)\([^)]*\)\s+C2PY\.(\w+)", line)
        if m:
            slots.add(m.group(2))
    return slots


def parse_slots_dlsym(text):
    """Return {slot: {"symbols": [..], "req": bool}} from c2py_dlsym.c."""
    result = {}
    # RESOLVE_REQ / RESOLVE: anchored so C2PY_RESOLVE(...) is not misread.
    pat_req = re.compile(r"(?<![A-Za-z0-9_])RESOLVE_REQ\(C2PY\.(\w+),\s*\"([^\"]+)\"\)")
    pat_opt = re.compile(r"(?<![A-Za-z0-9_])RESOLVE\(C2PY\.(\w+),\s*\"([^\"]+)\"\)")
    for m in pat_req.finditer(text):
        d = result.setdefault(m.group(1), {"symbols": [], "req": False})
        d["symbols"].append(m.group(2))
        d["req"] = True
    for m in pat_opt.finditer(text):
        d = result.setdefault(m.group(1), {"symbols": [], "req": False})
        d["symbols"].append(m.group(2))
        d.setdefault("opt", True)

    # Multi-line _resolve_raw assignments:  C2PY.Slot = <cast> _resolve_raw("Sym")
    pat_raw = re.compile(r"C2PY\.(\w+)\s*=\s*[^;]*?_resolve_raw\(\"([^\"]+)\"\)", re.DOTALL)
    for m in pat_raw.finditer(text):
        d = result.setdefault(m.group(1), {"symbols": [], "req": False})
        if m.group(2) not in d["symbols"]:
            d["symbols"].append(m.group(2))
    return result


def parse_slots_pythonh(text):
    """Return {slot: {"py2": [...], "py3": [...], "null_py2": bool, "null_py3": bool}}."""
    result = {}
    stack = []  # version markers: "py2", "py3", or None (other/unknown scope)
    lines = text.split("\n")
    for raw in lines:
        s = raw.strip()
        if re.match(r"#if\s+PY_MAJOR_VERSION\s*>=\s*3\b", s):
            stack.append("py3")
            continue
        if re.match(r"#if\s+PY_MAJOR_VERSION\s*==\s*2\b", s):
            stack.append("py2")
            continue
        if re.match(r"#if\b", s):
            stack.append(None)
            continue
        if re.match(r"#else\b", s):
            if stack and stack[-1] == "py3":
                stack[-1] = "py2"
            elif stack and stack[-1] == "py2":
                stack[-1] = "py3"
            continue
        if re.match(r"#endif\b", s):
            if stack:
                stack.pop()
            continue
        m = re.match(r"C2PY\.(\w+)\s*=\s*(NULL|[A-Za-z_]+)", s)
        if not m:
            continue
        slot = m.group(1)
        rhs = m.group(2)
        branch = None
        for mk in reversed(stack):
            if mk in ("py2", "py3"):
                branch = mk
                break
        d = result.setdefault(slot, {"py2": [], "py3": [], "null_py2": False, "null_py3": False})
        if branch == "py2":
            if rhs == "NULL":
                d["null_py2"] = True
            else:
                d["py2"].append(rhs)
        elif branch == "py3":
            if rhs == "NULL":
                d["null_py3"] = True
            else:
                d["py3"].append(rhs)
        else:
            # Common (unconditional) assignment, or inside a non-version #if.
            if slot in ("Long_FromLongLong", "Long_FromUnsignedLongLong", "Long_AsLongLong"):
                d["null_py2"] = (rhs == "NULL")
    return result


def parse_macro_map(text):
    """Return {PyName: slot} from the PyXxx macro -> C2PY.Slot table."""
    mmap = {}
    pat = re.compile(r"#define\s+(Py[A-Za-z_0-9]+)\([^)]*\)\s+C2PY\.(\w+)")
    for m in pat.finditer(text):
        mmap[m.group(1)] = m.group(2)
    return mmap


def parse_generated_symbols(text):
    """Return set of Py* and C2PY.Slot tokens emitted by the generator."""
    toks = set()
    for m in re.finditer(r"Py[A-Za-z_0-9]+", text):
        toks.add(m.group(0))
    slots = set()
    for m in re.finditer(r"C2PY\.(\w+)", text):
        slots.add(m.group(1))
    return toks, slots


def main():
    dlsym = read(DL)
    pythonh = read(PH)
    runtime_h = read(RH)
    generator = read(GEN)

    dlsym_slots = parse_slots_dlsym(dlsym)
    ph_slots = parse_slots_pythonh(pythonh)
    macro_map = parse_macro_map(runtime_h)
    gen_toks, gen_slots = parse_generated_symbols(generator)
    fn = fnptr_slots(runtime_h)
    guarded = guarded_slots(runtime_h)
    dlsym_only = dlsym_only_slots(runtime_h)

    issues = []
    info = []

    # 0. Slots referenced by the generator or macro table that are not fn-pointers.
    used_fn = set(gen_slots) & fn
    used_fn.update(set(macro_map.values()) & fn)
    used_fn.update(ALIASES.keys())

    # 1. For each alias slot, ensure a fallback to the py2 sibling exists.
    for slot, (py3, py2s) in ALIASES.items():
        syms = dlsym_slots.get(slot, {}).get("symbols", [])
        has_py3 = py3 in syms
        has_py2 = any(s in py2s for s in syms)
        if not has_py3 and not has_py2:
            issues.append("ALIAS slot %s: not resolved at all" % slot)
            continue
        if has_py3 and not has_py2:
            if slot in guarded:
                info.append(
                    "ALIAS slot %s: Py3 name %s with NO Py2 fallback, but NULL-guarded at use site "
                    "(%s is silently disabled on Python 2)." % (slot, py3, " or ".join(py2s))
                )
            else:
                issues.append(
                    "ALIAS slot %s: resolved only from Py3 name %s -- NO Py2 fallback (%s) "
                    "and no NULL guard. NULL on Python 2 if called." % (slot, py3, " or ".join(py2s))
                )
        else:
            info.append("ALIAS slot %s: OK (Py3=%s, Py2 fallback=%s)" % (slot, has_py3, has_py2))

    # 2. Every function-pointer slot used by the generator/macros must be resolved
    #    (dlsym) or assigned (pythonh).
    for slot in sorted(used_fn):
        resolved = slot in dlsym_slots or slot in ph_slots
        if not resolved:
            issues.append("GENERATED-CODE fn-ptr slot %s: no resolution in dlsym or pythonh backend" % slot)

    # 3. Slots left NULL on Python 2 in pythonh even though py2.7 exports them.
    #    This is only a hazard if the slot (a) has a real Python 2.7 C symbol,
    #    (b) is NULL on py2, and (c) is actually read in pythonh mode.
    #    Slots whose PyXxx macro is dlsym-only are read via <Python.h> in
    #    pythonh mode, so a NULL C2PY slot is never dereferenced there.
    #    Slots in PY3_ONLY_SLOTS (and the version flags) have no py2.7 symbol
    #    at all, so NULL is correct.
    for slot in sorted(set(ph_slots.keys()) & fn):
        d = ph_slots[slot]
        null_on_py2 = d.get("null_py2")
        if not null_on_py2:
            continue
        if slot in dlsym_only:
            info.append(
                "PYTHONH py2.7: %s left NULL, but the slot is dlsym-only-consumed "
                "(pythonh generated code resolves it via <Python.h>) -- no runtime impact."
                % slot
            )
            continue
        if slot in PY3_ONLY_SLOTS:
            continue  # pythonh mode flags the py3-only NAME as unavailable on py2; correct.
        issues.append(
            "PYTHONH py2.7: %s left NULL but Python 2.7 exports it "
            "and it is read in pythonh mode -- would deref NULL." % slot
        )

    # 4. Report any fn-ptr slot that is resolved but neither REQ nor obviously guarded.
    for slot in sorted(dlsym_slots):
        d = dlsym_slots[slot]
        if slot in fn and not d.get("req") and d.get("opt"):
            info.append("OPTIONAL slot %s: RESOLVE (non-fatal) -> %s; verify NULL guard at use site" % (
                slot, d["symbols"]))

    print("=== c2py23 runtime symbol-resolution self-check ===")
    print("dlsym slots resolved: %d" % len(dlsym_slots))
    print("pythonh slots seen:   %d" % len(ph_slots))
    print("generator Py* tokens: %d, C2PY.* slots: %d" % (len(gen_toks), len(gen_slots)))
    print("")
    if info:
        for line in info:
            print("  [INFO ] %s" % line)
    if issues:
        print("")
        print("---- POTENTIAL GAPS ----")
        for line in issues:
            print("  [WARN ] %s" % line)
        sys.exit(1)
    else:
        print("")
        print("No unguarded version-specific conflicts detected.")


if __name__ == "__main__":
    main()
