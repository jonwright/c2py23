"""Parametric generator tests: assert the emitted C for codegen branches.

Exercises c2py23/generator.py (line cover ~88%; branch gaps are in the
output-object, variant, single-header, alias and GIL-release paths that the
runtime suite never drives).  Pure Python; no extension build needed.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from c2py23.parser import from_c2py_dict
from c2py23.generator import generate


def _gen(spec, single=False):
    return generate(from_c2py_dict(spec), use_single_header=single)


def _func(py_sig, c_sig, maps, checks=None, outputs=None, gil_release=False,
          default_raise=None, variants=None, when=None, group=None):
    ol = {}
    if when is not None:
        ol["when"] = when
    ol["sig"] = c_sig
    ol["map"] = maps
    if variants is not None:
        ol["group"] = group or "g"
        ol["variants"] = variants
    if outputs is not None:
        ol["outputs"] = outputs
    f = {"py_sig": py_sig, "c_overloads": [ol]}
    if checks is not None:
        f["checks"] = checks
    if gil_release:
        f["gil_release"] = True
    if default_raise is not None:
        f["default_raise"] = default_raise
    return f


def _mk(name, funcs, **kw):
    spec = {"module": name, "source": [name + ".c"], "functions": funcs}
    spec.update(kw)
    return spec


def test_int64_output_uses_PyLong_FromLongLong():
    code = _gen(_mk("m64", [
        _func("proc(a: buffer) -> void", "void proc(const int64_t *a, intptr_t n, int64_t *out)",
              {"a": "a.ptr", "n": "a.n"}, outputs={"out": "int64_t"}),
    ]))
    assert "PyLong_FromLongLong" in code
    assert "PyFloat_FromDouble" not in code


def test_uint64_output_uses_PyLong_FromUnsignedLongLong():
    code = _gen(_mk("m64u", [
        _func("proc(a: buffer) -> void", "void proc(const uint64_t *a, intptr_t n, uint64_t *out)",
              {"a": "a.ptr", "n": "a.n"}, outputs={"out": "uint64_t"}),
    ]))
    assert "PyLong_FromUnsignedLongLong" in code


def test_double_output_uses_PyFloat_FromDouble():
    code = _gen(_mk("mdbl", [
        _func("proc(a: buffer) -> void", "void proc(const double *a, intptr_t n, double *out)",
              {"a": "a.ptr", "n": "a.n"}, outputs={"out": "double"}),
    ]))
    assert "PyFloat_FromDouble" in code


def test_gil_release_emits_save_restore():
    code = _gen(_mk("mgil", [
        _func("proc(a: buffer) -> void", "void proc(const float *a, int n)",
              {"a": "a.ptr", "n": "a.n"}, gil_release=True),
    ]))
    assert "PyEval_SaveThread" in code
    assert "PyEval_RestoreThread" in code
    assert "_gil_release_proc" in code


def test_default_raise_emits_message():
    code = _gen(_mk("mdr", [
        _func("proc(a: buffer) -> void", "void proc(const float *a, int n)",
              {"a": "a.ptr", "n": "a.n"},
              default_raise="TypeError: expected float buffer"),
    ]))
    assert "PyExc_TypeError" in code
    assert "expected float buffer" in code


def test_decode_time_dtype_check_emitted():
    code = _gen(_mk("mdt", [
        _func("proc(a: buffer) -> void", "void proc(const float *a, int n)",
              {"a": "a.ptr", "n": "a.n"},
              when="a.format == 'f'"),
    ]))
    assert "decode-time dtype check: a" in code
    assert "argument 1 (a)" in code
    assert "has unsupported format" in code
    assert "c2py_format_is_native" in code


def test_decode_time_dtype_check_position():
    code = _gen(_mk("mdt2", [
        _func("proc(a: buffer, b: buffer) -> void",
              "void proc(const double *a, const float *b, int n)",
              {"a": "a.ptr", "b": "b.ptr", "n": "a.n"},
              when="a.format == 'd' and b.format == 'f'"),
    ]))
    assert "argument 1 (a)" in code
    assert "argument 2 (b)" in code


def test_no_decode_check_for_shape_only_dispatch():
    code = _gen(_mk("mdt3", [
        _func("proc(p: buffer) -> void", "void proc(const double p[][3], int n)",
              {"p": "p.ptr", "n": "p.n"},
              when="p.shape[1] == 3"),
    ]))
    assert "decode-time dtype check" not in code


def test_decode_time_dtype_check_honors_itemsize_fallback():
    # A `when:` with an `or <buf>.itemsize == N` fallback (used to accept
    # numpy's 'L' for uint32 on Windows/LLP64, where sizeof(long) == 4)
    # must not be reduced to a bare `_last == 'I'` equality check -- that
    # rejects a valid same-width buffer whose format char differs by
    # platform. See: reorder_u16_a32 TypeError on Windows wheels.
    code = _gen(_mk("mdt4", [
        _func("proc(adr: buffer) -> void", "void proc(const uint32_t *adr, int n)",
              {"adr": "adr.ptr", "n": "adr.n"},
              when="adr.format == 'I' or adr.itemsize == 4"),
    ]))
    assert "decode-time dtype check: adr" in code
    assert "info_adr.itemsize == 4" in code
    assert "itemsize in (4)" in code


def test_slow_axis_array_dims():
    code = _gen(_mk("mta", [
        _func("proc(m: buffer) -> void", "void proc(const float m[][3], int n)",
              {"m": "m.ptr", "n": "m.n"}),
    ]))
    assert "_c2py_slow_axis_info_m" in code


def test_variants_group_emits_variants_fn():
    spec = {
        "module": "mvar",
        "source": ["mvar.c"],
        "functions": [
            {
                "py_sig": "proc(a: buffer) -> void",
                "checks": ["a.format == 'f'"],
                "c_overloads": [
                    {
                        "when": "a.format == 'f'",
                        "map": {"p": "a.ptr", "n": "a.n"},
                        "group": "g",
                        "variants": [
                            {"sig": "void proc_a(const float *p, int n)", "default": True},
                            {"sig": "void proc_b(const float *p, int n)", "default": False},
                        ],
                    }
                ],
            }
        ],
    }
    code = generate(from_c2py_dict(spec))
    assert "_variants_proc" in code
    assert "PyBytes_FromStringAndSize" in code
    assert "PyTuple_New" in code


def test_single_header_mode():
    code = _gen(_mk("mh", [
        _func("proc(a: buffer) -> void", "void proc(const float *a, int n)",
              {"a": "a.ptr", "n": "a.n"}),
    ]), single=True)
    assert "#define C2PY_IMPLEMENTATION" in code
    assert '#include "c2py.h"' in code


def test_fastcall_and_varargs_method_tables():
    code = _gen(_mk("mft", [
        _func("proc(a: buffer) -> void", "void proc(const float *a, int n)",
              {"a": "a.ptr", "n": "a.n"}),
    ]))
    assert "_methods_varargs" in code
    assert "_methods_fastcall" in code


def test_void_function_returns_none():
    code = _gen(_mk("mvoid", [
        _func("proc(a: buffer) -> void", "void proc(const float *a, int n)",
              {"a": "a.ptr", "n": "a.n"}),
    ]))
    assert "Py_RETURN_NONE" in code


def test_two_writable_buffers_emits_alias_check():
    code = _gen(_mk("malias", [
        _func("pair(x: buffer, y: buffer) -> void", "void pair(float *x, float *y, int n)",
              {"x": "x.ptr", "y": "y.ptr", "n": "x.n"}),
    ]))
    assert "buffer aliasing forbidden" in code
    assert "PyExc_ValueError" in code
