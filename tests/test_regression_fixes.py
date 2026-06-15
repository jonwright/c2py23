"""Unit tests for parser and generator bug fixes from referee reports.

Tests: B1 (VARARGS wrapper signature), B3 (unmatched paren), B4 (L/l format mapping),
P4 (coerce warning), P5 (trailing newline), INT_MAX overflow check present.
"""
from __future__ import print_function

import sys
import os
import tempfile
import warnings

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from c2py23.parser import load_c2py, _parse_c_sig, _FORMAT_TO_CTYPE, _C_TYPES_INT
from c2py23.parser import ModuleDef, FuncDef, PyParam, CParam, COverload, parse_expr
from c2py23.generator import generate


def test_passed():
    print("PASS: %s" % sys._getframe(1).f_code.co_name.replace('test_', ''))


def test_B1_varargs_wrapper_no_kwargs():
    """B1: VARARGS wrapper must NOT declare a 'kwargs' parameter.
    The signature must be (PyObject *self, PyObject *args) -- two parameters,
    not three, because the function address is cast to PyCFunction which takes
    exactly two parameters. A 3-param function through a 2-param pointer is UB."""
    mod = ModuleDef(
        name='b1test',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='f',
                py_params=[PyParam('x', 'float', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void do_f(double x)',
                    params=[CParam('x', 'double', 'double', False, False)],
                    return_type='void',
                    map_exprs={},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)

    varargs_line = None
    for line in code.split('\n'):
        if '_wrapper(PyObject' in line:
            varargs_line = line
            break

    assert varargs_line is not None, "Must emit a VARARGS wrapper"
    assert 'kwargs' not in varargs_line, (
        "VARARGS wrapper must not have kwargs param (UB): %s" % varargs_line)
    assert 'PyObject *self, PyObject *args' in varargs_line, (
        "VARARGS wrapper must have exactly 2 params, got: %s" % varargs_line)
    test_passed()


# ... (rest of tests remain the same)


def test_passed():
    print("PASS: %s" % sys._getframe(1).f_code.co_name.replace('test_', ''))


def test_B3_unmatched_paren_raises():
    """B3: Unmatched '(' in C signature must raise ValueError, not silently
    produce an empty param list."""
    try:
        _parse_c_sig("func(", "test")
        assert False, "Should have raised"
    except ValueError as e:
        msg = str(e)
        assert "Unmatched '('" in msg, "Expected 'Unmatched ('' in error, got: %s" % msg
    test_passed()


def test_B3_proper_paren_matching():
    """Verify paren matching uses a balanced-paren loop, not rfind.
    After the fix, a C signature with `->` return type suffix and a
    function with no trailing `)` should still parse correctly
    (the old rfind-based after_paren would match the wrong paren)."""
    name, params, ret = _parse_c_sig("func(int n, int m) -> int", "test")
    assert name == "func", "Expected func, got %s" % name
    assert len(params) == 2, "Expected 2 params, got %d" % len(params)
    assert ret == "int", "Expected int return type, got %s" % ret
    test_passed()


def test_B4_L_format_char_in_C_TYPES_INT():
    """B4: 'L' mapping must point to a type in _C_TYPES_INT to avoid false P4 errors."""
    assert 'L' in _FORMAT_TO_CTYPE, "'L' must be in _FORMAT_TO_CTYPE"
    assert _FORMAT_TO_CTYPE['L'] in _C_TYPES_INT, (
        "FORMAT_TO_CTYPE['L'] = '%s' must be in _C_TYPES_INT" % _FORMAT_TO_CTYPE['L'])

    assert 'l' in _FORMAT_TO_CTYPE, "'l' must be in _FORMAT_TO_CTYPE"
    assert _FORMAT_TO_CTYPE['l'] in _C_TYPES_INT, (
        "FORMAT_TO_CTYPE['l'] = '%s' must be in _C_TYPES_INT" % _FORMAT_TO_CTYPE['l'])
    test_passed()


def test_P4_coerce_warning_format():
    """P4: Coerce warning message must not have swapped format arguments.
    The warning must clearly state the value, type, and file context."""
    import io

    # Capture warnings
    buf = io.StringIO() if sys.version_info[0] >= 3 else io.BytesIO()

    from c2py23.parser import _coerce_expr_value

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = _coerce_expr_value(0, 'map', 'test.c2py')
        assert isinstance(result, str), "Should coerce int to str"
        assert len(w) == 1, "Expected 1 warning, got %d" % len(w)
        msg = str(w[0].message)
        # The message must contain the file path and must NOT contain the broken
        # '0: int' pattern (which was the bug)
        assert 'test.c2py' in msg, "Warning must mention file path"
        assert '0: int' not in msg, "Warning must not contain the swapped-arg bug pattern"
        assert 'map' in msg, "Warning must mention the context (map)"

    test_passed()


def test_P5_trailing_newline():
    """P5: Generated C source must end with a single newline character."""
    mod = ModuleDef(
        name='testmod',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='f',
                py_params=[PyParam('arr', 'buffer', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void do_f(float *arr, int n)',
                    params=[CParam('arr', 'float *', 'float', True, True),
                            CParam('n', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"),
                               'n': parse_expr("arr.n")},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    assert code.endswith('\n'), "Generated C must end with a newline"
    assert not code.endswith('\n\n'), "Generated C must end with exactly one newline"
    test_passed()


def test_INT_MAX_check_in_generated_code():
    """INT_MAX overflow guard must be present when int param maps from .n."""
    n_expr = parse_expr("arr.n")

    mod = ModuleDef(
        name='intcheck',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='process',
                py_params=[PyParam('arr', 'buffer', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void process(float *arr, int n)',
                    params=[CParam('arr', 'const float *', 'float', True, True),
                            CParam('n', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"), 'n': n_expr},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    # Must contain the INT_MAX guard
    assert 'INT_MAX' in code, "Generated code must include INT_MAX overflow guard"
    assert 'buffer too large for int n' in code, (
        "Generated code must have overflow error message")
    test_passed()


def test_INT_MAX_check_absent_when_no_int_n():
    """INT_MAX guard should NOT be emitted when no int param maps from .n or .len."""
    mod = ModuleDef(
        name='nointn',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='proc',
                py_params=[PyParam('arr', 'buffer', None),
                           PyParam('count', 'int', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void proc(float *arr, int count)',
                    params=[CParam('arr', 'const float *', 'float', True, True),
                            CParam('count', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"),
                               'count': parse_expr("count")},
                    when_expr=None,
                )],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    assert 'buffer too large' not in code, (
        "INT_MAX guard must not appear when no n/length-derived int params")
    test_passed()


if __name__ == '__main__':
    results = []
    for name in sorted(globals()):
        if name.startswith('test_'):
            try:
                globals()[name]()
                results.append(('PASS', name))
            except Exception as e:
                results.append(('FAIL', name + ': ' + str(e)))
                import traceback
                traceback.print_exc()

    passed = sum(1 for r, _ in results if r == 'PASS')
    total = len(results)
    print('\nResults: %d/%d passed' % (passed, total))
    sys.exit(0 if passed == total else 1)
