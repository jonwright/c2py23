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


def _pass():
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
        free_threading=False,
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
    _pass()


def test_B3_unmatched_paren_raises():
    """B3: Unmatched '(' in C signature must raise ValueError, not silently
    produce an empty param list."""
    try:
        _parse_c_sig("func(", "test")
        assert False, "Should have raised"
    except ValueError as e:
        msg = str(e)
        assert "Unmatched '('" in msg, "Expected 'Unmatched ('' in error, got: %s" % msg
    _pass()


def test_B3_proper_paren_matching():
    """Verify paren matching uses a balanced-paren loop, not rfind.
    After the fix, a C signature with `->` return type suffix and a
    function with no trailing `)` should still parse correctly
    (the old rfind-based after_paren would match the wrong paren)."""
    name, params, ret = _parse_c_sig("func(int n, int m) -> int", "test")
    assert name == "func", "Expected func, got %s" % name
    assert len(params) == 2, "Expected 2 params, got %d" % len(params)
    assert ret == "int", "Expected int return type, got %s" % ret
    _pass()


def test_B4_L_format_char_in_C_TYPES_INT():
    """B4: 'l'/'L' are platform-sized and handled in _expr_to_c
    with a sizeof(long) itemsize check, not via _FORMAT_TO_CTYPE."""
    # 'l' and 'L' are platform-sized -- sizeof(long) differs LP64 vs LLP64.
    # _expr_to_c generates a runtime itemsize check instead of a static mapping.
    for ch in ('l', 'L'):
        assert ch not in _FORMAT_TO_CTYPE, (
            "'%s' should not be in _FORMAT_TO_CTYPE (handled by _expr_to_c)" % ch)

    # Verify the codegen produces sizeof(long) check for format 'l'/'L'
    from c2py23.parser import Compare, StrLit, Attr, Var, _expr_to_c
    arr = Var('arr')
    for ch in ('l', 'L'):
        tree = Compare(Attr(arr, 'format'), '==', StrLit(ch))
        c_code = _expr_to_c(tree, [arr], [], None)
        assert 'sizeof(long)' in c_code, (
            "_expr_to_c('%s') must include sizeof(long): %s" % (ch, c_code))

    # Fixed-width formats still map via _FORMAT_TO_CTYPE
    assert 'i' in _FORMAT_TO_CTYPE
    assert 'I' in _FORMAT_TO_CTYPE
    _pass()


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

    _pass()


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
        free_threading=False,
    )
    code = generate(mod)
    assert code.endswith('\n'), "Generated C must end with a newline"
    assert not code.endswith('\n\n'), "Generated C must end with exactly one newline"
    _pass()


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
        free_threading=False,
    )
    code = generate(mod)
    # Must contain the INT_MAX guard
    assert 'INT_MAX' in code, "Generated code must include INT_MAX overflow guard"
    assert 'buffer too large for int n' in code, (
        "Generated code must have overflow error message")
    _pass()


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
        free_threading=False,
    )
    code = generate(mod)
    assert 'buffer too large' not in code, (
        "INT_MAX guard must not appear when no n/length-derived int params")
    _pass()


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
    _pass()


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
        free_threading=False,
    )
    code = generate(mod)
    assert 'PyExc_ValueError' in code, (
        "default_raise must emit PyExc_ValueError")
    assert 'no matching overload' in code, (
        "default_raise message must appear in generated C")
    _pass()


def test_default_raise_typeerror():
    """default_raise with TypeError must emit PyExc_TypeError."""
    from c2py23.parser import parse_expr

    mod = ModuleDef(
        name='defraise_te',
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
                default_raise='TypeError: expected float buffer',
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
        free_threading=False,
    )
    code = generate(mod)
    assert 'PyExc_TypeError' in code, (
        "default_raise must emit PyExc_TypeError")
    assert 'expected float buffer' in code, (
        "default_raise message must appear in generated C")
    _pass()


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
        free_threading=False,
    )
    code = generate(mod)
    # Verify default=0 appears in the C code for local var initialization
    assert 'int c_flags = 0;' in code, (
        "Optional int=0 must emit 'int c_flags = 0;', got: %s"
        % code[code.find('c_flags'):][:50] if 'c_flags' in code else 'no c_flags')
    _pass()


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
        free_threading=False,
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
    _pass()


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
        free_threading=False,
    )
    code = generate(mod)
    # Must NOT have METH_KEYWORDS on any method def
    assert 'METH_KEYWORDS' not in code, (
        "METH_VARARGS functions must not use METH_KEYWORDS")
    assert 'METH_VARARGS' in code, (
        "Function must use METH_VARARGS flag")
    _pass()


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

    _pass()


def test_A_int64_output_tuple():
    """A: int64_t output must emit NULL check + PyTuple_SetItem in multi-output path."""
    from c2py23.parser import parse_expr

    # Use two outputs to trigger the multi-output tuple path (n > 1)
    ol = COverload(
        sig_str='int64_t compute(int64_t *val, double *avg)',
        params=[CParam('val', 'int64_t *', 'int64_t', False, False),
                CParam('avg', 'double *', 'double', False, False)],
        return_type='int64_t',
        map_exprs={},
        when_expr=None,
        outputs={'val': 'int64_t', 'avg': 'double'},
    )
    mod = ModuleDef(
        name='int64out',
        sources=['test.c'],
        headers=[],
        functions=[
            FuncDef(
                name='compute',
                py_params=[PyParam('x', 'buffer', None)],
                return_type='void',
                checks=[],
                overloads=[ol],
                default_raise=None,
                doc=None,
                gil_release=False,
            )
        ],
        constants={},
        timing=False,
        free_threading=False,
    )
    code = generate(mod)
    assert 'PyLong_FromLongLong' in code, "int64_t must use FromLongLong"
    # Multi-output path (single output still uses tuple for outputs:)
    assert 'PyTuple_SetItem(_c2py_tup, 0, _c2py_obj0)' in code, (
        "int64_t output must have PyTuple_SetItem")
    assert 'if (_c2py_obj0 == NULL)' in code, (
        "int64_t output must have NULL check")
    assert 'Py_DECREF(_c2py_tup)' in code, (
        "int64_t output must have error cleanup")
    _pass()


def test_D_anchored_c_param_re():
    """D: _C_PARAM_RE must reject trailing junk after param name."""
    from c2py23.parser import _parse_c_params

    # Valid params must still work
    params = _parse_c_params("int x, double *y")
    assert len(params) == 2
    assert params[0].name == 'x'
    assert params[1].name == 'y'

    # Trailing junk must raise ValueError
    try:
        _parse_c_params("int x garbage")
        assert False, "Expected ValueError for trailing junk"
    except ValueError:
        pass

    # Array-like suffix is now valid (array dimension notation)
    params = _parse_c_params("double *ptr[]")
    assert len(params) == 1
    assert params[0].name == 'ptr'
    assert params[0].array_dims == [None]  # empty []

    _pass()


def test_array_dims_auto_checks():
    """Array dimension notation must derive correct auto-checks."""
    from c2py23.parser import _derive_array_checks, _parse_c_params

    # gv[][3]: variable rows, 3 cols -> slow_axis==0, ndim==2, shape[1]==3
    checks = _derive_array_checks('gv', [None, '3'])
    assert 'gv.slow_axis == 0' in checks
    assert 'gv.ndim == 2' in checks
    assert 'gv.shape[1] == 3' in checks
    assert len(checks) == 3

    # ubi[3][3]: fixed 3x3
    checks = _derive_array_checks('ubi', ['3', '3'])
    assert 'ubi.slow_axis == 0' in checks
    assert 'ubi.ndim == 2' in checks
    assert 'ubi.shape[0] == 3' in checks
    assert 'ubi.shape[1] == 3' in checks
    assert len(checks) == 4  # slow_axis, ndim, shape[0], shape[1]

    # arr[][][5]: 3D, innermost fixed
    checks = _derive_array_checks('arr', [None, None, '5'])
    assert 'arr.slow_axis == 0' in checks
    assert 'arr.ndim == 3' in checks
    assert 'arr.shape[2] == 5' in checks
    assert len(checks) == 3

    # arr[]: 1D variable
    checks = _derive_array_checks('arr', [None])
    assert 'arr.slow_axis == 0' in checks
    assert 'arr.ndim == 2' not in checks  # 1D, no ndim constraint
    assert len(checks) == 1

    # arr[5]: 1D fixed -> shape[0] == 5, no ndim check
    checks = _derive_array_checks('arr', ['5'])
    assert 'arr.slow_axis == 0' in checks
    assert 'arr.shape[0] == 5' in checks
    assert 'arr.ndim == 2' not in checks
    assert len(checks) == 2

    _pass()


def test_array_dims_symmetric_warning():
    """Symmetric fixed dimensions [3][3] must emit a warning."""
    import warnings
    from c2py23.parser import _derive_array_checks

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _derive_array_checks('ubi', ['3', '3'])
        assert len(w) == 1, "Expected 1 warning for symmetric [3][3]"
        assert 'symmetric' in str(w[0].message)
        assert 'transposed' in str(w[0].message)

    # Non-symmetric (different dims) must NOT warn
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _derive_array_checks('gv', [None, '3'])
        assert len(w) == 0, "Expected no warning for non-symmetric [][3]"

    # 1D fixed must NOT warn (only symmetric IF multi-dim and all equal)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _derive_array_checks('arr', ['5'])
        assert len(w) == 0, "Expected no warning for 1D fixed [5]"

    _pass()


def test_array_dims_dedup_with_user_checks():
    """Auto-checks must not duplicate user-written checks."""
    from c2py23.parser import load_c2py
    import os

    # The existing array_sig.c2py has sum_1d_fixed with user check
    # "data.format == 'd'" and auto-generated checks from arr[5].
    # This test verifies no duplicate check expressions.
    c2py_path = os.path.join(os.path.dirname(__file__),
                              'cases', 'array_sig', 'array_sig.c2py')
    mod = load_c2py(c2py_path)
    for func in mod.functions:
        expr_strings = set(str(c) for c in func.checks)
        user_count = sum(1 for c in func.checks)
        assert len(expr_strings) == user_count, (
            "Duplicate checks in '%s': %d unique but %d total" %
            (func.name, len(expr_strings), user_count))

    _pass()


def test_array_dims_variant_sigs():
    """Variant sigs with array dims must generate auto-checks."""
    from c2py23.parser import load_c2py
    import os

    yaml_src = """
module: test_arr
source: [dummy.c]
headers: []
functions:
  - py_sig: "process(data: buffer) -> void"
    c_overloads:
      - when: "data.format == 'f'"
        map: {arr: "data.ptr", n: "data.shape[0]"}
        group: float
        variants:
          - sig: "void proc_sse(const double arr[][3], int n)"
            when: "true"
          - sig: "void proc_scalar(const double arr[][3], int n)"
    default_raise: "TypeError: unsupported format"
"""
    tmp_path = os.path.join(os.path.dirname(__file__),
                             '_test_variant_arr.c2py')
    try:
        with open(tmp_path, 'w') as f:
            f.write(yaml_src)
        mod = load_c2py(tmp_path)
        for func in mod.functions:
            assert len(func.checks) >= 3, (
                "Variant sig array dims should generate >= 3 auto-checks, "
                "got %d for '%s'" % (len(func.checks), func.name))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    _pass()


def test_E_unsupported_return_type():
    """E: Parser must reject return types the generator cannot emit."""
    from c2py23.parser import _parse_c_sig

    # Supported types still work
    name, params, ret = _parse_c_sig("double norm(const double *a, int n)", "test")
    assert ret == 'double'

    # Unsupported types raise ValueError
    for sig in [
        "uint32_t crc32(const uint8_t *data)",
        "char get_char(void)",
        "int64_t compute(void)",
    ]:
        try:
            _parse_c_sig(sig, "test")
            assert False, "Expected ValueError for '%s'" % sig
        except ValueError as e:
            assert 'Unsupported return type' in str(e) or 'unsupported' in str(e).lower(), (
                "Error should mention unsupported type, got: %s" % e)

    _pass()


def test_G_expression_escape_handling():
    """G: Expression parser must handle backslash escapes in strings."""
    from c2py23.parser import parse_expr, StrLit

    # Newline escape in a simple string expression (a == b is Compare, not String)
    # Test a standalone string expression
    expr = parse_expr('"hello\\nworld"')
    assert expr is not None
    assert isinstance(expr, StrLit), "String expression should produce StrLit node"
    # The string value should contain actual newline, not literal \n
    assert expr.value == 'hello\nworld', (
        "Backslash-n should decode to \\n, got: %r" % expr.value)

    # Tab escape
    expr = parse_expr('"col1\\tcol2"')
    assert isinstance(expr, StrLit)
    assert expr.value == 'col1\tcol2', (
        "Backslash-t should decode to tab, got: %r" % expr.value)

    # Literal backslash
    expr = parse_expr('"path\\\\to\\\\file"')
    assert isinstance(expr, StrLit)
    assert expr.value == 'path\\to\\file', (
        "Double backslash should decode to one backslash, got: %r" % expr.value)

    # Embedded quote
    expr = parse_expr('"hello\\"world\\""')
    assert isinstance(expr, StrLit)
    assert expr.value == 'hello"world"', (
        'Backslash-quote should decode to quote, got: %r' % expr.value)

    _pass()


def test_H_template_expand_non_string():
    """H: Template expansion must reject non-string values."""
    from c2py23.parser import load_c2py
    import tempfile
    import os

    # Create a minimal .c2py file with non-string template expansion
    # 42 loaded as YAML int, not a string
    content = (
        "module: testmod\n"
        "source: [test.c]\n"
        "functions:\n"
        "  - expand:\n"
        "      VAL:\n"
        "        - 42\n"
        '    py_sig: "fill(arr: buffer) -> void"\n'
        '    c_overloads:\n'
        '      - sig: "fill_${VAL}(float *arr, int n, float value)"\n'
        '        map: {arr: "arr.ptr", n: "arr.n"}\n'
    )
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c2py', delete=False) as f:
        fname = f.name
        f.write(content)
    try:
        load_c2py(fname)
        assert False, "Expected ValueError for non-string expansion value"
    except ValueError as e:
        assert 'string' in str(e).lower(), (
            "Error must mention 'string', got: %s" % e)
    except TypeError as e:
        assert False, "Expected ValueError, got TypeError: %s" % e
    finally:
        os.unlink(fname)

    _pass()


def test_I_unsupported_return_error_message():
    """I: Parser should give specific error for unsupported return types."""
    from c2py23.parser import _parse_c_sig

    # Multi-word types
    try:
        _parse_c_sig("unsigned int func(void)", "test")
        assert False, "Expected ValueError"
    except ValueError as e:
        msg = str(e)
        assert 'unsigned int' in msg or 'multi-word' in msg, (
            "Error should mention the type, got: %s" % msg)

    # Unknown types
    try:
        _parse_c_sig("size_t func(void)", "test")
        assert False, "Expected ValueError"
    except ValueError as e:
        msg = str(e)
        assert 'size_t' in msg or 'Unsupported' in msg, (
            "Error should mention the type, got: %s" % msg)

    _pass()


def test_checker_catches_broken_int64():
    """Verify the C invariant checker catches the original int64_t bug pattern."""
    from c2py23.invariant_checker import verify_c_invariants as _verify_c_invariants

    # Simulate the broken pattern: missing NULL check + PyTuple_SetItem
    bad_code = """
static PyObject*
_broken_impl(Py_buffer *buf)
{
    {
        double _out_val = 42.0;
        PyObject *_c2py_tup = PyTuple_New(1);
        if (_c2py_tup == NULL) return NULL;
        PyObject *_c2py_obj0 = PyLong_FromLongLong((long long)_out_val);
        return _c2py_tup;
    }
}
"""
    try:
        _verify_c_invariants(bad_code)
        assert False, "Checker should have raised ValueError"
    except ValueError as e:
        assert '_c2py_obj0' in str(e), (
            "Checker should mention the broken object, got: %s" % e)

    # Verify correct pattern passes
    good_code = """
static PyObject*
_good_impl(Py_buffer *buf)
{
    {
        double _out_val = 42.0;
        PyObject *_c2py_tup = PyTuple_New(1);
        if (_c2py_tup == NULL) return NULL;
        PyObject *_c2py_obj0 = PyLong_FromLongLong((long long)_out_val);
        if (_c2py_obj0 == NULL) {
            Py_DECREF(_c2py_tup);
            return NULL;
        }
        PyTuple_SetItem(_c2py_tup, 0, _c2py_obj0);
        return _c2py_tup;
    }
}
"""
    # Should not raise
    _verify_c_invariants(good_code)

    _pass()


def test_all_cases_compile():
    """Verify generator produces compilable C for every test case.

    Uses gcc on Linux; skipped on Windows where gcc may not be
    available or may have include path issues.  The Windows CI
    already validates compilation via MSVC in the build step.
    """
    import sys as _sys
    if _sys.platform == 'win32':
        print("SKIP: test_all_cases_compile (gcc not guaranteed on Windows)")
        _pass()
        return

    from c2py23.parser import load_c2py
    from c2py23.generator import generate
    import subprocess
    import tempfile
    import os

    cases_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'tests', 'cases')
    runtime_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'c2py23', 'runtime')

    for case_name in sorted(os.listdir(cases_dir)):
        case_dir = os.path.join(cases_dir, case_name)
        c2py_files = [f for f in os.listdir(case_dir) if f.endswith('.c2py')]
        if not c2py_files:
            continue
        c2py_file = os.path.join(case_dir, c2py_files[0])
        mod = load_c2py(c2py_file)

        code = generate(mod)

        tmpf = tempfile.NamedTemporaryFile(suffix='.c', delete=False)
        tmpf.write(code.encode('ascii'))
        tmpf.close()
        try:
            ret = subprocess.call(
                ['gcc', '-Wall', '-Werror', '-c',
                 '-I', runtime_dir,
                 '-o', '/dev/null',
                 tmpf.name],
                timeout=30)
        except TypeError:
            # Python 2.7: subprocess.call does not support timeout=
            ret = subprocess.call(
                ['gcc', '-Wall', '-Werror', '-c',
                 '-I', runtime_dir,
                 '-o', '/dev/null',
                 tmpf.name])
        os.unlink(tmpf.name)

        if ret != 0:
            assert False, "generated code for %s failed to compile" % case_name

    _pass()


def test_float_default_args():
    """Verify float literals parse as default arg values: 3.14, 1.6e-7, 2.7E+16."""
    from c2py23.parser import _parse_py_sig
    import tempfile, os, yaml

    c2py_src = """
module: _ftest
source: [dummy.c]
functions:
""" + """\
  - py_sig: "scale(data: buffer, factor: float = 3.14) -> void"
    c_overloads:
      - sig: "scale(const double *data, intptr_t n, double factor) -> void"
        map: {data: "data.ptr", n: "data.n", factor: factor}
  - py_sig: "exp_decay(data: buffer, rate: float = 1.6e-7) -> void"
    c_overloads:
      - sig: "decay(const double *data, intptr_t n, double rate) -> void"
        map: {data: "data.ptr", n: "data.n", rate: rate}
  - py_sig: "scale_big(data: buffer, factor: float = 2.7E+16) -> void"
    c_overloads:
      - sig: "scale_big(const double *data, intptr_t n, double factor) -> void"
        map: {data: "data.ptr", n: "data.n", factor: factor}
"""

    tmpf = tempfile.NamedTemporaryFile(suffix='.c2py', mode='w', delete=False)
    tmpf.write(c2py_src)
    tmpf.close()
    try:
        mod = load_c2py(tmpf.name)
    finally:
        os.unlink(tmpf.name)

    f_scale = mod.functions[0]
    f_decay = mod.functions[1]
    f_big = mod.functions[2]

    p_scale = f_scale.py_params[1]
    p_decay = f_decay.py_params[1]
    p_big = f_big.py_params[1]

    assert p_scale.default == 3.14, "default not 3.14, got %s" % p_scale.default
    assert p_decay.default == 1.6e-7, "default not 1.6e-7, got %s" % p_decay.default
    assert p_big.default == 2.7e16, "default not 2.7e16, got %s" % p_big.default

    assert isinstance(p_scale.default, float)
    assert isinstance(p_decay.default, float)
    assert isinstance(p_big.default, float)

    # Verify float literals in when: expressions
    from c2py23.parser import parse_expr
    from c2py23.parser import FloatLit
    e = parse_expr("3.14")
    assert isinstance(e, FloatLit), "expected FloatLit, got %s" % type(e).__name__
    assert e.value == 3.14, "got %s" % e.value

    e = parse_expr("1.6e-7")
    assert isinstance(e, FloatLit), "expected FloatLit, got %s" % type(e).__name__
    assert abs(e.value - 1.6e-7) < 1e-20

    e = parse_expr("2.7E+16")
    assert isinstance(e, FloatLit), "expected FloatLit, got %s" % type(e).__name__
    assert abs(e.value - 2.7e16) < 1e5

    _pass()


def test_return_types_allowed():
    """Verify void/int/float/double are valid return types; others need outputs:."""
    from c2py23.parser import _parse_c_sig

    # Direct returns: only void, int, float, double
    for ctype, ok in [("void", True), ("int", True), ("float", True),
                       ("double", True)]:
        name, params, ret = _parse_c_sig(
            "%s func(const double *a)" % ctype, "<test>")
        assert ret == ctype

    # Other C types must use outputs:
    for ctype in ("int8_t", "uint8_t", "int16_t", "uint16_t",
                  "int32_t", "uint32_t", "int64_t", "uint64_t",
                  "char", "intptr_t", "size_t"):
        try:
            name, params, ret = _parse_c_sig(
                "%s func(const double *a)" % ctype, "<test>")
            assert False, "should have rejected %s" % ctype
        except ValueError as e:
            assert "outputs:" in str(e), \
                "expected outputs: hint, got: %s" % e

    _pass()


def test_float_expression_compiles():
    """Verify a .c2py with float literal in when: compiles.

    Uses gcc on Linux; skipped on Windows where gcc may not be
    available.  The Windows CI already validates compilation via
    MSVC in the build step.
    """
    import sys as _sys
    if _sys.platform == 'win32':
        print("SKIP: test_float_expression_compiles "
              "(gcc not guaranteed on Windows)")
        _pass()
        return

    from c2py23.parser import load_c2py
    from c2py23.generator import generate
    import tempfile, os, subprocess

    src = """module: _ftest
source: [dummy.c]
functions:
  - py_sig: "fn(a: buffer) -> int"
    checks:
      - "a.format == 'd'"
    c_overloads:
      - sig: "fn(const double *a, intptr_t n) -> int"
        map: {a: "a.ptr", n: "a.n"}
        when: "a.n > 0 and a.itemsize == 8"
"""
    tmpf = tempfile.NamedTemporaryFile(suffix='.c2py', mode='w', delete=False)
    tmpf.write(src)
    tmpf.close()
    try:
        mod = load_c2py(tmpf.name)
    finally:
        os.unlink(tmpf.name)
    code = generate(mod)
    # Must compile with -Wall -Werror
    tmpf = tempfile.NamedTemporaryFile(suffix='.c', delete=False)
    tmpf.write(code.encode('ascii'))
    tmpf.close()
    runtime_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'c2py23', 'runtime')
    try:
        ret = subprocess.call(
            ['gcc', '-Wall', '-Werror', '-c',
             '-I', runtime_dir,
             '-o', '/dev/null',
             tmpf.name],
            timeout=30)
    except TypeError:
        # Python 2.7: subprocess.call does not support timeout=
        ret = subprocess.call(
            ['gcc', '-Wall', '-Werror', '-c',
             '-I', runtime_dir,
             '-o', '/dev/null',
             tmpf.name])
    os.unlink(tmpf.name)
    assert ret == 0, "float expression wrapper failed to compile"

    _pass()


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
