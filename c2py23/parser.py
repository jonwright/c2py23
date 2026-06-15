"""Parser for .c2py interface definition files.

Handles:
  - YAML loading (via PyYAML)
  - C function signature parsing
  - Expression parsing (for 'when' conditions and 'map' substitutions)
  - Building the ModuleDef data model
"""
from __future__ import print_function

import os
import re
import sys
import warnings
import yaml
from collections import namedtuple

# Python 2/3 compat: str covers bytes+unicode on 2.x, text on 3.x
if sys.version_info[0] >= 3:
    _STRING_TYPES = (str,)
else:
    _STRING_TYPES = (str, unicode)  # noqa: F821

# ---------------------------------------------------------------------------
# AST nodes for expressions in 'when' and 'map'
# ---------------------------------------------------------------------------

class Var(namedtuple('Var', ['name'])):
    pass

class Attr(namedtuple('Attr', ['obj', 'attr'])):
    pass

class Subscript(namedtuple('Subscript', ['obj', 'index'])):
    pass

class IntLit(namedtuple('IntLit', ['value'])):
    pass

class StrLit(namedtuple('StrLit', ['value'])):
    pass

class Compare(namedtuple('Compare', ['left', 'op', 'right'])):
    pass

class BinOp(namedtuple('BinOp', ['left', 'op', 'right'])):
    pass

class UnaryOp(namedtuple('UnaryOp', ['op', 'operand'])):
    pass

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class PyParam(namedtuple('PyParam', ['name', 'pytype', 'default'])):
    """pytype is one of 'buffer', 'int', 'float'. default is None for
    required params, or a numeric value for optional int/float params."""
    pass

class CParam(namedtuple('CParam', ['name', 'ctype', 'base_type', 'is_const', 'is_pointer'])):
    """ctype is the full C type string, base_type is the element type"""
    pass

class COverload(namedtuple('_COverload', ['sig_str', 'params', 'return_type', 'map_exprs', 'when_expr'])):
    """A C function overload alternative with optional outputs dict for scalar outputs.
    
    outputs maps C parameter names to ctypes types (e.g. {'minval': 'double', 'maxval': 'float'}).
    Output params are auto-allocated as 1-element arrays and returned as tuple values.
    """
    def __new__(cls, sig_str, params, return_type, map_exprs, when_expr, outputs=None):
        self = super(COverload, cls).__new__(cls, sig_str, params, return_type, map_exprs, when_expr)
        self.outputs = outputs or {}
        return self

class FuncDef(namedtuple('FuncDef', ['name', 'py_params', 'return_type', 'checks', 'overloads', 'default_raise', 'doc'])):
    pass

class ModuleDef(namedtuple('ModuleDef', ['name', 'sources', 'headers', 'functions', 'constants', 'timing'])):
    """constants is a dict of {name: int_value} for module-level integer constants.
       timing is a bool enabling per-function performance profiling."""
    pass

# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_c2py(path):
    """Load and parse a .c2py YAML file, returning a ModuleDef."""
    with open(path, 'r') as f:
        raw = yaml.safe_load(f)

    module_name = _get_required(raw, 'module', path)
    sources = raw.get('source', [])
    if isinstance(sources, _STRING_TYPES):
        sources = [sources]
    headers = raw.get('headers', [])
    if isinstance(headers, _STRING_TYPES):
        headers = [headers]

    funcs = []
    for f in raw.get('functions', []):
        funcs.extend(_expand_func_template(f, path))

    constants = raw.get('constants', {})
    if not isinstance(constants, dict):
        raise ValueError("'constants' must be a dict in {}".format(path))
    for k, v in constants.items():
        if not isinstance(v, int):
            raise ValueError("Constant '{}' in {} must be an integer, got {}".format(k, path, type(v)))

    timing = bool(raw.get('timing', False))

    mod = ModuleDef(module_name, sources, headers, funcs, constants, timing)

    base_dir = os.path.dirname(os.path.abspath(path))
    _validate_module(mod, base_dir)

    return mod


def _get_required(d, key, path):
    if key not in d:
        raise ValueError("Missing required field '{}' in {}".format(key, path))
    return d[key]

# ---------------------------------------------------------------------------
# Python signature parser: "name(arg: type, ...) -> ret"
# ---------------------------------------------------------------------------

_PY_SIG_RE = re.compile(
    r'^\s*'
    r'(?P<name>\w+)\s*'
    r'\(\s*(?P<params>[^)]*?)\s*\)'
    r'\s*(?:->\s*(?P<ret>\w+))?\s*$'
)

_PYTYPE_MAP = {'buffer': 'buffer', 'int': 'int', 'float': 'float'}

_PY_PARAM_RE = re.compile(
    r'^(\w+)\s*:\s*(buffer|int|float)\s*(?:=\s*(-?\d+\.?\d*))?\s*$'
)

def _parse_py_sig(sig_str, path):
    m = _PY_SIG_RE.match(sig_str)
    if not m:
        raise ValueError("Invalid python signature '{}' in {}".format(sig_str, path))
    name = m.group('name')
    params_str = m.group('params')
    ret = m.group('ret') or 'void'

    params = []
    seen_optional = False
    if params_str.strip():
        for part in params_str.split(','):
            part = part.strip()
            if not part:
                continue
            pm = _PY_PARAM_RE.match(part)
            if not pm:
                raise ValueError("Invalid param '{}' in signature '{}'".format(part, sig_str))
            pname = pm.group(1)
            ptype = pm.group(2)
            default_str = pm.group(3)

            if ptype not in _PYTYPE_MAP:
                raise ValueError("Unknown param type '{}' in signature '{}'".format(ptype, sig_str))
            pytype = _PYTYPE_MAP[ptype]

            if default_str is not None:
                if pytype == 'buffer':
                    raise ValueError(
                        "Buffer param '{}' cannot have a default value in '{}'".format(pname, sig_str))
                if pytype == 'int':
                    default = int(default_str)
                else:
                    default = float(default_str)
                seen_optional = True
            else:
                default = None
                if seen_optional:
                    raise ValueError(
                        "Required param '{}' cannot follow optional params in '{}'".format(pname, sig_str))

            params.append(PyParam(pname, pytype, default))
    return name, params, ret

# ---------------------------------------------------------------------------
# C signature parser
#
# Formats supported:
#   "name(...)"                         -> void return
#   "name(...) -> ret"                  -> explicit return
#   "ret name(...)"                     -> C-style return type
#   "ret name(...) -> ret"              -> both (-> overrides)
# ---------------------------------------------------------------------------

_C_TYPES_INT = (
    'int8_t', 'uint8_t', 'int16_t', 'uint16_t',
    'int32_t', 'uint32_t', 'int64_t', 'uint64_t',
    'int', 'float', 'double', 'char', 'void'
)
_C_TYPES = set(_C_TYPES_INT)

# Tokens in param lists: CONST, TYPE, STAR, NAME, COMMA, LPAREN, RPAREN
_C_PARAM_RE = re.compile(
    r'\s*(?:const\s+)?(' + '|'.join(_C_TYPES_INT) + r')\s*\*?\s*(\w+)\s*'
)

def _parse_c_sig(sig_str, path):
    sig_str = sig_str.strip()

    # Extract name + param list
    # Find '(' and the matching ')'
    paren_start = sig_str.find('(')
    if paren_start == -1:
        raise ValueError("Missing '(' in C signature '{}' in {}".format(sig_str, path))

    # The part before '(' contains [return_type] name
    before = sig_str[:paren_start].strip()
    after_paren = sig_str[sig_str.rfind(')') + 1:].strip()

    # Find matching paren for nested parens (unlikely but be safe)
    depth = 0
    paren_end = paren_start
    for i in range(paren_start, len(sig_str)):
        if sig_str[i] == '(':
            depth += 1
        elif sig_str[i] == ')':
            depth -= 1
            if depth == 0:
                paren_end = i
                break

    params_str = sig_str[paren_start + 1:paren_end]

    # Parse return type from suffix
    return_type = None  # None means void (none returned)
    remaining_after = sig_str[paren_end + 1:].strip()
    if remaining_after.startswith('->'):
        ret_part = remaining_after[2:].strip()
        if ret_part in _C_TYPES:
            return_type = ret_part
        else:
            raise ValueError("Unknown return type '{}' in {}".format(ret_part, sig_str))

    # Parse [return_type] name from before parens
    before_parts = before.split()
    if len(before_parts) == 1:
        name = before_parts[0]
        if return_type is None:
            return_type = 'void'
    elif len(before_parts) == 2 and before_parts[0] in _C_TYPES:
        if return_type is None:
            return_type = before_parts[0]
        name = before_parts[1]
    else:
        raise ValueError("Cannot parse C signature '{}' in {}".format(sig_str, path))

    # Parse params
    params = _parse_c_params(params_str)

    return name, params, return_type


def _parse_c_params(params_str):
    params = []
    if not params_str.strip():
        return params

    for part in params_str.split(','):
        part = part.strip()
        if not part:
            continue
        m = _C_PARAM_RE.match(part)
        if not m:
            raise ValueError("Cannot parse C param '{}'".format(part))
        base_type = m.group(1)
        name = m.group(2)
        is_const = 'const' in part
        is_pointer = '*' in part
        if is_pointer:
            ctype = ('const ' if is_const else '') + base_type + ' *'
        else:
            ctype = base_type
        params.append(CParam(name, ctype, base_type, is_const, is_pointer))
    return params

# ---------------------------------------------------------------------------
# Expression parser
#
# Grammar:
#   expr     := or_expr
#   or_expr  := and_expr ('or' and_expr)*
#   and_expr := not_expr ('and' not_expr)*
#   not_expr := 'not' not_expr | compare
#   compare  := term (cmp_op term)?
#   cmp_op   := '==' | '!=' | '<' | '>' | '<=' | '>='
#   term     := primary ('.' name)* ('[' INTEGER ']')*
#   primary  := NAME | INTEGER | STRING_LIT | '(' expr ')'
# ---------------------------------------------------------------------------

_CMP_OPS = {'==', '!=', '<', '>', '<=', '>='}

class _ExprParser(object):
    def __init__(self, s):
        self.s = s
        self.pos = 0
        self.n = len(s)

    def _skip_ws(self):
        while self.pos < self.n and self.s[self.pos] in ' \t':
            self.pos += 1

    def _peek(self):
        self._skip_ws()
        if self.pos >= self.n:
            return None
        return self.s[self.pos]

    def _consume(self):
        self._skip_ws()
        if self.pos >= self.n:
            return None
        ch = self.s[self.pos]
        self.pos += 1
        return ch

    def parse(self):
        self.pos = 0
        result = self._parse_or()
        self._skip_ws()
        if self.pos < self.n:
            raise ValueError("Unexpected trailing characters '{}' in expression '{}'".format(
                self.s[self.pos:], self.s))
        return result

    def _parse_or(self):
        left = self._parse_and()
        while True:
            self._skip_ws()
            if self._match_word('or'):
                right = self._parse_and()
                left = BinOp(left, 'or', right)
            else:
                break
        return left

    def _parse_and(self):
        left = self._parse_not()
        while True:
            self._skip_ws()
            if self._match_word('and'):
                right = self._parse_not()
                left = BinOp(left, 'and', right)
            else:
                break
        return left

    def _parse_not(self):
        self._skip_ws()
        if self._match_word('not'):
            operand = self._parse_not()
            return UnaryOp('not', operand)
        return self._parse_compare()

    def _parse_compare(self):
        left = self._parse_term()
        self._skip_ws()
        pos = self.pos
        # Try to match a comparison operator
        if pos + 1 < self.n and self.s[pos:pos + 2] in _CMP_OPS:
            op = self.s[pos:pos + 2]
            self.pos = pos + 2
        elif pos < self.n and self.s[pos] in ('=', '!', '<', '>'):
            op = self.s[pos]
            self.pos = pos + 1
            # Check if followed by =
            if self.pos < self.n and self.s[self.pos] == '=':
                op += '='
                self.pos += 1
            if op not in _CMP_OPS:
                raise ValueError("Unknown comparison operator '{}'".format(op))
        else:
            return left
        right = self._parse_term()
        return Compare(left, op, right)

    def _parse_term(self):
        node = self._parse_primary()
        while True:
            self._skip_ws()
            if self.pos < self.n and self.s[self.pos] == '.':
                self.pos += 1
                name = self._parse_name()
                node = Attr(node, name)
            elif self.pos < self.n and self.s[self.pos] == '[':
                self.pos += 1
                idx = self._parse_integer()
                self._skip_ws()
                if self.pos >= self.n or self.s[self.pos] != ']':
                    raise ValueError("Expected ']'")
                self.pos += 1
                node = Subscript(node, idx)
            else:
                break
        return node

    def _parse_primary(self):
        self._skip_ws()
        ch = self._peek()
        if ch is None:
            raise ValueError("Unexpected end of expression")
        if ch == '(':
            self.pos += 1
            node = self._parse_or()
            self._skip_ws()
            if self.pos >= self.n or self.s[self.pos] != ')':
                raise ValueError("Expected ')'")
            self.pos += 1
            return node
        if ch == "'" or ch == '"':
            return StrLit(self._parse_string())
        if ch.isdigit():
            return IntLit(self._parse_integer())
        if ch.isalpha() or ch == '_':
            return Var(self._parse_name())
        raise ValueError("Unexpected character '{}' in expression".format(ch))

    def _match_word(self, word):
        self._skip_ws()
        if self.pos + len(word) <= self.n and self.s[self.pos:self.pos + len(word)] == word:
            # Check word boundary
            end = self.pos + len(word)
            if end == self.n or not self.s[end].isalnum() and self.s[end] != '_':
                self.pos = end
                return True
        return False

    def _parse_name(self):
        self._skip_ws()
        start = self.pos
        while self.pos < self.n and (self.s[self.pos].isalnum() or self.s[self.pos] == '_'):
            self.pos += 1
        if start == self.pos:
            raise ValueError("Expected identifier")
        return self.s[start:self.pos]

    def _parse_integer(self):
        self._skip_ws()
        start = self.pos
        while self.pos < self.n and self.s[self.pos].isdigit():
            self.pos += 1
        if start == self.pos:
            raise ValueError("Expected integer")
        return int(self.s[start:self.pos])

    def _parse_string(self):
        quote = self.s[self.pos]
        self.pos += 1
        start = self.pos
        while self.pos < self.n and self.s[self.pos] != quote:
            if self.s[self.pos] == '\\':
                self.pos += 2
            else:
                self.pos += 1
        if self.pos >= self.n:
            raise ValueError("Unterminated string")
        val = self.s[start:self.pos]
        self.pos += 1
        return val


def parse_expr(s):
    """Parse an expression string, returning an AST node."""
    if s is None:
        return None
    return _ExprParser(s).parse()

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Template expansion (P9)
# ---------------------------------------------------------------------------

def _strsubst(obj, vars_map):
    """Recursively substitute ${VAR} patterns in strings within obj.

    Walks dicts, lists, and strings. Returns a deep copy with substitutions.
    vars_map is {varname: replacement_value} for a single expansion step.
    """
    if isinstance(obj, dict):
        return {k: _strsubst(v, vars_map) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strsubst(item, vars_map) for item in obj]
    if isinstance(obj, _STRING_TYPES):
        s = obj
        for var, val in vars_map.items():
            s = s.replace('${' + var + '}', val)
        return s
    return obj


def _expand_func_template(raw_func, path):
    """Expand a function definition with template variable substitution.

    If raw_func has an 'expand:' key, the dict must map variable names
    to lists of values of equal length. The function definition is
    expanded N times with ${VAR} substitutions applied to all strings.
    Returns a list of parsed FuncDef objects.

    If no 'expand:' key, returns [parsed_func] as before.
    """
    expand = raw_func.get('expand')
    if expand is None:
        return [_parse_func(raw_func, path)]

    if not isinstance(expand, dict):
        raise ValueError(
            "'expand' must be a dict mapping var names to lists in {}".format(path))

    lengths = set()
    for var, vals in expand.items():
        if not isinstance(vals, list):
            raise ValueError(
                "expand value for '{}' must be a list in {}".format(var, path))
        lengths.add(len(vals))

    if len(lengths) != 1:
        raise ValueError(
            "All expand value lists must have the same length in {}".format(path))

    n = lengths.pop()
    if n == 0:
        return []

    results = []
    for i in range(n):
        vars_map = {var: vals[i] for var, vals in expand.items()}
        expanded = _strsubst(raw_func, vars_map)
        results.append(_parse_func(expanded, path))
    return results


# Function-level parsing
# ---------------------------------------------------------------------------

def _coerce_expr_value(val, context, path):
    """Coerce a non-string YAML value to string for expression parsing.
    
    YAML parses bare integers/floats as their native types, but the expression
    parser expects strings. Map values like `verbose: 0` would crash otherwise.
    """
    if isinstance(val, _STRING_TYPES):
        return val
    if isinstance(val, (int, float)):
        warnings.warn(
            "%s value '%s: %s' in %s is %s; auto-coercing to str. "
            "Quote YAML values: \"%s\"" % (
                context, val, type(val).__name__, path, val, val))
        return str(val)
    raise ValueError(
        "Expected string or number for %s value in %s, got %s" % (
            context, path, type(val).__name__))


def _parse_func(raw, path):
    py_sig_str = _get_required(raw, 'py_sig', path)
    name, py_params, ret_type = _parse_py_sig(py_sig_str, path)

    checks = [_parse_check_value(c, path) for c in raw.get('checks', [])]

    overloads = []
    for ol in raw.get('c_overloads', []):
        sig_str = _get_required(ol, 'sig', path)
        c_name, c_params, c_ret = _parse_c_sig(sig_str, path)
        map_raw = _get_required(ol, 'map', path)
        map_exprs = {}
        for cname, expr_str in map_raw.items():
            expr_str = _coerce_expr_value(expr_str, 'map', path)
            map_exprs[cname] = parse_expr(expr_str)
        when_raw = ol.get('when')
        if when_raw is not None:
            when_raw = _coerce_expr_value(when_raw, 'when', path)
        when_expr = parse_expr(when_raw)
        outputs = ol.get('outputs', {})
        if outputs and not isinstance(outputs, dict):
            raise ValueError("'outputs' must be a dict in {}".format(path))
        overloads.append(COverload(sig_str, c_params, c_ret, map_exprs, when_expr, outputs))

    default_raise = raw.get('default_raise')
    doc = raw.get('doc')

    return FuncDef(name, py_params, ret_type, checks, overloads, default_raise, doc)


def _parse_check_value(val, path):
    """Parse a check expression, coercing non-string values from YAML."""
    val = _coerce_expr_value(val, 'checks', path)
    return parse_expr(val)


# ---------------------------------------------------------------------------
# Validation: parameter counts, format-to-ctype mapping
# ---------------------------------------------------------------------------

_FORMAT_TO_CTYPE = {
    'b': 'int8_t',
    'B': 'uint8_t',
    'h': 'int16_t',
    'H': 'uint16_t',
    'i': 'int32_t',
    'I': 'uint32_t',
    'l': 'int',
    'L': 'unsigned int',
    'q': 'int64_t',
    'Q': 'uint64_t',
    'f': 'float',
    'd': 'double',
}

_FUNC_DECL_RE = re.compile(
    r'(?:^|;|\})\s*'
    r'(?:static\s+)?(?:inline\s+)?(?:extern\s+)?'
    r'([\w\s*]+?)\s*'           # return type
    r'(\w+)\s*'                 # function name
    r'\(\s*((?:[^()]|\([^)]*\))*?)\s*\)'  # params (allow one level of nesting)
    r'\s*[{;]',
    re.MULTILINE | re.DOTALL
)


def _strip_c_comments(text):
    """Strip C-style comments (both /* */ and //) from source text."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        if i + 1 < n and text[i] == '/' and text[i + 1] == '/':
            i += 2
            while i < n and text[i] != '\n':
                i += 1
        elif i + 1 < n and text[i] == '/' and text[i + 1] == '*':
            i += 2
            while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def _count_c_params(params_str):
    """Count the number of parameters in a C function parameter string."""
    if not params_str.strip():
        return 0
    count = 1
    for ch in params_str:
        if ch == ',':
            count += 1
    return count


def _parse_c_func_from_files(file_list, base_dir):
    """Parse C source/header files to extract function signatures.

    Returns a dict of {func_name: param_count} for all functions found.
    """
    funcs = {}
    for fname in file_list:
        fpath = os.path.join(base_dir, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, 'r') as f:
            content = f.read()
        content = _strip_c_comments(content)
        for m in _FUNC_DECL_RE.finditer(content):
            ret_type = m.group(1).strip()
            func_name = m.group(2)
            params_str = m.group(3)
            if not ret_type:
                continue
            ret_parts = ret_type.split()
            is_typedef = all(p in _C_TYPES_INT or p in ('const', 'static',
                                'inline', 'extern') or p == '*' for p in ret_parts)
            if not is_typedef:
                continue
            count = _count_c_params(params_str)
            funcs[func_name] = count
    return funcs


def _find_format_check(checks):
    """Extract format check info: {(buf_name, format_char)} from check expressions."""
    results = set()
    for check in checks:
        if isinstance(check, Compare) and check.op == '==':
            left = check.left
            right = check.right
            if isinstance(left, Attr) and left.attr == 'format':
                if isinstance(right, StrLit) and len(right.value) == 1:
                    buf_name = _resolve_buf_name(left.obj)
                    if buf_name:
                        results.add((buf_name, right.value))
            elif isinstance(right, Attr) and right.attr == 'format':
                if isinstance(left, StrLit) and len(left.value) == 1:
                    buf_name = _resolve_buf_name(right.obj)
                    if buf_name:
                        results.add((buf_name, left.value))
    return results


def _resolve_buf_name(expr):
    """Resolve a Var or Attr chain to a buffer name string."""
    if isinstance(expr, Var):
        return expr.name
    if isinstance(expr, Attr):
        return _resolve_buf_name(expr.obj)
    return None


def _validate_module(mod, base_dir):
    """Run validation checks on a parsed ModuleDef.

    Checks:
      1. P0: Parameter count mismatch between .c2py C sig and actual C source
      2. P4: Buffer format checks vs C pointer types in overloads
    """
    all_files = list(mod.sources) + list(mod.headers)
    if not all_files:
        return

    c_funcs = _parse_c_func_from_files(all_files, base_dir)

    for func in mod.functions:
        for ol in func.overloads:
            c_name = _extract_c_name(ol.sig_str)
            c2py_count = len(ol.params)
            actual_count = c_funcs.get(c_name)

            if actual_count is not None and c2py_count != actual_count:
                raise ValueError(
                    "P0: param count mismatch for '%s' in %s: "
                    ".c2py sig has %d params, C source has %d params" % (
                        c_name, mod.name, c2py_count, actual_count))

        # P4: format checks -> C type validation
        fmt_checks = _find_format_check(func.checks)
        if not fmt_checks:
            continue

        for buf_name, fmt_char in fmt_checks:
            expected_ctype = _FORMAT_TO_CTYPE.get(fmt_char)
            if expected_ctype is None:
                continue

            for ol in func.overloads:
                for cp in ol.params:
                    if not cp.is_pointer:
                        continue
                    expr = ol.map_exprs.get(cp.name)
                    if expr is None:
                        continue
                    if not _expr_refers_to(expr, buf_name):
                        continue
                    if cp.base_type != expected_ctype:
                        raise ValueError(
                            "P4: format check '%s.format == '%s'' implies %s*, "
                            "but overload '%s' uses %s* for param '%s' in %s" % (
                                buf_name, fmt_char, expected_ctype,
                                c_name, cp.base_type, cp.name, mod.name))


def _extract_c_name(sig_str):
    """Extract the C function name from a sig string."""
    return sig_str.split('(')[0].strip().split()[-1]


def _expr_refers_to(expr, buf_name):
    """Check if an expression refers to a specific buffer param name."""
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
    return False
