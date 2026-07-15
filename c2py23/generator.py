"""C code generator for c2py23.

Transpiles a parsed ModuleDef AST into a compilable CPython C extension.
Uses the CBuilder class to enforce structural invariants at emit time:
buffer acquires are paired with releases, GIL saves with restores,
output scalars with NULL checks and PyTuple_SetItem.
"""

from __future__ import print_function

from c2py23.parser import (
    Var,
    Attr,
    Subscript,
    IntLit,
    StrLit,
    Compare,
    BinOp,
    COverload,
    _FORMAT_CHAR_TO_NAME,
    _escape_c_str,
    _float_literal,
    _is_ptr_expr,
    _expr_is_count_or_len,
    _is_simple_expr,
    _expr_refers_to,
    _expr_to_c,
    _expr_to_source,
    _extract_fmt_from_expr,
)
from c2py23.invariant_checker import verify_c_invariants


class CBuilder:
    """Stateful builder for generating C wrapper code.

    Tracks buffer acquires, GIL depth, and output-object construction so
    that cleanup code is always structurally correct.
    """

    def __init__(self):
        self.lines = []
        self._buf_names = []  # declared buffer names in order
        self._acq_names = set()  # declared acq flag names
        self._acquired = []  # buffers acquired (stack, in order)
        self._acq_order = []  # backend source order (C2PY_PIN_* values)
        self._gil_depth = 0
        self._in_wrapper = False
        self._in_cleanup = False
        self._impl_has_gil_release = False
        self._gil_restore_before_py = True  # invariant marker
        self._has_goto_cleanup = False

    # -- Low-level emit --

    def emit(self, line=""):
        self.lines.append(line)

    def emit_indent(self, indent, line=""):
        self.lines.append(indent + line)

    def emit_blank(self):
        self.lines.append("")

    def get_code(self):
        return "\n".join(self.lines) + "\n"

    def extend(self, other):
        """Merge another CBuilder's output into this one."""
        self.lines.extend(other.lines)

    # -- Buffer management in wrapper --

    def declare_buffer(self, name):
        self._buf_names.append(name)
        base = name.replace("info_", "", 1)
        self.emit("    c2py_buf_pin pin_{0};".format(base))
        self.emit("    c2py_ptr_info info_{0};".format(base))

    def emit_buf_memset(self, buf_var):
        base = buf_var.replace("info_", "", 1)
        self.emit("    memset(&pin_{0}.buf, 0, C2PY.pybuffer_size);".format(base))

    def acquire_buffer(self, buf_var, py_var, flags, func_name):
        """Emits c2py_pin with correct failure path.

        First buffer: return NULL on failure (nothing to clean up).
        Subsequent: goto cleanup on failure.
        """
        first = len(self._acquired) == 0
        base = buf_var.replace("info_", "", 1)
        self.emit(
            "    if (c2py_pin({0}, &pin_{1}, &info_{1}, {2}, _acqord_{3}, {4}) == -1)".format(
                py_var, base, flags, func_name, len(self._acq_order)
            )
        )
        if first:
            self.emit("        return NULL;")
        else:
            self.emit("        goto cleanup;")
            self._has_goto_cleanup = True
        self._acquired.append(buf_var)

    def enter_cleanup(self):
        self._in_cleanup = True
        if not self._acquired:
            return
        if self._has_goto_cleanup:
            self.emit("cleanup:")
        for buf_var in reversed(self._acquired):
            base = buf_var.replace("info_", "", 1)
            self.emit("    c2py_unpin_buffer(&pin_{0});".format(base))
        self._acquired = []
        self._has_goto_cleanup = False

    def _acq_name(self, buf_var):
        base = buf_var.replace("info_", "", 1)
        return "pin_{0}.acquired".format(base)

    # -- GIL management --

    def gil_save(self, cond_var, thread_state_var, indent="    "):
        self._gil_depth += 1
        self.emit(indent + "if ({0}) {1} = PyEval_SaveThread();".format(cond_var, thread_state_var))

    def gil_restore(self, cond_var, thread_state_var, indent="    "):
        if self._gil_depth <= 0:
            raise ValueError("gil_restore without matching gil_save")
        self._gil_depth -= 1
        self.emit(indent + "if ({0}) PyEval_RestoreThread({1});".format(cond_var, thread_state_var))

    def assert_gil_balanced(self, name):
        if self._gil_depth != 0:
            raise ValueError("Function '%s': unbalanced GIL save/restore (%d)" % (name, self._gil_depth))

    # -- Output scalar construction --

    def _check_output_obj(self, obj_var, indent="    "):
        """Emit NULL check + Py_DECREF cleanup for an output object."""
        self.emit(indent + "if ({0} == NULL) {{".format(obj_var))
        self.emit(indent + "    Py_DECREF(_c2py_tup);")
        self.emit(indent + "    return NULL;")
        self.emit(indent + "}")

    def emit_tuple_new(self, n, indent="    "):
        self.emit(indent + "PyObject *_c2py_tup = PyTuple_New({0});".format(n))
        self.emit(indent + "if (_c2py_tup == NULL) return NULL;")

    def emit_output_long(self, index, val, ctype="int", indent="    "):
        if ctype in ("int64_t",):
            self.emit(indent + "PyObject *_c2py_obj{0} = PyLong_FromLongLong((long long){1});".format(index, val))
        elif ctype in ("uint64_t",):
            self.emit(indent + "PyObject *_c2py_obj{0} = PyLong_FromUnsignedLongLong({1});".format(index, val))
        else:
            self.emit(indent + "PyObject *_c2py_obj{0} = PyLong_FromLong((long){1});".format(index, val))
        self._check_output_obj("_c2py_obj{0}".format(index), indent)
        self.emit(indent + "PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});".format(index))

    def emit_output_double(self, index, val, indent="    "):
        self.emit(indent + "PyObject *_c2py_obj{0} = PyFloat_FromDouble((double){1});".format(index, val))
        self._check_output_obj("_c2py_obj{0}".format(index), indent)
        self.emit("    PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});".format(index))

    # -- Restrict and contiguity checks --

    def emit_restrict_checks(self, buf_params, func):
        """Emit restrict alias checks between writable buffers."""
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

        checked = set()
        for wn in writable:
            for other in list(writable | const_set):
                if other == wn:
                    continue
                pair = tuple(sorted([wn, other]))
                if pair in checked:
                    continue
                checked.add(pair)
                self.emit("    /* restrict check: {} vs {} */".format(wn, other))
                self.emit("    if ((char*)info_{0}.ptr >= (char*)info_{1}.ptr && ".format(wn, other))
                self.emit("        (char*)info_{0}.ptr < (char*)info_{1}.ptr + info_{1}.len) {{".format(wn, other))
                self.emit('        PyErr_SetString(PyExc_ValueError, "buffer aliasing forbidden");')
                self.emit("        goto cleanup;")
                self._has_goto_cleanup = True
                self.emit("    }")
                self.emit("    if ((char*)info_{0}.ptr >= (char*)info_{1}.ptr && ".format(other, wn))
                self.emit("        (char*)info_{0}.ptr < (char*)info_{1}.ptr + info_{1}.len) {{".format(other, wn))
                self.emit('        PyErr_SetString(PyExc_ValueError, "buffer aliasing forbidden");')
                self.emit("        goto cleanup;")
                self._has_goto_cleanup = True
                self.emit("    }")
                self.emit("")

    def emit_contiguity_checks(self, buf_params):
        """Emit contiguity validation for each buffer.

        Also emits _c2py_slow_axis_buf_{name} -- the index of the slowest
        varying axis (0 for C-contiguous, ndim-1 for F-contiguous).
        Set to -1 if the buffer is not C or F contiguous (rejected anyway).
        """
        if not buf_params:
            return

        for p in buf_params:
            name = p.name
            fmt = lambda s: s.format(name)
            self.emit("    int _c2py_slow_axis_info_{0} = -1;".format(name))
            self.emit("    int _c2py_fast_axis_info_{0} = -1;".format(name))
            self.emit("    (void)_c2py_slow_axis_info_{0};".format(name))
            self.emit("    (void)_c2py_fast_axis_info_{0};".format(name))
            self.emit("    /* contiguity check: {0} */".format(name))
            self.emit("    do {")
            self.emit("        int _ok = 1;")
            self.emit("        if (info_{0}->strides == NULL && info_{0}->ndim <= 1) {{".format(name))
            self.emit("            _c2py_slow_axis_info_{0} = 0;".format(name))
            self.emit("            _c2py_fast_axis_info_{0} = (int)(info_{0}->ndim - 1);".format(name))
            self.emit("            break;")
            self.emit("        }")
            self.emit(fmt("        if (info_{0}->ndim >= 1) {{"))
            self.emit(fmt("            Py_ssize_t _expected = info_{0}->itemsize;"))
            self.emit("            int _d;")
            self.emit("            /* check F-contiguous (column-major): first dim varies fastest */")
            self.emit(fmt("            for (_d = 0; _d < info_{0}->ndim; _d++) {{"))
            self.emit(fmt("                if (info_{0}->strides[_d] < 0) {{ _ok = 0; break; }}"))
            self.emit(fmt("                if (info_{0}->strides[_d] != _expected) {{ _ok = 0; break; }}"))
            self.emit(fmt("                _expected *= info_{0}->shape[_d];"))
            self.emit("            }")
            self.emit(
                "            if (_ok) {{ _c2py_slow_axis_info_{0} = (int)(info_{0}->ndim - 1); _c2py_fast_axis_info_{0} = 0; break; }}".format(
                    name
                )
            )
            self.emit("            /* check C-contiguous (row-major): last dim varies fastest */")
            self.emit("            _ok = 1;")
            self.emit(fmt("            _expected = info_{0}->itemsize;"))
            self.emit(fmt("            for (_d = info_{0}->ndim - 1; _d >= 0; _d--) {{"))
            self.emit(fmt("                if (info_{0}->strides[_d] < 0) {{ _ok = 0; break; }}"))
            self.emit(fmt("                if (info_{0}->strides[_d] != _expected) {{ _ok = 0; break; }}"))
            self.emit(fmt("                _expected *= info_{0}->shape[_d];"))
            self.emit("            }")
            self.emit(
                "            if (_ok) {{ _c2py_slow_axis_info_{0} = 0; _c2py_fast_axis_info_{0} = (int)(info_{0}->ndim - 1); }}".format(
                    name
                )
            )
            self.emit("        }")
            self.emit("        if (!_ok) {")
            self.emit("            PyErr_SetString(PyExc_ValueError,")
            self.emit('                "buffer not contiguous (C or Fortran contiguous required)");')
            self.emit("            return NULL;")
            self.emit("        }")
            self.emit("    } while(0);")
            self.emit("")


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


def _make_decl_string(ret, name, params):
    """Build extern declaration, handling array-typed parameters."""

    def _dim(d):
        """Format one array dimension: None -> [] , otherwise -> [N]."""
        return "[]" if d is None else "[%s]" % d

    parts = []
    for p in params:
        if p.array_dims:
            base = ("const " if p.is_const else "") + p.base_type
            if len(p.array_dims) == 1:
                parts.append("%s %s%s" % (base, p.name, _dim(p.array_dims[0])))
            else:
                inner = "".join(_dim(d) for d in p.array_dims[1:])
                parts.append("%s (*%s)%s" % (base, p.name, inner))
        else:
            parts.append(p.ctype + " " + p.name)
    return "extern {} {}({});".format(ret if ret != "void" else "void", name, ", ".join(parts))


# ---------------------------------------------------------------------------
# Top-level generate function (CBuilder version)
# ---------------------------------------------------------------------------


def generate(module_def):
    """Generate C wrapper source for a module using CBuilder pattern.

    Returns C source string.
    """
    b = CBuilder()

    # Header
    b.emit("/* Generated by c2py23 - do not edit by hand */")
    b.emit("#include <stdio.h>")
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
                        cn = v.sig_str.split("(")[0].strip().split()[-1]
                    if cn not in seen:
                        seen.add(cn)
                        b.emit(_make_decl_string(v.return_type, cn, v.params))
            else:
                cn = ol.c_name
                if cn is None:
                    cn = ol.sig_str.split("(")[0].strip().split()[-1]
                if cn not in seen:
                    seen.add(cn)
                    b.emit(_make_decl_string(ol.return_type, cn, ol.params))
    b.emit_blank()

    # Timing declarations
    if module_def.timing:
        _emit_timing_decls(b, module_def)

    # GIL release declarations
    if has_gil_release:
        b.emit("/* ---- GIL release ---- */")
        b.emit("static int _c2py_gil_release_enabled = 1;")
        for func in module_def.functions:
            if func.gil_release:
                b.emit("static int _gil_release_{0} = 1;".format(func.name))
        b.emit_blank()

    # Per-function emission (each function gets its own CBuilder to
    # prevent state leaks -- _has_goto_cleanup, _acquired, _gil_depth
    # all start fresh for each function).
    for func in module_def.functions:
        fb = CBuilder()
        _emit_function(fb, func, module_def.name, module_def.timing, has_gil_release)
        b.extend(fb)

    # Module init
    _emit_module_init(b, module_def, has_free_threading, has_gil_release)

    code = b.get_code()
    verify_c_invariants(code)
    return code


# ---------------------------------------------------------------------------
# Function-level emission (CBuilder pattern)
# ---------------------------------------------------------------------------


def _emit_function(b, func, module_name, timing, has_gil_release):
    name = func.name
    buf_params = [p for p in func.py_params if p.pytype == "buffer"]
    scalar_params = [p for p in func.py_params if p.pytype != "buffer"]

    # Acquisition backend order from .c2py `acquire:` key (default: [ndarray, buffer])
    acq = getattr(func, "acquire", None) or ["C2PY_PIN_NDARRAY", "C2PY_PIN_PEP3118"]
    b._acq_order = acq
    if buf_params:
        vals = ", ".join(acq)
        b.emit("static const uint8_t _acqord_{0}[] = {{ {1} }};".format(name, vals))
        b.emit_blank()

    b.emit("/* " + "-" * 44 + " */")
    b.emit("/* Wrapper for: {0} */".format(name))
    b.emit("/* " + "-" * 44 + " */")
    b.emit_blank()

    has_groups = any(ol.variants for ol in func.overloads)
    if has_groups:
        _emit_static_dispatch(b, func, buf_params, scalar_params, timing)

    _emit_impl_func(b, func, buf_params, scalar_params, timing, has_gil_release)

    # Wrapper functions (VARARGS + FASTCALL)
    _emit_varargs_wrapper(b, func, buf_params, scalar_params, timing)
    _emit_fastcall_wrapper(b, func, buf_params, scalar_params, timing)

    b.assert_gil_balanced(name)


# ---------------------------------------------------------------------------
# Static dispatch (grouped overloads)
# ---------------------------------------------------------------------------


def _emit_static_dispatch(b, func, buf_params, scalar_params, timing):
    name = func.name
    groups = [(i, ol) for i, ol in enumerate(func.overloads) if ol.variants]

    b.emit("/* ---- Variant dispatch for {0} ---- */".format(name))
    b.emit_blank()

    def _perf_meta(gi, vi, v):
        """Emit perf struct metadata for a variant."""
        if not timing:
            return
        c_name = v.c_name or v.sig_str.split("(")[0].strip().split()[-1]
        pf = "_perf_{0}__{1}".format(name, c_name)
        b.emit("        {0}.variant = {1};".format(pf, vi))
        b.emit("        {0}.group_idx = {1};".format(pf, gi))
        b.emit('        {0}.variant_name = "{1}";'.format(pf, v.name))
        b.emit("        _active_perf_{0} = &{1};".format(name, pf))

    for gi, (i, ol) in enumerate(groups):
        gname = ol.group_name or "group{0}".format(gi)
        b.emit("static int _var_{0}_{1} = -1;".format(name, gi))
        b.emit("static const char *_vname_{0}_{1} = NULL;".format(name, gi))

    b.emit_blank()

    for gi, (i, ol) in enumerate(groups):
        b.emit("static void _resolve_{0}_{1}(void) {{".format(name, gi))
        has_default = False
        for vi, v in enumerate(ol.variants):
            if not v.default:
                continue
            has_default = True
            if v.when_expr is not None:
                when_c = _expr_to_c(v.when_expr, buf_params, scalar_params, None)
                b.emit("    if ({0}) {{".format(when_c))
                b.emit('        _var_{0}_{1} = {2}; _vname_{0}_{1} = "{3}";'.format(name, gi, vi, v.name))
                _perf_meta(gi, vi, v)
                b.emit("        return;")
                b.emit("    }")
        # Find the last default:true variant for fallback
        last_default_vi = -1
        last_default_name = ""
        for vi, v in enumerate(ol.variants):
            if v.default:
                last_default_vi = vi
                last_default_name = v.name
        if not has_default:
            raise ValueError(
                "Group '{0}' has no variant with default: true. "
                "At least one variant must be auto-selectable.".format(ol.group_name or "group{}".format(gi))
            )
        b.emit('    _var_{0}_{1} = {2}; _vname_{0}_{1} = "{3}";'.format(name, gi, last_default_vi, last_default_name))
        _perf_meta(gi, last_default_vi, ol.variants[last_default_vi])
        b.emit("}")
        b.emit_blank()

    # Aggregate resolve
    b.emit("static void _resolve_{0}(void) {{".format(name))
    for gi in range(len(groups)):
        b.emit("    _resolve_{0}_{1}();".format(name, gi))
    b.emit("}")
    b.emit_blank()

    # Rebind function
    b.emit("static PyObject* _rebind_{0}(PyObject *self, PyObject *args) {{".format(name))
    b.emit("    const char *target = NULL;")
    b.emit('    if (!C2PY.ParseTuple(args, "z", &target)) return NULL;')
    b.emit_blank()
    b.emit("    if (target == NULL) {")
    b.emit("        _resolve_{0}();".format(name))
    b.emit("        Py_RETURN_NONE;")
    b.emit("    }")
    b.emit_blank()
    for gi, (i, ol) in enumerate(groups):
        gname = ol.group_name or "group{0}".format(gi)
        for vi, v in enumerate(ol.variants):
            b.emit('    if (!strcmp(target, "{0}")) {{'.format(v.name))
            b.emit('        _var_{0}_{1} = {2}; _vname_{0}_{1} = "{3}";'.format(name, gi, vi, v.name))
            _perf_meta(gi, vi, v)
            b.emit("        Py_RETURN_NONE;")
            b.emit("    }")
    b.emit_blank()
    b.emit('    C2PY.Err_SetString(C2PY.exc_ValueError, "unknown variant");')
    b.emit("    return NULL;")
    b.emit("}")
    b.emit_blank()

    # Variants enumeration function
    b.emit("static PyObject* _variants_{0}(PyObject *self, PyObject *args) {{".format(name))
    # Collect all variant names across groups
    all_names = []
    for gi, (i, ol) in enumerate(groups):
        for v in ol.variants:
            all_names.append(v.name)
    b.emit("    PyObject *tuple = PyTuple_New({0});".format(len(all_names)))
    for idx, vname in enumerate(all_names):
        b.emit(
            '        PyTuple_SetItem(tuple, {0}, PyBytes_FromStringAndSize("{1}", {2}));'.format(idx, vname, len(vname))
        )
    b.emit("    return tuple;")
    b.emit("}")
    b.emit_blank()


# ---------------------------------------------------------------------------
# Impl function
# ---------------------------------------------------------------------------


def _emit_impl_func(b, func, buf_params, scalar_params, timing, has_gil_release):
    name = func.name
    void_ptr_names = _collect_void_ptr_names(func)

    params_c = []
    for p in buf_params:
        params_c.append("c2py_ptr_info *info_" + p.name)
    for p in scalar_params:
        if p.pytype == "int":
            if p.name in void_ptr_names:
                params_c.append("intptr_t c_{0}".format(p.name))
            else:
                params_c.append("int c_{0}".format(p.name))
        else:
            params_c.append("double c_{0}".format(p.name))

    b.emit("static PyObject*")
    b.emit("_{0}_impl({1})".format(name, ", ".join(params_c)))
    b.emit("{")

    # Contiguity checks (inside impl so when: conditions can use them)
    b.emit_contiguity_checks(buf_params)

    if timing:
        b.emit("    int _c2py_do_time = _c2py_timing_enabled;")
        b.emit("    uint64_t _c2py_ct0 = 0, _c2py_ct1 = 0;")
        b.emit_blank()

    gil = func.gil_release and has_gil_release
    if gil:
        b.emit("    int _c2py_do_gil = _c2py_gil_release_enabled" " && _gil_release_{0};".format(name))
        b.emit("    void *_c2py_thread_state = NULL;")
        b.emit_blank()

    # Checks
    for check in func.checks:
        b.emit("    /* check: {0} */".format(_expr_to_source(check)))
        _emit_check(b, check, buf_params, scalar_params)

    # Overload dispatch
    _emit_overload_dispatch(b, func, buf_params, scalar_params, timing, has_gil_release)

    b.emit_blank()
    b.emit("#ifdef _MSC_VER")
    b.emit("__pragma(warning(push))")
    b.emit("__pragma(warning(disable:4702)) /* unreachable code */")
    b.emit("#endif")
    b.emit("    return NULL;")
    b.emit("#ifdef _MSC_VER")
    b.emit("__pragma(warning(pop))")
    b.emit("#endif")
    b.emit("}")
    b.emit_blank()


# ---------------------------------------------------------------------------
# Check emission
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Overload dispatch emission
# ---------------------------------------------------------------------------


def _emit_overload_dispatch(b, func, buf_params, scalar_params, timing, has_gil_release):
    name = func.name
    overloads = func.overloads
    default_raise = func.default_raise
    gil = func.gil_release and has_gil_release

    has_groups = any(ol.variants for ol in overloads)
    if not has_groups:
        _emit_flat_dispatch(b, overloads, buf_params, scalar_params, timing, name, gil, default_raise)
        return

    group_index = 0
    for i, ol in enumerate(overloads):
        is_group = ol.variants is not None
        if i == 0:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                b.emit("    if (" + when_c + ") {")
            else:
                b.emit("    if (1) {  /* group 0 (always) */")
        else:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                b.emit("    } else if (" + when_c + ") {")
            else:
                b.emit("    }} else {{  /* group {0} (always) */".format(i))

        if is_group:
            gi = group_index
            b.emit("        /* group {0}: {1} variants */".format(gi, len(ol.variants)))
            b.emit("        switch (_var_{0}_{1}) {{".format(name, gi))

            for vi, v in enumerate(ol.variants):
                syn_ol = COverload(
                    v.sig_str,
                    v.params,
                    v.return_type,
                    ol.map_exprs,
                    v.when_expr,
                    name=v.name,
                    outputs=v.outputs,
                    c_name=v.c_name,
                )
                b.emit("        case {0}: {{".format(vi))
                _emit_c_call(
                    b,
                    syn_ol,
                    buf_params,
                    scalar_params,
                    timing,
                    name,
                    gil,
                    indent="                ",
                )
                b.emit("            break;")
                b.emit("        }")
            b.emit("        default: break;")
            b.emit("        }")
            group_index += 1
        else:
            b.emit("        /* {0} */".format(ol.sig_str))
            _emit_c_call(b, ol, buf_params, scalar_params, timing, name, gil, indent="        ")

    if default_raise:
        b.emit("    } else {")
        _emit_default_raise_body(b, default_raise, buf_params)
    b.emit("    }")


# ---------------------------------------------------------------------------
# Flat dispatch emission
# ---------------------------------------------------------------------------


def _emit_flat_dispatch(b, overloads, buf_params, scalar_params, timing, name, gil, default_raise):
    if len(overloads) == 1 and overloads[0].when_expr is None:
        b.emit("    /* overload 0 (always) */")
        b.emit("    {")
        _emit_c_call(b, overloads[0], buf_params, scalar_params, timing, name, gil)
        b.emit("    }")
        return

    for i, ol in enumerate(overloads):
        if i == 0:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                b.emit("    if (" + when_c + ") {")
            else:
                b.emit("    if (1) {  /* overload 0 (always) */")
        else:
            if ol.when_expr is not None:
                when_c = _expr_to_c(ol.when_expr, buf_params, scalar_params, ol)
                b.emit("    } else if (" + when_c + ") {")
            else:
                b.emit("    }} else {{  /* overload {0} (always) */".format(i))
        b.emit("        /* {0} */".format(ol.sig_str))
        _emit_c_call(b, ol, buf_params, scalar_params, timing, name, gil)

    if default_raise:
        b.emit("    } else {")
        _emit_default_raise_body(b, default_raise, buf_params)
    b.emit("    }")


# ---------------------------------------------------------------------------
# C call emission
# ---------------------------------------------------------------------------


def _emit_c_call(
    b,
    ol,
    buf_params,
    scalar_params,
    timing,
    func_name,
    gil_release_call=False,
    indent=None,
):
    if indent is None:
        indent = "        "

    def emitl(line):
        b.emit_indent(indent, line)

    c_name = ol.c_name
    if c_name is None:
        c_name = ol.sig_str.split("(")[0].strip().split()[-1]
    perf_name = "_perf_{0}__{1}".format(func_name, c_name)
    outputs = getattr(ol, "outputs", {}) or {}

    # Declare output variables before call
    for p in ol.params:
        if p.name in outputs:
            ctype = outputs[p.name]
            var_name = "_out_{0}".format(p.name)
            if ctype in (
                "int",
                "int8_t",
                "int16_t",
                "int32_t",
                "uint8_t",
                "uint16_t",
                "uint32_t",
                "int64_t",
                "uint64_t",
            ):
                emitl("int {0} = 0;".format(var_name))
            elif ctype in ("float",):
                emitl("float {0} = 0.0f;".format(var_name))
            else:
                emitl("double {0} = 0.0;".format(var_name))

    # Build args
    args = []
    for p in ol.params:
        if p.name in outputs:
            args.append("&_out_{0}".format(p.name))
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
            raw_c = "(" + p.ctype + ")" + raw_c
            arg_c = raw_c
        elif p.is_pointer and p.base_type == "void":
            raw_c = "(void *)(intptr_t)" + raw_c
            arg_c = raw_c
        elif not p.is_pointer and p.base_type == "int" and _expr_is_count_or_len(expr):
            arg_c = "(int)(" + arg_c + ")"
        elif not p.is_pointer and p.base_type == "float":
            arg_c = "(float)(" + arg_c + ")"
        elif not p.is_pointer and p.base_type not in ("int", "double", "void", "float"):
            arg_c = "(" + p.ctype + ")(" + arg_c + ")"
        # Check for INT_MAX overflow (use raw Py_ssize_t expression, not casted)
        if not _expr_is_count_or_len(expr):
            args.append(arg_c)
        else:
            emitl("if (({0}) > (Py_ssize_t)INT_MAX) {{".format(raw_c))
            emitl("    PyErr_SetString(PyExc_ValueError,")
            emitl('        "buffer too large for int n (> INT_MAX elements)");')
            emitl("    return NULL;")
            emitl("}")
            args.append(arg_c)

    call_str = c_name + "(" + ", ".join(args) + ")"

    has_outputs = bool(outputs)
    has_ret = ol.return_type and ol.return_type != "void" and ol.return_type is not None

    # GIL release: save before C call
    if gil_release_call:
        b.gil_save("_c2py_do_gil", "_c2py_thread_state", indent)

    # Timing: start
    if timing:
        emitl("if (_c2py_do_time) _c2py_ct0 = c2py_ticks();")

    if not has_outputs:
        if ol.return_type in ("void", None):
            emitl(call_str + ";")
        elif ol.return_type == "int":
            emitl("int _ret = " + call_str + ";")
        elif ol.return_type == "float":
            emitl("float _ret = " + call_str + ";")
        elif ol.return_type == "double":
            emitl("double _ret = " + call_str + ";")
        else:
            emitl("/* unknown return type: {0} */".format(ol.return_type))
            emitl(call_str + ";")

        # GIL restore (for no-outputs path, before PyObject creation)
        if gil_release_call:
            b.gil_restore("_c2py_do_gil", "_c2py_thread_state", indent)

        if timing:
            emitl("if (_c2py_do_time) {")
            emitl("    _c2py_ct1 = c2py_ticks();")
            emitl("    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);".format(perf_name))
            emitl("}")

        if ol.return_type in ("void", None):
            emitl("Py_RETURN_NONE;")
        elif ol.return_type == "int":
            emitl("return PyLong_FromLong((long)_ret);")
        elif ol.return_type == "float":
            emitl("return PyFloat_FromDouble((double)_ret);")
        elif ol.return_type == "double":
            emitl("return PyFloat_FromDouble(_ret);")
        else:
            emitl("Py_RETURN_NONE;")
        return

    # Output scalar handling
    out_items = []
    if has_ret:
        ret_var = "_c2py_retval"
        if ol.return_type == "int":
            emitl("int {0} = {1};".format(ret_var, call_str))
        elif ol.return_type == "float":
            emitl("float {0} = {1};".format(ret_var, call_str))
        elif ol.return_type == "double":
            emitl("double {0} = {1};".format(ret_var, call_str))
        else:
            emitl("/* unknown return type: {0} */".format(ol.return_type))
            emitl(call_str + ";")
            emitl("int {0} = 0;".format(ret_var))
        out_items.append(("ret", ol.return_type, ret_var))
    else:
        emitl(call_str + ";")

    # GIL restore before Python object construction
    if gil_release_call:
        b.gil_restore("_c2py_do_gil", "_c2py_thread_state", indent)

    if timing:
        emitl("if (_c2py_do_time) {")
        emitl("    _c2py_ct1 = c2py_ticks();")
        emitl("    c2py_perf_record_call(&{0}, _c2py_ct0, _c2py_ct1);".format(perf_name))
        emitl("}")

    for p in ol.params:
        if p.name in outputs:
            ctype = outputs[p.name]
            var_name = "_out_{0}".format(p.name)
            out_items.append((p.name, ctype, var_name))

    n = len(out_items)
    if n == 1:
        ctype = out_items[0][1]
        val = out_items[0][2]
        if ctype in (
            "int",
            "int8_t",
            "int16_t",
            "int32_t",
            "uint8_t",
            "uint16_t",
            "uint32_t",
        ):
            emitl("return PyLong_FromLong((long){0});".format(val))
        elif ctype == "int64_t":
            emitl("return PyLong_FromLongLong((long long){0});".format(val))
        elif ctype == "uint64_t":
            emitl("return PyLong_FromUnsignedLongLong({0});".format(val))
        elif ctype in ("float", "double"):
            emitl("return PyFloat_FromDouble((double){0});".format(val))
        else:
            emitl("return PyFloat_FromDouble((double){0});".format(val))
    else:
        b.emit_tuple_new(n, indent)
        for i, (name, ctype, val) in enumerate(out_items):
            if ctype in (
                "int",
                "int8_t",
                "int16_t",
                "int32_t",
                "uint8_t",
                "uint16_t",
                "uint32_t",
            ):
                b.emit_output_long(i, val, "int", indent)
            elif ctype == "int64_t":
                b.emit_output_long(i, val, "int64_t", indent)
            elif ctype == "uint64_t":
                b.emit_output_long(i, val, "uint64_t", indent)
            elif ctype in ("float", "double"):
                b.emit_output_double(i, val, indent)
            else:
                b.emit_output_double(i, val, indent)
        emitl("return _c2py_tup;")


# ---------------------------------------------------------------------------


# ---- Module support ----
def _emit_module_init(b, module_def, has_free_threading, has_gil_release):
    name = module_def.name
    has_timing = module_def.timing
    has_variants = any(any(ol.variants for ol in f.overloads) for f in module_def.functions)
    has_attrs = module_def.constants or has_timing or has_gil_release
    mod_doc_c = _escape_c_str(_mod_doc(module_def)) if _mod_doc(module_def) else None

    b.emit("")
    b.emit("/* " + "-" * 44 + " */")
    b.emit("/* Module definition                          */")
    b.emit("/* " + "-" * 44 + " */")
    b.emit("")

    # VARARGS method table
    b.emit("static PyMethodDef _methods_varargs[] = {")
    for func in module_def.functions:
        doc_str = _escape_c_str(_doc(func))
        b.emit('    {{"{}", (PyCFunction)_{}_wrapper, METH_VARARGS, "{}"}},'.format(func.name, func.name, doc_str))
    if has_variants:
        for func in module_def.functions:
            if any(ol.variants for ol in func.overloads):
                b.emit('    {{"_rebind_{0}", (PyCFunction)_rebind_{0}, METH_VARARGS,'.format(func.name))
                b.emit('     "rebind variant for {0}"}},'.format(func.name))
                b.emit('    {{"_variants_{0}", (PyCFunction)_variants_{0}, METH_VARARGS,'.format(func.name))
                b.emit('     "list variant names for {0}"}},'.format(func.name))
    if has_timing:
        b.emit('    {"_c2py_tick_frequency", (PyCFunction)__c2py_tick_frequency,' " METH_VARARGS,")
        b.emit('     "return tick source frequency in Hz"},')
        b.emit('    {"_c2py_ticks_to_ns", (PyCFunction)__c2py_ticks_to_ns,' " METH_VARARGS,")
        b.emit('     "convert (ticks, freq_hz) to nanoseconds"},')
        b.emit('    {"_c2py_perf_read", (PyCFunction)_c2py_perf_read,' " METH_VARARGS,")
        b.emit('     "read perf data into uint64 buffer"},')
        b.emit('    {"_c2py_perf_meta", (PyCFunction)_c2py_perf_meta,' " METH_VARARGS,")
        b.emit('     "get perf metadata tuple"},')
        b.emit('    {"_c2py_perf_reset", (PyCFunction)_c2py_perf_reset,' " METH_VARARGS,")
        b.emit('     "reset perf counter"},')
        b.emit('    {"_c2py_perf_get_enabled", (PyCFunction)_c2py_perf_get_enabled,' " METH_VARARGS,")
        b.emit('     "get timing enabled flag"},')
        b.emit('    {"_c2py_perf_set_enabled", (PyCFunction)_c2py_perf_set_enabled,' " METH_VARARGS,")
        b.emit('     "set timing enabled flag"},')
        b.emit('    {"_c2py_set_tick_source", (PyCFunction)__c2py_set_tick_source,' " METH_VARARGS,")
        b.emit('     "set tick source (\\"clock\\" or \\"cycle\\")"},')
    b.emit("    {NULL, NULL, 0, NULL}")
    b.emit("};")
    b.emit("")

    # FASTCALL method table
    b.emit("static PyMethodDef _methods_fastcall[] = {")
    for func in module_def.functions:
        doc_str = _escape_c_str(_doc(func))
        b.emit('    {{"{}", (PyCFunction)_{}_fastcall, METH_FASTCALL, "{}"}},'.format(func.name, func.name, doc_str))
    if has_variants:
        for func in module_def.functions:
            if any(ol.variants for ol in func.overloads):
                b.emit('    {{"_rebind_{0}", (PyCFunction)_rebind_{0}, METH_VARARGS,'.format(func.name))
                b.emit('     "rebind variant for {0}"}},'.format(func.name))
                b.emit('    {{"_variants_{0}", (PyCFunction)_variants_{0}, METH_VARARGS,'.format(func.name))
                b.emit('     "list variant names for {0}"}},'.format(func.name))
    if has_timing:
        b.emit('    {"_c2py_tick_frequency", (PyCFunction)__c2py_tick_frequency,' " METH_VARARGS,")
        b.emit('     "return tick source frequency in Hz"},')
        b.emit('    {"_c2py_ticks_to_ns", (PyCFunction)__c2py_ticks_to_ns,' " METH_VARARGS,")
        b.emit('     "convert (ticks, freq_hz) to nanoseconds"},')
        b.emit('    {"_c2py_perf_read", (PyCFunction)_c2py_perf_read,' " METH_VARARGS,")
        b.emit('     "read perf data into uint64 buffer"},')
        b.emit('    {"_c2py_perf_meta", (PyCFunction)_c2py_perf_meta,' " METH_VARARGS,")
        b.emit('     "get perf metadata tuple"},')
        b.emit('    {"_c2py_perf_reset", (PyCFunction)_c2py_perf_reset,' " METH_VARARGS,")
        b.emit('     "reset perf counter"},')
        b.emit('    {"_c2py_perf_get_enabled", (PyCFunction)_c2py_perf_get_enabled,' " METH_VARARGS,")
        b.emit('     "get timing enabled flag"},')
        b.emit('    {"_c2py_perf_set_enabled", (PyCFunction)_c2py_perf_set_enabled,' " METH_VARARGS,")
        b.emit('     "set timing enabled flag"},')
        b.emit('    {"_c2py_set_tick_source", (PyCFunction)__c2py_set_tick_source,' " METH_VARARGS,")
        b.emit('     "set tick source (\\"clock\\" or \\"cycle\\")"},')
    b.emit("    {NULL, NULL, 0, NULL}")
    b.emit("};")
    b.emit("")

    # Module definition struct
    b.emit("static PyModuleDef _module_def = {")
    b.emit("    PyModuleDef_HEAD_INIT,")
    b.emit('    "{}",'.format(name))
    if mod_doc_c:
        b.emit('    "{}",'.format(mod_doc_c))
    else:
        b.emit("    NULL,")
    b.emit("    -1,")
    b.emit("    NULL,  /* methods set at init */")
    b.emit("    NULL, NULL, NULL, NULL")
    b.emit("};")
    b.emit("")

    b.emit("static PyModuleDef_FT _module_def_ft = {")
    b.emit("    PyModuleDef_HEAD_INIT_FT,")
    b.emit('    "{}",'.format(name))
    if mod_doc_c:
        b.emit('    "{}",'.format(mod_doc_c))
    else:
        b.emit("    NULL,")
    b.emit("    -1,")
    b.emit("    NULL,  /* methods set at init */")
    b.emit("    NULL,  /* m_slots = NULL (single-phase init; PyUnstable_Module_SetGIL handles FT) */")
    b.emit("    NULL, NULL, NULL")
    b.emit("};")
    b.emit("")

    # Resolve calls for variants
    resolve_calls = []
    if has_variants:
        for func in module_def.functions:
            if any(ol.variants for ol in func.overloads):
                resolve_calls.append("    _resolve_{}();".format(func.name))

    # PyInit (Python 3)
    b.emit("C2PY_EXPORT PyObject* PyInit_{}(void) {{".format(name))
    b.emit("    if (c2py_runtime_init() != 0) {")
    b.emit("        return NULL;  /* Python will raise ImportError */")
    b.emit("    }")
    for rc in resolve_calls:
        b.emit(rc)
    b.emit("")
    b.emit("    PyObject *module = NULL;")
    b.emit("    PyMethodDef *methods = C2PY.use_fastcall" " ? _methods_fastcall : _methods_varargs;")
    b.emit("")
    b.emit("    if (C2PY.is_free_threaded) {")
    b.emit("        _module_def_ft.m_methods = methods;")
    b.emit("        if (C2PY.Module_Create2 != NULL) {")
    b.emit("            module = C2PY.Module_Create2(" "(PyModuleDef*)&_module_def_ft, 3);")
    b.emit("        }")
    b.emit("    } else {")
    b.emit("        _module_def.m_methods = methods;")
    if has_attrs:
        b.emit("        if (C2PY.Module_Create2 != NULL) {")
        b.emit("            module = C2PY.Module_Create2(&_module_def, 3);")
        b.emit("        } else {")
        b.emit("            /* Fallback for Python 2.7 where PyModuleDef" " is not supported */")
        b.emit("            module = C2PY.InitModule_2_7(" '"{}", methods);'.format(name))
        b.emit("        }")
    else:
        b.emit("        if (C2PY.Module_Create2 != NULL) {")
        b.emit("            module = C2PY.Module_Create2(&_module_def, 3);")
        b.emit("        } else {")
        b.emit("            module = C2PY.InitModule_2_7(" '"{}", methods);'.format(name))
        b.emit("        }")
    b.emit("    }")
    b.emit("")
    b.emit("    if (module != NULL) {")
    _emit_constants(b, module_def)
    if has_free_threading:
        b.emit("        if (C2PY.Unstable_Module_SetGIL != NULL) {")
        b.emit("            C2PY.Unstable_Module_SetGIL(module, (void*)1);" "  /* Py_MOD_GIL_NOT_USED */")
        b.emit("        }")
    b.emit("    }")
    b.emit("    return module;")
    b.emit("}")
    b.emit("")

    # Python 2.7 init
    b.emit("C2PY_EXPORT void init{}(void) {{".format(name))
    b.emit("    c2py_runtime_init();")
    for rc in resolve_calls:
        b.emit(rc)
    # Match original: resolve_calls always emitted (even if empty, adds blank line)
    if not resolve_calls:
        b.emit("")
    b.emit('    PyObject *module = C2PY.InitModule_2_7("{}",'.format(name))
    b.emit("        C2PY.use_fastcall ? _methods_fastcall : _methods_varargs);")
    b.emit("    if (module != NULL) {")
    _emit_constants(b, module_def)
    b.emit("    }")
    b.emit("}")


# ---------------------------------------------------------------------------
# Utility and emit functions
# ---------------------------------------------------------------------------


# ---- Expression helpers ----
def _build_parse_format(py_params, func=None):
    """Build the PyArg_ParseTuple format string.

    Inserts '|' before the first optional parameter (one with a default).
    If func is provided, Python int params that map to C void* use
    pointer-width format 'l' (long) instead of 'i' (int).
    """
    void_ptr_names = _collect_void_ptr_names(func) if func else set()
    fmt = ""
    hit_optional = False
    for p in py_params:
        if not hit_optional and p.default is not None:
            hit_optional = True
            fmt += "|"
        if p.pytype == "buffer":
            fmt += "O"
        elif p.pytype == "int":
            if p.name in void_ptr_names:
                fmt += "n"  # Py_ssize_t: pointer-width on all platforms
            else:
                fmt += "i"
        elif p.pytype == "float":
            fmt += "d"
    return fmt


# ---- Expression transpilation ----
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
        return "PyBUF_WRITABLE | PyBUF_STRIDES | PyBUF_FORMAT"
    else:
        return "PyBUF_STRIDES | PyBUF_FORMAT"


# ---- Expression helpers ----
def _make_compare_diag(compare, buf_params, scalar_params):
    """Generate diagnostic C code for a Compare expression."""
    left = compare.left
    right = compare.right
    op = compare.op

    left_c = _expr_to_c(left, buf_params, scalar_params, None)
    right_c = _expr_to_c(right, buf_params, scalar_params, None)
    source = _expr_to_source(compare)

    # Determine if either side is a format attribute
    left_is_format = isinstance(left, Attr) and left.attr == "format"
    right_is_format = isinstance(right, Attr) and right.attr == "format"

    # Format comparison: show actual format chars
    if left_is_format and isinstance(right, StrLit) and len(right.value) == 1:
        escaped_src = _escape_c_str(source)
        lines = [
            "char _c2py_err[256];",
            'const char *_fmt = {0} ? {0} : "";'.format(left_c),
            "char _got = _fmt[0] ? _fmt[strlen(_fmt) - 1] : '?';",
            "snprintf(_c2py_err, sizeof(_c2py_err), "
            "\"check failed: {0} (got format='%c')\", _got);".format(escaped_src),
        ]
        return lines
    if right_is_format and isinstance(left, StrLit) and len(left.value) == 1:
        escaped_src = _escape_c_str(source)
        lines = [
            "char _c2py_err[256];",
            'const char *_fmt = {0} ? {0} : "";'.format(right_c),
            "char _got = _fmt[0] ? _fmt[strlen(_fmt) - 1] : '?';",
            "snprintf(_c2py_err, sizeof(_c2py_err), "
            "\"check failed: {0} (got format='%c')\", _got);".format(escaped_src),
        ]
        return lines

    # Format vs format comparison
    if left_is_format and right_is_format:
        escaped_src = _escape_c_str(source)
        lines = [
            "char _c2py_err[256];",
            'const char *_fmt_l = {0} ? {0} : "";'.format(left_c),
            'const char *_fmt_r = {0} ? {0} : "";'.format(right_c),
            "char _gl = _fmt_l[0] ? _fmt_l[strlen(_fmt_l) - 1] : '?';",
            "char _gr = _fmt_r[0] ? _fmt_r[strlen(_fmt_r) - 1] : '?';",
            "snprintf(_c2py_err, sizeof(_c2py_err), "
            "\"check failed: {0} (got '%c' vs '%c')\", _gl, _gr);".format(escaped_src),
        ]
        return lines

    # Generic numeric comparison: show both sides as int
    if _is_simple_expr(left) and _is_simple_expr(right):
        escaped_src = _escape_c_str(source)
        # Detect slow_axis == 0 (from array-dim notation or user checks)
        # and add a clarifying message about C-contiguous requirement.
        if (
            isinstance(left, Attr)
            and left.attr == "slow_axis"
            and op == "=="
            and isinstance(right, IntLit)
            and right.value == 0
        ):
            lines = [
                "char _c2py_err[256];",
                "snprintf(_c2py_err, sizeof(_c2py_err), "
                '"check failed: %s (got %%ld). '
                'Buffer must be C-contiguous (use slow_axis=0 or [][] notation).",'
                " (long)(%s));" % (escaped_src, left_c),
            ]
        else:
            lines = [
                "char _c2py_err[256];",
                "snprintf(_c2py_err, sizeof(_c2py_err), "
                '"check failed: %s (got %%ld vs %%ld)",'
                " (long)(%s), (long)(%s));" % (escaped_src, left_c, right_c),
            ]
        return lines

    return None


# ---- Check emission and diagnostics ----
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


# ---- Check emission and diagnostics ----
def _emit_check(b, check, buf_params, scalar_params):
    """Emit a check that raises if condition is false.

    For single-char format comparisons on old buffers (format == NULL),
    the generated expression already uses !format || ... to pass safely.
    For two-sided format comparisons, NULL == NULL passes correctly.

    Includes actual runtime values in the failure message when possible.
    """
    c_expr = _expr_to_c(check, buf_params, scalar_params, None)
    msg = _expr_to_source(check)
    diag = _make_check_diag(check, buf_params, scalar_params)
    b.emit("    if (!(" + c_expr + ")) {")
    if diag:
        b.emit("        " + diag[0])
        if len(diag) > 1:
            for d in diag[1:]:
                b.emit("        " + d)
        b.emit("        PyErr_SetString(PyExc_ValueError, _c2py_err);")
    else:
        b.emit('        PyErr_SetString(PyExc_ValueError, "check failed: ' + _escape_c_str(msg) + '");')
    b.emit("        return NULL;")
    b.emit("    }")


# ---- Check emission and diagnostics ----
def _emit_default_raise_body(b, default_raise, buf_params=None):
    """Emit the body of a default raise block."""
    if ":" in default_raise:
        exc_type, msg = default_raise.split(":", 1)
        exc_type = exc_type.strip()
        msg = msg.strip()
    else:
        exc_type = "TypeError"
        msg = default_raise
    exc_name = "PyExc_" + exc_type
    b.emit("        PyErr_SetString(" + exc_name + ', "{}");'.format(_escape_c_str(msg)))
    b.emit("        return NULL;")


# ---------------------------------------------------------------------------
# _wrapper function (arg parsing, buffer acquire, cleanup)
# ---------------------------------------------------------------------------


# ---- Buffer and wrapper helpers ----
def _collect_void_ptr_names(func):
    """Return set of scalar param names that map to C void* in any overload."""
    if func is None:
        return set()
    scalar_names = set(p.name for p in func.py_params if p.pytype == "int")
    result = set()
    for ol in func.overloads:
        if ol.variants:
            entries = [(v.params, ol.map_exprs) for v in ol.variants]
        else:
            entries = [(ol.params, ol.map_exprs)]
        for params, map_exprs in entries:
            for cp in params:
                if cp.is_pointer and cp.base_type == "void":
                    expr = map_exprs.get(cp.name)
                    if expr is not None and isinstance(expr, Var) and expr.name in scalar_names:
                        result.add(expr.name)
    return result


# ---- Buffer and wrapper helpers ----
def _emit_wrapper_locals(b, buf_params, scalar_params, func, timing=False):
    """Emit local variable declarations shared by both wrappers."""
    void_ptr_names = _collect_void_ptr_names(func)
    for p in buf_params:
        b.emit("    PyObject *py_" + p.name + " = NULL;")
    for p in scalar_params:
        default_val = p.default
        if p.pytype == "int":
            if p.name in void_ptr_names:
                if default_val is None:
                    b.emit("    intptr_t c_%s = 0;" % p.name)
                else:
                    b.emit("    intptr_t c_%s = %ld;" % (p.name, int(default_val)))
            else:
                if default_val is None:
                    b.emit("    int c_%s = 0;" % p.name)
                else:
                    b.emit("    int c_%s = %d;" % (p.name, int(default_val)))
        else:
            if default_val is None:
                b.emit("    double c_%s = 0.0;" % p.name)
            else:
                b.emit("    double c_%s = %s;" % (p.name, _float_literal(default_val)))

    for p in buf_params:
        b.declare_buffer("info_" + p.name)

    b.emit("    PyObject *ret = NULL;")

    if timing:
        b.emit("    int _c2py_do_time = _c2py_timing_enabled;")
        b.emit("    uint64_t _c2py_t0 = 0, _c2py_t1 = 0, _c2py_t2 = 0;")
        b.emit("    if (_c2py_do_time) _c2py_t0 = c2py_ticks();")

    b.emit("")


# ---------------------------------------------------------------------------
# Expression transpiler: AST -> C code string
# ---------------------------------------------------------------------------


# ---- Buffer and wrapper helpers ----
def _emit_wrapper_body(b, func, buf_params, scalar_params, name, timing=False):
    """Emit the shared wrapper body: buffer init, acquire, checks, impl call, cleanup."""
    perf_name = "_perf_" + name

    # Zero-initialize buffer pins (size varies by runtime: CPython 80/96, PyPy ~660)
    for p in buf_params:
        b.emit_buf_memset("info_" + p.name)
    b.emit("")

    # Acquire buffers (first: return NULL on failure, subsequent: goto cleanup)
    for i, p in enumerate(buf_params):
        flags = _get_buf_flags(p, func)
        want_write = "PyBUF_WRITABLE" in flags
        write_val = "C2PY_BUF_WRITE" if want_write else "C2PY_BUF_READ"
        b.acquire_buffer("info_" + p.name, "py_" + p.name, write_val, name)
        b.emit("")

    # Restrict checks
    b.emit_restrict_checks(buf_params, func)

    # Call impl (with timing ticks around it)
    impl_args = []
    for p in buf_params:
        impl_args.append("&info_" + p.name)
    for p in scalar_params:
        impl_args.append("c_" + p.name)

    if timing:
        b.emit("    if (_c2py_do_time) _c2py_t1 = c2py_ticks();")
    b.emit("    ret = _{0}_impl({1});".format(name, ", ".join(impl_args)))
    if timing:
        b.emit("    if (_c2py_do_time) _c2py_t2 = c2py_ticks();")
    b.emit("")

    # Cleanup
    b.enter_cleanup()

    if timing:
        b.emit("")
        b.emit("    if (_c2py_do_time) {")
        b.emit("        c2py_perf_record(&{0}, _c2py_t0, _c2py_t1, _c2py_t2, c2py_ticks());".format(perf_name))
        b.emit("    }")

    b.emit("    return ret;")


# ---- Buffer and wrapper helpers ----
def _emit_varargs_wrapper(b, func, buf_params, scalar_params, timing):
    """Emit the METH_VARARGS wrapper (Python 2.7 through 3.11)."""
    name = func.name
    all_params = func.py_params

    b.emit("static PyObject*")
    b.emit("_" + name + "_wrapper(PyObject *self, PyObject *args)")
    b.emit("{")

    # Local variables
    _emit_wrapper_locals(b, buf_params, scalar_params, func, timing)

    # Arg parse via PyArg_ParseTuple
    fmt_str = _build_parse_format(all_params, func)
    parse_args = ["args", '"' + fmt_str + '"']
    for p in all_params:
        if p.pytype == "buffer":
            parse_args.append("&py_" + p.name)
        elif p.pytype == "int":
            parse_args.append("&c_" + p.name)
        else:
            parse_args.append("&c_" + p.name)
    b.emit("    if (!PyArg_ParseTuple({}))".format(", ".join(parse_args)))
    b.emit("        return NULL;")
    b.emit("")

    # Shared body: buffer init, acquire, checks, impl, cleanup
    _emit_wrapper_body(b, func, buf_params, scalar_params, name, timing)

    b.emit("}")
    b.emit("")


# ---- Buffer and wrapper helpers ----
def _emit_fastcall_wrapper(b, func, buf_params, scalar_params, timing):
    """Emit the METH_FASTCALL wrapper (Python >= 3.12)."""
    name = func.name
    all_params = func.py_params

    b.emit("static PyObject*")
    b.emit("_" + name + "_fastcall(PyObject *self, PyObject *const *args, Py_ssize_t nargs)")
    b.emit("{")

    # Local variables
    _emit_wrapper_locals(b, buf_params, scalar_params, func, timing)

    # Arg count check (handle optional params with defaults)
    total = len(all_params)
    min_req = sum(1 for p in all_params if p.default is None)
    if min_req == total:
        b.emit("    if (nargs != {0}) {{".format(total))
        b.emit("        PyErr_SetString(PyExc_TypeError,")
        b.emit('            "{0} expects {1} argument{2}");'.format(name, total, "s" if total != 1 else ""))
        b.emit("        return NULL;")
        b.emit("    }")
    else:
        b.emit("    if (nargs < {0} || nargs > {1}) {{".format(min_req, total))
        b.emit("        PyErr_SetString(PyExc_TypeError,")
        b.emit('            "{0} expects {1} to {2} arguments");'.format(name, min_req, total))
        b.emit("        return NULL;")
        b.emit("    }")
    b.emit("")

    # Extract args directly from the array (only up to nargs)
    void_ptr_names = _collect_void_ptr_names(func)
    idx = 0
    for p in all_params:
        is_optional = p.default is not None
        if p.pytype == "buffer":
            b.emit("    py_{0} = args[{1}];".format(p.name, idx))
        elif p.pytype == "int":
            b.emit(
                "    /* extract int: {0} from args[{1}]{2} */".format(p.name, idx, " (optional)" if is_optional else "")
            )
            if is_optional:
                b.emit("    if (nargs > {0}) {{".format(idx))
            else:
                b.emit("    {")
            if p.name in void_ptr_names:
                b.emit("        long long _c2py_tmp = PyLong_AsLongLong(args[{0}]);".format(idx))
                b.emit("        if (_c2py_tmp == -1 && PyErr_Occurred()) return NULL;")
                b.emit("        c_{0} = (intptr_t)_c2py_tmp;".format(p.name))
            else:
                b.emit("        long _c2py_tmp = PyLong_AsLong(args[{0}]);".format(idx))
                b.emit("        if (_c2py_tmp == -1 && PyErr_Occurred()) return NULL;")
                b.emit("        if (_c2py_tmp < (long)INT_MIN || _c2py_tmp > (long)INT_MAX) {{".format())
                b.emit("            PyErr_SetString(PyExc_ValueError,")
                b.emit('                "int parameter {0} out of range (must fit in C int)");'.format(p.name))
                b.emit("            return NULL;")
                b.emit("        }")
                b.emit("        c_{0} = (int)_c2py_tmp;".format(p.name))
            b.emit("    }")
        else:
            b.emit(
                "    /* extract float: {0} from args[{1}]{2} */".format(
                    p.name, idx, " (optional)" if is_optional else ""
                )
            )
            if is_optional:
                b.emit("    if (nargs > {0}) {{".format(idx))
            else:
                b.emit("    {")
            b.emit("        double _c2py_tmp = PyFloat_AsDouble(args[{0}]);".format(idx))
            b.emit("        if (_c2py_tmp == -1.0 && PyErr_Occurred()) return NULL;")
            b.emit("        c_{0} = _c2py_tmp;".format(p.name))
            b.emit("    }")
        idx += 1

    b.emit("")

    # Shared body: buffer init, acquire, checks, impl, cleanup
    _emit_wrapper_body(b, func, buf_params, scalar_params, name, timing)

    b.emit("}")
    b.emit("")


# ---- Docstring generation ----
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

    outputs = getattr(ol, "outputs", {}) or {}
    if outputs:
        out_strs = sorted("{} ({})".format(k, v) for k, v in outputs.items())
        lines.append(indent + "Outputs: " + ", ".join(out_strs))

    return lines


# ---- Docstring generation ----
def _derive_param_info(param_name, checks, overloads):
    """Auto-derive parameter description info from checks and overloads.
    Returns a list of description strings (one per line)."""
    info = []

    # Derive format types from function-level checks and overload when conditions
    fmt_chars = set()
    for chk in checks:
        if isinstance(chk, Compare) and chk.op == "==":
            for side, other in [(chk.left, chk.right), (chk.right, chk.left)]:
                if (
                    isinstance(side, Attr)
                    and side.attr == "format"
                    and _expr_refers_to(side.obj, param_name)
                    and isinstance(other, StrLit)
                    and len(other.value) == 1
                ):
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
                    if cp.is_pointer and not cp.is_const and _expr_refers_to(ol.map_exprs.get(cp.name), param_name):
                        writable = True
                        break
        else:
            for cp in ol.params:
                if cp.is_pointer and not cp.is_const and _expr_refers_to(ol.map_exprs.get(cp.name), param_name):
                    writable = True
                    break

    if writable:
        info.append("Writable")

    # Derive dimensionality and size relationships from checks
    for chk in checks:
        if isinstance(chk, Compare):
            left, right, op = chk.left, chk.right, chk.op
            if (
                isinstance(left, Attr)
                and left.attr == "ndim"
                and _expr_refers_to(left.obj, param_name)
                and op == "=="
                and isinstance(right, IntLit)
            ):
                info.append("Shape: {}D".format(right.value))
            elif (
                isinstance(left, Attr)
                and left.attr == "n"
                and _expr_refers_to(left.obj, param_name)
                and op in ("==", ">=", ">", "<=", "<")
                and isinstance(right, Attr)
                and right.attr == "n"
            ):
                other_name = _expr_to_source(right.obj)
                if other_name:
                    info.append("Size {} {}".format("must equal" if op == "==" else op, other_name))
            elif (
                isinstance(left, Subscript)
                and isinstance(left.obj, Attr)
                and left.obj.attr == "shape"
                and _expr_refers_to(left.obj.obj, param_name)
                and isinstance(right, IntLit)
                and op == "=="
            ):
                info.append("Axis {}: {} elements".format(left.index, right.value))

    return info


# ---- Module support ----
def _emit_constants(b, mod):
    """Emit PyObject_SetAttrString calls for module-level integer constants,
    timing perf struct pointers (deprecated raw attrs + new _c2py_ attrs),
    and GIL release flags."""
    has_gil = any(f.gil_release for f in mod.functions)
    if not mod.constants and not mod.timing and not has_gil:
        return
    if mod.constants:
        for cname, cvalue in sorted(mod.constants.items()):
            b.emit('        PyObject_SetAttrString(module, "{}",'.format(_escape_c_str(cname)))
            b.emit("            PyLong_FromLong({}));".format(cvalue))
    if mod.timing:
        b.emit('        PyObject_SetAttrString(module, "_c2py_cycle_counter_frequency",')
        b.emit("            PyLong_FromUnsignedLongLong(c2py_cycle_counter_frequency_hz));")
        for func in mod.functions:
            b.emit('        PyObject_SetAttrString(module, "_c2py_perf_ptr_{0}",'.format(func.name))
            b.emit("            PyLong_FromVoidPtr(&_perf_{0}));".format(func.name))
            for ol in func.overloads:
                if ol.variants:
                    b.emit('        PyObject_SetAttrString(module, "_c2py_active_ptr_{0}",'.format(func.name))
                    b.emit("            PyLong_FromVoidPtr((void*)&_active_perf_{0}));".format(func.name))
                    for v in ol.variants:
                        c_name = v.c_name if v.c_name is not None else v.sig_str.split("(")[0].strip().split()[-1]
                        perf_name = "_perf_{0}__{1}".format(func.name, c_name)
                        b.emit(
                            '        PyObject_SetAttrString(module, "_c2py_ol_ptr_{0}__{1}",'.format(func.name, c_name)
                        )
                        b.emit("            PyLong_FromVoidPtr(&{}));".format(perf_name))
                else:
                    c_name = ol.c_name if ol.c_name is not None else ol.sig_str.split("(")[0].strip().split()[-1]
                    perf_name = "_perf_{0}__{1}".format(func.name, c_name)
                    b.emit('        PyObject_SetAttrString(module, "_c2py_ol_ptr_{0}__{1}",'.format(func.name, c_name))
                    b.emit("            PyLong_FromVoidPtr(&{}));".format(perf_name))
    if has_gil:
        b.emit('        PyObject_SetAttrString(module, "_c2py_gil_release_enabled",')
        b.emit("            PyLong_FromVoidPtr(&_c2py_gil_release_enabled));")
        for func in mod.functions:
            if func.gil_release:
                b.emit('        PyObject_SetAttrString(module, "_c2py_gil_release_{0}",'.format(func.name))
                b.emit("            PyLong_FromVoidPtr(&_gil_release_{0}));".format(func.name))


# ---- Module support ----
def _emit_perf_accessors(b):
    """Emit Python-callable C functions: _c2py_perf_read, _c2py_perf_meta,
    _c2py_perf_reset, _c2py_perf_get_enabled, _c2py_perf_set_enabled."""
    b.emit("/* ---- Perf accessor functions (no ctypes needed) ---- */")
    b.emit("")
    b.emit("/* Fill a uint64 array with perf fields from the given pointer. */")
    b.emit("static PyObject*")
    b.emit("_c2py_perf_read(PyObject *self, PyObject *args) {")
    b.emit("    unsigned long long ptr_val;")
    b.emit("    PyObject *buf_obj;")
    b.emit("    c2py_buf_pin pin;")
    b.emit("    Py_buffer *buf = &pin.buf;")
    b.emit("    (void)self;")
    b.emit("    memset(&pin.buf, 0, C2PY.pybuffer_size);")
    b.emit('    if (!PyArg_ParseTuple(args, "KO", &ptr_val, &buf_obj))')
    b.emit("        return NULL;")
    b.emit("    if (PyObject_GetBuffer(buf_obj, buf, PyBUF_SIMPLE) != 0)")
    b.emit("        return NULL;")
    b.emit("    if (buf->len < (Py_ssize_t)(11 * sizeof(uint64_t))) {")
    b.emit("        PyBuffer_Release(buf);")
    b.emit("        PyErr_SetString(PyExc_ValueError,")
    b.emit('            "buffer too small for perf data (need 11 uint64)");')
    b.emit("        return NULL;")
    b.emit("    }")
    b.emit("    c2py_perf_extract_u64((c2py_perf_t*)(uintptr_t)ptr_val,")
    b.emit("                           (uint64_t*)buf->buf);")
    b.emit("    PyBuffer_Release(buf);")
    b.emit("    Py_RETURN_NONE;")
    b.emit("}")
    b.emit("")
    b.emit("/* Return (variant, group_idx, variant_name=None) metadata tuple. */")
    b.emit("static PyObject*")
    b.emit("_c2py_perf_meta(PyObject *self, PyObject *args) {")
    b.emit("    unsigned long long ptr_val;")
    b.emit("    c2py_perf_t *p;")
    b.emit("    PyObject *tuple;")
    b.emit("    (void)self;")
    b.emit('    if (!PyArg_ParseTuple(args, "K", &ptr_val))')
    b.emit("        return NULL;")
    b.emit("    p = (c2py_perf_t*)(uintptr_t)ptr_val;")
    b.emit("    tuple = PyTuple_New(3);")
    b.emit("    if (!tuple) return NULL;")
    b.emit("    /* Extract to locals: nested p->variant inside PyLong_FromLong")
    b.emit("     * fails on PyPy cpyext (calling-convention issue). */")
    b.emit("    {")
    b.emit("        int _v = p->variant;")
    b.emit("        int _gi = p->group_idx;")
    b.emit("        PyTuple_SetItem(tuple, 0, PyLong_FromLong((long)_v));")
    b.emit("        PyTuple_SetItem(tuple, 1, PyLong_FromLong((long)_gi));")
    b.emit("    }")
    b.emit("    /* variant_name is diagnostic-only; return None to avoid")
    b.emit("     * Python string/unicode API.  Callers can use _variants_<name>()")
    b.emit("     * to map variant indices to names (returned as bytes). */")
    b.emit("    Py_INCREF(C2PY.none_obj);")
    b.emit("    PyTuple_SetItem(tuple, 2, C2PY.none_obj);")
    b.emit("    return tuple;")
    b.emit("}")
    b.emit("")
    b.emit("/* Reset a perf counter to initial state. */")
    b.emit("static PyObject*")
    b.emit("_c2py_perf_reset(PyObject *self, PyObject *args) {")
    b.emit("    unsigned long long ptr_val;")
    b.emit("    (void)self;")
    b.emit('    if (!PyArg_ParseTuple(args, "K", &ptr_val))')
    b.emit("        return NULL;")
    b.emit("    c2py_perf_reset((c2py_perf_t*)(uintptr_t)ptr_val);")
    b.emit("    Py_RETURN_NONE;")
    b.emit("}")
    b.emit("")
    b.emit("/* Read timing enabled flag (0 or 1). */")
    b.emit("static PyObject*")
    b.emit("_c2py_perf_get_enabled(PyObject *self, PyObject *args) {")
    b.emit("    (void)self;")
    b.emit('    if (!PyArg_ParseTuple(args, ""))')
    b.emit("        return NULL;")
    b.emit("    return PyLong_FromLong((long)_c2py_timing_enabled);")
    b.emit("}")
    b.emit("")
    b.emit("/* Set timing enabled flag. */")
    b.emit("static PyObject*")
    b.emit("_c2py_perf_set_enabled(PyObject *self, PyObject *args) {")
    b.emit("    int val;")
    b.emit("    (void)self;")
    b.emit('    if (!PyArg_ParseTuple(args, "i", &val))')
    b.emit("        return NULL;")
    b.emit("    _c2py_timing_enabled = val;")
    b.emit("    Py_RETURN_NONE;")
    b.emit("}")
    b.emit("")


# ---- Module support ----
def _emit_timing_decls(b, mod):
    """Emit global timing declarations: enabled flag, perf structs, tick API,
    perf accessor functions (read, meta, reset)."""
    b.emit("/* ---- Performance timing ---- */")
    b.emit("static int _c2py_timing_enabled = 1;")
    b.emit("")
    for func in mod.functions:
        b.emit("static c2py_perf_t _perf_{0};".format(func.name))
        for ol in func.overloads:
            if ol.variants:
                for v in ol.variants:
                    c_name = v.c_name if v.c_name is not None else v.sig_str.split("(")[0].strip().split()[-1]
                    b.emit("static c2py_perf_t _perf_{0}__{1};".format(func.name, c_name))
            else:
                c_name = ol.c_name if ol.c_name is not None else ol.sig_str.split("(")[0].strip().split()[-1]
                b.emit("static c2py_perf_t _perf_{0}__{1};".format(func.name, c_name))
    # Active-overload pointers (updated by resolve for variant groups)
    has_any_variants = any(any(ol.variants for ol in f.overloads) for f in mod.functions)
    if has_any_variants:
        for func in mod.functions:
            has_variants = any(ol.variants for ol in func.overloads)
            if has_variants:
                b.emit("static c2py_perf_t * _active_perf_{0} = &_perf_{0};".format(func.name))
    b.emit("")
    b.emit("/* Python-callable: return tick source frequency in Hz */")
    b.emit("static PyObject*")
    b.emit("__c2py_tick_frequency(PyObject *self, PyObject *args) {")
    b.emit("    (void)self;")
    b.emit('    if (!PyArg_ParseTuple(args, ""))')
    b.emit("        return NULL;")
    b.emit("    return PyLong_FromUnsignedLongLong(c2py_tick_frequency());")
    b.emit("}")
    b.emit("")
    b.emit("/* Python-callable: convert ticks to nanoseconds at given frequency */")
    b.emit("static PyObject*")
    b.emit("__c2py_ticks_to_ns(PyObject *self, PyObject *args) {")
    b.emit("    unsigned long long ticks, freq_hz;")
    b.emit("    (void)self;")
    b.emit('    if (!PyArg_ParseTuple(args, "KK", &ticks, &freq_hz))')
    b.emit("        return NULL;")
    b.emit("    return PyLong_FromUnsignedLongLong(")
    b.emit("        c2py_ticks_to_ns((uint64_t)ticks, (uint64_t)freq_hz));")
    b.emit("}")
    b.emit("")
    b.emit('/* Python-callable: select tick source ("clock" or "cycle").')
    b.emit(" * Returns (old_freq_hz, new_freq_hz) tuple. */")
    b.emit("static PyObject*")
    b.emit("__c2py_set_tick_source(PyObject *self, PyObject *args) {")
    b.emit("    const char *source = NULL;")
    b.emit("    (void)self;")
    b.emit('    if (!PyArg_ParseTuple(args, "s", &source))')
    b.emit("        return NULL;")
    b.emit("")
    b.emit("    uint64_t old_freq = c2py_tick_frequency_hz;")
    b.emit("    uint64_t new_freq;")
    b.emit("    int new_mode;")
    b.emit("")
    b.emit('    if (source != NULL && strcmp(source, "cycle") == 0) {')
    b.emit("        new_mode = 1;")
    b.emit("        new_freq = c2py_cycle_counter_frequency_hz;")
    b.emit("        if (new_freq == 0) {")
    b.emit("            PyErr_SetString(PyExc_RuntimeError,")
    b.emit('                "cycle counter frequency not detected on this platform");')
    b.emit("            return NULL;")
    b.emit("        }")
    b.emit("    } else {")
    b.emit("        new_mode = 0;")
    b.emit("        new_freq = 1000000000ULL;")
    b.emit("    }")
    b.emit("")
    b.emit("    _c2py_use_cycle_counter = new_mode;")
    b.emit("    c2py_tick_frequency_hz = new_freq;")
    b.emit("")
    b.emit("    PyObject *tup = PyTuple_New(2);")
    b.emit("    if (tup == NULL) return NULL;")
    b.emit("    PyTuple_SetItem(tup, 0, PyLong_FromUnsignedLongLong(old_freq));")
    b.emit("    PyTuple_SetItem(tup, 1, PyLong_FromUnsignedLongLong(new_freq));")
    b.emit("    return tup;")
    b.emit("}")
    b.emit("")
    # Perf accessor functions
    _emit_perf_accessors(b)


# ---- Docstring generation ----
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


# ---- Docstring generation ----
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
    has_overloads = func.overloads and any(ol.sig_str or ol.variants for ol in func.overloads)
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
                    v_out = getattr(v, "outputs", {}) or {}
                    if v_out:
                        out_strs = sorted("{} ({})".format(k, ctype) for k, ctype in v_out.items())
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
