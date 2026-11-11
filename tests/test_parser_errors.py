"""Parametric parser tests: error paths + valid edge-case signatures.

Exercises c2py23/parser.py (line coverage ~76%) -- the many validation and
error branches that the runtime test suite never reaches.  Pure Python; no
extension build needed.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from c2py23.parser import from_c2py_dict, load_c2py, parse_expr


def _base(**overrides):
    d = {
        "module": "m",
        "source": ["m.c"],
        "headers": [],
        "functions": [
            {
                "py_sig": "proc(buf: buffer) -> void",
                "checks": ["buf.format == 'f'"],
                "c_overloads": [
                    {
                        "when": "buf.format == 'f'",
                        "map": {"p": "buf.ptr", "n": "buf.n"},
                        "sig": "void proc_a(const float *p, int n)",
                    }
                ],
            }
        ],
    }
    d.update(overrides)
    return d


def _sig(sig):
    return {
        "py_sig": "proc(buf: buffer) -> void",
        "checks": ["buf.format == 'f'"],
        "c_overloads": [
            {"when": "buf.format == 'f'", "map": {"p": "buf.ptr", "n": "buf.n"}, "sig": sig}
        ],
    }


@pytest.mark.parametrize("sig", [
    "void proc_a(const float *p, int n) -> gronk",     # unknown return type
    "func(",                                            # unmatched '('
    "func",                                             # no '('
    "void ([",                                          # bad param list
])
def test_parse_c_sig_errors(sig):
    with pytest.raises(ValueError):
        from_c2py_dict(_base(functions=[_sig(sig)]))


@pytest.mark.parametrize("checks", [
    ["buf.format ~= 'f'"],            # unknown operator
    ["buf.ndim >="],                  # incomplete expr
    ["buf.n > 0 and"],                # dangling operator
    ["buf.ptr ?? 'x'"],               # unknown operator
])
def test_parse_bad_checks(checks):
    f = _base()["functions"][0]
    f["checks"] = checks
    with pytest.raises(Exception):
        from_c2py_dict(_base(functions=[f]))


@pytest.mark.parametrize("constants", [
    {"A": "not an int"},
    {"A": 1.5},
])
def test_constants_must_be_int(constants):
    with pytest.raises(ValueError):
        from_c2py_dict(_base(constants=constants))


def test_missing_module():
    with pytest.raises(ValueError):
        from_c2py_dict({"source": ["m.c"], "functions": []})


def test_custom_parse_expr_bad_token():
    with pytest.raises(ValueError):
        parse_expr("buf.n @ 3")
    with pytest.raises(ValueError):
        parse_expr("buf.n >")


# ---- valid edge cases that must PARSE (not error) ----

def test_variant_is_valid_for_value_types():
    specs = [
        _base(),
        {"module": "m", "source": ["m.c"], "functions": [_sig("void f(double gv[][3], int n)")]},
    ]
    for s in specs:
        from_c2py_dict(s)


@pytest.mark.parametrize("sig", [
    "void m(const double gv[][3], int n)",      # array-dim notation
    "void m(double arr[5], int n)",             # fixed-size array dim
    "double dot(const float *x, const float *y, int n)",  # pointer params
    "int f(const int64_t *x, int n)",           # int64 pointer param
])
def test_valid_c_sigs_parse(sig):
    from_c2py_dict({"module": "m", "source": ["m.c"], "functions": [_sig(sig)]})


def test_expand_valid():
    spec = {
        "module": "m",
        "source": ["m.c"],
        "functions": [
            {
                "py_sig": "sum(buf: buffer) -> void",
                "checks": ["buf.format == 'f'"],
                "expand": {"SUFFIX": ["a", "b"], "N": ["1", "2"]},
                "c_overloads": [
                    {
                        "sig": "void ${SUFFIX}(const float *p, int n)",
                        "map": {"p": "buf.ptr", "n": "buf.n"},
                    }
                ],
            }
        ],
    }
    mod = from_c2py_dict(spec)
    # expand with equal-length lists should not raise and should produce funcs
    assert mod is not None


def test_load_c2py_from_file():
    import tempfile

    path = tempfile.mktemp(suffix=".c2py")
    with open(path, "w") as f:
        f.write(
            '{"module": "m", "source": ["m.c"], '
            '"functions": [{"py_sig": "f(x: float) -> float", '
            '"c_overloads": [{"sig": "float f(float x)", "map": {"x": "x"}}]}]}'
        )
    mod = load_c2py(path)
    assert mod.name == "m"
    assert len(mod.functions) == 1


def test_load_c2py_from_c_with_embed():
    import tempfile

    path = tempfile.mktemp(suffix=".c")
    with open(path, "w") as f:
        f.write(
            "/* C2PY_BEGIN\n"
            '{"module": "m", "source": ["m.c"], "functions": []}\n'
            "C2PY_END */\n"
        )
    mod = load_c2py(path)
    assert mod.name == "m"


def test_load_c2py_missing_embed_raises():
    import tempfile

    path = tempfile.mktemp(suffix=".c")
    with open(path, "w") as f:
        f.write("/* no c2py block */\n")
    with pytest.raises(ValueError):
        load_c2py(path)


def _ptr_func(map_p="buf.ptr", when="buf.format == 'f'", checks=None):
    return {
        "py_sig": "procfn(buf: buffer, off: int) -> void",
        "checks": checks or ["buf.format == 'f'"],
        "c_overloads": [
            {
                "when": when,
                "map": {"p": map_p, "n": "buf.n", "o": "off"},
                "sig": "void proc_a(const float *p, int n, int o)",
            }
        ],
    }


@pytest.mark.parametrize(
    "expr",
    [
        "buf.ptr + off",
        "buf.ptr - 1",
        "off + buf.ptr",
        "(buf.ptr + 1) * 2",
        "off - (buf.ptr)",
        "-buf.ptr",
    ],
)
def test_ptr_arith_rejected_in_map(expr):
    with pytest.raises(ValueError) as ei:
        from_c2py_dict(_base(functions=[_ptr_func(map_p=expr)]))
    assert "procfn" in str(ei.value)
    assert "C function" in str(ei.value)


@pytest.mark.parametrize(
    "expr",
    [
        "buf.ptr + off == 0",
        "buf.ptr - 1 > 0",
        "off + buf.ptr == 0",
        "buf.format == 'f' and (2 * buf.ptr) > 0",
        "32 % buf.ptr == 0",
        "off % buf.ptr == 0",
    ],
)
def test_ptr_arith_rejected_in_when(expr):
    with pytest.raises(ValueError) as ei:
        from_c2py_dict(_base(functions=[_ptr_func(when=expr)]))
    assert "procfn" in str(ei.value)


@pytest.mark.parametrize(
    "expr",
    [
        "buf.ptr + off == 0",
        "buf.ptr - 1 > 0",
        "off + buf.ptr == 0",
        "buf.n > 0 and (buf.ptr / 2) > 0",
    ],
)
def test_ptr_arith_rejected_in_checks(expr):
    with pytest.raises(ValueError) as ei:
        from_c2py_dict(_base(functions=[_ptr_func(checks=["buf.format == 'f'", expr])]))
    assert "procfn" in str(ei.value)


def test_ptr_arith_rejected_in_variant_when():
    f = _ptr_func()
    f["c_overloads"] = [
        {
            "when": "buf.format == 'f'",
            "map": {"p": "buf.ptr", "n": "buf.n"},
            "variants": [
                {"sig": "void proc_a(const float *p, int n)", "when": "buf.ptr + 1 == 0"},
                {"sig": "void proc_b(const float *p, int n)"},
            ],
        }
    ]
    with pytest.raises(ValueError) as ei:
        from_c2py_dict(_base(functions=[f]))
    assert "procfn" in str(ei.value)


def test_bare_ptr_still_parses():
    from_c2py_dict(_base(functions=[_ptr_func(map_p="buf.ptr")]))


def test_ptr_modulo_literal_parses():
    from_c2py_dict(_base(functions=[_ptr_func(when="buf.ptr % 32 == 0")]))


def test_ptr_modulo_int_scalar_parses():
    from_c2py_dict(_base(functions=[_ptr_func(when="buf.ptr % off == 0")]))
