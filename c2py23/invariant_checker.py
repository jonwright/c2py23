"""Invariant checker for generated C code.

Scans generated C source and verifies structural properties:
  - Buffer acquire/release pairs in wrapper functions
  - GIL save/restore pairs in impl functions
  - Output scalar NULL checks + PyTuple_SetItem
  - Balanced braces

Raises ValueError with line number on first violation.
"""

from __future__ import print_function

import re


def verify_c_invariants(code):
    """Check generated C for structural errors before returning.

    Scans the generated C and verifies:
      - Buffer acquire/release pairs in wrapper functions
      - GIL save/restore pairs in impl functions
      - Output scalar NULL checks + PyTuple_SetItem
      - Balanced braces

    Raises ValueError with line number on first violation.
    """
    lines = code.split("\n")
    _check_balanced_braces(lines)
    _check_buffer_invariants(lines)
    _check_output_scalar_invariants(lines)


def _check_balanced_braces(lines):
    """Verify brace depth returns to zero after each function."""
    depth = 0
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("static PyObject*"):
            if depth != 0:
                raise ValueError("Line %d: unbalanced braces before function start " "(depth=%d)" % (lineno, depth))
        if not stripped or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        if stripped.startswith("#"):
            continue
        depth += stripped.count("{") - stripped.count("}")
        if depth < 0:
            raise ValueError("Line %d: unmatched closing brace" % lineno)
    if depth != 0:
        raise ValueError("End of file: unbalanced braces (depth=%d)" % depth)


def _check_buffer_invariants(lines):
    """Check buffer acquire/release pairs in every wrapper function."""
    lineno = 0
    while lineno < len(lines):
        line = lines[lineno]
        stripped = line.strip()

        if stripped.startswith("static PyObject*"):
            end = _check_one_wrapper(lines, lineno)
            lineno = end + 1 if end else lineno + 1
        else:
            lineno += 1


def _check_one_wrapper(lines, start_lineno):
    """Check buffer / GIL invariants for a single wrapper function."""
    first_brace = None
    depth = 0
    end_lineno = None
    for i in range(start_lineno, len(lines)):
        stripped = lines[i].strip()
        depth += stripped.count("{") - stripped.count("}")
        if "{" in stripped and first_brace is None:
            first_brace = i
        if depth == 0 and first_brace is not None:
            end_lineno = i
            break

    if end_lineno is None or first_brace is None:
        return None

    buf_names = []
    acq_names = set()
    pending_acquires = []
    acquired = []
    released = []
    acquire_count = 0
    in_cleanup = False
    gil_save_count = 0
    gil_restore_count = 0

    for lineno in range(first_brace, end_lineno + 1):
        line = lines[lineno]
        stripped = line.strip()

        if not stripped or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        if stripped.startswith("#"):
            continue

        m = re.match(r"\s*Py_buffer\s+(buf_\w+);", line)
        if m:
            buf_names.append(m.group(1))
            continue

        m = re.match(r"\s*int\s+(acq_\w+)\s*=\s*0;", line)
        if m:
            acq_names.add(m.group(1))
            continue

        if stripped == "cleanup:":
            in_cleanup = True
            continue

        # Also detect cleanup by the release pattern when label is absent
        if not in_cleanup and re.match(r"\s*if\s*\(\s*(acq_\w+)\s*\)\s*c2py_release_buffer\(&(buf_\w+)\);", line):
            in_cleanup = True

        m = re.match(r".*if\s*\(\s*c2py_acquire(_buffer)?\(([^,]+),\s*&(buf_\w+),", line)
        if m:
            buf_name = m.group(3)
            acquire_count += 1
            pending_acquires.append(buf_name)

            next_line = None
            for j in range(lineno + 1, min(lineno + 5, end_lineno + 1)):
                nl = lines[j].strip()
                if nl and not nl.startswith("/*") and not nl.startswith("*"):
                    next_line = nl
                    break

            if acquire_count == 1:
                if next_line and "return NULL" not in next_line:
                    raise ValueError(
                        "Line %d: first buffer acquire must return NULL "
                        "on failure, got: %s" % (lineno + 1, next_line)
                    )
            else:
                if next_line and "goto cleanup" not in next_line:
                    raise ValueError(
                        "Line %d: subsequent buffer acquire must goto cleanup "
                        "on failure, got: %s" % (lineno + 1, next_line)
                    )
            continue

        m = re.match(r"\s*(acq_\w+)\s*=\s*1;", line)
        if m:
            flag_name = m.group(1)
            exp_buf = re.sub(r"^acq_", "buf_", flag_name)
            if exp_buf not in buf_names:
                raise ValueError(
                    "Line %d: acq flag '%s' has no matching buf variable " "'%s'" % (lineno + 1, flag_name, exp_buf)
                )
            if flag_name not in acq_names:
                raise ValueError("Line %d: acq flag '%s' was not declared" % (lineno + 1, flag_name))
            if not pending_acquires or pending_acquires[0] != exp_buf:
                raise ValueError(
                    "Line %d: acq flag '%s' set but no pending acquire " "for '%s'" % (lineno + 1, flag_name, exp_buf)
                )
            pending_acquires.pop(0)
            acquired.append(exp_buf)
            continue

        if pending_acquires and (
            stripped.startswith("return")
            or stripped.startswith("goto")
            or stripped.startswith("if")
            or stripped.startswith("{")
            or stripped.startswith("}")
        ):
            continue

        if in_cleanup:
            m = re.match(
                r"\s*if\s*\(\s*(acq_\w+)\s*\)\s*c2py_release_buffer\(&(buf_\w+)\);",
                line,
            )
            if m:
                released.append(m.group(2))
                continue

        if "PyEval_SaveThread" in stripped:
            gil_save_count += 1
        if "PyEval_RestoreThread" in stripped:
            gil_restore_count += 1

    if pending_acquires:
        raise ValueError(
            "Function starting at line %d: buffer(s) '%s' acquired but "
            "never flagged with acq_X = 1" % (start_lineno + 1, ", ".join(pending_acquires))
        )

    for buf in acquired:
        if buf not in released:
            raise ValueError(
                "Function starting at line %d: buffer '%s' acquired but "
                "not released in cleanup" % (start_lineno + 1, buf)
            )

    for buf in reversed(released):
        if buf not in acquired:
            raise ValueError(
                "Function starting at line %d: buffer '%s' released but " "never acquired" % (start_lineno + 1, buf)
            )

    expected_reverse = list(reversed(acquired))
    if released and released != expected_reverse:
        raise ValueError(
            "Function starting at line %d: release order mismatch. "
            "Expected reverse of acquire: %s, got: %s" % (start_lineno + 1, expected_reverse, released)
        )

    if gil_save_count != gil_restore_count:
        raise ValueError(
            "Function starting at line %d: unbalanced GIL save/restore "
            "(%d save vs %d restore)" % (start_lineno + 1, gil_save_count, gil_restore_count)
        )

    return end_lineno


def _check_output_scalar_invariants(lines):
    """Check that every output PyObject has NULL check + PyTuple_SetItem."""
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()

        m = re.match(r"PyObject\s*\*\s*_c2py_tup\s*=\s*PyTuple_New\(", stripped)
        if m:
            next_line = None
            for j in range(lineno, min(lineno + 3, len(lines) + 1)):
                nl = lines[j - 1].strip()
                if nl and not nl.startswith("/*") and not nl.startswith("*") and "PyTuple_New" not in nl:
                    next_line = nl
                    break
            if next_line and "_c2py_tup == NULL" not in next_line:
                raise ValueError("Line %d: PyTuple_New missing NULL check, got: %s" % (lineno, next_line))

        m = re.match(
            r"PyObject\s*\*\s*(_c2py_obj\d+)\s*="
            r"\s*(PyLong_FromLong|PyLong_FromLongLong|"
            r"PyLong_FromUnsignedLongLong|PyFloat_FromDouble)",
            stripped,
        )
        if m:
            obj_name = m.group(1)
            has_null_check = False
            has_decref = False
            has_setitem = False
            in_null_block = False

            for j in range(lineno, min(lineno + 10, len(lines) + 1)):
                nl = lines[j - 1].strip()
                if not nl or nl.startswith("/*") or nl.startswith("*"):
                    continue
                if "if (%s == NULL)" % obj_name in nl:
                    in_null_block = True
                    has_null_check = True
                    continue
                if in_null_block:
                    if "Py_DECREF(_c2py_tup)" in nl:
                        has_decref = True
                    if "}" == nl:
                        in_null_block = False
                        continue
                if "PyTuple_SetItem(_c2py_tup," in nl and obj_name in nl:
                    has_setitem = True

            if not has_null_check:
                raise ValueError("Line %d: '%s' missing NULL check" % (lineno, obj_name))
            if not has_decref:
                raise ValueError("Line %d: '%s' missing Py_DECREF in NULL check" % (lineno, obj_name))
            if not has_setitem:
                raise ValueError("Line %d: '%s' missing PyTuple_SetItem" % (lineno, obj_name))
