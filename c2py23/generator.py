"""C code generator for c2py23 using the CBuilder pattern.

Reimplements generate() using a CBuilder that tracks emission state
(buffer acquires, GIL saves) and enforces invariants at emit time
rather than detecting violations post-hoc.
"""
from __future__ import print_function

import re

from c2py23.parser import (
    Var, Attr, Subscript, IntLit, StrLit, Compare, BinOp, UnaryOp,
    PyParam, CParam, COverload, CVariant, FuncDef, ModuleDef,
    _FORMAT_TO_CTYPE,
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

    code = b.get_code()
    _verify_c_invariants(code)
    return code


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
    _emit_varargs_wrapper(b.lines, func, buf_params, scalar_params, timing)
    _emit_fastcall_wrapper(b.lines, func, buf_params, scalar_params, timing)

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
    void_ptr_names = _collect_void_ptr_names(func)

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
        _emit_check(b.lines, check, buf_params, scalar_params)

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
        _emit_default_raise_body(b.lines, default_raise)
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
        _emit_default_raise_body(b.lines, default_raise)
    b.emit('    }')




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

    # Free-threading slots array (Py_mod_gil for Python 3.15t+)
    if has_free_threading:
        b.emit('static PyModuleDef_Slot _slots[] = {')
        b.emit('    {Py_mod_gil, Py_MOD_GIL_NOT_USED},')
        b.emit('    {0, NULL}')
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
    if has_free_threading:
        b.emit('    _slots,  /* m_slots */')
    else:
        b.emit('    NULL,  /* m_slots */')
    b.emit('    NULL, NULL, NULL')
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
    _emit_constants(b.lines, module_def)
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
    _emit_constants(b.lines, module_def)
    b.emit('    }')
    b.emit('}')


# ---------------------------------------------------------------------------
# Functions copied from the original reference generator
# ---------------------------------------------------------------------------
_FORMAT_CHAR_TO_NAME = {
    'b': 'int8', 'B': 'uint8',
    'h': 'int16', 'H': 'uint16',
    'i': 'int32', 'I': 'uint32',
    'q': 'int64', 'Q': 'uint64',
    'l': 'int64 (platform)', 'L': 'uint64 (platform)',
    'f': 'float32', 'd': 'float64',
    'c': 'char', '?': 'bool', 'e': 'half-float',
    'Z': 'complex64', 'z': 'complex128',
}


def _is_ptr_expr(expr):
    """Check if expression is a .ptr access."""
    if isinstance(expr, Attr) and expr.attr == 'ptr':
        return True
    return False

def _expr_is_count_or_len(expr):
    """Check if expression is a buffer .n (element count) or .len (byte length)."""
    if isinstance(expr, Attr) and expr.attr in ('n', 'len'):
        return True
    return False

def _escape_c_str(s):
    """Escape a string for use in a C string literal."""
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    s = s.replace('\t', '\\t')
    return s

def _float_literal(value):
    """Convert a Python float to a C double literal string.
    Handles whole-number floats (3.0 -> 3.0) and fractions."""
    s = "%.15g" % value
    if '.' not in s and 'e' not in s and 'E' not in s:
        s += ".0"
    return s


# ---------------------------------------------------------------------------
# Generated C invariant checker
# ---------------------------------------------------------------------------

def _expr_refers_to(expr, buf_name):
    """Check if an expression refers to a specific buffer param."""
    if isinstance(expr, Var):
        return expr.name == buf_name
    elif isinstance(expr, Attr):
        return _expr_refers_to(expr.obj, buf_name)
    elif isinstance(expr, Subscript):
        return _expr_refers_to(expr.obj, buf_name)
    elif isinstance(expr, Compare):
        return _expr_refers_to(expr.left, buf_name) or _expr_refers_to(expr.right, buf_name)
    elif isinstance(expr, BinOp):
        return _expr_refers_to(expr.left, buf_name) or _expr_refers_to(expr.right, buf_name)
    elif isinstance(expr, UnaryOp):
        return _expr_refers_to(expr.operand, buf_name)
    return False

def _build_parse_format(py_params, func=None):
    """Build the PyArg_ParseTuple format string.

    Inserts '|' before the first optional parameter (one with a default).
    If func is provided, Python int params that map to C void* use
    pointer-width format 'l' (long) instead of 'i' (int).
    """
    void_ptr_names = _collect_void_ptr_names(func) if func else set()
    fmt = ''
    hit_optional = False
    for p in py_params:
        if not hit_optional and p.default is not None:
            hit_optional = True
            fmt += '|'
        if p.pytype == 'buffer':
            fmt += 'O'
        elif p.pytype == 'int':
            if p.name in void_ptr_names:
                fmt += 'l'
            else:
                fmt += 'i'
        elif p.pytype == 'float':
            fmt += 'd'
    return fmt

def _expr_to_c(expr, buf_params, scalar_params, current_ol):
    """Transpile an expression AST node to a C expression string."""
    if expr is None:
        return '1'  # No condition = always true

    if isinstance(expr, Var):
        name = expr.name
        # Is it a buffer param?
        for p in buf_params:
            if p.name == name:
                return 'buf_' + name
        # Is it a scalar param?
        for p in scalar_params:
            if p.name == name:
                return 'c_' + name
        return name

    elif isinstance(expr, Attr):
        obj = _expr_to_c(expr.obj, buf_params, scalar_params, current_ol)
        attr = expr.attr
        if attr == 'format':
            return obj + '->format'
        elif attr == 'ndim':
            return obj + '->ndim'
        elif attr == 'itemsize':
            return obj + '->itemsize'
        elif attr == 'len':
            return obj + '->len'
        elif attr == 'n':
            return '(' + obj + '->len / ' + obj + '->itemsize)'
        elif attr == 'ptr':
            return obj + '->buf'
        elif attr == 'shape':
            return obj + '->shape'
        elif attr == 'strides':
            return obj + '->strides'
        else:
            return obj + '->' + attr

    elif isinstance(expr, Subscript):
        obj = _expr_to_c(expr.obj, buf_params, scalar_params, current_ol)
        idx = expr.index
        return '{}[{}]'.format(obj, idx)

    elif isinstance(expr, IntLit):
        return str(expr.value)

    elif isinstance(expr, StrLit):
        return '"' + _escape_c_str(expr.value) + '"'

    elif isinstance(expr, Compare):
        left = _expr_to_c(expr.left, buf_params, scalar_params, current_ol)
        right = _expr_to_c(expr.right, buf_params, scalar_params, current_ol)
        op = expr.op

        # String comparison with format char: use last-char match for
        # PEP 3118 format strings (handles "d", "<d", "=d", etc.)
        # On old buffers (format == NULL), treat as matching (we can't check)
        if isinstance(expr.left, StrLit) or isinstance(expr.right, StrLit):
            str_lit = expr.left if isinstance(expr.left, StrLit) else expr.right
            fmt_expr = right if isinstance(expr.left, StrLit) else left
            if len(str_lit.value) == 1:
                ch = str_lit.value
                if op == '==':
                    return '(!{0} || {0}[strlen({0}) - 1] == \'{1}\')'.format(fmt_expr, ch)
                elif op == '!=':
                    return '({0} && {0}[strlen({0}) - 1] != \'{1}\')'.format(fmt_expr, ch)
            if op == '==':
                return 'strcmp({}, {}) == 0'.format(left, right)
            elif op == '!=':
                return 'strcmp({}, {}) != 0'.format(left, right)
            else:
                raise ValueError("Unsupported comparison op '{}' for strings".format(op))
        else:
            return '({}) {} ({})'.format(left, op, right)

    elif isinstance(expr, BinOp):
        left = _expr_to_c(expr.left, buf_params, scalar_params, current_ol)
        right = _expr_to_c(expr.right, buf_params, scalar_params, current_ol)
        if expr.op == 'and':
            return '({}) && ({})'.format(left, right)
        elif expr.op == 'or':
            return '({}) || ({})'.format(left, right)
        elif expr.op in ('+', '-', '*', '/', '%'):
            return '({} {} {})'.format(left, expr.op, right)
        else:
            raise ValueError("Unknown binop: {}".format(expr.op))

    elif isinstance(expr, UnaryOp):
        operand = _expr_to_c(expr.operand, buf_params, scalar_params, current_ol)
        if expr.op == 'not':
            return '!({})'.format(operand)
        elif expr.op == '-':
            return '-({})'.format(operand)
        elif expr.op == '+':
            return '+({})'.format(operand)
        else:
            raise ValueError("Unknown unary op: {}".format(expr.op))

    else:
        raise ValueError("Unknown expression type: {}".format(type(expr)))

def _expr_to_source(expr):
    """Convert an AST node back to its source form (for comments/error messages)."""
    if isinstance(expr, Var):
        return expr.name
    elif isinstance(expr, Attr):
        return _expr_to_source(expr.obj) + '.' + expr.attr
    elif isinstance(expr, Subscript):
        return _expr_to_source(expr.obj) + '[' + str(expr.index) + ']'
    elif isinstance(expr, IntLit):
        return str(expr.value)
    elif isinstance(expr, StrLit):
        return "'" + expr.value + "'"
    elif isinstance(expr, Compare):
        return '{} {} {}'.format(
            _expr_to_source(expr.left), expr.op, _expr_to_source(expr.right))
    elif isinstance(expr, BinOp):
        return '({} {} {})'.format(
            _expr_to_source(expr.left), expr.op, _expr_to_source(expr.right))
    elif isinstance(expr, UnaryOp):
        return '{}({})'.format(expr.op, _expr_to_source(expr.operand))
    else:
        return str(expr)


# ---------------------------------------------------------------------------
# Rich docstring generation
# ---------------------------------------------------------------------------

_FORMAT_CHAR_TO_NAME = {
    'b': 'int8', 'B': 'uint8',
    'h': 'int16', 'H': 'uint16',
    'i': 'int32', 'I': 'uint32',
    'q': 'int64', 'Q': 'uint64',
    'l': 'int64 (platform)', 'L': 'uint64 (platform)',
    'f': 'float32', 'd': 'float64',
    'c': 'char', '?': 'bool', 'e': 'half-float',
    'Z': 'complex64', 'z': 'complex128',
}

def _extract_fmt_from_expr(expr, param_name, fmt_chars):
    """Recursively extract format char comparisons from an expression tree."""
    if isinstance(expr, Compare) and expr.op == '==':
        for side, other in [(expr.left, expr.right), (expr.right, expr.left)]:
            if (isinstance(side, Attr) and side.attr == 'format'
                    and _expr_refers_to(side.obj, param_name)
                    and isinstance(other, StrLit) and len(other.value) == 1):
                fmt_chars.add(other.value)
    elif isinstance(expr, BinOp):
        _extract_fmt_from_expr(expr.left, param_name, fmt_chars)
        _extract_fmt_from_expr(expr.right, param_name, fmt_chars)
    elif isinstance(expr, UnaryOp):
        _extract_fmt_from_expr(expr.operand, param_name, fmt_chars)

def _get_buf_flags(buf_param, func):
    """Determine PyObject_GetBuffer flags for a buffer param.

    NOTE: Buffer writability is determined per-function, not per-selected-overload.
    If any overload (including variants) writes to a buffer, the buffer is acquired
    as PyBUF_WRITABLE for ALL dispatch paths. Callers must provide writable buffers
    even when the selected overload only reads.

    Returns a string like "PyBUF_STRIDES | PyBUF_FORMAT" or
    "PyBUF_WRITABLE | PyBUF_STRIDES | PyBUF_FORMAT".
    """
    is_writable = False
    for ol in func.overloads:
        if ol.variants:
            for v in ol.variants:
                for cp in v.params:
                    if cp.is_pointer and not cp.is_const:
                        expr = ol.map_exprs.get(cp.name)
                        if expr is not None and _expr_refers_to(expr, buf_param.name):
                            is_writable = True
                            break
                if is_writable:
                    break
        else:
            for cp in ol.params:
                if cp.is_pointer and not cp.is_const:
                    expr = ol.map_exprs.get(cp.name)
                    if expr is not None and _expr_refers_to(expr, buf_param.name):
                        is_writable = True
                        break
        if is_writable:
            break

    if is_writable:
        return 'PyBUF_WRITABLE | PyBUF_STRIDES | PyBUF_FORMAT'
    else:
        return 'PyBUF_STRIDES | PyBUF_FORMAT'

def _is_simple_expr(expr):
    """Check if an expression is simple enough to inline in a format string."""
    if isinstance(expr, (Var, IntLit)):
        return True
    if isinstance(expr, Attr) and isinstance(expr.obj, Var):
        return True  # a.n, a.len, a.ndim etc.
    if isinstance(expr, UnaryOp):
        return False
    if isinstance(expr, BinOp):
        if expr.op in ('and', 'or'):
            return _is_simple_expr(expr.left) and _is_simple_expr(expr.right)
        return False  # arithmetic is never simple
    return False

def _make_compare_diag(compare, buf_params, scalar_params):
    """Generate diagnostic C code for a Compare expression."""
    left = compare.left
    right = compare.right
    op = compare.op

    left_c = _expr_to_c(left, buf_params, scalar_params, None)
    right_c = _expr_to_c(right, buf_params, scalar_params, None)
    source = _expr_to_source(compare)

    # Determine if either side is a format attribute
    left_is_format = isinstance(left, Attr) and left.attr == 'format'
    right_is_format = isinstance(right, Attr) and right.attr == 'format'

    # Format comparison: show actual format chars
    if left_is_format and isinstance(right, StrLit) and len(right.value) == 1:
        escaped_src = _escape_c_str(source)
        lines = [
            'char _c2py_err[256];',
            'const char *_fmt = {0} ? {0} : "";'.format(left_c),
            'char _got = _fmt[0] ? _fmt[strlen(_fmt) - 1] : \'?\';',
            'snprintf(_c2py_err, sizeof(_c2py_err), '
            '"check failed: {0} (got format=\'%c\')", _got);'.format(escaped_src)
        ]
        return lines
    if right_is_format and isinstance(left, StrLit) and len(left.value) == 1:
        escaped_src = _escape_c_str(source)
        lines = [
            'char _c2py_err[256];',
            'const char *_fmt = {0} ? {0} : "";'.format(right_c),
            'char _got = _fmt[0] ? _fmt[strlen(_fmt) - 1] : \'?\';',
            'snprintf(_c2py_err, sizeof(_c2py_err), '
            '"check failed: {0} (got format=\'%c\')", _got);'.format(escaped_src)
        ]
        return lines

    # Format vs format comparison
    if left_is_format and right_is_format:
        escaped_src = _escape_c_str(source)
        lines = [
            'char _c2py_err[256];',
            'const char *_fmt_l = {0} ? {0} : "";'.format(left_c),
            'const char *_fmt_r = {0} ? {0} : "";'.format(right_c),
            'char _gl = _fmt_l[0] ? _fmt_l[strlen(_fmt_l) - 1] : \'?\';',
            'char _gr = _fmt_r[0] ? _fmt_r[strlen(_fmt_r) - 1] : \'?\';',
            'snprintf(_c2py_err, sizeof(_c2py_err), '
            '"check failed: {0} (got \'%c\' vs \'%c\')", _gl, _gr);'.format(escaped_src)
        ]
        return lines

    # Generic numeric comparison: show both sides as int
    if _is_simple_expr(left) and _is_simple_expr(right):
        escaped_src = _escape_c_str(source)
        lines = [
            'char _c2py_err[256];',
            'snprintf(_c2py_err, sizeof(_c2py_err), '
            '"check failed: {0} (got %ld vs %ld)",'
            ' (long)({1}), (long)({2}));'.format(escaped_src, left_c, right_c)
        ]
        return lines

    return None

def _make_check_diag(check, buf_params, scalar_params):
    """Generate C code to capture actual runtime values for a check failure message.

    Returns a list of C code lines (strings) that produce a diagnostic,
    ending with a snprintf into _c2py_err. Returns None if diagnostics
    cannot be generated for this expression shape.
    """
    if isinstance(check, Compare):
        return _make_compare_diag(check, buf_params, scalar_params)
    elif isinstance(check, BinOp):
        left_diag = _make_check_diag(check.left, buf_params, scalar_params)
        if left_diag is not None:
            return left_diag
        return _make_check_diag(check.right, buf_params, scalar_params)
    return None

def _emit_check(out, check, buf_params, scalar_params):
    """Emit a check that raises if condition is false.

    For single-char format comparisons on old buffers (format == NULL),
    the generated expression already uses !format || ... to pass safely.
    For two-sided format comparisons, NULL == NULL passes correctly.

    Includes actual runtime values in the failure message when possible.
    """
    c_expr = _expr_to_c(check, buf_params, scalar_params, None)
    msg = _expr_to_source(check)
    diag = _make_check_diag(check, buf_params, scalar_params)
    out.append('    if (!(' + c_expr + ')) {')
    if diag:
        out.append('        ' + diag[0])
        if len(diag) > 1:
            for d in diag[1:]:
                out.append('        ' + d)
        out.append('        PyErr_SetString(PyExc_ValueError, _c2py_err);')
    else:
        out.append('        PyErr_SetString(PyExc_ValueError, "check failed: ' + _escape_c_str(msg) + '");')
    out.append('        return NULL;')
    out.append('    }')

def _emit_default_raise_body(out, default_raise):
    """Emit the body of a default raise block."""
    if ':' in default_raise:
        exc_type, msg = default_raise.split(':', 1)
        exc_type = exc_type.strip()
        msg = msg.strip()
    else:
        exc_type = 'TypeError'
        msg = default_raise
    exc_name = 'PyExc_' + exc_type
    out.append('        PyErr_SetString(' + exc_name + ', "{}");'.format(_escape_c_str(msg)))
    out.append('        return NULL;')


# ---------------------------------------------------------------------------
# _wrapper function (arg parsing, buffer acquire, cleanup)
# ---------------------------------------------------------------------------

def _collect_void_ptr_names(func):
    """Return set of scalar param names that map to C void* in any overload."""
    if func is None:
        return set()
    scalar_names = set(p.name for p in func.py_params if p.pytype == 'int')
    result = set()
    for ol in func.overloads:
        if ol.variants:
            entries = [(v.params, ol.map_exprs) for v in ol.variants]
        else:
            entries = [(ol.params, ol.map_exprs)]
        for params, map_exprs in entries:
            for cp in params:
                if cp.is_pointer and cp.base_type == 'void':
                    expr = map_exprs.get(cp.name)
                    if expr is not None and isinstance(expr, Var) and expr.name in scalar_names:
                        result.add(expr.name)
    return result

def _emit_wrapper_locals(out, buf_params, scalar_params, func, timing=False):
    """Emit local variable declarations shared by both wrappers."""
    void_ptr_names = _collect_void_ptr_names(func)
    for p in buf_params:
        out.append('    PyObject *py_' + p.name + ' = NULL;')
    for p in scalar_params:
        default_val = p.default
        if p.pytype == 'int':
            if p.name in void_ptr_names:
                if default_val is None:
                    out.append('    intptr_t c_%s = 0;' % p.name)
                else:
                    out.append('    intptr_t c_%s = %d;' % (p.name, int(default_val)))
            else:
                if default_val is None:
                    out.append('    int c_%s = 0;' % p.name)
                else:
                    out.append('    int c_%s = %d;' % (p.name, int(default_val)))
        else:
            if default_val is None:
                out.append('    double c_%s = 0.0;' % p.name)
            else:
                out.append('    double c_%s = %s;' % (p.name, _float_literal(default_val)))

    for p in buf_params:
        out.append('    Py_buffer buf_{0};'.format(p.name))
        out.append('    int acq_{0} = 0;'.format(p.name))

    out.append('    PyObject *ret = NULL;')

    if timing:
        out.append('    int _c2py_do_time = _c2py_timing_enabled;')
        out.append('    uint64_t _c2py_t0 = 0, _c2py_t1 = 0, _c2py_t2 = 0;')
        out.append('    if (_c2py_do_time) _c2py_t0 = c2py_ticks();')

    out.append('')

def _emit_restrict_checks(out, buf_params, func):
    """Emit restrict alias checks between buffers.

    Any non-const pointer must not alias with any other pointer.
    """
    writable = set()
    const_set = set()
    for p in buf_params:
        for ol in func.overloads:
            if ol.variants:
                all_params = []
                for v in ol.variants:
                    all_params.extend(v.params)
                for cp in all_params:
                    if cp.is_pointer:
                        expr = ol.map_exprs.get(cp.name)
                        if expr is not None and _expr_refers_to(expr, p.name):
                            if cp.is_const:
                                const_set.add(p.name)
                            else:
                                writable.add(p.name)
            else:
                for cp in ol.params:
                    if cp.is_pointer:
                        expr = ol.map_exprs.get(cp.name)
                        if expr is not None and _expr_refers_to(expr, p.name):
                            if cp.is_const:
                                const_set.add(p.name)
                            else:
                                writable.add(p.name)

    # Check writable vs writable, and writable vs const
    checked = set()
    for wn in writable:
        for other in list(writable | const_set):
            if other == wn:
                continue
            pair = tuple(sorted([wn, other]))
            if pair in checked:
                continue
            checked.add(pair)
            out.append('    /* restrict check: {} vs {} */'.format(wn, other))
            out.append('    if (buf_{0}.buf >= buf_{1}.buf && '.format(wn, other))
            out.append('        buf_{0}.buf < buf_{1}.buf + buf_{1}.len) {{'.format(wn, other))
            out.append('        PyErr_SetString(PyExc_ValueError, "buffer aliasing forbidden");')
            out.append('        goto cleanup;')
            out.append('    }')
            out.append('    if (buf_{0}.buf >= buf_{1}.buf && '.format(other, wn))
            out.append('        buf_{0}.buf < buf_{1}.buf + buf_{1}.len) {{'.format(other, wn))
            out.append('        PyErr_SetString(PyExc_ValueError, "buffer aliasing forbidden");')
            out.append('        goto cleanup;')
            out.append('    }')
            out.append('')

def _emit_contiguity_checks(out, buf_params):
    """Emit contiguity validation for each buffer.

    Accepts C-contiguous and Fortran-contiguous layouts.
    Rejects strided arrays, negative strides, indirect buffers.
    """
    if not buf_params:
        return

    for p in buf_params:
        name = p.name
        fmt = lambda s: s.format(name)
        out.append('    /* contiguity check: {0} */'.format(name))
        out.append('    do {')
        out.append('        int _ok = 1;')
        out.append('        if (buf_{0}.strides == NULL && buf_{0}.ndim <= 1) break;'.format(name))
        out.append(fmt('        if (buf_{0}.ndim >= 1) {{'))
        out.append(fmt('            Py_ssize_t _expected = buf_{0}.itemsize;'))
        out.append('            int _d;')
        out.append('            /* check F-contiguous (column-major): first dim varies fastest */')
        out.append(fmt('            for (_d = 0; _d < buf_{0}.ndim; _d++) {{'))
        out.append(fmt('                if (buf_{0}.strides[_d] < 0) {{ _ok = 0; break; }}'))
        out.append(fmt('                if (buf_{0}.strides[_d] != _expected) {{ _ok = 0; break; }}'))
        out.append(fmt('                _expected *= buf_{0}.shape[_d];'))
        out.append('            }')
        out.append('            if (_ok) break;')
        out.append('            /* check C-contiguous (row-major): last dim varies fastest */')
        out.append('            _ok = 1;')
        out.append(fmt('            _expected = buf_{0}.itemsize;'))
        out.append(fmt('            for (_d = buf_{0}.ndim - 1; _d >= 0; _d--) {{'))
        out.append(fmt('                if (buf_{0}.strides[_d] < 0) {{ _ok = 0; break; }}'))
        out.append(fmt('                if (buf_{0}.strides[_d] != _expected) {{ _ok = 0; break; }}'))
        out.append(fmt('                _expected *= buf_{0}.shape[_d];'))
        out.append('            }')
        out.append('        }')
        out.append('        if (!_ok) {')
        out.append('            PyErr_SetString(PyExc_ValueError,')
        out.append('                "buffer not contiguous (C or Fortran contiguous required)");')
        out.append('            goto cleanup;')
        out.append('        }')
        out.append('    } while(0);')
        out.append('')


# ---------------------------------------------------------------------------
# Expression transpiler: AST -> C code string
# ---------------------------------------------------------------------------

def _emit_wrapper_body(out, func, buf_params, scalar_params, name, timing=False):
    """Emit the shared wrapper body: buffer init, acquire, checks, impl call, cleanup."""
    perf_name = '_perf_' + name

    # Initialize buffers
    for p in buf_params:
        out.append('    memset(&buf_{0}, 0, C2PY.pybuffer_size);'.format(p.name))
    out.append('')

    # Acquire buffers
    for i, p in enumerate(buf_params):
        flags = _get_buf_flags(p, func)
        want_write = 'PyBUF_WRITABLE' in flags
        write_val = 'C2PY_BUF_WRITE' if want_write else 'C2PY_BUF_READ'
        out.append('    if (c2py_acquire_buffer(py_{0}, &buf_{0}, {1}) == -1)'.format(p.name, write_val))
        if i == 0:
            out.append('        return NULL;')
        else:
            out.append('        goto cleanup;')
        out.append('    acq_{0} = 1;'.format(p.name))
        out.append('')

    # Restrict checks
    _emit_restrict_checks(out, buf_params, func)

    # Contiguity checks
    _emit_contiguity_checks(out, buf_params)

    # Call impl (with timing ticks around it)
    impl_args = []
    for p in buf_params:
        impl_args.append('&buf_' + p.name)
    for p in scalar_params:
        impl_args.append('c_' + p.name)

    if timing:
        out.append('    if (_c2py_do_time) _c2py_t1 = c2py_ticks();')
    out.append('    ret = _{0}_impl({1});'.format(name, ', '.join(impl_args)))
    if timing:
        out.append('    if (_c2py_do_time) _c2py_t2 = c2py_ticks();')
    out.append('')

    # Cleanup
    if len(buf_params) >= 1:
        out.append('cleanup:')
    for p in reversed(buf_params):
        out.append('    if (acq_{0}) c2py_release_buffer(&buf_{0});'.format(p.name))

    if timing:
        out.append('')
        out.append('    if (_c2py_do_time) {')
        out.append('        c2py_perf_record(&{0}, _c2py_t0, _c2py_t1, _c2py_t2, c2py_ticks());'.format(perf_name))
        out.append('    }')

    out.append('    return ret;')

def _emit_varargs_wrapper(out, func, buf_params, scalar_params, timing):
    """Emit the METH_VARARGS wrapper (Python 2.7 through 3.11)."""
    name = func.name
    all_params = func.py_params

    out.append('static PyObject*')
    out.append('_' + name + '_wrapper(PyObject *self, PyObject *args)')
    out.append('{')

    # Local variables
    _emit_wrapper_locals(out, buf_params, scalar_params, func, timing)

    # Arg parse via PyArg_ParseTuple
    fmt_str = _build_parse_format(all_params, func)
    parse_args = ['args', '"' + fmt_str + '"']
    for p in all_params:
        if p.pytype == 'buffer':
            parse_args.append('&py_' + p.name)
        elif p.pytype == 'int':
            parse_args.append('&c_' + p.name)
        else:
            parse_args.append('&c_' + p.name)
    out.append('    if (!PyArg_ParseTuple({}))'.format(', '.join(parse_args)))
    out.append('        return NULL;')
    out.append('')

    # Shared body: buffer init, acquire, checks, impl, cleanup
    _emit_wrapper_body(out, func, buf_params, scalar_params, name, timing)

    out.append('}')
    out.append('')

def _emit_fastcall_wrapper(out, func, buf_params, scalar_params, timing):
    """Emit the METH_FASTCALL wrapper (Python >= 3.12)."""
    name = func.name
    all_params = func.py_params

    out.append('static PyObject*')
    out.append('_' + name + '_fastcall(PyObject *self, PyObject *const *args, Py_ssize_t nargs)')
    out.append('{')

    # Local variables
    _emit_wrapper_locals(out, buf_params, scalar_params, func, timing)

    # Arg count check (handle optional params with defaults)
    total = len(all_params)
    min_req = sum(1 for p in all_params if p.default is None)
    if min_req == total:
        out.append('    if (nargs != {0}) {{'.format(total))
        out.append('        PyErr_SetString(PyExc_TypeError,')
        out.append('            \"{0} expects {1} argument{2}\");'.format(
            name, total, 's' if total != 1 else ''))
        out.append('        return NULL;')
        out.append('    }')
    else:
        out.append('    if (nargs < {0} || nargs > {1}) {{'.format(min_req, total))
        out.append('        PyErr_SetString(PyExc_TypeError,')
        out.append('            \"{0} expects {1} to {2} arguments\");'.format(
            name, min_req, total))
        out.append('        return NULL;')
        out.append('    }')
    out.append('')

    # Extract args directly from the array (only up to nargs)
    void_ptr_names = _collect_void_ptr_names(func)
    idx = 0
    for p in all_params:
        is_optional = (p.default is not None)
        if p.pytype == 'buffer':
            out.append('    py_{0} = args[{1}];'.format(p.name, idx))
        elif p.pytype == 'int':
            out.append('    /* extract int: {0} from args[{1}]{2} */'.format(
                p.name, idx, ' (optional)' if is_optional else ''))
            if is_optional:
                out.append('    if (nargs > {0}) {{'.format(idx))
            else:
                out.append('    {')
            out.append('        long _c2py_tmp = PyLong_AsLong(args[{0}]);'.format(idx))
            out.append('        if (_c2py_tmp == -1 && PyErr_Occurred()) return NULL;')
            if p.name in void_ptr_names:
                out.append('        c_{0} = (intptr_t)_c2py_tmp;'.format(p.name))
            else:
                out.append('        c_{0} = (int)_c2py_tmp;'.format(p.name))
            out.append('    }')
        else:
            out.append('    /* extract float: {0} from args[{1}]{2} */'.format(
                p.name, idx, ' (optional)' if is_optional else ''))
            if is_optional:
                out.append('    if (nargs > {0}) {{'.format(idx))
            else:
                out.append('    {')
            out.append('        double _c2py_tmp = PyFloat_AsDouble(args[{0}]);'.format(idx))
            out.append('        if (_c2py_tmp == -1.0 && PyErr_Occurred()) return NULL;')
            out.append('        c_{0} = _c2py_tmp;'.format(p.name))
            out.append('    }')
        idx += 1

    out.append('')

    # Shared body: buffer init, acquire, checks, impl, cleanup
    _emit_wrapper_body(out, func, buf_params, scalar_params, name, timing)

    out.append('}')
    out.append('')

def _overload_map_lines(ol, indent):
    """Build Map: and Outputs: description lines for an overload or group.
    Returns a list of strings."""
    lines = []

    # Determine the C params to show maps for
    params = ol.params if ol.params else []
    if not params and ol.variants and ol.variants[0].params:
        params = ol.variants[0].params

    map_items = []
    for cp in params:
        expr = ol.map_exprs.get(cp.name)
        if expr is not None:
            expr_src = _expr_to_source(expr)
            if expr_src:
                map_items.append("{} = {} ({})".format(cp.name, expr_src, cp.ctype))

    if map_items:
        lines.append(indent + "Map: " + map_items[0])
        for m in map_items[1:]:
            lines.append(indent + "     " + m)

    outputs = getattr(ol, 'outputs', {}) or {}
    if outputs:
        out_strs = sorted("{} ({})".format(k, v) for k, v in outputs.items())
        lines.append(indent + "Outputs: " + ", ".join(out_strs))

    return lines

def _derive_param_info(param_name, checks, overloads):
    """Auto-derive parameter description info from checks and overloads.
    Returns a list of description strings (one per line)."""
    info = []

    # Derive format types from function-level checks and overload when conditions
    fmt_chars = set()
    for chk in checks:
        if isinstance(chk, Compare) and chk.op == '==':
            for side, other in [(chk.left, chk.right), (chk.right, chk.left)]:
                if (isinstance(side, Attr) and side.attr == 'format'
                        and _expr_refers_to(side.obj, param_name)
                        and isinstance(other, StrLit) and len(other.value) == 1):
                    fmt_chars.add(other.value)
    for ol in overloads:
        if ol.when_expr:
            _extract_fmt_from_expr(ol.when_expr, param_name, fmt_chars)
        if ol.variants:
            for v in ol.variants:
                if v.when_expr:
                    _extract_fmt_from_expr(v.when_expr, param_name, fmt_chars)

    if fmt_chars:
        fmt_names = []
        for c in sorted(fmt_chars):
            ctype = _FORMAT_CHAR_TO_NAME.get(c, "?")
            fmt_names.append("{} (format '{}')".format(ctype, c))
        info.append("Type: " + " or ".join(fmt_names))

    # Derive writability from overload C params
    writable = False
    for ol in overloads:
        if ol.variants:
            for v in ol.variants:
                for cp in v.params:
                    if (cp.is_pointer and not cp.is_const
                            and _expr_refers_to(ol.map_exprs.get(cp.name), param_name)):
                        writable = True
                        break
        else:
            for cp in ol.params:
                if (cp.is_pointer and not cp.is_const
                        and _expr_refers_to(ol.map_exprs.get(cp.name), param_name)):
                    writable = True
                    break

    if writable:
        info.append("Writable")

    # Derive dimensionality and size relationships from checks
    for chk in checks:
        if isinstance(chk, Compare):
            left, right, op = chk.left, chk.right, chk.op
            if (isinstance(left, Attr) and left.attr == 'ndim'
                    and _expr_refers_to(left.obj, param_name)
                    and op == '==' and isinstance(right, IntLit)):
                info.append("Shape: {}D".format(right.value))
            elif (isinstance(left, Attr) and left.attr == 'n'
                  and _expr_refers_to(left.obj, param_name)
                  and op in ('==', '>=', '>', '<=', '<')
                  and isinstance(right, Attr) and right.attr == 'n'):
                other_name = _expr_to_source(right.obj)
                if other_name:
                    info.append("Size {} {}".format(
                        "must equal" if op == '==' else op, other_name))
            elif (isinstance(left, Subscript)
                  and isinstance(left.obj, Attr) and left.obj.attr == 'shape'
                  and _expr_refers_to(left.obj.obj, param_name)
                  and isinstance(right, IntLit) and op == '=='):
                info.append("Axis {}: {} elements".format(left.index, right.value))

    return info

def _emit_constants(out, mod):
    """Emit PyObject_SetAttrString calls for module-level integer constants,
    timing perf struct pointers, and GIL release flags."""
    has_gil = any(f.gil_release for f in mod.functions)
    if not mod.constants and not mod.timing and not has_gil:
        return
    if mod.constants:
        for cname, cvalue in sorted(mod.constants.items()):
            out.append('        PyObject_SetAttrString(module, "{}",'.format(_escape_c_str(cname)))
            out.append('            PyLong_FromLong({}));'.format(cvalue))
    if mod.timing:
        out.append('        PyObject_SetAttrString(module, "_c2py_timing_enabled",')
        out.append('            PyLong_FromVoidPtr(&_c2py_timing_enabled));')
        for func in mod.functions:
            out.append('        PyObject_SetAttrString(module, "_perf_{0}",'.format(func.name))
            out.append('            PyLong_FromVoidPtr(&_perf_{0}));'.format(func.name))
            for ol in func.overloads:
                if ol.variants:
                    for v in ol.variants:
                        c_name = v.c_name if v.c_name is not None else v.sig_str.split('(')[0].strip().split()[-1]
                        perf_name = '_perf_{0}__{1}'.format(func.name, c_name)
                        out.append('        PyObject_SetAttrString(module, "{}",'.format(perf_name))
                        out.append('            PyLong_FromVoidPtr(&{}));'.format(perf_name))
                else:
                    c_name = ol.c_name if ol.c_name is not None else ol.sig_str.split('(')[0].strip().split()[-1]
                    perf_name = '_perf_{0}__{1}'.format(func.name, c_name)
                    out.append('        PyObject_SetAttrString(module, "{}",'.format(perf_name))
                    out.append('            PyLong_FromVoidPtr(&{}));'.format(perf_name))
    if has_gil:
        out.append('        PyObject_SetAttrString(module, "_c2py_gil_release_enabled",')
        out.append('            PyLong_FromVoidPtr(&_c2py_gil_release_enabled));')
        for func in mod.functions:
            if func.gil_release:
                out.append('        PyObject_SetAttrString(module, "_c2py_gil_release_{0}",'.format(func.name))
                out.append('            PyLong_FromVoidPtr(&_gil_release_{0}));'.format(func.name))

def _emit_timing_decls(out, mod):
    """Emit global timing declarations: enabled flag, perf structs, tick API."""
    out.append('/* ---- Performance timing ---- */')
    out.append('static int _c2py_timing_enabled = 1;')
    out.append('')
    for func in mod.functions:
        out.append('static c2py_perf_t _perf_{0};'.format(func.name))
        for ol in func.overloads:
            if ol.variants:
                for v in ol.variants:
                    c_name = v.c_name if v.c_name is not None else v.sig_str.split('(')[0].strip().split()[-1]
                    out.append('static c2py_perf_t _perf_{0}__{1};'.format(func.name, c_name))
            else:
                c_name = ol.c_name if ol.c_name is not None else ol.sig_str.split('(')[0].strip().split()[-1]
                out.append('static c2py_perf_t _perf_{0}__{1};'.format(func.name, c_name))
    out.append('')
    out.append('/* Python-callable: return tick source frequency in Hz */')
    out.append('static PyObject*')
    out.append('__c2py_tick_frequency(PyObject *self, PyObject *args) {')
    out.append('    (void)self;')
    out.append('    if (!PyArg_ParseTuple(args, ""))')
    out.append('        return NULL;')
    out.append('    return PyLong_FromUnsignedLongLong(c2py_tick_frequency());')
    out.append('}')
    out.append('')
    out.append('/* Python-callable: convert ticks to nanoseconds at given frequency */')
    out.append('static PyObject*')
    out.append('__c2py_ticks_to_ns(PyObject *self, PyObject *args) {')
    out.append('    unsigned long long ticks, freq_hz;')
    out.append('    (void)self;')
    out.append('    if (!PyArg_ParseTuple(args, "KK", &ticks, &freq_hz))')
    out.append('        return NULL;')
    out.append('    return PyLong_FromUnsignedLongLong(')
    out.append('        c2py_ticks_to_ns((uint64_t)ticks, (uint64_t)freq_hz));')
    out.append('}')
    out.append('')

def _mod_doc(mod):
    """Build a module-level docstring.
    Returns a string with module info, or empty string if no info."""
    parts = []
    parts.append("Module: {}".format(mod.name))
    if mod.sources:
        parts.append("Source: {}".format(str(mod.sources)))
    if mod.headers:
        parts.append("Headers: {}".format(str(mod.headers)))
    if mod.constants:
        const_strs = sorted("{}={}".format(k, v) for k, v in mod.constants.items())
        parts.append("Constants: {}".format(", ".join(const_strs)))
    if mod.timing:
        parts.append("Timing: enabled")
    else:
        parts.append("Timing: no")
    if mod.free_threading:
        parts.append("Free-threading: yes (Py_MOD_GIL_NOT_USED)")
    else:
        parts.append("Free-threading: no (GIL re-enabled on 3.14t)")
    gil_funcs = [f.name for f in mod.functions if f.gil_release]
    if gil_funcs:
        parts.append("GIL release: {}".format(", ".join(gil_funcs)))
    return "\n".join(parts)

def _doc(func):
    """Build a fully transparent docstring for a function.
    Every piece of YAML info is surfaced: checks, maps, GIL, overloads, outputs.
    Returns a Python string with real newlines (escaped at C embedding point)."""
    lines = []

    # 1a. Signature line (parseable by CPython for __text_signature__)
    sig_args = ", ".join(p.name for p in func.py_params)
    lines.append("{}({})".format(func.name, sig_args) if sig_args else func.name + "()")
    lines.append("--")
    lines.append("")

    # 1b. Full annotated signature
    py_args = []
    for p in func.py_params:
        arg = "{}: {}".format(p.name, p.pytype)
        if p.default is not None:
            arg += " = {}".format(p.default)
        py_args.append(arg)
    lines.append("{}({}) -> {}".format(func.name, ", ".join(py_args), func.return_type))

    # 2. User doc
    if func.doc:
        lines.append("")
        lines.append(func.doc)

    # 3. Parameters section
    if func.py_params:
        lines.append("")
        lines.append("Parameters")
        lines.append("----------")
        for p in func.py_params:
            lines.append("{} : {}".format(p.name, p.pytype))
            param_info = _derive_param_info(p.name, func.checks, func.overloads)
            if param_info:
                for info in param_info:
                    lines.append("    " + info)
            if func.params and p.name in func.params:
                lines.append("    " + func.params[p.name])

    # 4. Checks section
    if func.checks:
        lines.append("")
        lines.append("Checks")
        lines.append("------")
        for chk in func.checks:
            lines.append("  " + _expr_to_source(chk) + "  [ValueError]")

    # 5. GIL state (only show when released, to avoid noise)
    if func.gil_release:
        lines.append("")
        lines.append("GIL: released")

    # 6. Overloads section
    has_overloads = func.overloads and any(
        ol.sig_str or ol.variants for ol in func.overloads)
    if has_overloads:
        lines.append("")
        lines.append("Overloads")
        lines.append("---------")
        for ol in func.overloads:
            if ol.variants:
                header = "Group"
                if ol.group_name:
                    header += " " + ol.group_name
                if ol.when_expr:
                    header += " (When: {})".format(_expr_to_source(ol.when_expr))
                lines.append("  " + header)
                if ol.doc:
                    lines.append("    " + ol.doc)
                # Map is shared by all variants in the group
                lines.extend(_overload_map_lines(ol, "    "))
                for v in ol.variants:
                    lines.append("    {} -> {}".format(v.name, v.sig_str))
                    if v.when_expr:
                        lines.append("      When: {}".format(_expr_to_source(v.when_expr)))
                    if v.doc:
                        lines.append("      " + v.doc)
                    v_out = getattr(v, 'outputs', {}) or {}
                    if v_out:
                        out_strs = sorted("{} ({})".format(k, ctype)
                                          for k, ctype in v_out.items())
                        lines.append("      Outputs: " + ", ".join(out_strs))
            else:
                sig = ol.sig_str
                if ol.when_expr:
                    lines.append("  {} (When: {})".format(sig, _expr_to_source(ol.when_expr)))
                else:
                    lines.append("  " + sig)
                if ol.doc:
                    lines.append("    " + ol.doc)
                lines.extend(_overload_map_lines(ol, "    "))

    # 7. Default raise
    if func.default_raise:
        lines.append("")
        if ":" in func.default_raise:
            exc_type, msg = func.default_raise.split(":", 1)
            lines.append("{}: {}".format(exc_type.strip(), msg.strip()))
        else:
            lines.append(func.default_raise)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module init
# ---------------------------------------------------------------------------

def _emit_module_init(out, mod, has_free_threading=False):
    name = mod.name
    has_gil = any(f.gil_release for f in mod.functions)
    has_variants = any(any(ol.variants for ol in f.overloads) for f in mod.functions)
    has_attrs = mod.constants or mod.timing or has_gil
    out.append('')
    out.append('/* ' + '-' * 44 + ' */')
    out.append('/* Module definition                          */')
    out.append('/* ' + '-' * 44 + ' */')
    out.append('')

    # --- VARARGS method table (Python < 3.12) ---
    out.append('static PyMethodDef _methods_varargs[] = {')
    for func in mod.functions:
        out.append('    {{"{}", (PyCFunction)_{}_wrapper, METH_VARARGS, "{}"}},'.format(
            func.name, func.name, _escape_c_str(_doc(func))))
    if has_variants:
        for func in mod.functions:
            if any(ol.variants for ol in func.overloads):
                out.append('    {{"_rebind_{0}", (PyCFunction)_rebind_{0}, METH_VARARGS,'
                           .format(func.name))
                out.append('     "rebind variant for {0}"}},'.format(func.name))
    if mod.timing:
        out.append('    {"_c2py_tick_frequency", (PyCFunction)__c2py_tick_frequency, METH_VARARGS,')
        out.append('     "return tick source frequency in Hz"},')
        out.append('    {"_c2py_ticks_to_ns", (PyCFunction)__c2py_ticks_to_ns, METH_VARARGS,')
        out.append('     "convert (ticks, freq_hz) to nanoseconds"},')
    out.append('    {NULL, NULL, 0, NULL}')
    out.append('};')
    out.append('')

    # --- FASTCALL method table (Python >= 3.12) ---
    out.append('static PyMethodDef _methods_fastcall[] = {')
    for func in mod.functions:
        out.append('    {{"{}", (PyCFunction)_{}_fastcall, METH_FASTCALL, "{}"}},'.format(
            func.name, func.name, _escape_c_str(_doc(func))))
    if has_variants:
        for func in mod.functions:
            if any(ol.variants for ol in func.overloads):
                out.append('    {{"_rebind_{0}", (PyCFunction)_rebind_{0}, METH_VARARGS,'
                           .format(func.name))
                out.append('     "rebind variant for {0}"}},'.format(func.name))
    if mod.timing:
        out.append('    {"_c2py_tick_frequency", (PyCFunction)__c2py_tick_frequency, METH_VARARGS,')
        out.append('     "return tick source frequency in Hz"},')
        out.append('    {"_c2py_ticks_to_ns", (PyCFunction)__c2py_ticks_to_ns, METH_VARARGS,')
        out.append('     "convert (ticks, freq_hz) to nanoseconds"},')
    out.append('    {NULL, NULL, 0, NULL}')
    out.append('};')
    out.append('')

    # Module-level docstring
    mod_doc = _mod_doc(mod)
    mod_doc_c = _escape_c_str(mod_doc) if mod_doc else None

    # Module definition struct - methods pointer set at init time
    # GIL-enabled layout (standard CPython)
    out.append('static PyModuleDef _module_def = {')
    out.append('    PyModuleDef_HEAD_INIT,')
    out.append('    "{}",'.format(name))
    if mod_doc_c:
        out.append('    "{}",'.format(mod_doc_c))
    else:
        out.append('    NULL,')
    out.append('    -1,')
    out.append('    NULL,  /* methods set at init */')
    out.append('    NULL, NULL, NULL, NULL')
    out.append('};')
    out.append('')

    # Free-threading slots array (Py_mod_gil for Python 3.15t+)
    if has_free_threading:
        out.append('static PyModuleDef_Slot _slots[] = {')
        out.append('    {Py_mod_gil, Py_MOD_GIL_NOT_USED},')
        out.append('    {0, NULL}')
        out.append('};')
        out.append('')

    # Free-threaded layout (PyModuleDef_FT, PyObject is 32 bytes)
    out.append('static PyModuleDef_FT _module_def_ft = {')
    out.append('    PyModuleDef_HEAD_INIT_FT,')
    out.append('    "{}",'.format(name))
    if mod_doc_c:
        out.append('    "{}",'.format(mod_doc_c))
    else:
        out.append('    NULL,')
    out.append('    -1,')
    out.append('    NULL,  /* methods set at init */')
    if has_free_threading:
        out.append('    _slots,  /* m_slots */')
    else:
        out.append('    NULL,  /* m_slots */')
    out.append('    NULL, NULL, NULL')
    out.append('};')
    out.append('')

    # Resolve calls at init
    resolve_calls = ''
    if has_variants:
        for func in mod.functions:
            if any(ol.variants for ol in func.overloads):
                resolve_calls += '    _resolve_{}();\n'.format(func.name)

    # Python 3 init
    out.append('PyObject* PyInit_{}(void) {{'.format(name))
    out.append('    c2py_runtime_init();')
    if resolve_calls:
        out.append(resolve_calls.rstrip('\n'))
    out.append('')
    out.append('    PyObject *module = NULL;')
    out.append('    PyMethodDef *methods = C2PY.use_fastcall ? _methods_fastcall : _methods_varargs;')
    out.append('')
    out.append('    if (C2PY.is_free_threaded) {')
    out.append('        _module_def_ft.m_methods = methods;')
    out.append('        if (C2PY.Module_Create2 != NULL) {')
    out.append('            module = C2PY.Module_Create2((PyModuleDef*)&_module_def_ft, 3);')
    out.append('        }')
    out.append('    } else {')
    out.append('        _module_def.m_methods = methods;')
    if has_attrs:
        out.append('        if (C2PY.Module_Create2 != NULL) {')
        out.append('            module = C2PY.Module_Create2(&_module_def, 3);')
        out.append('        } else {')
        out.append('            /* Fallback for Python 2.7 where PyModuleDef is not supported */')
        out.append('            module = C2PY.InitModule_2_7("{}", methods);'.format(name))
        out.append('        }')
    else:
        out.append('        if (C2PY.Module_Create2 != NULL) {')
        out.append('            module = C2PY.Module_Create2(&_module_def, 3);')
        out.append('        } else {')
        out.append('            module = C2PY.InitModule_2_7("{}", methods);'.format(name))
        out.append('        }')
    out.append('    }')
    out.append('')
    out.append('    if (module != NULL) {')
    _emit_constants(out, mod)
    if has_free_threading:
        out.append('        if (C2PY.Unstable_Module_SetGIL != NULL) {')
        out.append('            C2PY.Unstable_Module_SetGIL(module, (void*)1);'
                   '  /* Py_MOD_GIL_NOT_USED */')
        out.append('        }')
    out.append('    }')
    out.append('    return module;')
    out.append('}')
    out.append('')
    # Python 2.7 init (free_threading not applicable -- Python 2.7 has no FT builds)
    out.append('void init{}(void) {{'.format(name))
    out.append('    c2py_runtime_init();')
    out.append(resolve_calls)
    out.append('    PyObject *module = C2PY.InitModule_2_7("{}",'.format(name))
    out.append('        C2PY.use_fastcall ? _methods_fastcall : _methods_varargs);')
    out.append('    if (module != NULL) {')
    _emit_constants(out, mod)
    out.append('    }')
    out.append('}')

def _verify_c_invariants(code):
    """Check generated C for structural errors before returning.

    Scans the generated C and verifies:
      - Buffer acquire/release pairs in wrapper functions
      - GIL save/restore pairs in impl functions
      - Output scalar NULL checks + PyTuple_SetItem
      - Balanced braces

    Raises ValueError with line number on first violation.
    """
    lines = code.split('\n')
    _check_balanced_braces(lines)
    _check_buffer_invariants(lines)
    _check_output_scalar_invariants(lines)

def _check_balanced_braces(lines):
    """Verify brace depth returns to zero after each function."""
    depth = 0
    in_function = False
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('static PyObject*'):
            if depth != 0:
                raise ValueError(
                    "Line %d: unbalanced braces before function start "
                    "(depth=%d)" % (lineno, depth))
            in_function = True
        if not stripped or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        if stripped.startswith('#'):
            continue
        depth += stripped.count('{') - stripped.count('}')
        if depth < 0:
            raise ValueError(
                "Line %d: unmatched closing brace" % lineno)
    if depth != 0:
        raise ValueError(
            "End of file: unbalanced braces (depth=%d)" % depth)

def _check_buffer_invariants(lines):
    """Check buffer acquire/release pairs in every wrapper function.

    For each function containing c2py_acquire_buffer:
      - Every acquire must have a matching acq_X = 1 on the next line.
      - The first acquire may return NULL on failure (no cleanup needed).
      - Subsequent acquires must goto cleanup on failure.
      - Cleanup must release every acquired buffer in reverse order.
    """
    lineno = 0
    while lineno < len(lines):
        line = lines[lineno]
        stripped = line.strip()

        if stripped.startswith('static PyObject*'):
            _check_one_wrapper(lines, lineno)
            # Find next function (skip past current line first)
            lineno += 1
            while lineno < len(lines) and 'static PyObject*' not in lines[lineno]:
                lineno += 1
        else:
            lineno += 1

def _check_one_wrapper(lines, start_lineno):
    """Check buffer / GIL invariants for a single wrapper function.

    We scan from start_lineno until the matching closing brace at depth 0
    to locate the function body, then verify structured properties.
    """
    first_brace = None
    depth = 0
    end_lineno = None
    for i in range(start_lineno, len(lines)):
        stripped = lines[i].strip()
        depth += stripped.count('{') - stripped.count('}')
        if '{' in stripped and first_brace is None:
            first_brace = i
        if depth == 0 and first_brace is not None:
            end_lineno = i
            break

    if end_lineno is None or first_brace is None:
        return  # malformed function, leave to brace checker

    # -- Scan body for invariants --
    body_start = first_brace

    # Collect buffer variable names and acq flag names
    buf_names = []  # in order of Py_buffer decl
    acq_names = set()  # from int acq_X = 0;
    pending_acquires = []  # buffers seen in acquire but not yet flagged with acq_X=1
    acquired = []  # ordered list of buffer names acquired (from acq_X = 1;)
    released = []  # ordered list of buffer names released in cleanup
    acquire_count = 0
    in_cleanup = False
    gil_save_count = 0
    gil_restore_count = 0

    for lineno in range(body_start, end_lineno + 1):
        line = lines[lineno]
        stripped = line.strip()

        # Skip comments and preprocessor directives
        if not stripped or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        if stripped.startswith('#'):
            continue

        # Collect buffer declarations
        m = re.match(r'\s*Py_buffer\s+(buf_\w+);', line)
        if m:
            buf_names.append(m.group(1))
            continue

        # Collect acq flag declarations
        m = re.match(r'\s*int\s+(acq_\w+)\s*=\s*0;', line)
        if m:
            acq_names.add(m.group(1))
            continue

        # Detect cleanup label
        if stripped == 'cleanup:':
            in_cleanup = True
            continue

        # Track acquire calls
        m = re.match(r'.*if\s*\(\s*c2py_acquire_buffer\(([^,]+),\s*&(buf_\w+),', line)
        if m:
            buf_name = m.group(2)
            acquire_count += 1
            pending_acquires.append(buf_name)

            # Check the next non-blank line for return/goto
            next_line = None
            for j in range(lineno + 1, min(lineno + 5, end_lineno + 1)):
                nl = lines[j].strip()
                if nl and not nl.startswith('/*') and not nl.startswith('*'):
                    next_line = nl
                    break

            if acquire_count == 1:
                if next_line and 'return NULL' not in next_line:
                    raise ValueError(
                        "Line %d: first buffer acquire must return NULL "
                        "on failure, got: %s" % (lineno + 1, next_line))
            else:
                if next_line and 'goto cleanup' not in next_line:
                    raise ValueError(
                        "Line %d: subsequent buffer acquire must goto cleanup "
                        "on failure, got: %s" % (lineno + 1, next_line))
            continue

        # Track acq_X = 1
        m = re.match(r'\s*(acq_\w+)\s*=\s*1;', line)
        if m:
            flag_name = m.group(1)
            # Map acq_a -> buf_a (same suffix)
            exp_buf = re.sub(r'^acq_', 'buf_', flag_name)
            if exp_buf not in buf_names:
                raise ValueError(
                    "Line %d: acq flag '%s' has no matching buf variable "
                    "'%s'" % (lineno + 1, flag_name, exp_buf))
            if flag_name not in acq_names:
                raise ValueError(
                    "Line %d: acq flag '%s' was not declared" % (
                        lineno + 1, flag_name))
            if not pending_acquires or pending_acquires[0] != exp_buf:
                raise ValueError(
                    "Line %d: acq flag '%s' set but no pending acquire "
                    "for '%s'" % (lineno + 1, flag_name, exp_buf))
            pending_acquires.pop(0)
            acquired.append(exp_buf)
            continue

        # Both return/goto are expected intermediate lines between acquire and acq flag
        if pending_acquires and (stripped.startswith('return')
                                  or stripped.startswith('goto')
                                  or stripped.startswith('if')
                                  or stripped.startswith('{')
                                  or stripped.startswith('}')):
            continue

        # Track releases in cleanup
        if in_cleanup:
            m = re.match(r'\s*if\s*\(\s*(acq_\w+)\s*\)\s*c2py_release_buffer\(&(buf_\w+)\);', line)
            if m:
                released.append(m.group(2))
                continue

        # Track GIL save/restore
        if 'PyEval_SaveThread' in stripped:
            gil_save_count += 1
        if 'PyEval_RestoreThread' in stripped:
            gil_restore_count += 1

    # -- Post-function checks --

    # Check that all acquires were resolved with acq_X = 1
    if pending_acquires:
        raise ValueError(
            "Function starting at line %d: buffer(s) '%s' acquired but "
            "never flagged with acq_X = 1" % (
                start_lineno + 1, ', '.join(pending_acquires)))

    # Check that every acquired buffer has a matching release in cleanup
    for buf in acquired:
        if buf not in released:
            raise ValueError(
                "Function starting at line %d: buffer '%s' acquired but "
                "not released in cleanup" % (start_lineno + 1, buf))

    # Check that all releases are of previously acquired buffers
    for buf in reversed(released):
        if buf not in acquired:
            raise ValueError(
                "Function starting at line %d: buffer '%s' released but "
                "never acquired" % (start_lineno + 1, buf))

    # Check release order: must be reverse of acquisition
    expected_reverse = list(reversed(acquired))
    if released and released != expected_reverse:
        raise ValueError(
            "Function starting at line %d: release order mismatch. "
            "Expected reverse of acquire: %s, got: %s" % (
                start_lineno + 1, expected_reverse, released))

    # Check GIL save/restore balance
    if gil_save_count != gil_restore_count:
        raise ValueError(
            "Function starting at line %d: unbalanced GIL save/restore "
            "(%d save vs %d restore)" % (
                start_lineno + 1, gil_save_count, gil_restore_count))

def _check_output_scalar_invariants(lines):
    """Check that every output PyObject has NULL check + PyTuple_SetItem.

    Scan for patterns like:
        PyObject *_c2py_objN = PyLong_From*(...)
      which must be followed by:
        if (_c2py_objN == NULL) { ... }
        PyTuple_SetItem(_c2py_tup, N, _c2py_objN);

    Also check that PyTuple_New is NULL-checked.
    """
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()

        # Check PyTuple_New has NULL check
        m = re.match(r'PyObject\s*\*\s*_c2py_tup\s*=\s*PyTuple_New\(', stripped)
        if m:
            next_line = None
            for j in range(lineno, min(lineno + 3, len(lines) + 1)):
                nl = lines[j - 1].strip()
                if nl and not nl.startswith('/*') and not nl.startswith('*') and 'PyTuple_New' not in nl:
                    next_line = nl
                    break
            if next_line and '_c2py_tup == NULL' not in next_line:
                raise ValueError(
                    "Line %d: PyTuple_New missing NULL check, got: %s" % (
                        lineno, next_line))

        # Check PyObject creation followed by NULL check + Tuple_SetItem
        m = re.match(
            r'PyObject\s*\*\s*(_c2py_obj\d+)\s*='
            r'\s*(PyLong_FromLong|PyLong_FromLongLong|'
            r'PyLong_FromUnsignedLongLong|PyFloat_FromDouble)',
            stripped)
        if m:
            obj_name = m.group(1)
            # Check subsequent lines for:
            #   if (_c2py_objN == NULL) {
            #       Py_DECREF(_c2py_tup);
            #       return NULL;
            #   }
            #   PyTuple_SetItem(_c2py_tup, N, _c2py_objN);
            has_null_check = False
            has_decref = False
            has_setitem = False
            in_null_block = False

            for j in range(lineno, min(lineno + 10, len(lines) + 1)):
                nl = lines[j - 1].strip()
                if not nl or nl.startswith('/*') or nl.startswith('*'):
                    continue
                if 'if (%s == NULL)' % obj_name in nl:
                    in_null_block = True
                    has_null_check = True
                    continue
                if in_null_block:
                    if 'Py_DECREF(_c2py_tup)' in nl:
                        has_decref = True
                    if 'return NULL' in nl:
                        pass  # expected after Py_DECREF
                    if '}' == nl:
                        in_null_block = False
                        continue
                if 'PyTuple_SetItem(_c2py_tup,' in nl and obj_name in nl:
                    has_setitem = True

            if not has_null_check:
                raise ValueError(
                    "Line %d: '%s' missing NULL check" % (lineno, obj_name))
            if not has_decref:
                raise ValueError(
                    "Line %d: '%s' missing Py_DECREF in NULL check" % (
                        lineno, obj_name))
            if not has_setitem:
                raise ValueError(
                    "Line %d: '%s' missing PyTuple_SetItem" % (lineno, obj_name))

