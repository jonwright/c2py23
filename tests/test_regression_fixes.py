"""Unit tests for parser and generator bug fixes from referee reports.

Tests: B1 (VARARGS wrapper signature), B3 (unmatched paren), B4 (L/l format mapping),
P4 (coerce warning), P5 (trailing newline), INT_MAX overflow check present,
+ coverage gaps: empty expand, default_raise, optional int=0 (falsy),
outputs + GIL release order, keyword argument rejection.
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
from c2py23.generator import generate, _doc, _expr_to_source


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


def test_empty_expand():
    """expand with zero-length list: should produce no functions, no crash."""
    from c2py23.parser import _expand_func_template, _parse_func

    raw_func = {
        'py_sig': 'sum_a(arr: buffer) -> int',
        'c_overloads': [{
            'sig': 'int sum_a(const int *arr, int n)',
            'map': {'arr': 'arr.ptr', 'n': 'arr.n'}
        }],
        'expand': {'SUFFIX': [], 'TYPE': []},
    }
    expanded = _expand_func_template(raw_func, 'test.c2py')
    assert expanded == [], "Empty expand must produce empty list, got %s" % expanded
    test_passed()


def test_default_raise_valid():
    """default_raise with a known exception type must generate correct C code."""
    from c2py23.parser import parse_expr

    mod = ModuleDef(
        name='defraise',
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
                    when_expr=parse_expr("arr.format == 'f'"),
                )],
                default_raise='ValueError: no matching overload',
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    assert 'PyExc_ValueError' in code, (
        "default_raise must emit PyExc_ValueError")
    assert 'no matching overload' in code, (
        "default_raise message must appear in generated C")
    test_passed()


def test_optional_int_default_zero():
    """Optional int param with default 0: must not be mistaken for 'no default' (falsy edge case)."""
    from c2py23.parser import PyParam, _parse_py_sig

    name, params, ret = _parse_py_sig('f(arr: buffer, flags: int = 0) -> void', 'test.c2py')
    assert len(params) == 2
    assert params[1].default == 0, "default=0 must be stored as int 0, got %s" % repr(params[1].default)
    assert params[1].default is not None, "default=0 must not be conflated with None"

    from c2py23.parser import parse_expr

    mod = ModuleDef(
        name='optzero',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='f',
                py_params=[PyParam('arr', 'buffer', None),
                            PyParam('flags', 'int', 0)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void do_f(float *arr, int n, int flags)',
                    params=[CParam('arr', 'float *', 'float', True, True),
                            CParam('n', 'int', 'int', False, False),
                            CParam('flags', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"),
                                'n': parse_expr("arr.n"),
                                'flags': parse_expr("flags")},
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
    # Verify default=0 appears in the C code for local var initialization
    assert 'int c_flags = 0;' in code, (
        "Optional int=0 must emit 'int c_flags = 0;', got: %s"
        % code[code.find('c_flags'):][:50] if 'c_flags' in code else 'no c_flags')
    test_passed()


def test_outputs_with_gil_release():
    """GIL restore must happen before output tuple construction (outputs + gil_release combined)."""
    from c2py23.parser import parse_expr

    ol = COverload(
        sig_str='int get_min_max(const float *arr, int n, float *minv, float *maxv)',
        params=[CParam('arr', 'const float *', 'float', True, True),
                CParam('n', 'int', 'int', False, False),
                CParam('minv', 'float *', 'float', False, False),
                CParam('maxv', 'float *', 'float', False, False)],
        return_type='int',
        map_exprs={'arr': parse_expr("arr.ptr"),
                    'n': parse_expr("arr.n")},
        when_expr=None,
        outputs={'minv': 'float', 'maxv': 'float'},
    )

    mod = ModuleDef(
        name='outgil',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='stats',
                py_params=[PyParam('arr', 'buffer', None)],
                return_type='void',
                checks=[],
                overloads=[ol],
                default_raise=None,
                doc=None,
                gil_release=True,
            )
        ],
        constants={},
        timing=False,
    )
    code = generate(mod)
    # GIL restore must appear before output tuple construction
    restore_pos = code.find('PyEval_RestoreThread')
    tuple_pos = code.find('PyTuple_New')

    if restore_pos >= 0 and tuple_pos >= 0:
        assert restore_pos < tuple_pos, (
            "PyEval_RestoreThread (pos %d) must come before PyTuple_New (pos %d)"
            % (restore_pos, tuple_pos))
    # And the gil_release flag should be emitted
    assert '_c2py_gil_release_enabled' in code, (
        "GIL release must emit module-level flag")
    test_passed()


def test_keyword_argument_rejection():
    """METH_VARARGS without METH_KEYWORDS must reject keyword arguments."""
    from c2py23.parser import parse_expr

    mod = ModuleDef(
        name='nokw',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='f',
                py_params=[PyParam('arr', 'buffer', None),
                            PyParam('n', 'int', None)],
                return_type='void',
                checks=[],
                overloads=[COverload(
                    sig_str='void do_f(float *arr, int n)',
                    params=[CParam('arr', 'float *', 'float', True, True),
                            CParam('n', 'int', 'int', False, False)],
                    return_type='void',
                    map_exprs={'arr': parse_expr("arr.ptr"),
                                'n': parse_expr("n")},
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
    # Must NOT have METH_KEYWORDS on any method def
    assert 'METH_KEYWORDS' not in code, (
        "METH_VARARGS functions must not use METH_KEYWORDS")
    assert 'METH_VARARGS' in code, (
        "Function must use METH_VARARGS flag")
    test_passed()


def test_docstring_verification():
    """Verify every .c2py YAML field appears in the generated docstring."""
    import glob as glob_mod

    cases_dir = os.path.join(os.path.dirname(__file__), 'cases')
    c2py_files = glob_mod.glob(os.path.join(cases_dir, '*', '*.c2py'))
    assert c2py_files, "No .c2py files found in cases/"

    for c2py_path in sorted(c2py_files):
        mod = load_c2py(c2py_path)
        for func in mod.functions:
            doc = _doc(func)

            # Verify function name in docstring
            assert func.name in doc, "%s: missing func name" % func.name

            # Verify every param name in docstring
            for p in func.py_params:
                assert p.name in doc, "%s: missing param '%s'" % (func.name, p.name)

            # Verify user doc string
            if func.doc:
                assert func.doc in doc, "%s: missing doc text" % func.name

            # Verify params descriptions
            if func.params:
                for pname, pdesc in func.params.items():
                    assert pdesc in doc, "%s: missing param desc for '%s'" % (func.name, pname)

            # Verify every check expression in docstring
            for chk in func.checks:
                chk_str = _expr_to_source(chk)
                assert chk_str in doc, "%s: missing check '%s'" % (func.name, chk_str)

            # Verify GIL state (only shown when released)
            if func.gil_release:
                assert "GIL: released" in doc, "%s: missing GIL released" % func.name

            # Verify overloads
            for ol in func.overloads:
                if ol.sig_str:
                    assert ol.sig_str in doc, "%s: missing flat overload sig" % func.name
                if ol.when_expr:
                    when_str = _expr_to_source(ol.when_expr)
                    assert when_str in doc, "%s: missing overload when" % func.name
                # Verify map expressions for this overload
                for cp_name, expr in ol.map_exprs.items():
                    expr_src = _expr_to_source(expr)
                    assert expr_src in doc, "%s: missing map '%s'" % (func.name, expr_src)
                if ol.variants:
                    for v in ol.variants:
                        assert v.sig_str in doc, "%s: missing variant sig" % func.name
                        assert v.name in doc, "%s: missing variant name" % func.name
                        if v.when_expr:
                            when_str = _expr_to_source(v.when_expr)
                            assert when_str in doc, "%s: missing variant when" % func.name
                        if v.doc:
                            assert v.doc in doc, "%s: missing variant doc" % func.name

            # Verify default raise
            if func.default_raise:
                assert func.default_raise in doc, "%s: missing default_raise" % func.name

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
