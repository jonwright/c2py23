"""C code generator for c2py23 using an explicit C AST.

Builds a tree of CNode objects (CFunction, CBlock, CIf, etc.) and
renders the tree to C source code in a single pass at the end.
"""
from __future__ import print_function

from c2py23.parser import (
    Var, Attr, Subscript, IntLit, StrLit, Compare, BinOp, UnaryOp,
    PyParam, CParam, COverload, CVariant, FuncDef, ModuleDef,
)
from c2py23.generator import (
    _FORMAT_CHAR_TO_NAME,
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


# ---------------------------------------------------------------------------
# C AST nodes
# ---------------------------------------------------------------------------

class CNode:
    def to_c(self, indent=0):
        raise NotImplementedError


class CBlock(CNode):
    """Braced block: { stmt; stmt; }"""
    def __init__(self, children=None):
        self.children = children or []

    def add(self, child):
        self.children.append(child)
        return self

    def to_c(self, indent=0):
        if not self.children:
            return ' ' * indent + '{}'
        lines = [' ' * indent + '{']
        for c in self.children:
            lines.append(c.to_c(indent + 4))
        lines.append(' ' * indent + '}')
        return '\n'.join(lines)


class CComment(CNode):
    def __init__(self, text):
        self.text = text

    def to_c(self, indent=0):
        return ' ' * indent + '/* ' + self.text + ' */'


class CLine(CNode):
    """A single line of C code (no trailing semicolon)."""
    def __init__(self, code):
        self.code = code

    def to_c(self, indent=0):
        return ' ' * indent + self.code


class CStmt(CLine):
    """A single statement ending with semicolon."""
    def __init__(self, code):
        super(CStmt, self).__init__(code)

    def to_c(self, indent=0):
        return ' ' * indent + self.code + ';'


class CBlank(CNode):
    def to_c(self, indent=0):
        return ''


class CAssign(CStmt):
    def __init__(self, lhs, rhs):
        super(CAssign, self).__init__(lhs + ' = ' + rhs)


class CDecl(CStmt):
    """Variable declaration with optional init: type name = init;"""
    def __init__(self, ctype, name, init=None):
        if init is not None:
            code = '{0} {1} = {2}'.format(ctype, name, init)
        else:
            code = '{0} {1}'.format(ctype, name)
        super(CDecl, self).__init__(code)


class CCall(CStmt):
    """Function call: func(args);"""
    def __init__(self, func_name, args=None):
        args_str = ', '.join(args) if args else ''
        super(CCall, self).__init__('{0}({1})'.format(func_name, args_str))


class CReturn(CStmt):
    def __init__(self, value=None):
        if value is not None:
            super(CReturn, self).__init__('return ' + value)
        else:
            super(CReturn, self).__init__('return')


class CGoto(CStmt):
    def __init__(self, label):
        super(CGoto, self).__init__('goto ' + label)


class CIf(CNode):
    def __init__(self, condition, then_body, else_body=None):
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body

    def to_c(self, indent=0):
        lines = [' ' * indent + 'if (' + self.condition + ')']
        if isinstance(self.then_body, CBlock):
            lines.append(self.then_body.to_c(indent))
        else:
            lines.append(self.then_body.to_c(indent + 4))
        if self.else_body is not None:
            lines.append(' ' * indent + 'else')
            if isinstance(self.else_body, CBlock):
                lines.append(self.else_body.to_c(indent))
            elif isinstance(self.else_body, CIf):
                lines.append(self.else_body.to_c(indent + 4))
            else:
                lines.append(self.else_body.to_c(indent + 4))
        return '\n'.join(lines)


class CSwitch(CNode):
    def __init__(self, var, cases):
        self.var = var
        self.cases = cases  # list of (label, body_nodes)

    def to_c(self, indent=0):
        lines = [' ' * indent + 'switch (' + self.var + ') {']
        for label, body in self.cases:
            lines.append(' ' * (indent + 4) + 'case ' + label + ':')
            lines.append(' ' * (indent + 8) + '{')
            for node in body:
                lines.append(node.to_c(indent + 12))
            lines.append(' ' * (indent + 8) + '}')
            lines.append(' ' * (indent + 8) + 'break;')
        lines.append(' ' * (indent + 4) + 'default:')
        lines.append(' ' * (indent + 8) + 'break;')
        lines.append(' ' * indent + '}')
        return '\n'.join(lines)


class CFunction(CNode):
    def __init__(self, return_type, name, params, body, is_static=True,
                 is_extern=False):
        self.return_type = return_type
        self.name = name
        self.params = params
        self.body = body
        self.is_static = is_static
        self.is_extern = is_extern

    def to_c(self, indent=0):
        prefix = ''
        if self.is_static:
            prefix = 'static '
        elif self.is_extern:
            prefix = 'extern '
        param_str = ', '.join(self.params)
        header = ' ' * indent + prefix + self.return_type + ' ' + self.name + '(' + param_str + ')'
        body_str = self.body.to_c(0) if isinstance(self.body, CBlock) else (' ' * 4 + self.body.to_c(4))
        return header + '\n' + body_str


class CLabel(CNode):
    def __init__(self, name):
        self.name = name

    def to_c(self, indent=0):
        return ' ' * indent + self.name + ':'

# ---------------------------------------------------------------------------
# Helper functions for building AST
# ---------------------------------------------------------------------------

def stmt(code):
    return CStmt(code)

def line(code):
    return CLine(code)

def decl(ctype, name, init=None):
    return CDecl(ctype, name, init)

def call(func_name, args=None):
    return CCall(func_name, args)

def _cast_c_name(ol):
    c_name = ol.c_name
    if c_name is None:
        c_name = ol.sig_str.split('(')[0].strip().split()[-1]
    return c_name


# ---------------------------------------------------------------------------
# Top-level generate function (CAST version)
# ---------------------------------------------------------------------------

def generate(module_def):
    """Generate C wrapper source for a module using explicit C AST.

    Returns C source string.
    """
    nodes = []
    has_gil_release = any(f.gil_release for f in module_def.functions)
    has_free_threading = module_def.free_threading

    nodes.append(CLine('/* Generated by c2py23 cast - do not edit by hand */'))
    nodes.append(CLine('#include <stdio.h>'))
    nodes.append(CLine('#include "c2py_runtime.h"'))
    for h in module_def.headers:
        nodes.append(CLine('#include "{0}"'.format(h)))
    nodes.append(CBlank())

    # Forward declarations
    seen = set()
    for func in module_def.functions:
        for ol in func.overloads:
            if ol.variants:
                for v in ol.variants:
                    cn = _cast_c_name(v)
                    if cn not in seen:
                        seen.add(cn)
                        ret = v.return_type if v.return_type != 'void' else 'void'
                        param_strs = [p.ctype + ' ' + p.name for p in v.params]
                        nodes.append(CLine(
                            'extern {0} {1}({2});'.format(
                                ret, cn, ', '.join(param_strs))))
            else:
                cn = _cast_c_name(ol)
                if cn not in seen:
                    seen.add(cn)
                    ret = ol.return_type if ol.return_type != 'void' else 'void'
                    param_strs = [p.ctype + ' ' + p.name for p in ol.params]
                    nodes.append(CLine(
                        'extern {0} {1}({2});'.format(
                            ret, cn, ', '.join(param_strs))))
    nodes.append(CBlank())

    # Timing declarations (use original for helper functions)
    if module_def.timing:
        from c2py23.generator import _emit_timing_decls
        temp = []
        _emit_timing_decls(temp, module_def)
        for tl in temp:
            nodes.append(CLine(tl.lstrip()))

    # GIL release declarations
    if has_gil_release:
        nodes.append(CComment('GIL release'))
        nodes.append(CDecl('int', '_c2py_gil_release_enabled', '1'))
        for func in module_def.functions:
            if func.gil_release:
                nodes.append(CDecl(
                    'int', '_gil_release_' + func.name, '1'))
        nodes.append(CBlank())

    # Per-function emission
    for func in module_def.functions:
        _build_function_ast(nodes, func, module_def.name,
                            module_def.timing, has_gil_release)

    # Module init
    _build_module_init_ast(nodes, module_def, has_free_threading,
                           has_gil_release)

    return '\n'.join(n.to_c() for n in nodes) + '\n'


# ---------------------------------------------------------------------------
# Per-function AST builder
# ---------------------------------------------------------------------------

def _build_function_ast(nodes, func, module_name, timing, has_gil_release):
    name = func.name
    buf_params = [p for p in func.py_params if p.pytype == 'buffer']
    scalar_params = [p for p in func.py_params if p.pytype != 'buffer']

    nodes.append(CComment('Wrapper for: ' + name))
    nodes.append(CBlank())

    has_groups = any(ol.variants for ol in func.overloads)
    if has_groups:
        _build_static_dispatch_ast(nodes, func, buf_params, scalar_params)

    # Impl function
    impl_body = _build_impl_body_ast(func, buf_params, scalar_params,
                                     timing, has_gil_release)
    void_ptr_names = set()
    for ol in func.overloads:
        for cp in ol.params:
            if cp.base_type == 'void' and cp.is_pointer:
                void_ptr_names.add(cp.name)

    impl_params = []
    for p in buf_params:
        impl_params.append('Py_buffer *buf_' + p.name)
    for p in scalar_params:
        if p.pytype == 'int':
            if p.name in void_ptr_names:
                impl_params.append('intptr_t c_' + p.name)
            else:
                impl_params.append('int c_' + p.name)
        else:
            impl_params.append('double c_' + p.name)

    nodes.append(CFunction('PyObject*', '_{0}_impl'.format(name),
                           impl_params, impl_body))
    nodes.append(CBlank())

    # Wrapper functions
    _build_varargs_wrapper_ast(nodes, func, buf_params, scalar_params, name)
    _build_fastcall_wrapper_ast(nodes, func, buf_params, scalar_params, name)


# ---------------------------------------------------------------------------
# Static dispatch AST (grouped overloads)
# ---------------------------------------------------------------------------

def _build_static_dispatch_ast(nodes, func, buf_params, scalar_params):
    name = func.name
    groups = [(i, ol) for i, ol in enumerate(func.overloads) if ol.variants]

    nodes.append(CComment('Variant dispatch for ' + name))
    nodes.append(CBlank())

    for gi, (i, ol) in enumerate(groups):
        nodes.append(CLine(
            'static int _var_{0}_{1} = -1;'.format(name, gi)))
        nodes.append(CLine(
            'static const char *_vname_{0}_{1} = NULL;'.format(name, gi)))
    nodes.append(CBlank())

    for gi, (i, ol) in enumerate(groups):
        body = CBlock()
        for vi, v in enumerate(ol.variants):
            if v.when_expr is not None:
                when_c = _expr_to_c(v.when_expr, buf_params, scalar_params, None)
                ifbody = CBlock()
                ifbody.add(CStmt(
                    '_var_{0}_{1} = {2}; _vname_{0}_{1} = "{3}"; return'.format(
                        name, gi, vi, v.name)))
                body.add(CIf(when_c, ifbody))
        last_vi = len(ol.variants) - 1
        body.add(CStmt(
            '_var_{0}_{1} = {2}; _vname_{0}_{1} = "{3}"'.format(
                name, gi, last_vi, ol.variants[last_vi].name)))
        func_params = ['void']
        nodes.append(CFunction('void', '_resolve_{0}_{1}'.format(name, gi),
                               func_params, body,
                               is_static=True))
        nodes.append(CBlank())

    # Aggregate resolve
    agg_body = CBlock()
    for gi in range(len(groups)):
        agg_body.add(CStmt(
            '_resolve_{0}_{1}()'.format(name, gi)))
    nodes.append(CFunction('void', '_resolve_{0}'.format(name),
                           ['void'], agg_body, is_static=True))
    nodes.append(CBlank())

    # Rebind
    rebind_body = CBlock()
    rebind_body.add(CDecl('const char*', 'target', 'NULL'))
    rebind_body.add(CIf(
        '!C2PY.ParseTuple(args, "z", &target)',
        CBlock().add(CReturn('NULL'))))
    rebind_body.add(CBlank())
    rebind_body.add(CIf(
        'target == NULL',
        CBlock()
            .add(CStmt('_resolve_{0}()'.format(name)))
            .add(CStmt('Py_RETURN_NONE'))))
    rebind_body.add(CBlank())

    for gi, (i, ol) in enumerate(groups):
        for vi, v in enumerate(ol.variants):
            rebind_body.add(CIf(
                '!strcmp(target, "{0}")'.format(v.name),
                CBlock()
                    .add(CStmt(
                        '_var_{0}_{1} = {2}; _vname_{0}_{1} = "{3}"'.format(
                            name, gi, vi, v.name)))
                    .add(CStmt('Py_RETURN_NONE'))))
    rebind_body.add(CBlank())
    rebind_body.add(CStmt(
        'C2PY.Err_SetString(C2PY.exc_ValueError, "unknown variant")'))
    rebind_body.add(CReturn('NULL'))

    nodes.append(CFunction(
        'PyObject*', '_rebind_{0}'.format(name),
        ['PyObject *self', 'PyObject *args'],
        rebind_body, is_static=True))
    nodes.append(CBlank())


# ---------------------------------------------------------------------------
# Impl function body AST
# ---------------------------------------------------------------------------

def _build_impl_body_ast(func, buf_params, scalar_params, timing, has_gil_release):
    body = CBlock()
    name = func.name
    gil = func.gil_release and has_gil_release

    if timing:
        body.add(CDecl('int', '_c2py_do_time', '_c2py_timing_enabled'))
        body.add(CDecl('uint64_t', '_c2py_ct0', '0'))
        body.add(CStmt('uint64_t _c2py_ct1 = 0'))
        body.add(CBlank())

    if gil:
        body.add(CDecl(
            'int', '_c2py_do_gil',
            '_c2py_gil_release_enabled && _gil_release_{0}'.format(name)))
        body.add(CDecl('void*', '_c2py_thread_state', 'NULL'))
        body.add(CBlank())

    # Checks
    for check in func.checks:
        body.add(CComment('check: {0}'.format(_expr_to_source(check))))

    # Overload dispatch
    _build_overload_dispatch_ast(body, func, buf_params, scalar_params,
                                 timing, gil)

    body.add(CBlank())
    body.add(CComment('should not reach here'))
    body.add(CReturn('NULL'))
    return body


# ---------------------------------------------------------------------------
# Overload dispatch AST
# ---------------------------------------------------------------------------

def _build_overload_dispatch_ast(body, func, buf_params, scalar_params,
                                 timing, gil):
    name = func.name
    overloads = func.overloads
    default_raise = func.default_raise

    has_groups = any(ol.variants for ol in overloads)
    if not has_groups:
        _build_flat_dispatch_ast(body, overloads, buf_params, scalar_params,
                                 timing, name, gil, default_raise)
        return

    group_index = 0
    for i, ol in enumerate(overloads):
        is_group = ol.variants is not None
        if i == 0:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                inner = CBlock()
                _build_inner_dispatch_ast(inner, ol, buf_params, scalar_params,
                                          timing, name, gil, group_index)
                body.add(CIf(when_c, inner))
                if is_group:
                    group_index += 1
            else:
                inner = CBlock()
                if is_group:
                    _build_inner_dispatch_ast(inner, ol, buf_params, scalar_params,
                                              timing, name, gil, group_index)
                    group_index += 1
                else:
                    _build_single_call_ast(inner, ol, buf_params, scalar_params,
                                           timing, name, gil)
                body.add(inner)
        else:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                inner = CBlock()
                if is_group:
                    _build_inner_dispatch_ast(inner, ol, buf_params, scalar_params,
                                              timing, name, gil, group_index)
                    group_index += 1
                else:
                    _build_single_call_ast(inner, ol, buf_params, scalar_params,
                                           timing, name, gil)
                # Need to chain else-ifs
                body.add(CIf(when_c, inner))
            else:
                inner = CBlock()
                if is_group:
                    _build_inner_dispatch_ast(inner, ol, buf_params, scalar_params,
                                              timing, name, gil, group_index)
                    group_index += 1
                else:
                    _build_single_call_ast(inner, ol, buf_params, scalar_params,
                                           timing, name, gil)
                body.add(inner)

    if default_raise:
        _build_default_raise_ast(body, default_raise)


def _build_flat_dispatch_ast(body, overloads, buf_params, scalar_params,
                             timing, name, gil, default_raise):
    if len(overloads) == 1 and overloads[0].when_expr is None:
        inner = CBlock()
        _build_single_call_ast(inner, overloads[0], buf_params, scalar_params,
                               timing, name, gil)
        body.add(CComment('overload 0 (always)'))
        body.add(inner)
        return

    for i, ol in enumerate(overloads):
        inner = CBlock()
        if i == 0:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                _build_single_call_ast(inner, ol, buf_params, scalar_params,
                                       timing, name, gil)
                body.add(CIf(when_c, inner))
            else:
                _build_single_call_ast(inner, ol, buf_params, scalar_params,
                                       timing, name, gil)
                if len(overloads) == 1 or all(
                        o.when_expr is None for o in overloads[i + 1:]):
                    body.add(inner)
                else:
                    body.add(CIf('1', inner))
        elif i == len(overloads) - 1:
            _build_single_call_ast(inner, ol, buf_params, scalar_params,
                                   timing, name, gil)
            body.add(CIf('1', inner))
        else:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                _build_single_call_ast(inner, ol, buf_params, scalar_params,
                                       timing, name, gil)
                body.add(CIf(when_c, inner))
            else:
                _build_single_call_ast(inner, ol, buf_params, scalar_params,
                                       timing, name, gil)
                body.add(inner)

    if default_raise:
        _build_default_raise_ast(body, default_raise)


def _build_default_raise_ast(body, default_raise):
    from c2py23.generator import _emit_default_raise_body
    temp = []
    _emit_default_raise_body(temp, default_raise)
    for tl in temp:
        body.add(CLine(tl.lstrip()))


def _build_inner_dispatch_ast(body, ol, buf_params, scalar_params,
                              timing, name, gil, group_index):
    body.add(CComment(
        'group {0}: {1} variants'.format(group_index, len(ol.variants))))
    cases = []
    for vi, v in enumerate(ol.variants):
        syn_ol = COverload(
            v.sig_str, v.params, v.return_type,
            ol.map_exprs, v.when_expr,
            name=v.name, outputs=v.outputs, c_name=v.c_name)
        case_body = CBlock()
        _build_c_call_ast(case_body, syn_ol, buf_params, scalar_params,
                          timing, name, gil, indent=12)
        cases.append((str(vi), case_body.children))
    body.add(CSwitch('_var_{0}_{1}'.format(name, group_index), cases))


def _build_single_call_ast(body, ol, buf_params, scalar_params,
                           timing, name, gil):
    body.add(CComment(ol.sig_str))
    _build_c_call_ast(body, ol, buf_params, scalar_params,
                      timing, name, gil)


# ---------------------------------------------------------------------------
# C call AST (the core: emits the actual C function call + return marshalling)
# ---------------------------------------------------------------------------

def _build_c_call_ast(body, ol, buf_params, scalar_params,
                      timing, func_name, gil_release_call=False,
                      indent=4):
    c_name = _cast_c_name(ol)
    perf_name = '_perf_{0}__{1}'.format(func_name, c_name)
    outputs = getattr(ol, 'outputs', {}) or {}

    # Declare output variables
    for p in ol.params:
        if p.name in outputs:
            ctype = outputs[p.name]
            var_name = '_out_{0}'.format(p.name)
            if ctype in ('int', 'int8_t', 'int16_t', 'int32_t',
                         'uint8_t', 'uint16_t', 'uint32_t', 'int64_t', 'uint64_t'):
                body.add(CDecl('int', var_name, '0'))
            else:
                body.add(CDecl('double', var_name, '0.0'))

    # Build args + INT_MAX checks
    args = []
    for p in ol.params:
        if p.name in outputs:
            args.append('&_out_{0}'.format(p.name))
            continue
        expr = ol.map_exprs.get(p.name)
        if expr is None:
            continue
        arg_c = _expr_to_c(expr, buf_params, scalar_params, ol)
        # Save pre-cast expression for INT_MAX check (must use raw Py_ssize_t)
        raw_c = arg_c
        # Add casts for void* / type conversion
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
        if not _expr_is_count_or_len(expr):
            args.append(arg_c)
        else:
            body.add(CIf(
                '({0}) > (Py_ssize_t)INT_MAX'.format(raw_c),
                CBlock()
                    .add(CStmt('PyErr_SetString(PyExc_ValueError,'
                               ' "buffer too large for int n'
                               ' (> INT_MAX elements)")'))
                    .add(CReturn('NULL'))))
            args.append(arg_c)

    call_str = c_name + '(' + ', '.join(args) + ')'

    has_outputs = bool(outputs)
    has_ret = (ol.return_type and ol.return_type != 'void'
               and ol.return_type is not None)

    # GIL save
    if gil_release_call:
        body.add(CStmt(
            'if (_c2py_do_gil) _c2py_thread_state = PyEval_SaveThread()'))

    # Timing start
    if timing:
        body.add(CStmt(
            'if (_c2py_do_time) _c2py_ct0 = c2py_ticks()'))

    if not has_outputs:
        if ol.return_type in ('void', None):
            body.add(CStmt(call_str))
        elif ol.return_type == 'int':
            body.add(CDecl('int', '_ret', call_str))
        elif ol.return_type == 'float':
            body.add(CDecl('float', '_ret', call_str))
        elif ol.return_type == 'double':
            body.add(CDecl('double', '_ret', call_str))
        else:
            body.add(CStmt(call_str))

        # GIL restore
        if gil_release_call:
            body.add(CStmt(
                'if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state)'))

        if timing:
            body.add(CBlock()
                .add(CStmt('if (_c2py_do_time) {'))
                .add(CStmt('    _c2py_ct1 = c2py_ticks()'))
                .add(CStmt(
                    '    c2py_perf_record_call(&{0},'
                    ' _c2py_ct0, _c2py_ct1)'.format(perf_name)))
                .add(CStmt('}')))

        if ol.return_type in ('void', None):
            body.add(CStmt('Py_RETURN_NONE'))
        elif ol.return_type == 'int':
            body.add(CReturn('PyLong_FromLong((long)_ret)'))
        elif ol.return_type == 'float':
            body.add(CReturn('PyFloat_FromDouble((double)_ret)'))
        elif ol.return_type == 'double':
            body.add(CReturn('PyFloat_FromDouble(_ret)'))
        else:
            body.add(CStmt('Py_RETURN_NONE'))
        return

    # Output scalar handling
    out_items = []
    if has_ret:
        ret_var = '_c2py_retval'
        if ol.return_type == 'int':
            body.add(CDecl('int', ret_var, call_str))
        elif ol.return_type == 'float':
            body.add(CDecl('float', ret_var, call_str))
        elif ol.return_type == 'double':
            body.add(CDecl('double', ret_var, call_str))
        else:
            body.add(CStmt(call_str))
            body.add(CDecl('int', ret_var, '0'))
        out_items.append(('ret', ol.return_type, ret_var))
    else:
        body.add(CStmt(call_str))

    # GIL restore before Python object construction
    if gil_release_call:
        body.add(CStmt(
            'if (_c2py_do_gil) PyEval_RestoreThread(_c2py_thread_state)'))

    if timing:
        body.add(CBlock()
            .add(CStmt('if (_c2py_do_time) {'))
            .add(CStmt('    _c2py_ct1 = c2py_ticks()'))
            .add(CStmt(
                '    c2py_perf_record_call(&{0},'
                ' _c2py_ct0, _c2py_ct1)'.format(perf_name)))
            .add(CStmt('}')))

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
            body.add(CReturn('PyLong_FromLong((long){0})'.format(val)))
        elif ctype == 'int64_t':
            body.add(CReturn(
                'PyLong_FromLongLong((long long){0})'.format(val)))
        elif ctype == 'uint64_t':
            body.add(CReturn(
                'PyLong_FromUnsignedLongLong({0})'.format(val)))
        elif ctype in ('float', 'double'):
            body.add(CReturn('PyFloat_FromDouble((double){0})'.format(val)))
        else:
            body.add(CReturn('PyFloat_FromDouble((double){0})'.format(val)))
    else:
        body.add(CDecl('PyObject*', '_c2py_tup', 'PyTuple_New({0})'.format(n)))
        body.add(CIf('_c2py_tup == NULL', CBlock().add(CReturn('NULL'))))
        for i, (name, ctype, val) in enumerate(out_items):
            if ctype in ('int', 'int8_t', 'int16_t', 'int32_t',
                         'uint8_t', 'uint16_t', 'uint32_t'):
                body.add(CDecl(
                    'PyObject*', '_c2py_obj{0}'.format(i),
                    'PyLong_FromLong((long){0})'.format(val)))
            elif ctype == 'int64_t':
                body.add(CDecl(
                    'PyObject*', '_c2py_obj{0}'.format(i),
                    'PyLong_FromLongLong((long long){0})'.format(val)))
            elif ctype == 'uint64_t':
                body.add(CDecl(
                    'PyObject*', '_c2py_obj{0}'.format(i),
                    'PyLong_FromUnsignedLongLong({0})'.format(val)))
            elif ctype in ('float', 'double'):
                body.add(CDecl(
                    'PyObject*', '_c2py_obj{0}'.format(i),
                    'PyFloat_FromDouble((double){0})'.format(val)))
            else:
                body.add(CDecl(
                    'PyObject*', '_c2py_obj{0}'.format(i),
                    'PyFloat_FromDouble((double){0})'.format(val)))
            body.add(CIf(
                '_c2py_obj{0} == NULL'.format(i),
                CBlock()
                    .add(CStmt('Py_DECREF(_c2py_tup)'))
                    .add(CReturn('NULL'))))
            body.add(CStmt(
                'PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0})'.format(i)))
        body.add(CReturn('_c2py_tup'))


# ---------------------------------------------------------------------------
# Wrapper functions AST (VARARGS + FASTCALL)
# ---------------------------------------------------------------------------

def _build_varargs_wrapper_ast(nodes, func, buf_params, scalar_params, name):
    from c2py23.generator import _emit_varargs_wrapper
    lines_before = len(nodes)
    # Use a temporary list, then wrap each line as a CLine in the function
    temp = []
    _emit_varargs_wrapper(temp, func, buf_params, scalar_params, False)
    # Find the function start and body in temp
    if temp:
        # First line is "static PyObject*"
        func_header = temp[0]
        func_name_line = temp[1] if len(temp) > 1 else ''
        body_lines = temp[2:] if len(temp) > 2 else []
        nodes.append(CLine(func_header))
        nodes.append(CLine(func_name_line))
        for tl in body_lines:
            nodes.append(CLine(tl.lstrip()))


def _build_fastcall_wrapper_ast(nodes, func, buf_params, scalar_params, name):
    from c2py23.generator import _emit_fastcall_wrapper
    temp = []
    _emit_fastcall_wrapper(temp, func, buf_params, scalar_params, False)
    if temp:
        func_header = temp[0]
        func_name_line = temp[1] if len(temp) > 1 else ''
        body_lines = temp[2:] if len(temp) > 2 else []
        nodes.append(CLine(func_header))
        nodes.append(CLine(func_name_line))
        for tl in body_lines:
            nodes.append(CLine(tl.lstrip()))


def _build_wrapper_decls(body, func, buf_params, scalar_params):
    void_ptr_names = set()
    for ol in func.overloads:
        for cp in ol.params:
            if cp.base_type == 'void' and cp.is_pointer:
                void_ptr_names.add(cp.name)

    for p in buf_params:
        body.add(CDecl('PyObject*', 'py_' + p.name, 'NULL'))
    for p in scalar_params:
        if p.pytype != 'int' or p.name not in void_ptr_names:
            body.add(CDecl('PyObject*', 'py_' + p.name, 'NULL'))
    body.add(CDecl('PyObject*', 'ret', 'NULL'))
    for p in buf_params:
        body.add(CDecl('Py_buffer', 'buf_' + p.name))
        body.add(CDecl('int', 'acq_' + p.name, '0'))
    body.add(CBlank())


def _build_varargs_argparse(body, buf_params, scalar_params, name):
    all_params = buf_params + scalar_params
    py_names = ['&py_' + p.name for p in all_params]
    fmt = '"' + 'O' * len(py_names) + '"'
    body.add(CIf(
        '!PyArg_ParseTuple(args, {0}, {1})'.format(
            fmt, ', '.join(py_names)),
        CBlock().add(CReturn('NULL'))))


def _build_fastcall_argparse(body, buf_params, scalar_params, name):
    n_expected = len(buf_params) + len(scalar_params)
    body.add(CIf(
        'nargs != {0}'.format(n_expected),
        CBlock()
            .add(CStmt('PyErr_SetString(PyExc_TypeError,'
                       ' "{0} expects {1} arguments")'.format(
                           name, n_expected)))
            .add(CReturn('NULL'))))
    for i, p in enumerate(buf_params + scalar_params):
        body.add(CStmt('py_{0} = args[{1}]'.format(p.name, i)))
    body.add(CBlank())


def _build_wrapper_acquire_checks_call(body, func, buf_params, scalar_params, name):
    for p in buf_params:
        body.add(CCall(
            'memset',
            ['&buf_{0}'.format(p.name), '0', 'C2PY.pybuffer_size']))

    for i, p in enumerate(buf_params):
        flags = _get_buf_flags(p, func)
        want_write = 'PyBUF_WRITABLE' in flags
        write_val = 'C2PY_BUF_WRITE' if want_write else 'C2PY_BUF_READ'
        acq = CBlock()
        acq.add(CStmt(''))
        acq.add(CStmt(
            'if (c2py_acquire_buffer(py_{0}, &buf_{0}, {1}) == -1)'.format(
                p.name, write_val)))
        if i == 0:
            acq.add(CStmt('    return NULL'))
        else:
            acq.add(CStmt('    goto cleanup'))
        acq.add(CStmt('acq_{0} = 1'.format(p.name)))
        # Flatten acq into body
        body.add(CBlank())
        body.add(CLine(
            'if (c2py_acquire_buffer(py_{0}, &buf_{0}, {1}) == -1)'.format(
                p.name, write_val)))
        if i == 0:
            body.add(CStmt('return NULL'))
        else:
            body.add(CStmt('goto cleanup'))
        body.add(CStmt('acq_{0} = 1'.format(p.name)))

    # Restrict checks (use original function with ast body's line rendering)
    # We can't easily use the original function here because it uses out.append().
    # Instead we build a simple version inline.

    # Restrict and contiguity checks: bridge to original functions
    temp_lines = []
    _emit_restrict_checks(temp_lines, buf_params, func)
    _emit_contiguity_checks_orig(temp_lines, buf_params)
    for tl in temp_lines:
        body.add(CLine(tl.lstrip()))

    # Call impl
    body.add(CBlank())
    impl_args = []
    for p in buf_params:
        impl_args.append('&buf_' + p.name)
    for p in scalar_params:
        impl_args.append('c_' + p.name)
    body.add(CStmt(
        'ret = _{0}_impl({1})'.format(name, ', '.join(impl_args))))

    # Cleanup
    body.add(CLabel('cleanup'))
    for i in range(len(buf_params) - 1, -1, -1):
        p = buf_params[i]
        body.add(CStmt(
            'if (acq_{0}) c2py_release_buffer(&buf_{0})'.format(p.name)))
    body.add(CReturn('ret'))


# ---------------------------------------------------------------------------
# Module init AST
# ---------------------------------------------------------------------------

def _build_module_init_ast(nodes, module_def, has_free_threading, has_gil_release):
    name = module_def.name
    has_timing = module_def.timing
    has_variants = any(
        any(ol.variants for ol in f.overloads) for f in module_def.functions)
    has_attrs = module_def.constants or has_timing or has_gil_release
    mod_doc_c = _escape_c_str(_mod_doc(module_def)) if _mod_doc(module_def) else None

    nodes.append(CBlank())
    nodes.append(CComment('Module definition'))
    nodes.append(CBlank())

    # VARARGS method table
    nodes.append(CLine('static PyMethodDef _methods_varargs[] = {'))
    for func in module_def.functions:
        doc_str = _escape_c_str(_doc(func))
        nodes.append(CLine(
            '    {{"{0}", (PyCFunction)_{0}_wrapper, METH_VARARGS,'
            ' "{1}"}},'.format(func.name, doc_str)))
    if has_variants:
        for func in module_def.functions:
            if any(ol.variants for ol in func.overloads):
                nodes.append(CLine(
                    '    {{"_rebind_{0}", (PyCFunction)_rebind_{0},'
                    ' METH_VARARGS,'.format(func.name)))
                nodes.append(CLine(
                    '     "rebind variant for {0}"}},'.format(func.name)))
    if has_timing:
        nodes.append(CLine(
            '    {"_c2py_tick_frequency", (PyCFunction)__c2py_tick_frequency,'
            ' METH_VARARGS,'))
        nodes.append(CLine('     "return tick source frequency in Hz"},'))
        nodes.append(CLine(
            '    {"_c2py_ticks_to_ns", (PyCFunction)__c2py_ticks_to_ns,'
            ' METH_VARARGS,'))
        nodes.append(CLine('     "convert (ticks, freq_hz) to nanoseconds"},'))
    nodes.append(CLine('    {NULL, NULL, 0, NULL}'))
    nodes.append(CLine('};'))
    nodes.append(CBlank())

    # FASTCALL method table
    nodes.append(CLine('static PyMethodDef _methods_fastcall[] = {'))
    for func in module_def.functions:
        doc_str = _escape_c_str(_doc(func))
        nodes.append(CLine(
            '    {{"{0}", (PyCFunction)_{0}_fastcall, METH_FASTCALL,'
            ' "{1}"}},'.format(func.name, doc_str)))
    if has_variants:
        for func in module_def.functions:
            if any(ol.variants for ol in func.overloads):
                nodes.append(CLine(
                    '    {{"_rebind_{0}", (PyCFunction)_rebind_{0},'
                    ' METH_VARARGS,'.format(func.name)))
                nodes.append(CLine(
                    '     "rebind variant for {0}"}},'.format(func.name)))
    if has_timing:
        nodes.append(CLine(
            '    {"_c2py_tick_frequency", (PyCFunction)__c2py_tick_frequency,'
            ' METH_VARARGS,'))
        nodes.append(CLine('     "return tick source frequency in Hz"},'))
        nodes.append(CLine(
            '    {"_c2py_ticks_to_ns", (PyCFunction)__c2py_ticks_to_ns,'
            ' METH_VARARGS,'))
        nodes.append(CLine('     "convert (ticks, freq_hz) to nanoseconds"},'))
    nodes.append(CLine('    {NULL, NULL, 0, NULL}'))
    nodes.append(CLine('};'))
    nodes.append(CBlank())

    # Module definition struct
    nodes.append(CLine('static PyModuleDef _module_def = {'))
    nodes.append(CLine('    PyModuleDef_HEAD_INIT,'))
    nodes.append(CLine('    "{0}",'.format(name)))
    if mod_doc_c:
        nodes.append(CLine('    "{0}",'.format(mod_doc_c)))
    else:
        nodes.append(CLine('    NULL,'))
    nodes.append(CLine('    -1,'))
    nodes.append(CLine('    NULL,  /* methods set at init */'))
    nodes.append(CLine('    NULL, NULL, NULL, NULL'))
    nodes.append(CLine('};'))
    nodes.append(CBlank())
    nodes.append(CLine('static PyModuleDef_FT _module_def_ft = {'))
    nodes.append(CLine('    PyModuleDef_HEAD_INIT_FT,'))
    nodes.append(CLine('    "{0}",'.format(name)))
    if mod_doc_c:
        nodes.append(CLine('    "{0}",'.format(mod_doc_c)))
    else:
        nodes.append(CLine('    NULL,'))
    nodes.append(CLine('    -1,'))
    nodes.append(CLine('    NULL,  /* methods set at init */'))
    nodes.append(CLine('    NULL, NULL, NULL, NULL'))
    nodes.append(CLine('};'))
    nodes.append(CBlank())

    # PyInit
    resolve_calls = []
    if has_variants:
        for func in module_def.functions:
            if any(ol.variants for ol in func.overloads):
                resolve_calls.append('    _resolve_{}();'.format(func.name))

    pyinit_body = CBlock()
    pyinit_body.add(CStmt('c2py_runtime_init()'))
    for rc in resolve_calls:
        pyinit_body.add(CLine(rc))
    pyinit_body.add(CBlank())
    pyinit_body.add(CDecl('PyObject*', 'module', 'NULL'))
    pyinit_body.add(CStmt(
        'PyMethodDef *methods = C2PY.use_fastcall'
        ' ? _methods_fastcall : _methods_varargs'))
    pyinit_body.add(CBlank())
    ft_block = CBlock()
    ft_block.add(CStmt('_module_def_ft.m_methods = methods'))
    ft_block.add(CIf(
        'C2PY.Module_Create2 != NULL',
        CBlock().add(CStmt(
            'module = C2PY.Module_Create2('
            '(PyModuleDef*)&_module_def_ft, 3)'))))
    standard_block = CBlock()
    standard_block.add(CStmt('_module_def.m_methods = methods'))
    if has_attrs:
        standard_block.add(CIf(
            'C2PY.Module_Create2 != NULL',
            CBlock().add(CStmt(
                'module = C2PY.Module_Create2(&_module_def, 3)')),
            CBlock()
                .add(CLine(
                    '            /* Fallback for Python 2.7'
                    ' where PyModuleDef is not supported */'))
                .add(CStmt(
                    'module = C2PY.InitModule_2_7('
                    '"{0}", methods)'.format(name)))))
    else:
        standard_block.add(CIf(
            'C2PY.Module_Create2 != NULL',
            CBlock().add(CStmt(
                'module = C2PY.Module_Create2(&_module_def, 3)')),
            CBlock().add(CStmt(
                'module = C2PY.InitModule_2_7('
                '"{0}", methods)'.format(name)))))
    pyinit_body.add(CIf('C2PY.is_free_threaded', ft_block, standard_block))
    pyinit_body.add(CBlank())

    module_block = CBlock()
    # Use original constants emitter on a temporary list
    const_lines = []
    _emit_constants_orig(const_lines, module_def)
    for cl in const_lines:
        module_block.add(CLine(cl))
    if has_free_threading:
        module_block.add(CIf(
            'C2PY.Unstable_Module_SetGIL != NULL',
            CBlock().add(CStmt(
                'C2PY.Unstable_Module_SetGIL(module, (void*)1)'))))
    pyinit_body.add(CIf('module != NULL', module_block))
    pyinit_body.add(CReturn('module'))

    nodes.append(CFunction(
        'PyObject*', 'PyInit_{0}'.format(name), ['void'],
        pyinit_body, is_static=False))
    nodes.append(CBlank())

    # Python 2.7 init
    py2body = CBlock()
    py2body.add(CStmt('c2py_runtime_init()'))
    for rc in resolve_calls:
        py2body.add(CLine(rc))
    py2body.add(CStmt(
        'PyObject *module = C2PY.InitModule_2_7("{0}",'
        ' C2PY.use_fastcall ? _methods_fastcall'
        ' : _methods_varargs)'.format(name)))
    modblock2 = CBlock()
    const_lines2 = []
    _emit_constants_orig(const_lines2, module_def)
    for cl in const_lines2:
        modblock2.add(CLine(cl))
    py2body.add(CIf('module != NULL', modblock2))
    nodes.append(CFunction(
        'void', 'init{0}'.format(name), ['void'],
        py2body, is_static=False))
