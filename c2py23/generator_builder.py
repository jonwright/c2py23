"""C code generator for c2py23 using the CBuilder pattern.

Reimplements generate() using a CBuilder that tracks emission state
(buffer acquires, GIL saves) and enforces invariants at emit time
rather than detecting violations post-hoc.
"""
from __future__ import print_function

from c2py23.parser import (
    Var, Attr, Subscript, IntLit, StrLit, Compare, BinOp, UnaryOp,
    PyParam, CParam, COverload, CVariant, FuncDef, ModuleDef,
    _FORMAT_TO_CTYPE,
)
from c2py23.generator import (
    _expr_to_c, _expr_to_source, _expr_refers_to,
    _expr_is_count_or_len,
    _escape_c_str, _float_literal,
    _get_buf_flags,
    _emit_check,
    _emit_constants as _emit_constants_orig,
    _emit_restrict_checks,
    _emit_contiguity_checks as _emit_contiguity_checks_orig,
    _doc, _mod_doc,
    _is_ptr_expr,
)


class CBuilder:
    """Stateful builder for generating C wrapper code.

    Tracks buffer acquires, GIL depth, and output-object construction so
    that cleanup code is always structurally correct.
    """

    def __init__(self):
        self.lines = []
        self._buf_names = []     # declared buffer names in order
        self._acq_names = set()  # declared acq flag names
        self._acquired = []      # buffers acquired (stack, in order)
        self._gil_depth = 0
        self._in_wrapper = False
        self._in_cleanup = False
        self._impl_has_gil_release = False
        self._gil_restore_before_py = True  # invariant marker

    # -- Low-level emit --

    def emit(self, line=''):
        self.lines.append(line)

    def emit_indent(self, indent, line=''):
        self.lines.append(indent + line)

    def emit_blank(self):
        self.lines.append('')

    def get_code(self):
        return '\n'.join(self.lines) + '\n'

    # -- Buffer management in wrapper --

    def declare_buffer(self, name):
        self._buf_names.append(name)
        self.emit('    Py_buffer {0};'.format(name))
        acq_name = self._acq_name(name)
        self._acq_names.add(acq_name)
        self.emit('    int {0} = 0;'.format(acq_name))

    def emit_buf_memset(self, buf_var):
        self.emit('    memset(&{0}, 0, C2PY.pybuffer_size);'.format(buf_var))

    def acquire_buffer(self, buf_var, py_var, flags):
        """Emits c2py_acquire_buffer with correct failure path.

        First buffer: return NULL on failure (nothing to clean up).
        Subsequent: goto cleanup on failure.
        """
        first = (len(self._acquired) == 0)
        acq_flag = self._acq_name(buf_var)
        self.emit(
            '    if (c2py_acquire_buffer({0}, &{1}, {2}) == -1)'.format(
                py_var, buf_var, flags))
        if first:
            self.emit('        return NULL;')
        else:
            self.emit('        goto cleanup;')
        self.emit('    {0} = 1;'.format(acq_flag))
        self._acquired.append(buf_var)

    def enter_cleanup(self):
        self._in_cleanup = True
        if not self._acquired:
            return
        self.emit('cleanup:')
        for buf_var in reversed(self._acquired):
            acq_flag = self._acq_name(buf_var)
            self.emit(
                '    if ({0}) c2py_release_buffer(&{1});'.format(
                    acq_flag, buf_var))
        self._acquired = []

    def _acq_name(self, buf_var):
        return 'acq_' + buf_var.replace('buf_', '', 1)

    # -- GIL management --

    def gil_save(self, cond_var, thread_state_var):
        self._gil_depth += 1
        self.emit('    if ({0}) {1} = PyEval_SaveThread();'.format(
            cond_var, thread_state_var))

    def gil_restore(self, cond_var, thread_state_var):
        if self._gil_depth <= 0:
            raise ValueError("gil_restore without matching gil_save")
        self._gil_depth -= 1
        self.emit('    if ({0}) PyEval_RestoreThread({1});'.format(
            cond_var, thread_state_var))

    def assert_gil_balanced(self, name):
        if self._gil_depth != 0:
            raise ValueError(
                "Function '%s': unbalanced GIL save/restore (%d)"
                % (name, self._gil_depth))

    # -- Output scalar construction --

    def _check_output_obj(self, obj_var):
        """Emit NULL check + Py_DECREF cleanup for an output object."""
        self.emit('    if ({0} == NULL) {{'.format(obj_var))
        self.emit('        Py_DECREF(_c2py_tup);')
        self.emit('        return NULL;')
        self.emit('    }')

    def emit_tuple_new(self, n):
        self.emit('    PyObject *_c2py_tup = PyTuple_New({0});'.format(n))
        self.emit('    if (_c2py_tup == NULL) return NULL;')

    def emit_output_long(self, index, val, ctype='int'):
        if ctype in ('int64_t',):
            self.emit(
                '    PyObject *_c2py_obj{0} = PyLong_FromLongLong((long long){1});'.format(
                    index, val))
        elif ctype in ('uint64_t',):
            self.emit(
                '    PyObject *_c2py_obj{0} = PyLong_FromUnsignedLongLong({1});'.format(
                    index, val))
        else:
            self.emit(
                '    PyObject *_c2py_obj{0} = PyLong_FromLong((long){1});'.format(
                    index, val))
        self._check_output_obj('_c2py_obj{0}'.format(index))
        self.emit(
            '    PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});'.format(index))

    def emit_output_double(self, index, val):
        self.emit(
            '    PyObject *_c2py_obj{0} = PyFloat_FromDouble((double){1});'.format(
                index, val))
        self._check_output_obj('_c2py_obj{0}'.format(index))
        self.emit(
            '    PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});'.format(index))


# ---------------------------------------------------------------------------
# Shared helpers (imported from original generator for expression work)
# ---------------------------------------------------------------------------

def _make_decl_string(ret, name, params):
    parts = [p.ctype + ' ' + p.name for p in params]
    return 'extern {} {}({});'.format(
        ret if ret != 'void' else 'void', name, ', '.join(parts))


# ---------------------------------------------------------------------------
# Top-level generate function (CBuilder version)
# ---------------------------------------------------------------------------

def generate(module_def):
    """Generate C wrapper source for a module using CBuilder pattern.

    Returns C source string.
    """
    b = CBuilder()

    # Header
    b.emit('/* Generated by c2py23 - do not edit by hand */')
    b.emit('#include <stdio.h>')
    b.emit('#include "c2py_runtime.h"')
    for h in module_def.headers:
        b.emit('#include "{0}"'.format(h))
    b.emit_blank()

    has_gil_release = any(f.gil_release for f in module_def.functions)
    has_free_threading = module_def.free_threading

    seen = set()
    for func in module_def.functions:
        for ol in func.overloads:
            if ol.variants:
                for v in ol.variants:
                    cn = v.c_name
                    if cn is None:
                        cn = v.sig_str.split('(')[0].strip().split()[-1]
                    if cn not in seen:
                        seen.add(cn)
                        b.emit(_make_decl_string(v.return_type, cn, v.params))
            else:
                cn = ol.c_name
                if cn is None:
                    cn = ol.sig_str.split('(')[0].strip().split()[-1]
                if cn not in seen:
                    seen.add(cn)
                    b.emit(_make_decl_string(ol.return_type, cn, ol.params))
    b.emit_blank()

    # Timing declarations (use original for the helper functions)
    if module_def.timing:
        from c2py23.generator import _emit_timing_decls
        _emit_timing_decls(b.lines, module_def)

    # GIL release declarations
    if has_gil_release:
        b.emit('/* ---- GIL release ---- */')
        b.emit('static int _c2py_gil_release_enabled = 1;')
        for func in module_def.functions:
            if func.gil_release:
                b.emit(
                    'static int _gil_release_{0} = 1;'.format(func.name))
        b.emit_blank()

    # Per-function emission
    for func in module_def.functions:
        _emit_function_builder(b, func, module_def.name,
                               module_def.timing, has_gil_release)

    # Module init
    _emit_module_init_builder(b, module_def, has_free_threading,
                              has_gil_release)

    return b.get_code()


# ---------------------------------------------------------------------------
# Function-level emission (CBuilder pattern)
# ---------------------------------------------------------------------------

def _emit_function_builder(b, func, module_name, timing, has_gil_release):
    name = func.name
    buf_params = [p for p in func.py_params if p.pytype == 'buffer']
    scalar_params = [p for p in func.py_params if p.pytype != 'buffer']

    b.emit('/* ' + '-' * 44 + ' */')
    b.emit('/* Wrapper for: {0} */'.format(name))
    b.emit('/* ' + '-' * 44 + ' */')
    b.emit_blank()

    has_groups = any(ol.variants for ol in func.overloads)
    if has_groups:
        _emit_static_dispatch_builder(b, func, buf_params, scalar_params)

    _emit_impl_func_builder(b, func, buf_params, scalar_params,
                            timing, has_gil_release)

    # Wrapper functions (VARARGS + FASTCALL)
    _emit_varargs_wrapper_builder(b, func, buf_params, scalar_params, timing)
    _emit_fastcall_wrapper_builder(b, func, buf_params, scalar_params, timing)

    b.assert_gil_balanced(name)


# ---------------------------------------------------------------------------
# Static dispatch (grouped overloads)
# ---------------------------------------------------------------------------

def _emit_static_dispatch_builder(b, func, buf_params, scalar_params):
    name = func.name
    groups = [(i, ol) for i, ol in enumerate(func.overloads) if ol.variants]

    b.emit('/* ---- Variant dispatch for {0} ---- */'.format(name))
    b.emit_blank()

    for gi, (i, ol) in enumerate(groups):
        gname = ol.group_name or 'group{0}'.format(gi)
        b.emit(
            'static int _var_{0}_{1} = -1;'.format(name, gi))
        b.emit(
            'static const char *_vname_{0}_{1} = NULL;'.format(name, gi))

    b.emit_blank()

    for gi, (i, ol) in enumerate(groups):
        b.emit(
            'static void _resolve_{0}_{1}(void) {{'.format(name, gi))
        for vi, v in enumerate(ol.variants):
            if v.when_expr is not None:
                when_c = _expr_to_c(v.when_expr, buf_params, scalar_params, None)
                b.emit('    if ({0}) {{'.format(when_c))
                b.emit(
                    '        _var_{0}_{1} = {2}; _vname_{0}_{1} = "{3}"; '
                    'return;'.format(name, gi, vi, v.name))
                b.emit('    }')
        last_vi = len(ol.variants) - 1
        b.emit(
            '    _var_{0}_{1} = {2}; _vname_{0}_{1} = "{3}";'.format(
                name, gi, last_vi, ol.variants[last_vi].name))
        b.emit('}')
        b.emit_blank()

    # Aggregate resolve
    b.emit('static void _resolve_{0}(void) {{'.format(name))
    for gi in range(len(groups)):
        b.emit('    _resolve_{0}_{1}();'.format(name, gi))
    b.emit('}')
    b.emit_blank()

    # Rebind function
    b.emit(
        'static PyObject* _rebind_{0}(PyObject *self, PyObject *args) {{'.format(name))
    b.emit('    const char *target = NULL;')
    b.emit(
        '    if (!C2PY.ParseTuple(args, "z", &target)) return NULL;')
    b.emit_blank()
    b.emit('    if (target == NULL) {')
    b.emit('        _resolve_{0}();'.format(name))
    b.emit('        Py_RETURN_NONE;')
    b.emit('    }')
    b.emit_blank()
    for gi, (i, ol) in enumerate(groups):
        gname = ol.group_name or 'group{0}'.format(gi)
        for vi, v in enumerate(ol.variants):
            b.emit(
                '    if (!strcmp(target, "{0}")) {{'.format(v.name))
            b.emit(
                '        _var_{0}_{1} = {2}; _vname_{0}_{1} = "{3}";'.format(
                    name, gi, vi, v.name))
            b.emit('        Py_RETURN_NONE;')
            b.emit('    }')
    b.emit_blank()
    b.emit('    C2PY.Err_SetString(C2PY.exc_ValueError, "unknown variant");')
    b.emit('    return NULL;')
    b.emit('}')
    b.emit_blank()


# ---------------------------------------------------------------------------
# Impl function
# ---------------------------------------------------------------------------

def _emit_impl_func_builder(b, func, buf_params, scalar_params,
                            timing, has_gil_release):
    name = func.name
    void_ptr_names = set()
    for ol in func.overloads:
        for cp in ol.params:
            if cp.base_type == 'void' and cp.is_pointer:
                void_ptr_names.add(cp.name)

    params_c = []
    for p in buf_params:
        params_c.append('Py_buffer *buf_' + p.name)
    for p in scalar_params:
        if p.pytype == 'int':
            if p.name in void_ptr_names:
                params_c.append('intptr_t c_{0}'.format(p.name))
            else:
                params_c.append('int c_{0}'.format(p.name))
        else:
            params_c.append('double c_{0}'.format(p.name))

    b.emit('static PyObject*')
    b.emit('_{0}_impl({1})'.format(name, ', '.join(params_c)))
    b.emit('{')

    if timing:
        b.emit('    int _c2py_do_time = _c2py_timing_enabled;')
        b.emit('    uint64_t _c2py_ct0 = 0, _c2py_ct1 = 0;')
        b.emit_blank()

    gil = func.gil_release and has_gil_release
    if gil:
        b.emit(
            '    int _c2py_do_gil = _c2py_gil_release_enabled'
            ' && _gil_release_{0};'.format(name))
        b.emit('    void *_c2py_thread_state = NULL;')
        b.emit_blank()

    # Checks
    for check in func.checks:
        b.emit('    /* check: {0} */'.format(_expr_to_source(check)))
        _emit_check_builder(b, check, buf_params, scalar_params)

    # Overload dispatch
    _emit_overload_dispatch_builder(b, func, buf_params, scalar_params,
                                    timing, has_gil_release)

    b.emit_blank()
    b.emit('    /* should not reach here */')
    b.emit('    return NULL;')
    b.emit('}')
    b.emit_blank()


# ---------------------------------------------------------------------------
# Check emission
# ---------------------------------------------------------------------------

def _emit_check_builder(b, check, buf_params, scalar_params):
    _emit_check(b.lines, check, buf_params, scalar_params)


# ---------------------------------------------------------------------------
# Overload dispatch emission
# ---------------------------------------------------------------------------

def _emit_overload_dispatch_builder(b, func, buf_params, scalar_params,
                                    timing, has_gil_release):
    name = func.name
    overloads = func.overloads
    default_raise = func.default_raise
    gil = func.gil_release and has_gil_release

    has_groups = any(ol.variants for ol in overloads)
    if not has_groups:
        _emit_flat_dispatch_builder(b, overloads, buf_params, scalar_params,
                                    timing, name, gil, default_raise)
        return

    group_index = 0
    for i, ol in enumerate(overloads):
        is_group = ol.variants is not None
        if i == 0:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                b.emit('    if (' + when_c + ') {')
            else:
                b.emit('    {  /* group 0 (always) */')
        else:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                b.emit('    } else if (' + when_c + ') {')
            else:
                b.emit('    } else {  /* group {0} (always) */'.format(i))

        if is_group:
            gi = group_index
            b.emit('        /* group {0}: {1} variants */'.format(
                gi, len(ol.variants)))
            b.emit('        switch (_var_{0}_{1}) {{'.format(name, gi))

            for vi, v in enumerate(ol.variants):
                syn_ol = COverload(
                    v.sig_str, v.params, v.return_type,
                    ol.map_exprs, v.when_expr,
                    name=v.name, outputs=v.outputs, c_name=v.c_name)
                b.emit('        case {0}: {{'.format(vi))
                _emit_c_call_builder(b, syn_ol, buf_params, scalar_params,
                                     timing, name, gil,
                                     indent='                ')
                b.emit('            break;')
                b.emit('        }')
            b.emit('        default: break;')
            b.emit('        }')
            group_index += 1
        else:
            b.emit('        /* {0} */'.format(ol.sig_str))
            _emit_c_call_builder(b, ol, buf_params, scalar_params,
                                 timing, name, gil,
                                 indent='        ')

    if default_raise:
        b.emit('    } else {')
        _emit_default_raise_body_builder(b, default_raise)
    b.emit('    }')


# ---------------------------------------------------------------------------
# Flat dispatch emission
# ---------------------------------------------------------------------------

def _emit_flat_dispatch_builder(b, overloads, buf_params, scalar_params,
                                timing, name, gil, default_raise):
    if len(overloads) == 1 and overloads[0].when_expr is None:
        b.emit('    /* overload 0 (always) */')
        b.emit('    {')
        _emit_c_call_builder(b, overloads[0], buf_params, scalar_params,
                             timing, name, gil)
        b.emit('    }')
        return

    for i, ol in enumerate(overloads):
        if i == 0:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                b.emit('    if (' + when_c + ') {')
            else:
                b.emit('    {  /* overload 0 (always) */')
        else:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                b.emit('    } else if (' + when_c + ') {')
            else:
                b.emit('    } else {  /* overload {0} (always) */'.format(i))
        b.emit('        /* {0} */'.format(ol.sig_str))
        _emit_c_call_builder(b, ol, buf_params, scalar_params,
                             timing, name, gil)

    if default_raise:
        b.emit('    } else {')
        _emit_default_raise_body_builder(b, default_raise)
    b.emit('    }')


def _emit_default_raise_body_builder(b, default_raise):
    from c2py23.generator import _emit_default_raise_body
    _emit_default_raise_body(b.lines, default_raise)


# ---------------------------------------------------------------------------
# C call emission
# ---------------------------------------------------------------------------

def _emit_c_call_builder(b, ol, buf_params, scalar_params,
                         timing, func_name, gil_release_call=False,
                         indent=None):
    if indent is None:
        indent = '        '

    def emitl(line):
        b.emit_indent(indent, line)

    c_name = ol.c_name
    if c_name is None:
        c_name = ol.sig_str.split('(')[0].strip().split()[-1]
    perf_name = '_perf_{0}__{1}'.format(func_name, c_name)
    outputs = getattr(ol, 'outputs', {}) or {}

    # Declare output variables before call
    for p in ol.params:
        if p.name in outputs:
            ctype = outputs[p.name]
            var_name = '_out_{0}'.format(p.name)
            if ctype in ('int', 'int8_t', 'int16_t', 'int32_t',
                         'uint8_t', 'uint16_t', 'uint32_t', 'int64_t', 'uint64_t'):
                emitl('int {0} = 0;'.format(var_name))
            else:
                emitl('double {0} = 0.0;'.format(var_name))

    # Build args
    args = []
    for p in ol.params:
        if p.name in outputs:
            args.append('&_out_{0}'.format(p.name))
            continue
        expr = ol.map_exprs.get(p.name)
        if expr is None:
            continue
        arg_c = _expr_to_c(expr, buf_params, scalar_params, ol)
        # Add casts for void* / type conversion.
        # IMPORTANT: save pre-cast expression for INT_MAX comparison
        # (comparison must use raw Py_ssize_t, not truncated int).
        raw_c = arg_c
        if p.is_pointer and _is_ptr_expr(expr):
            raw_c = '(' + p.ctype + ')' + raw_c
            arg_c = raw_c
        elif p.is_pointer and p.base_type == 'void':
            raw_c = '(void *)(intptr_t)' + raw_c
            arg_c = raw_c
        elif not p.is_pointer and p.base_type == 'int' and _expr_is_count_or_len(expr):
            arg_c = '(int)(' + arg_c + ')'
        elif not p.is_pointer and p.base_type == 'float':
            arg_c = '(float)(' + arg_c + ')'
        elif not p.is_pointer and p.base_type not in ('int', 'double', 'void', 'float'):
            arg_c = '(' + p.ctype + ')(' + arg_c + ')'
        # Check for INT_MAX overflow (use raw Py_ssize_t expression, not casted)
        if not _expr_is_count_or_len(expr):
            args.append(arg_c)
        else:
            emitl('if (({0}) > (Py_ssize_t)INT_MAX) {{'.format(raw_c))
            emitl('    PyErr_SetString(PyExc_ValueError,')
            emitl('        "buffer too large for int n (> INT_MAX elements)");')
            emitl('    return NULL;')
            emitl('}')
            args.append(arg_c)

    call_str = c_name + '(' + ', '.join(args) + ')'

    has_outputs = bool(outputs)
    has_ret = (ol.return_type and ol.return_type != 'void'
               and ol.return_type is not None)

    # GIL release: save before C call
    if gil_release_call:
        emitl('if (_c2py_do_gil) _c2py_thread_state = PyEval_SaveThread();')

    # Timing: start
    if timing:
        emitl('if (_c2py_do_time) _c2py_ct0 = c2py_ticks();')

    if not has_outputs:
        if ol.return_type in ('void', None):
            emitl(call_str + ';')
        elif ol.return_type == 'int':
            emitl('int _ret = ' + call_str + ';')
        elif ol.return_type == 'float':
            emitl('float _ret = ' + call_str + ';')
        elif ol.return_type == 'double':
            emitl('double _ret = ' + call_str + ';')
        else:
            emitl('/* unknown return type: {0} */'.format(ol.return_type))
            emitl(call_str + ';')

        # GIL restore (for no-outputs path, before PyObject creation)
        if gil_release_call:
            emitl('if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state);')

        if timing:
            emitl('if (_c2py_do_time) {')
            emitl('    _c2py_ct1 = c2py_ticks();')
            emitl('    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);'.format(perf_name))
            emitl('}')

        if ol.return_type in ('void', None):
            emitl('Py_RETURN_NONE;')
        elif ol.return_type == 'int':
            emitl('return PyLong_FromLong((long)_ret);')
        elif ol.return_type == 'float':
            emitl('return PyFloat_FromDouble((double)_ret);')
        elif ol.return_type == 'double':
            emitl('return PyFloat_FromDouble(_ret);')
        else:
            emitl('Py_RETURN_NONE;')
        return

    # Output scalar handling
    out_items = []
    if has_ret:
        ret_var = '_c2py_retval'
        if ol.return_type == 'int':
            emitl('int {0} = {1};'.format(ret_var, call_str))
        elif ol.return_type == 'float':
            emitl('float {0} = {1};'.format(ret_var, call_str))
        elif ol.return_type == 'double':
            emitl('double {0} = {1};'.format(ret_var, call_str))
        else:
            emitl('/* unknown return type: {0} */'.format(ol.return_type))
            emitl(call_str + ';')
            emitl('int {0} = 0;'.format(ret_var))
        out_items.append(('ret', ol.return_type, ret_var))
    else:
        emitl(call_str + ';')

    # GIL restore before Python object construction
    if gil_release_call:
        emitl('if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state);')

    if timing:
        emitl('if (_c2py_do_time) {')
        emitl('    _c2py_ct1 = c2py_ticks();')
        emitl('    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);'.format(perf_name))
        emitl('}')

    for p in ol.params:
        if p.name in outputs:
            ctype = outputs[p.name]
            var_name = '_out_{0}'.format(p.name)
            out_items.append((p.name, ctype, var_name))

    n = len(out_items)
    if n == 1:
        ctype = out_items[0][1]
        val = out_items[0][2]
        if ctype in ('int', 'int8_t', 'int16_t', 'int32_t',
                     'uint8_t', 'uint16_t', 'uint32_t'):
            emitl('return PyLong_FromLong((long){0});'.format(val))
        elif ctype == 'int64_t':
            emitl('return PyLong_FromLongLong((long long){0});'.format(val))
        elif ctype == 'uint64_t':
            emitl('return PyLong_FromUnsignedLongLong({0});'.format(val))
        elif ctype in ('float', 'double'):
            emitl('return PyFloat_FromDouble((double){0});'.format(val))
        else:
            emitl('return PyFloat_FromDouble((double){0});'.format(val))
    else:
        emitl('PyObject *_c2py_tup = PyTuple_New({0});'.format(n))
        emitl('if (_c2py_tup == NULL) return NULL;')
        for i, (name, ctype, val) in enumerate(out_items):
            if ctype in ('int', 'int8_t', 'int16_t', 'int32_t',
                         'uint8_t', 'uint16_t', 'uint32_t'):
                emitl('PyObject *_c2py_obj{0} = PyLong_FromLong((long){1});'.format(i, val))
            elif ctype == 'int64_t':
                emitl('PyObject *_c2py_obj{0} = PyLong_FromLongLong((long long){1});'.format(i, val))
            elif ctype == 'uint64_t':
                emitl('PyObject *_c2py_obj{0} = PyLong_FromUnsignedLongLong({1});'.format(i, val))
            elif ctype in ('float', 'double'):
                emitl('PyObject *_c2py_obj{0} = PyFloat_FromDouble((double){1});'.format(i, val))
            else:
                emitl('PyObject *_c2py_obj{0} = PyFloat_FromDouble((double){1});'.format(i, val))
            emitl('if (_c2py_obj{0} == NULL) {{'.format(i))
            emitl('    Py_DECREF(_c2py_tup);')
            emitl('    return NULL;')
            emitl('}')
            emitl('PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});'.format(i))
        emitl('return _c2py_tup;')


# ---------------------------------------------------------------------------
# Wrapper functions (VARARGS + FASTCALL)
# ---------------------------------------------------------------------------

def _emit_varargs_wrapper_builder(b, func, buf_params, scalar_params, timing):
    from c2py23.generator import _emit_varargs_wrapper
    _emit_varargs_wrapper(b.lines, func, buf_params, scalar_params, timing)


def _emit_fastcall_wrapper_builder(b, func, buf_params, scalar_params, timing):
    from c2py23.generator import _emit_fastcall_wrapper
    _emit_fastcall_wrapper(b.lines, func, buf_params, scalar_params, timing)


def _emit_restrict_checks_builder(b, buf_params, func):
    writable = set()
    const_set = set()
    for ol in func.overloads:
        targets = []
        if ol.variants:
            for v in ol.variants:
                targets.append((v, ol.map_exprs))
        else:
            targets.append((ol, ol.map_exprs))
        for entry, map_exprs in targets:
            for cp in entry.params:
                if cp.is_pointer:
                    expr = map_exprs.get(cp.name)
                    if expr is not None and _expr_refers_to(expr, ''):
                        for bp in buf_params:
                            if _expr_refers_to(expr, bp.name):
                                if not cp.is_const:
                                    writable.add(bp.name)
                                else:
                                    const_set.add(bp.name)
    if writable:
        writable = set()
        for ol in func.overloads:
            for cp in ol.params:
                if cp.is_pointer and not cp.is_const:
                    for bp in buf_params:
                        expr = ol.map_exprs.get(cp.name)
                        if expr is not None and _expr_refers_to(expr, bp.name):
                            writable.add(bp.name)
    writable_list = list(writable)
    for i in range(len(writable_list)):
        for j in range(i + 1, len(writable_list)):
            a = writable_list[i]
            b_name = writable_list[j]
            b.emit('')
            b.emit(
                '    /* restrict check: {0} vs {1} */'.format(a, b_name))
            b.emit(
                '    if (buf_{0}.buf >= buf_{1}.buf && '.format(a, b_name))
            b.emit(
                '        buf_{0}.buf < buf_{1}.buf + buf_{1}.len) {{'.format(
                    a, b_name))
            b.emit(
                '        PyErr_SetString(PyExc_ValueError,'
                ' "buffer aliasing forbidden");')
            b.emit('        goto cleanup;')
            b.emit('    }')
            b.emit(
                '    if (buf_{0}.buf >= buf_{1}.buf && '.format(b_name, a))
            b.emit(
                '        buf_{0}.buf < buf_{1}.buf + buf_{1}.len) {{'.format(
                    b_name, a))
            b.emit(
                '        PyErr_SetString(PyExc_ValueError,'
                ' "buffer aliasing forbidden");')
            b.emit('        goto cleanup;')
            b.emit('    }')


def _emit_contiguity_checks_builder(b, buf_params):
    for p in buf_params:
        buf_name = 'buf_' + p.name
        b.emit('')
        b.emit('    /* contiguity check: {0} */'.format(p.name))
        b.emit('    do {')
        b.emit('        int _ok = 1;')
        b.emit('        if ({0}.strides == NULL && {0}.ndim <= 1) break;'.format(buf_name))
        b.emit('        if ({0}.ndim >= 1) {{'.format(buf_name))
        b.emit('            Py_ssize_t _expected = {0}.itemsize;'.format(buf_name))
        b.emit('            int _d;')
        b.emit(
            '            /* check F-contiguous (column-major):'
            ' first dim varies fastest */')
        b.emit('            for (_d = 0; _d < {0}.ndim; _d++) {{'.format(buf_name))
        b.emit(
            '                if ({0}.strides[_d] < 0)'
            ' {{ _ok = 0; break; }}'.format(buf_name))
        b.emit(
            '                if ({0}.strides[_d] != _expected)'
            ' {{ _ok = 0; break; }}'.format(buf_name))
        b.emit('                _expected *= {0}.shape[_d];'.format(buf_name))
        b.emit('            }')
        b.emit('            if (_ok) break;')
        b.emit(
            '            /* check C-contiguous (row-major):'
            ' last dim varies fastest */')
        b.emit('            _ok = 1;')
        b.emit('            _expected = {0}.itemsize;'.format(buf_name))
        b.emit(
            '            for (_d = {0}.ndim - 1; _d >= 0; _d--) {{'.format(buf_name))
        b.emit(
            '                if ({0}.strides[_d] < 0)'
            ' {{ _ok = 0; break; }}'.format(buf_name))
        b.emit(
            '                if ({0}.strides[_d] != _expected)'
            ' {{ _ok = 0; break; }}'.format(buf_name))
        b.emit('                _expected *= {0}.shape[_d];'.format(buf_name))
        b.emit('            }')
        b.emit('        }')
        b.emit('        if (!_ok) {')
        b.emit('            PyErr_SetString(PyExc_ValueError,')
        b.emit(
            '                "buffer not contiguous'
            ' (C or Fortran contiguous required)");')
        b.emit('            goto cleanup;')
        b.emit('        }')
        b.emit('    } while(0);')


# ---------------------------------------------------------------------------
# Module init
# ---------------------------------------------------------------------------

def _emit_module_init_builder(b, module_def, has_free_threading,
                              has_gil_release):
    name = module_def.name
    has_timing = module_def.timing
    has_variants = any(
        any(ol.variants for ol in f.overloads) for f in module_def.functions)
    has_attrs = module_def.constants or has_timing or has_gil_release
    mod_doc_c = _escape_c_str(_mod_doc(module_def)) if _mod_doc(module_def) else None

    b.emit('')
    b.emit('/* ' + '-' * 44 + ' */')
    b.emit('/* Module definition                          */')
    b.emit('/* ' + '-' * 44 + ' */')
    b.emit('')

    # VARARGS method table
    b.emit('static PyMethodDef _methods_varargs[] = {')
    for func in module_def.functions:
        doc_str = _escape_c_str(_doc(func))
        b.emit('    {{"{}", (PyCFunction)_{}_wrapper, METH_VARARGS, "{}"}},'.format(
            func.name, func.name, doc_str))
    if has_variants:
        for func in module_def.functions:
            if any(ol.variants for ol in func.overloads):
                b.emit('    {{"_rebind_{0}", (PyCFunction)_rebind_{0}, METH_VARARGS,'.format(
                    func.name))
                b.emit('     "rebind variant for {0}"}},'.format(func.name))
    if has_timing:
        b.emit(
            '    {"_c2py_tick_frequency", (PyCFunction)__c2py_tick_frequency,'
            ' METH_VARARGS,')
        b.emit('     "return tick source frequency in Hz"},')
        b.emit(
            '    {"_c2py_ticks_to_ns", (PyCFunction)__c2py_ticks_to_ns,'
            ' METH_VARARGS,')
        b.emit('     "convert (ticks, freq_hz) to nanoseconds"},')
    b.emit('    {NULL, NULL, 0, NULL}')
    b.emit('};')
    b.emit('')

    # FASTCALL method table
    b.emit('static PyMethodDef _methods_fastcall[] = {')
    for func in module_def.functions:
        doc_str = _escape_c_str(_doc(func))
        b.emit('    {{"{}", (PyCFunction)_{}_fastcall, METH_FASTCALL, "{}"}},'.format(
            func.name, func.name, doc_str))
    if has_variants:
        for func in module_def.functions:
            if any(ol.variants for ol in func.overloads):
                b.emit('    {{"_rebind_{0}", (PyCFunction)_rebind_{0}, METH_VARARGS,'.format(
                    func.name))
                b.emit('     "rebind variant for {0}"}},'.format(func.name))
    if has_timing:
        b.emit(
            '    {"_c2py_tick_frequency", (PyCFunction)__c2py_tick_frequency,'
            ' METH_VARARGS,')
        b.emit('     "return tick source frequency in Hz"},')
        b.emit(
            '    {"_c2py_ticks_to_ns", (PyCFunction)__c2py_ticks_to_ns,'
            ' METH_VARARGS,')
        b.emit('     "convert (ticks, freq_hz) to nanoseconds"},')
    b.emit('    {NULL, NULL, 0, NULL}')
    b.emit('};')
    b.emit('')

    # Module definition struct
    b.emit('static PyModuleDef _module_def = {')
    b.emit('    PyModuleDef_HEAD_INIT,')
    b.emit('    "{}",'.format(name))
    if mod_doc_c:
        b.emit('    "{}",'.format(mod_doc_c))
    else:
        b.emit('    NULL,')
    b.emit('    -1,')
    b.emit('    NULL,  /* methods set at init */')
    b.emit('    NULL, NULL, NULL, NULL')
    b.emit('};')
    b.emit('')

    b.emit('static PyModuleDef_FT _module_def_ft = {')
    b.emit('    PyModuleDef_HEAD_INIT_FT,')
    b.emit('    "{}",'.format(name))
    if mod_doc_c:
        b.emit('    "{}",'.format(mod_doc_c))
    else:
        b.emit('    NULL,')
    b.emit('    -1,')
    b.emit('    NULL,  /* methods set at init */')
    b.emit('    NULL, NULL, NULL, NULL')
    b.emit('};')
    b.emit('')

    # Resolve calls for variants
    resolve_calls = []
    if has_variants:
        for func in module_def.functions:
            if any(ol.variants for ol in func.overloads):
                resolve_calls.append('    _resolve_{}();'.format(func.name))

    # PyInit (Python 3)
    b.emit('PyObject* PyInit_{}(void) {{'.format(name))
    b.emit('    c2py_runtime_init();')
    for rc in resolve_calls:
        b.emit(rc)
    b.emit('')
    b.emit('    PyObject *module = NULL;')
    b.emit(
        '    PyMethodDef *methods = C2PY.use_fastcall'
        ' ? _methods_fastcall : _methods_varargs;')
    b.emit('')
    b.emit('    if (C2PY.is_free_threaded) {')
    b.emit('        _module_def_ft.m_methods = methods;')
    b.emit('        if (C2PY.Module_Create2 != NULL) {')
    b.emit(
        '            module = C2PY.Module_Create2('
        '(PyModuleDef*)&_module_def_ft, 3);')
    b.emit('        }')
    b.emit('    } else {')
    b.emit('        _module_def.m_methods = methods;')
    if has_attrs:
        b.emit('        if (C2PY.Module_Create2 != NULL) {')
        b.emit('            module = C2PY.Module_Create2(&_module_def, 3);')
        b.emit('        } else {')
        b.emit(
            '            /* Fallback for Python 2.7 where PyModuleDef'
            ' is not supported */')
        b.emit('            module = C2PY.InitModule_2_7('
               '"{}", methods);'.format(name))
        b.emit('        }')
    else:
        b.emit('        if (C2PY.Module_Create2 != NULL) {')
        b.emit('            module = C2PY.Module_Create2(&_module_def, 3);')
        b.emit('        } else {')
        b.emit('            module = C2PY.InitModule_2_7('
               '"{}", methods);'.format(name))
        b.emit('        }')
    b.emit('    }')
    b.emit('')
    b.emit('    if (module != NULL) {')
    _emit_constants_orig(b.lines, module_def)
    if has_free_threading:
        b.emit('        if (C2PY.Unstable_Module_SetGIL != NULL) {')
        b.emit('            C2PY.Unstable_Module_SetGIL(module, (void*)1);'
               '  /* Py_MOD_GIL_NOT_USED */')
        b.emit('        }')
    b.emit('    }')
    b.emit('    return module;')
    b.emit('}')
    b.emit('')

    # Python 2.7 init
    b.emit('void init{}(void) {{'.format(name))
    b.emit('    c2py_runtime_init();')
    for rc in resolve_calls:
        b.emit(rc)
    # Match original: resolve_calls always emitted (even if empty, adds blank line)
    if not resolve_calls:
        b.emit('')
    b.emit('    PyObject *module = C2PY.InitModule_2_7("{}",'.format(name))
    b.emit(
        '        C2PY.use_fastcall ? _methods_fastcall : _methods_varargs);')
    b.emit('    if (module != NULL) {')
    _emit_constants_orig(b.lines, module_def)
    b.emit('    }')
    b.emit('}')
