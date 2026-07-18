"""Parser for .c2py interface definition files.

Handles:
  - Python dict format (native, no dependency)
  - YAML loading (via PyYAML)
  - C function signature parsing
  - Expression parsing (for 'when' conditions and 'map' substitutions)
  - Building the ModuleDef data model

The entry point is `load_c2py(path)` which auto-detects the input format
(Python dict or YAML).  For programmatic use, `from_c2py_dict(raw_dict, path)`
accepts a Python dict directly.
"""

from __future__ import print_function

import ast
import os
import re
import sys
import warnings
from collections import namedtuple

try:
    import yaml as _yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# Python 2/3 compat: str covers bytes+unicode on 2.x, text on 3.x
if sys.version_info[0] >= 3:
    _STRING_TYPES = (str,)
else:
    _STRING_TYPES = (str, unicode)  # noqa: F821

# ---------------------------------------------------------------------------
# 7-bit ASCII validation
# ---------------------------------------------------------------------------


def _check_ascii(value, label, path):
    """Validate a string contains only 7-bit ASCII characters.
    Raises ValueError if non-ASCII bytes are found or if value is not a string.
    """
    if not isinstance(value, _STRING_TYPES):
        raise ValueError("Expected a string for '%s' in %s, got %s" % (label, path, type(value).__name__))
    for ch in value:
        if ord(ch) > 127:
            raise ValueError("Non-ASCII character %r in %s at %s: %s" % (ch, label, path, value[:80]))
    return value


# ---------------------------------------------------------------------------
# AST nodes for expressions in 'when' and 'map'
# ---------------------------------------------------------------------------


class Var(namedtuple("Var", ["name"])):
    pass


class Attr(namedtuple("Attr", ["obj", "attr"])):
    pass


class Subscript(namedtuple("Subscript", ["obj", "index"])):
    pass


class IntLit(namedtuple("IntLit", ["value"])):
    pass


class FloatLit(namedtuple("FloatLit", ["value"])):
    pass


class StrLit(namedtuple("StrLit", ["value"])):
    pass


class Compare(namedtuple("Compare", ["left", "op", "right"])):
    pass


class BinOp(namedtuple("BinOp", ["left", "op", "right"])):
    pass


class UnaryOp(namedtuple("UnaryOp", ["op", "operand"])):
    pass


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class PyParam(namedtuple("PyParam", ["name", "pytype", "default"])):
    """pytype is one of 'buffer', 'int', 'float'. default is None for
    required params, or a numeric value for optional int/float params."""

    pass


class CParam(namedtuple("CParam", ["name", "ctype", "base_type", "is_const", "is_pointer", "array_dims"])):
    """ctype is the full C type string, base_type is the element type.
    array_dims is a list of dimension values (strings or None for [])
    from C array notation like gv[][3] (-> [None, '3']).
    None means the parameter was declared with plain * pointer notation."""

    def __new__(cls, name, ctype, base_type, is_const, is_pointer, array_dims=None):
        return super(CParam, cls).__new__(cls, name, ctype, base_type, is_const, is_pointer, array_dims)


class COverload(
    namedtuple(
        "_COverload",
        [
            "sig_str",
            "params",
            "return_type",
            "map_exprs",
            "when_expr",
            "name",
            "group_name",
            "variants",
            "c_name",
        ],
    )
):
    """A C function overload alternative or a dispatch group.

    For flat overloads (backward compatible):
        sig_str, params, return_type, map_exprs, when_expr are populated.
        name is optional (required if when_expr is static for rebind support).
        variants is None.
        c_name is the extracted C function name (no re-parsing needed).

    For grouped dispatch:
        variants is a non-empty list of CVariant.
        sig_str, params, return_type are None.
        map_exprs is the shared argument map for all variants in the group.
        when_expr is the per-call group condition (e.g. data.format == 'f').
        group_name is an optional label (for rebind qualifiers, docstrings).
        c_name is None (variants carry their own c_name).

    outputs maps C parameter names to ctypes types (e.g. {'minval': 'double'}).
    Output params are auto-allocated as 1-element arrays and returned in the tuple.

    doc is an optional per-overload or per-group description string.
    """

    def __new__(
        cls,
        sig_str,
        params,
        return_type,
        map_exprs,
        when_expr,
        name=None,
        group_name=None,
        variants=None,
        outputs=None,
        doc=None,
        c_name=None,
    ):
        self = super(COverload, cls).__new__(
            cls,
            sig_str,
            params,
            return_type,
            map_exprs,
            when_expr,
            name,
            group_name,
            variants,
            c_name,
        )
        self.outputs = outputs or {}
        self.doc = doc
        return self


class CVariant(
    namedtuple(
        "CVariant",
        ["name", "sig_str", "params", "return_type", "when_expr", "outputs", "c_name"],
    )
):
    """A variant within a dispatch group. Inherits map_exprs from the parent group.

    name is required for rebind, docstring, and timing identification.
    when_expr is the static (CPU feature) dispatch condition, or None for default.
    outputs is an optional dict for scalar output parameters (same format as COverload).
    doc is an optional per-variant description string.
    c_name is the extracted C function name (no re-parsing needed).
    default is True if the variant should be auto-selected at init.
      Set default: false to make the variant reachable only via _rebind_<name>().
    """

    def __new__(
        cls,
        name,
        sig_str,
        params,
        return_type,
        when_expr,
        outputs=None,
        doc=None,
        c_name=None,
        default=True,
    ):
        self = super(CVariant, cls).__new__(cls, name, sig_str, params, return_type, when_expr, outputs, c_name)
        self.doc = doc
        self.default = default
        return self


class FuncDef(
    namedtuple(
        "FuncDef",
        [
            "name",
            "py_params",
            "return_type",
            "checks",
            "overloads",
            "default_raise",
            "doc",
            "gil_release",
        ],
    )
):
    """A wrapped Python function definition.

    params is an optional dict mapping parameter names to human-readable
    descriptions, parsed from the YAML block. Keys are validated against
    py_sig parameter names.
    """

    def __new__(
        cls,
        name,
        py_params,
        return_type,
        checks,
        overloads,
        default_raise,
        doc,
        gil_release,
        params=None,
        acquire=None,
    ):
        self = super(FuncDef, cls).__new__(
            cls,
            name,
            py_params,
            return_type,
            checks,
            overloads,
            default_raise,
            doc,
            gil_release,
        )
        self.params = params or {}
        self.acquire = acquire
        return self


class ModuleDef(
    namedtuple(
        "ModuleDef",
        [
            "name",
            "sources",
            "headers",
            "functions",
            "constants",
            "timing",
            "free_threading",
        ],
    )
):
    """constants is a dict of {name: int_value} for module-level integer constants.
    timing is a bool enabling per-function performance profiling.
    free_threading is a bool; when true, the module declares Py_MOD_GIL_NOT_USED
    on free-threaded Python builds (prevents GIL re-enablement)."""

    pass


# ---------------------------------------------------------------------------
# Loading (Python dict or YAML)
# ---------------------------------------------------------------------------


def from_c2py_dict(raw_dict, path="<dict>"):
    """Parse a Python dict (from Python dict format or YAML) into a ModuleDef.

    Args:
        raw_dict: A dict with keys: module, source, headers, functions,
                  constants, timing, free_threading.
        path: A label for error messages (file path or "<dict>").

    Returns:
        A ModuleDef namedtuple.
    """
    module_name = _get_required(raw_dict, "module", path)
    sources = raw_dict.get("source", [])
    if isinstance(sources, _STRING_TYPES):
        sources = [sources]
    headers = raw_dict.get("headers", [])
    if isinstance(headers, _STRING_TYPES):
        headers = [headers]

    funcs = []
    for f in raw_dict.get("functions", []):
        funcs.extend(_expand_func_template(f, path))

    constants = raw_dict.get("constants", {})
    if not isinstance(constants, dict):
        raise ValueError("'constants' must be a dict in {}".format(path))
    for k, v in constants.items():
        if not isinstance(v, int):
            raise ValueError("Constant '{}' in {} must be an integer, got {}".format(k, path, type(v)))

    timing = bool(raw_dict.get("timing", False))
    free_threading = bool(raw_dict.get("free_threading", False))

    mod = ModuleDef(module_name, sources, headers, funcs, constants, timing, free_threading)
    return mod


def load_c2py(path):
    """Load and parse an interface definition, returning a ModuleDef.

    Supports three formats, auto-detected:
      1. C source (.c, .h): C2PY_BEGIN..C2PY_END blocks embedded in
         comments (parsed via c2py23.harvester, no dependencies).
      2. Python dict (.c2py or .c2py.py): a file containing a Python
         dict literal (parsed via ast.literal_eval, no PyYAML needed).
         Lines starting with '#' are stripped as comments.
      3. YAML (.c2py): standard YAML format (requires PyYAML).

    For .c and .h files, interface definitions are embedded as:
        /* C2PY_BEGIN
        module: mymod
        source: [mymod.c]
        functions: ...
        C2PY_END */
    """
    # C source files -- extract C2PY_BEGIN blocks via harvester
    if path.endswith(".c") or path.endswith(".h"):
        from c2py23.harvester import extract_from_file

        raw = extract_from_file(path)
        if not isinstance(raw, dict) or "module" not in raw:
            raise ValueError("No C2PY_BEGIN block with 'module' key found in {}".format(path))
        mod = from_c2py_dict(raw, path)
        base_dir = os.path.dirname(os.path.abspath(path))
        _validate_module(mod, base_dir)
        return mod

    with open(path, "r") as f:
        text = f.read()

    # Try Python dict format first (safe, no dependencies).
    # Strip whole-line comments (#) before passing to literal_eval.
    try:
        stripped = re.sub(r"(?m)^\s*#.*$", "", text)
        raw = ast.literal_eval(stripped)
        if isinstance(raw, dict):
            mod = from_c2py_dict(raw, path)
            base_dir = os.path.dirname(os.path.abspath(path))
            _validate_module(mod, base_dir)
            return mod
    except (ValueError, SyntaxError):
        pass

    # Fall back to YAML
    if not _HAS_YAML:
        raise ImportError(
            "Could not parse '{}' as a Python dict and PyYAML is not installed.\n"
            "Install PyYAML with: pip install PyYAML\n"
            "Or use the Python dict format (see docs/specification.md).".format(path)
        )

    raw = _yaml.safe_load(text)
    mod = from_c2py_dict(raw, path)
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

_PY_SIG_RE = re.compile(r"^\s*" r"(?P<name>\w+)\s*" r"\(\s*(?P<params>[^)]*?)\s*\)" r"\s*(?:->\s*(?P<ret>\w+))?\s*$")

_PYTYPE_MAP = {"buffer": "buffer", "int": "int", "float": "float"}

_PY_PARAM_RE = re.compile(r"^(\w+)\s*:\s*(buffer|int|float)\s*(?:=\s*(-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))?\s*$")


def _parse_py_sig(sig_str, path):
    m = _PY_SIG_RE.match(sig_str)
    if not m:
        raise ValueError("Invalid python signature '{}' in {}".format(sig_str, path))
    name = m.group("name")
    params_str = m.group("params")
    ret = m.group("ret") or "void"
    if ret not in ("void", "int", "float"):
        raise ValueError(
            "Invalid return type '{}' in signature '{}'; " "expected void, int, or float".format(ret, sig_str)
        )

    params = []
    seen_optional = False
    if params_str.strip():
        for part in params_str.split(","):
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
                if pytype == "buffer":
                    raise ValueError("Buffer param '{}' cannot have a default value in '{}'".format(pname, sig_str))
                if pytype == "int":
                    if not re.match(r"^-?\d+$", default_str):
                        raise ValueError(
                            "Integer param '{}' default '{}' is not a valid integer "
                            "in '{}'".format(pname, default_str, sig_str)
                        )
                    default = int(default_str)
                else:
                    default = float(default_str)
                seen_optional = True
            else:
                default = None
                if seen_optional:
                    raise ValueError("Required param '{}' cannot follow optional params in '{}'".format(pname, sig_str))

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
    "int8_t",
    "uint8_t",
    "int16_t",
    "uint16_t",
    "int32_t",
    "uint32_t",
    "int64_t",
    "uint64_t",
    "intptr_t",  # signed pointer-width: matches Py_ssize_t on 64-bit
    "ptrdiff_t",  # signed pointer-width: stddef.h type (C99)
    "size_t",  # unsigned pointer-width
    "int",
    "float",
    "double",
    "char",
    "void",
    "_Bool",
)
_C_TYPES = set(_C_TYPES_INT)

# Tokens in param lists: CONST, TYPE, STAR, NAME, COMMA, LPAREN, RPAREN
_C_PARAM_RE = re.compile(r"\s*(?:const\s+)?(" + "|".join(_C_TYPES_INT) + r")\s*\*?\s*(\w+)\s*$")


def _parse_c_sig(sig_str, path):
    sig_str = sig_str.strip()

    # Extract name + param list
    # Find '(' and the matching ')'
    paren_start = sig_str.find("(")
    if paren_start == -1:
        raise ValueError("Missing '(' in C signature '{}' in {}".format(sig_str, path))

    # The part before '(' contains [return_type] name
    before = sig_str[:paren_start].strip()

    # Find matching paren for nested parens (unlikely but be safe)
    depth = 0
    paren_end = paren_start
    for i in range(paren_start, len(sig_str)):
        if sig_str[i] == "(":
            depth += 1
        elif sig_str[i] == ")":
            depth -= 1
            if depth == 0:
                paren_end = i
                break

    params_str = sig_str[paren_start + 1 : paren_end]

    if depth != 0:
        raise ValueError("Unmatched '(' in C signature '{}' in {}".format(sig_str, path))

    # Parse return type from suffix
    return_type = None  # None means void (none returned)
    remaining_after = sig_str[paren_end + 1 :].strip()
    if remaining_after.startswith("->"):
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
            return_type = "void"
    elif len(before_parts) == 2 and before_parts[0] in _C_TYPES:
        if return_type is None:
            return_type = before_parts[0]
        name = before_parts[1]
    elif len(before_parts) == 2:
        raise ValueError(
            "Unsupported return type '{}' in '{}' in {}. "
            "Supported: void, int, float, double.".format(before_parts[0], sig_str, path)
        )
    elif len(before_parts) > 2:
        raise ValueError(
            "Unsupported multi-word return type in '{}' in {}. "
            "Use a typedef or single-word type.".format(sig_str, path)
        )
    else:
        raise ValueError("Cannot parse C signature '{}' in {}".format(sig_str, path))

    # Validate return type: generator only supports void, int, float, double
    _SUPPORTED_RETURN_TYPES = {"void", "int", "float", "double"}
    if return_type is not None and return_type not in _SUPPORTED_RETURN_TYPES:
        raise ValueError(
            "Unsupported return type '{}' in C signature '{}' in {}. "
            "Supported return types: void, int, float, double. "
            "Use outputs: for other types.".format(return_type, sig_str, path)
        )

    # Parse params
    params = _parse_c_params(params_str)

    return name, params, return_type


def _parse_c_params(params_str):
    params = []
    if not params_str.strip():
        return params

    for part in params_str.split(","):
        part = part.strip()
        if not part:
            continue
        # Extract array dimension suffixes like [3], [][3], [M][N][K]
        array_dims = []
        while part.endswith("]"):
            close = part.rfind("]")
            open_br = part.rfind("[", 0, close)
            if open_br == -1:
                raise ValueError("Cannot parse C param '{}': unmatched ']'".format(part))
            dim_str = part[open_br + 1 : close].strip()
            array_dims.insert(0, dim_str if dim_str else None)
            part = part[:open_br].strip()
        m = _C_PARAM_RE.match(part)
        if not m:
            raise ValueError("Cannot parse C param '{}'".format(part))
        base_type = m.group(1)
        name = m.group(2)
        is_const = "const" in part
        is_pointer = "*" in part or bool(array_dims)
        if array_dims:
            # Build ctype for casts: const double (*)[3] for [][3]
            inner_dims = array_dims[1:]  # first dim absorbed into pointer
            ctype = ("const " if is_const else "") + base_type
            if inner_dims:
                ctype += " (*)" + "".join("[" + d + "]" for d in inner_dims)
            else:
                ctype += " *"
        elif is_pointer:
            ctype = ("const " if is_const else "") + base_type + " *"
        else:
            ctype = base_type
        params.append(CParam(name, ctype, base_type, is_const, is_pointer, array_dims or None))
    return params


def _cparam_to_bufname(cp, map_exprs, py_params):
    """Map a C parameter name to its Python buffer name via map: expressions.

    For the common case `{gv: 'data.ptr'}`, C param `gv` maps to buffer `data`.
    Falls back to the C param name if no buffer mapping found.
    """
    if map_exprs is None:
        return cp.name
    expr = map_exprs.get(cp.name)
    if expr is None:
        return cp.name
    # Check for `buf_name.ptr` pattern
    if isinstance(expr, Attr) and expr.attr == "ptr" and isinstance(expr.obj, Var):
        for pp in py_params:
            if pp.name == expr.obj.name and pp.pytype == "buffer":
                return expr.obj.name
    return cp.name


def _derive_array_checks(param_name, array_dims):
    """Generate checks from array dimension notation in C sig.

    The generated checks enforce C-contiguous layout (slow_axis == 0),
    dimensionality (ndim), and per-dimension fixed sizes (shape[i] == N).
    C-contiguous layout is required because the C function uses native
    row-major array indexing (arr[i][j]) and c2py23 never copies data.

    Returns a list of check expression strings.

    Example: for param 'gv' with dims [None, 3]:
      -> ['gv.slow_axis == 0', 'gv.ndim == 2', 'gv.shape[1] == 3']
    """
    checks = []
    ndim = len(array_dims)

    # C-contiguous required for row-major array access
    checks.append("%s.slow_axis == 0" % param_name)

    # Dimensionality check
    if ndim > 1:
        checks.append("%s.ndim == %d" % (param_name, ndim))

    # Shape checks for each fixed dimension
    for i, dim in enumerate(array_dims):
        if dim is not None:
            checks.append("%s.shape[%d] == %s" % (param_name, i, dim))

    return checks


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

_CMP_OPS = {"==", "!=", "<", ">", "<=", ">="}


class _ExprParser(object):
    def __init__(self, s):
        self.s = s
        self.pos = 0
        self.n = len(s)

    def _skip_ws(self):
        while self.pos < self.n and self.s[self.pos] in " \t":
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
            raise ValueError(
                "Unexpected trailing characters '{}' in expression '{}'".format(self.s[self.pos :], self.s)
            )
        return result

    def _parse_or(self):
        left = self._parse_and()
        while True:
            self._skip_ws()
            if self._match_word("or"):
                right = self._parse_and()
                left = BinOp(left, "or", right)
            else:
                break
        return left

    def _parse_and(self):
        left = self._parse_not()
        while True:
            self._skip_ws()
            if self._match_word("and"):
                right = self._parse_not()
                left = BinOp(left, "and", right)
            else:
                break
        return left

    def _parse_not(self):
        self._skip_ws()
        if self._match_word("not"):
            operand = self._parse_not()
            return UnaryOp("not", operand)
        return self._parse_compare()

    def _parse_compare(self):
        left = self._parse_additive()
        self._skip_ws()
        pos = self.pos
        # Try to match a comparison operator
        if pos + 1 < self.n and self.s[pos : pos + 2] in _CMP_OPS:
            op = self.s[pos : pos + 2]
            self.pos = pos + 2
        elif pos < self.n and self.s[pos] in ("=", "!", "<", ">"):
            op = self.s[pos]
            self.pos = pos + 1
            # Check if followed by =
            if self.pos < self.n and self.s[self.pos] == "=":
                op += "="
                self.pos += 1
            if op not in _CMP_OPS:
                raise ValueError("Unknown comparison operator '{}'".format(op))
        else:
            return left
        right = self._parse_additive()
        return Compare(left, op, right)

    def _parse_additive(self):
        left = self._parse_multiplicative()
        while True:
            self._skip_ws()
            if self.pos < self.n and self.s[self.pos] in ("+", "-"):
                op = self.s[self.pos]
                self.pos += 1
                right = self._parse_multiplicative()
                left = BinOp(left, op, right)
            else:
                break
        return left

    def _parse_multiplicative(self):
        left = self._parse_unary()
        while True:
            self._skip_ws()
            if self.pos < self.n and self.s[self.pos] in ("*", "/", "%"):
                op = self.s[self.pos]
                self.pos += 1
                right = self._parse_unary()
                left = BinOp(left, op, right)
            else:
                break
        return left

    def _parse_unary(self):
        self._skip_ws()
        if self.pos < self.n and self.s[self.pos] in ("+", "-"):
            op = self.s[self.pos]
            self.pos += 1
            operand = self._parse_unary()
            return UnaryOp(op, operand)
        return self._parse_term()

    def _parse_term(self):
        node = self._parse_primary()
        while True:
            self._skip_ws()
            if self.pos < self.n and self.s[self.pos] == ".":
                self.pos += 1
                name = self._parse_name()
                node = Attr(node, name)
            elif self.pos < self.n and self.s[self.pos] == "[":
                self.pos += 1
                idx = self._parse_integer()
                self._skip_ws()
                if self.pos >= self.n or self.s[self.pos] != "]":
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
        if ch == "(":
            self.pos += 1
            node = self._parse_or()
            self._skip_ws()
            if self.pos >= self.n or self.s[self.pos] != ")":
                raise ValueError("Expected ')'")
            self.pos += 1
            return node
        if ch == "'" or ch == '"':
            return StrLit(self._parse_string())
        if ch.isdigit():
            return self._parse_number()
        if ch.isalpha() or ch == "_":
            return Var(self._parse_name())
        raise ValueError("Unexpected character '{}' in expression".format(ch))

    def _match_word(self, word):
        self._skip_ws()
        if self.pos + len(word) <= self.n and self.s[self.pos : self.pos + len(word)] == word:
            # Check word boundary
            end = self.pos + len(word)
            if end == self.n or not self.s[end].isalnum() and self.s[end] != "_":
                self.pos = end
                return True
        return False

    def _parse_name(self):
        self._skip_ws()
        start = self.pos
        while self.pos < self.n and (self.s[self.pos].isalnum() or self.s[self.pos] == "_"):
            self.pos += 1
        if start == self.pos:
            raise ValueError("Expected identifier")
        return self.s[start : self.pos]

    def _parse_number(self):
        """Parse an unsigned integer or float literal (no leading sign).

        Leading '-' is handled by _parse_unary(), which wraps the result
        in UnaryOp('-', ...).  The caller must not pass a negative literal
        directly to this method.
        """
        self._skip_ws()
        start = self.pos
        saw_dot = False
        saw_exp = False
        while self.pos < self.n:
            ch = self.s[self.pos]
            if ch.isdigit():
                self.pos += 1
                continue
            if ch == "." and not saw_dot and not saw_exp:
                saw_dot = True
                self.pos += 1
                continue
            if ch in ("e", "E") and not saw_exp:
                saw_exp = True
                self.pos += 1
                if self.pos < self.n and self.s[self.pos] in ("+", "-"):
                    self.pos += 1
                continue
            break
        if start == self.pos:
            raise ValueError("Expected number")
        s = self.s[start : self.pos]
        if saw_dot or saw_exp:
            return FloatLit(float(s))
        return IntLit(int(s))

    def _parse_integer(self):
        self._skip_ws()
        start = self.pos
        while self.pos < self.n and self.s[self.pos].isdigit():
            self.pos += 1
        if start == self.pos:
            raise ValueError("Expected integer")
        return int(self.s[start : self.pos])

    def _parse_string(self):
        quote = self.s[self.pos]
        self.pos += 1
        chars = []
        while self.pos < self.n and self.s[self.pos] != quote:
            if self.s[self.pos] == "\\":
                self.pos += 1
                if self.pos >= self.n:
                    raise ValueError("Unterminated string escape")
                esc = self.s[self.pos]
                if esc == "n":
                    chars.append("\n")
                elif esc == "t":
                    chars.append("\t")
                elif esc == "r":
                    chars.append("\r")
                elif esc == "0":
                    chars.append("\0")
                elif esc == "\\":
                    chars.append("\\")
                elif esc == quote:
                    chars.append(quote)
                else:
                    # Unknown escape: keep literal (\\ + char)
                    chars.append("\\")
                    chars.append(esc)
                self.pos += 1
            else:
                chars.append(self.s[self.pos])
                self.pos += 1
        if self.pos >= self.n:
            raise ValueError("Unterminated string")
        val = "".join(chars)
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
            s = s.replace("${" + var + "}", val)
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
    expand = raw_func.get("expand")
    if expand is None:
        return [_parse_func(raw_func, path)]

    if not isinstance(expand, dict):
        raise ValueError("'expand' must be a dict mapping var names to lists in {}".format(path))

    lengths = set()
    for var, vals in expand.items():
        if not isinstance(vals, list):
            raise ValueError("expand value for '{}' must be a list in {}".format(var, path))
        for v in vals:
            if not isinstance(v, _STRING_TYPES):
                raise ValueError(
                    "expand value '{}' for '{}' must be a string, "
                    "got {} in {}".format(v, var, type(v).__name__, path)
                )
        lengths.add(len(vals))

    if len(lengths) != 1:
        raise ValueError("All expand value lists must have the same length in {}".format(path))

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
            "{ctx} value in {path} is a bare {typ} ({val!r}); "
            'auto-coercing to string. Quote it: "{val}"'.format(ctx=context, path=path, typ=type(val).__name__, val=val)
        )
        return str(val)
    raise ValueError("Expected string or number for %s value in %s, got %s" % (context, path, type(val).__name__))


def _parse_func(raw, path):
    py_sig_str = _get_required(raw, "py_sig", path)
    name, py_params, ret_type = _parse_py_sig(py_sig_str, path)

    checks = [_parse_check_value(c, path) for c in raw.get("checks", [])]

    overloads = []
    for ol in raw.get("c_overloads", []):
        # --- Grouped dispatch (has 'variants:') ---
        if "variants" in ol:
            variants_raw = ol.get("variants", [])
            if not variants_raw:
                raise ValueError("'variants' must be a non-empty list in {}".format(path))
            if "sig" in ol:
                raise ValueError(
                    "Grouped overload cannot have 'sig'; use 'map:' and 'when:' at group level in {}".format(path)
                )

            # Group-level when: (per-call dynamic condition)
            when_raw = ol.get("when")
            if when_raw is not None:
                when_raw = _coerce_expr_value(when_raw, "when", path)
            group_when = parse_expr(when_raw)

            # Group-level map: (shared argument preparation)
            map_raw = _get_required(ol, "map", path)
            group_map = {}
            for cname, expr_str in map_raw.items():
                expr_str = _coerce_expr_value(expr_str, "map", path)
                group_map[cname] = parse_expr(expr_str)

            group_name = ol.get("group")

            # Parse variants
            variants = []
            for v in variants_raw:
                v_sig_str = _get_required(v, "sig", path)
                v_c_name, v_params, v_ret = _parse_c_sig(v_sig_str, path)
                v_name = v.get("name")
                if v_name is None:
                    v_name = v_c_name
                else:
                    _check_ascii(v_name, "variant.name", path)
                    if v_name != v_c_name:
                        raise ValueError(
                            "variant name '%s' does not match C function name "
                            "'%s' in %s.  Omit 'name' to auto-fill from sig, "
                            "or set them equal." % (v_name, v_c_name, path)
                        )
                v_when_raw = v.get("when")
                if v_when_raw is not None:
                    v_when_raw = _coerce_expr_value(v_when_raw, "when", path)
                v_when_expr = parse_expr(v_when_raw)
                v_outputs = v.get("outputs", {})
                if v_outputs and not isinstance(v_outputs, dict):
                    raise ValueError("'outputs' must be a dict in {}".format(path))
                v_doc = v.get("doc")
                if v_doc is not None:
                    v_doc = _check_ascii(v_doc, "variant.doc", path)
                v_default = v.get("default", True)
                if not isinstance(v_default, bool):
                    raise ValueError("'default' must be true or false in {}".format(path))
                variants.append(
                    CVariant(
                        v_name,
                        v_sig_str,
                        v_params,
                        v_ret,
                        v_when_expr,
                        v_outputs,
                        doc=v_doc,
                        c_name=v_c_name,
                        default=v_default,
                    )
                )

            ol_doc = ol.get("doc")
            if ol_doc is not None:
                ol_doc = _check_ascii(ol_doc, "overload.doc", path)
            overloads.append(
                COverload(
                    None,
                    None,
                    None,
                    group_map,
                    group_when,
                    group_name=group_name,
                    variants=variants,
                    doc=ol_doc,
                )
            )
        else:
            # --- Flat overload (backward compatible) ---
            sig_str = _get_required(ol, "sig", path)
            c_name, c_params, c_ret = _parse_c_sig(sig_str, path)
            map_raw = _get_required(ol, "map", path)
            map_exprs = {}
            for cname, expr_str in map_raw.items():
                expr_str = _coerce_expr_value(expr_str, "map", path)
                map_exprs[cname] = parse_expr(expr_str)
            when_raw = ol.get("when")
            if when_raw is not None:
                when_raw = _coerce_expr_value(when_raw, "when", path)
            when_expr = parse_expr(when_raw)
            outputs = ol.get("outputs", {})
            if outputs and not isinstance(outputs, dict):
                raise ValueError("'outputs' must be a dict in {}".format(path))
            oname = ol.get("name")
            if oname is not None and not isinstance(oname, _STRING_TYPES):
                oname = str(oname)
            ol_doc = ol.get("doc")
            if ol_doc is not None:
                ol_doc = _check_ascii(ol_doc, "overload.doc", path)
            overloads.append(
                COverload(
                    sig_str,
                    c_params,
                    c_ret,
                    map_exprs,
                    when_expr,
                    name=oname,
                    outputs=outputs,
                    doc=ol_doc,
                    c_name=c_name,
                )
            )

    default_raise = raw.get("default_raise")
    doc = raw.get("doc")
    if doc is not None:
        doc = _check_ascii(doc, "doc", path)
    gil_release = bool(raw.get("gil_release", False))

    # Acquisition backend order. Maps to C2PY_PIN_* constants.
    # Default: [ndarray, buffer]
    _ACQUIRE_MAP = {
        "ndarray": "C2PY_PIN_NDARRAY",
        "buffer": "C2PY_PIN_PEP3118",
        "dlpack": "C2PY_PIN_DLPACK",
    }
    acquire_raw = raw.get("acquire", ["ndarray", "buffer"])
    if not isinstance(acquire_raw, list):
        raise ValueError("acquire must be a list in {}".format(path))
    acquire = []
    for entry in acquire_raw:
        if entry not in _ACQUIRE_MAP:
            raise ValueError("Unknown acquire value '{}' in {} (expected: ndarray, buffer, dlpack)".format(entry, path))
        acquire.append(_ACQUIRE_MAP[entry])

    # Derive auto-checks from array dimension notation in overload signatures
    # Map C param names to buffer names via map: expressions
    # Pre-populate seen set with user-written check sources (dedup across
    # both auto-vs-auto and auto-vs-user).
    seen_auto = set()
    for c in checks:
        s = _expr_to_source(c)
        if s:
            seen_auto.add(s)

    def _add_auto_checks_from(cparams, map_exprs):
        for cp in cparams:
            if cp.array_dims:
                buf_name = _cparam_to_bufname(cp, map_exprs, py_params)
                for ac in _derive_array_checks(buf_name, cp.array_dims):
                    if ac not in seen_auto:
                        checks.append(_parse_check_value(ac, path))
                        seen_auto.add(ac)

    for ol in overloads:
        if ol.params is not None:
            _add_auto_checks_from(ol.params, ol.map_exprs)
        elif ol.variants is not None:
            for v in ol.variants:
                if v.params:
                    _add_auto_checks_from(v.params, ol.map_exprs)

    # Parse optional params: block (human-readable per-parameter descriptions)
    params = raw.get("params", {})
    if params:
        if not isinstance(params, dict):
            raise ValueError("'params' must be a dict in {}".format(path))
        py_param_names = set(p.name for p in py_params)
        for pname in params:
            if pname not in py_param_names:
                raise ValueError(
                    "Unknown param '{}' in params block of '{}' -- " "not in py_sig signature".format(pname, name)
                )
            pdesc = str(params[pname]) if not isinstance(params[pname], _STRING_TYPES) else params[pname]
            params[pname] = _check_ascii(pdesc, "params.{}".format(pname), path)

    return FuncDef(
        name,
        py_params,
        ret_type,
        checks,
        overloads,
        default_raise,
        doc,
        gil_release,
        params=params,
        acquire=acquire,
    )


def _parse_check_value(val, path):
    """Parse a check expression, coercing non-string values from YAML."""
    val = _coerce_expr_value(val, "checks", path)
    return parse_expr(val)


# ---------------------------------------------------------------------------
# Validation: parameter counts, format-to-ctype mapping
# ---------------------------------------------------------------------------

_FORMAT_TO_CTYPE = {
    "b": "int8_t",
    "B": "uint8_t",
    "h": "int16_t",
    "H": "uint16_t",
    "i": "int32_t",
    "I": "uint32_t",
    # 'l' and 'L' are platform-sized (PEP 3118): sizeof(long) differs
    # between LP64 (8) and LLP64 (4).  They are handled in _expr_to_c
    # with a runtime itemsize == sizeof(long) check.  See AGENTS.md.
    "q": "int64_t",
    "Q": "uint64_t",
    "f": "float",
    "d": "double",
    "?": "uint8_t",
}

_FORMAT_CHAR_TO_NAME = {
    "b": "int8",
    "B": "uint8",
    "h": "int16",
    "H": "uint16",
    "i": "int32",
    "I": "uint32",
    "q": "int64",
    "Q": "uint64",
    # 'l'/'L' are platform-sized, handled in _expr_to_c
    "f": "float32",
    "d": "float64",
    "c": "char",
    "?": "bool",
    "e": "half-float",
    "Z": "complex64",
    "z": "complex128",
}

_FUNC_DECL_RE = re.compile(
    r"(?:^|;|\})\s*"
    r"(?:static\s+)?(?:inline\s+)?(?:extern\s+)?"
    r"([\w\s*]+?)\s*"  # return type
    r"(\w+)\s*"  # function name
    r"\(\s*((?:[^()]|\([^)]*\))*?)\s*\)"  # params (allow one level of nesting)
    r"\s*[{;]",
    re.MULTILINE | re.DOTALL,
)


def _strip_c_comments(text):
    """Strip C-style comments (both /* */ and //) from source text."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        if i + 1 < n and text[i] == "/" and text[i + 1] == "/":
            i += 2
            while i < n and text[i] != "\n":
                i += 1
        elif i + 1 < n and text[i] == "/" and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def _count_c_params(params_str):
    """Count the number of parameters in a C function parameter string."""
    stripped = params_str.strip()
    if not stripped:
        return 0
    if stripped == "void":
        return 0
    count = 1
    for ch in stripped:
        if ch == ",":
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
        # Only parse C source/header files; skip .o and other binary files
        ext = os.path.splitext(fname)[1].lower()
        if ext not in (".c", ".h", ".i"):
            continue
        with open(fpath, "r") as f:
            content = f.read()
        content = _strip_c_comments(content)
        for m in _FUNC_DECL_RE.finditer(content):
            ret_type = m.group(1).strip()
            func_name = m.group(2)
            params_str = m.group(3)
            if not ret_type:
                continue
            ret_parts = ret_type.split()
            is_typedef = all(
                p in _C_TYPES_INT or p in ("const", "static", "inline", "extern") or p == "*" for p in ret_parts
            )
            if not is_typedef:
                continue
            count = _count_c_params(params_str)
            funcs[func_name] = count
    return funcs


def _find_format_check(checks):
    """Extract format check info: {(buf_name, format_char)} from check expressions."""
    results = set()
    for check in checks:
        if isinstance(check, Compare) and check.op == "==":
            left = check.left
            right = check.right
            if isinstance(left, Attr) and left.attr == "format":
                if isinstance(right, StrLit) and len(right.value) == 1:
                    buf_name = _resolve_buf_name(left.obj)
                    if buf_name:
                        results.add((buf_name, right.value))
            elif isinstance(right, Attr) and right.attr == "format":
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
            # Validate both flat and grouped overloads
            targets = []
            if ol.variants:
                for v in ol.variants:
                    targets.append((v.c_name, len(v.params), v))
            else:
                targets.append((ol.c_name, len(ol.params), ol))

            for c_name, c2py_count, entry in targets:
                actual_count = c_funcs.get(c_name)
                if actual_count is not None and c2py_count != actual_count:
                    raise ValueError(
                        "P0: param count mismatch for '%s' in %s: "
                        ".c2py sig has %d params, C source has %d params" % (c_name, mod.name, c2py_count, actual_count)
                    )

        # P4: format checks -> C type validation
        fmt_checks = _find_format_check(func.checks)
        if not fmt_checks:
            continue

        for buf_name, fmt_char in fmt_checks:
            expected_ctype = _FORMAT_TO_CTYPE.get(fmt_char)
            if expected_ctype is None:
                continue

            for ol in func.overloads:
                # For grouped overloads, validate each variant
                if ol.variants:
                    check_entries = [(v.params, v.sig_str, v.c_name) for v in ol.variants]
                else:
                    check_entries = [(ol.params, ol.sig_str, ol.c_name)]

                for use_params, use_sig_str, use_c_name in check_entries:
                    for cp in use_params:
                        if not cp.is_pointer:
                            continue
                        expr = ol.map_exprs.get(cp.name)
                        if expr is None:
                            continue
                        if not _expr_refers_to(expr, buf_name):
                            continue
                        if cp.base_type != expected_ctype:
                            c_name = use_c_name
                            # LP64 compat: bare 'int' == 'int32_t'
                            if (cp.base_type, expected_ctype) not in (
                                ("int", "int32_t"),
                                ("int32_t", "int"),
                                ("unsigned int", "uint32_t"),
                                ("uint32_t", "unsigned int"),
                            ):
                                raise ValueError(
                                    "P4: format check '%s.format == '%s'' implies %s*, "
                                    "but overload '%s' uses %s* for param '%s' in %s"
                                    % (
                                        buf_name,
                                        fmt_char,
                                        expected_ctype,
                                        c_name,
                                        cp.base_type,
                                        cp.name,
                                        mod.name,
                                    )
                                )


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
    elif isinstance(expr, UnaryOp):
        return _expr_refers_to(expr.operand, buf_name)
    return False


def _escape_c_str(s):
    """Escape a string for use in a C string literal."""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s


# ---- String and numeric formatting ----


def _is_ptr_expr(expr):
    """Check if expression is a .ptr access."""
    if isinstance(expr, Attr) and expr.attr == "ptr":
        return True
    return False


# ---- Expression transpilation ----


def _expr_is_count_or_len(expr):
    """Check if expression is a buffer .n (element count) or .len (byte length)."""
    if isinstance(expr, Attr) and expr.attr in ("n", "len"):
        return True
    return False


# ---- String and numeric formatting ----


def _is_simple_expr(expr):
    """Check if an expression is simple enough to inline in a format string."""
    if isinstance(expr, (Var, IntLit, FloatLit)):
        return True
    if isinstance(expr, Attr) and isinstance(expr.obj, Var):
        return True  # a.n, a.len, a.ndim etc.
    if isinstance(expr, UnaryOp):
        return False
    if isinstance(expr, BinOp):
        if expr.op in ("and", "or"):
            return _is_simple_expr(expr.left) and _is_simple_expr(expr.right)
        return False  # arithmetic is never simple
    return False


# ---- Check emission and diagnostics ----


def _expr_to_source(expr):
    """Convert an AST node back to its source form (for comments/error messages)."""
    if isinstance(expr, Var):
        return expr.name
    elif isinstance(expr, Attr):
        return _expr_to_source(expr.obj) + "." + expr.attr
    elif isinstance(expr, Subscript):
        return _expr_to_source(expr.obj) + "[" + str(expr.index) + "]"
    elif isinstance(expr, IntLit):
        return str(expr.value)
    elif isinstance(expr, FloatLit):
        return _float_literal(expr.value)
    elif isinstance(expr, StrLit):
        return "'" + expr.value + "'"
    elif isinstance(expr, Compare):
        return "{} {} {}".format(_expr_to_source(expr.left), expr.op, _expr_to_source(expr.right))
    elif isinstance(expr, BinOp):
        return "({} {} {})".format(_expr_to_source(expr.left), expr.op, _expr_to_source(expr.right))
    elif isinstance(expr, UnaryOp):
        return "{}({})".format(expr.op, _expr_to_source(expr.operand))
    else:
        return str(expr)


# ---------------------------------------------------------------------------
# Rich docstring generation
# ---------------------------------------------------------------------------


# ---- Expression transpilation ----


def _expr_to_c(expr, buf_params, scalar_params, current_ol):
    """Transpile an expression AST node to a C expression string."""
    if expr is None:
        return "1"  # No condition = always true

    if isinstance(expr, Var):
        name = expr.name
        # Is it a buffer param?
        for p in buf_params:
            if p.name == name:
                return "info_" + name
        # Is it a scalar param?
        for p in scalar_params:
            if p.name == name:
                return "c_" + name
        return name

    elif isinstance(expr, Attr):
        obj = _expr_to_c(expr.obj, buf_params, scalar_params, current_ol)
        attr = expr.attr
        if attr == "format":
            return obj + "->format"
        elif attr == "ndim":
            return obj + "->ndim"
        elif attr == "itemsize":
            return obj + "->itemsize"
        elif attr == "len":
            return obj + "->len"
        elif attr == "n":
            return "((" + obj + "->len == 0) ? 0 : (" + obj + "->len / " + obj + "->itemsize))"
        elif attr == "ptr":
            return obj + "->ptr"
        elif attr == "shape":
            return obj + "->shape"
        elif attr == "strides":
            return obj + "->strides"
        elif attr == "slow_axis":
            return "_c2py_slow_axis_" + obj
        elif attr == "fast_axis":
            return "_c2py_fast_axis_" + obj
        elif attr == "slow_dim":
            return "{0}->shape[_c2py_slow_axis_{0}]".format(obj)
        elif attr == "fast_dim":
            return "{0}->shape[_c2py_fast_axis_{0}]".format(obj)
        else:
            return obj + "->" + attr

    elif isinstance(expr, Subscript):
        obj = _expr_to_c(expr.obj, buf_params, scalar_params, current_ol)
        idx = expr.index
        return "{}[{}]".format(obj, idx)

    elif isinstance(expr, IntLit):
        return str(expr.value)

    elif isinstance(expr, FloatLit):
        return _float_literal(expr.value)

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
                if op == "==":
                    result = "(!{0} || {0}[strlen({0}) - 1] == '{1}')".format(fmt_expr, ch)
                elif op == "!=":
                    result = "({0} && {0}[strlen({0}) - 1] != '{1}')".format(fmt_expr, ch)
                # 'l'/'L' are platform-sized in PEP 3118: sizeof(long)
                # differs between LP64 (8) and LLP64 (4).  Add an
                # itemsize check so the same .c2py works on both.
                if ch in ("l", "L"):
                    buf_var = fmt_expr[:-8]  # strip '->format'
                    result = "({0} && {1}->itemsize == (Py_ssize_t)sizeof(long))".format(result, buf_var)
                return result
            if op == "==":
                return "strcmp({}, {}) == 0".format(left, right)
            elif op == "!=":
                return "strcmp({}, {}) != 0".format(left, right)
            else:
                raise ValueError("Unsupported comparison op '{}' for strings".format(op))
        # Both sides are format attributes: compare the last character
        # of each format string (handles endian prefixes like "<d", "=d").
        # Pointer comparison is wrong -- PyPy cpyext may allocate distinct
        # format strings with identical content.
        elif (
            isinstance(expr.left, Attr)
            and expr.left.attr == "format"
            and isinstance(expr.right, Attr)
            and expr.right.attr == "format"
        ):
            if op == "==":
                return "((!{0} && !{1}) || ({0} && {1} && " "{0}[strlen({0}) - 1] == {1}[strlen({1}) - 1]))".format(
                    left, right
                )
            elif op == "!=":
                return "({0} && {1} && " "{0}[strlen({0}) - 1] != {1}[strlen({1}) - 1])".format(left, right)
            else:
                raise ValueError("Unsupported comparison op '{}' for format attributes".format(op))
        else:
            return "({}) {} ({})".format(left, op, right)

    elif isinstance(expr, BinOp):
        left = _expr_to_c(expr.left, buf_params, scalar_params, current_ol)
        right = _expr_to_c(expr.right, buf_params, scalar_params, current_ol)
        if expr.op == "and":
            return "({}) && ({})".format(left, right)
        elif expr.op == "or":
            return "({}) || ({})".format(left, right)
        elif expr.op in ("+", "-", "*", "/", "%"):
            return "({} {} {})".format(left, expr.op, right)
        else:
            raise ValueError("Unknown binop: {}".format(expr.op))

    elif isinstance(expr, UnaryOp):
        operand = _expr_to_c(expr.operand, buf_params, scalar_params, current_ol)
        if expr.op == "not":
            return "!({})".format(operand)
        elif expr.op == "-":
            return "-({})".format(operand)
        elif expr.op == "+":
            return "+({})".format(operand)
        else:
            raise ValueError("Unknown unary op: {}".format(expr.op))

    else:
        raise ValueError("Unknown expression type: {}".format(type(expr)))


# ---- Expression transpilation ----


def _extract_fmt_from_expr(expr, param_name, fmt_chars):
    """Recursively extract format char comparisons from an expression tree."""
    if isinstance(expr, Compare) and expr.op == "==":
        for side, other in [(expr.left, expr.right), (expr.right, expr.left)]:
            if (
                isinstance(side, Attr)
                and side.attr == "format"
                and _expr_refers_to(side.obj, param_name)
                and isinstance(other, StrLit)
                and len(other.value) == 1
            ):
                fmt_chars.add(other.value)
    elif isinstance(expr, BinOp):
        _extract_fmt_from_expr(expr.left, param_name, fmt_chars)
        _extract_fmt_from_expr(expr.right, param_name, fmt_chars)
    elif isinstance(expr, UnaryOp):
        _extract_fmt_from_expr(expr.operand, param_name, fmt_chars)


# ---- Buffer and wrapper helpers ----


def _float_literal(value):
    """Convert a Python float to a C double literal string.
    Handles whole-number floats (3.0 -> 3.0) and fractions."""
    s = "%.15g" % value
    if "." not in s and "e" not in s and "E" not in s:
        s += ".0"
    return s
