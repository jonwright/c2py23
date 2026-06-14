"""Parser for .c2py interface definition files.

Handles:
  - YAML loading (via PyYAML)
  - C function signature parsing
  - Expression parsing (for 'when' conditions and 'map' substitutions)
  - Building the ModuleDef data model
"""
from __future__ import print_function

import re
import yaml
from collections import namedtuple

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

class COverload(namedtuple('COverload', ['sig_str', 'params', 'return_type', 'map_exprs', 'when_expr'])):
    pass

class FuncDef(namedtuple('FuncDef', ['name', 'py_params', 'return_type', 'checks', 'overloads', 'default_raise', 'doc'])):
    pass

class ModuleDef(namedtuple('ModuleDef', ['name', 'sources', 'headers', 'functions', 'constants'])):
    """constants is a dict of {name: int_value} for module-level integer constants."""
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
    if isinstance(sources, str):
        sources = [sources]
    headers = raw.get('headers', [])
    if isinstance(headers, str):
        headers = [headers]

    funcs = []
    for f in raw.get('functions', []):
        funcs.append(_parse_func(f, path))

    constants = raw.get('constants', {})
    if not isinstance(constants, dict):
        raise ValueError("'constants' must be a dict in {}".format(path))
    for k, v in constants.items():
        if not isinstance(v, int):
            raise ValueError("Constant '{}' in {} must be an integer, got {}".format(k, path, type(v)))

    return ModuleDef(module_name, sources, headers, funcs, constants)


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
# Function-level parsing
# ---------------------------------------------------------------------------

def _parse_func(raw, path):
    py_sig_str = _get_required(raw, 'py_sig', path)
    name, py_params, ret_type = _parse_py_sig(py_sig_str, path)

    checks = [parse_expr(c) for c in raw.get('checks', [])]

    overloads = []
    for ol in raw.get('c_overloads', []):
        sig_str = _get_required(ol, 'sig', path)
        c_name, c_params, c_ret = _parse_c_sig(sig_str, path)
        map_raw = _get_required(ol, 'map', path)
        map_exprs = {}
        for cname, expr_str in map_raw.items():
            map_exprs[cname] = parse_expr(expr_str)
        when_expr = parse_expr(ol.get('when'))
        overloads.append(COverload(sig_str, c_params, c_ret, map_exprs, when_expr))

    default_raise = raw.get('default_raise')
    doc = raw.get('doc')

    return FuncDef(name, py_params, ret_type, checks, overloads, default_raise, doc)
