# c2py23 Referee Report Workplan

## Instructions for the implementing agent

For each task below:

1. Read the referenced files at the exact line numbers given.
2. Make the change described.
3. Verify the fix by running: `python3 tests/test_regression_fixes.py`
4. For parser/generator changes, also run: `bash tests/run_tests.sh python3`
5. Write a short report for each task: what was the issue, what was changed, and verification result.

## Pre-work: read key files

Before starting, read these files so you understand the architecture:

- `/home/worker/c2py23/c2py23/parser.py` — AST nodes around lines 80-130, `_parse_c_sig` around 284-339, `_parse_c_params` around 342-363, `_C_PARAM_RE` at 280-282, expression parser `_parse_string` around 569-582, template expansion `_expand_func_template` around 614-652, `_validate_module` around 920-987.
- `/home/worker/c2py23/c2py23/generator.py` — `_emit_c_call` around 519-763 (focus on 730-762), `_get_buf_flags` around 1052, `_emit_static_dispatch` around 174-241, `_emit_gil_release_decls` around 139-146, free-threading module init around 1760-1770.
- `/home/worker/c2py23/c2py23/cli.py` — lines 50-65 for dead code.
- `/home/worker/c2py23/c2py23/runtime/c2py_runtime.h` — struct `c2py_api_t` around 191-277, `_c2py_dec_ref_manual` around 332-340.
- `/home/worker/c2py23/c2py23/runtime/c2py_runtime.c` — init and FT detection, `RESOLVE` macro usage.
- `/home/worker/c2py23/docs/specification.md` — free-threading section around 1050-1100.
- `/home/worker/c2py23/AGENTS.md` — safety documentation section.
- `/home/worker/c2py23/tests/test_regression_fixes.py` — for the test pattern to follow.

---

## TASK A — Fix `int64_t` multi-output tuple bug (P1)

**File:** `/home/worker/c2py23/c2py23/generator.py`

**Issue:** In `_emit_c_call`, the multi-output branch (where `n > 1`) handles `int64_t` at lines 740-741 with only one line:
```python
elif ctype == 'int64_t':
    out.append(indent + 'PyObject *_c2py_obj{0} = PyLong_FromLongLong((long long){1});'.format(i, val))
```
Every other type in the same branch (int/int8_t/uint16_t/etc., uint64_t, float/double, fallback else) follows the full pattern:

1. Create Python object
2. NULL check with `Py_DECREF(_c2py_tup); return NULL;` on failure
3. `PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0})`

The `int64_t` branch is missing all three of lines 2-4. This means the created PyLong is leaked (never attached to tuple, never DECREF'd), the NULL check is missing, and the tuple slot is left NULL — a crash if Python ever accesses it.

**Fix:** Add 4 lines after the existing line 741, following the uint64_t pattern at lines 743-748 verbatim but using `PyLong_FromLongLong` naming:
```python
elif ctype == 'int64_t':
    out.append(indent + 'PyObject *_c2py_obj{0} = PyLong_FromLongLong((long long){1});'.format(i, val))
    out.append(indent + 'if (_c2py_obj{0} == NULL) {{'.format(i))
    out.append(indent + '    Py_DECREF(_c2py_tup);')
    out.append(indent + '    return NULL;')
    out.append(indent + '}')
    out.append(indent + 'PyTuple_SetItem(_c2py_tup, {0}, _c2py_obj{0});'.format(i))
```

**Verification:** After fixing, add a regression test to `/home/worker/c2py23/tests/test_regression_fixes.py` that:
1. Builds a `ModuleDef` AST with a function that has `outputs: {val: int64_t}` (single output `int64_t` is fine — verify the generated C has `PyLong_FromLongLong`).
2. Builds a `ModuleDef` AST with a function that has multiple `outputs:` where one is `int64_t`. Assert that the generated C contains `PyTuple_SetItem` for the `int64_t` output.
3. Assert the generated C does NOT contain any mismatched `PyTuple_SetItem` calls (the tuple index should match `_c2py_obj` index).

Also check: does `scalar_output/stats.c2py` test file exist? Consider adding a real `.c2py` test case with int64_t outputs, or add a unit test pattern (like existing regression tests) that builds an AST and checks generated C strings.

---

## TASK B — Fix `Unstable_Module_SetGIL` function pointer type mismatch (P1)

**Files:**
- `/home/worker/c2py23/c2py23/runtime/c2py_runtime.h`
- `/home/worker/c2py23/c2py23/generator.py`

**Issue:** The struct field at `c2py_runtime.h:275` declares:
```c
void (*Unstable_Module_SetGIL)(PyObject*, int);
```
The real CPython 3.13+ function is:
```c
int PyUnstable_Module_SetGIL(PyObject *mod, void *gil_state);
```
Both the return type (`void` vs `int`) and the second parameter (`int` vs `void*`) differ. The generated call at `generator.py:1765` passes `1` as an `int` argument through a function pointer typed to take `int`, but the underlying function expects `void*`. On LP64 platforms (x86-64, AArch64, POWER64) `int` is 32-bit and `void*` is 64-bit. This is technically undefined behavior per C99 6.3.2.3 — calling a function through a function pointer with incompatible types. In practice the 32-bit immediate zero-extends and works, but it's UB that could break on other ABIs.

**Fix:**

Step 1 — `c2py_runtime.h:274-275`: Change the declaration to:
```c
/* Free-threading: set Py_MOD_GIL_NOT_USED on module (optional, may be NULL) */
void (*Unstable_Module_SetGIL)(PyObject*, void*);
```

Step 2 — `generator.py:1765`: Change the line from:
```python
''C2PY.Unstable_Module_SetGIL(module, 1);  /* Py_MOD_GIL_NOT_USED */''
```
to:
```python
''C2PY.Unstable_Module_SetGIL(module, (void*)1);  /* Py_MOD_GIL_NOT_USED */''
```

**Verification:** Run `bash tests/run_tests.sh python3` and verify tests pass. Build the threading_bench example and verify it still compiles/works. Check that generated wrappers compile with `-Wall -Werror`.

---

## TASK C — Remove dead `src_path` code in cli.py (P1)

**File:** `/home/worker/c2py23/c2py23/cli.py`

**Issue:** Lines 56-57 compute a value for `src_path`:
```python
        src_path = os.path.join(base_dir, os.path.dirname(
            os.path.join(base_dir, src)), os.path.basename(src))
```
Then line 59 immediately reassigns `src_path` to a different value:
```python
        src_path = os.path.normpath(os.path.join(base_dir, src))
```
The value from lines 56-57 is never read. The comment on line 58 (`# Normalise: join(base_dir, src) handles both absolute and relative`) applies to line 59, not lines 56-57. Lines 56-57 are dead code — likely an earlier iteration that was replaced by the simpler normpath approach.

**Fix:** Delete lines 56-57. Keep the comment on line 58 and the actual assignment on line 59. The loop body should look like:
```python
    for src in module_def.sources:
        # Normalise: join(base_dir, src) handles both absolute and relative
        src_path = os.path.normpath(os.path.join(base_dir, src))
```

**Verification:** Run `python3 -c "from c2py23.cli import build; print('OK')"` to verify import. Run `bash tests/run_tests.sh python3` to ensure all test modules still build correctly.

---

## TASK D — Anchor `_C_PARAM_RE` to end-of-string (P2)

**File:** `/home/worker/c2py23/c2py23/parser.py`

**Issue:** At line 280-282:
```python
_C_PARAM_RE = re.compile(
    r'\s*(?:const\s+)?(' + '|'.join(_C_TYPES_INT) + r')\s*\*?\s*(\w+)\s*'
)
```
Used at line 351 with:
```python
m = _C_PARAM_RE.match(part)
```
`re.match()` anchors at start but does **not** require consuming the full string. The trailing `\s*` is greedy but does not enforce end-of-string. This means `double *x garbage_trailing_junk` would match successfully and silently ignore the trailing junk. Similarly `double *x[]` or `double *x more text` would parse when they should be rejected.

**Fix:** Add `$` at the end of the pattern:
```python
_C_PARAM_RE = re.compile(
    r'\s*(?:const\s+)?(' + '|'.join(_C_TYPES_INT) + r')\s*\*?\s*(\w+)\s*$'
)
```
The implicit `^` from `re.match()` handles start-anchoring. The `$` ensures the match consumes the entire string.

**Verification:** Add a regression test to `test_regression_fixes.py` that:
1. Calls `_parse_c_params("int x garbage")` and asserts it raises `ValueError` (currently would silently parse as `int x`).
2. Calls `_parse_c_params("double *ptr[]")` and asserts it raises `ValueError`.
3. Verifies normal params like `"int x, double *y"` still parse correctly.
4. Verifies `"int x"` still parses correctly (no regression).

Run `python3 tests/test_regression_fixes.py`.

---

## TASK E — Validate return types against generator capabilities (P2)

**File:** `/home/worker/c2py23/c2py23/parser.py`

**Issue:** `_parse_c_sig` (line 284) accepts all 13 types from `_C_TYPES_INT` as valid return types: `int8_t`, `uint8_t`, `int16_t`, `uint16_t`, `int32_t`, `uint32_t`, `int64_t`, `uint64_t`, `int`, `float`, `double`, `char`, `void`. But `_emit_c_call` in `generator.py` only has proper handling for four: `void`, `int`, `float`, `double`. Everything else falls into the `/* unknown return type */` branch (line 663-673) which calls the function, discards the return value, and returns `Py_RETURN_NONE`. For example, a `uint32_t crc32(...)` function would parse cleanly, generate a wrapper, and silently return `None` to Python instead of the checksum.

**Fix:** In `_parse_c_sig`, add a check after the return type is determined. Around line 326-328, after the return type is set, add validation that the return type is one the generator can emit. Determine where return_type is finalized (both suffix `-> type` and prefix `type func(...)` paths) and add:

```python
_SUPPORTED_RETURN_TYPES = {'void', 'int', 'float', 'double'}

# After return_type is determined (both paths), add:
if return_type is not None and return_type not in _SUPPORTED_RETURN_TYPES:
    raise ValueError(
        "Unsupported return type '{}' in C signature '{}' in {}. "
        "Supported return types: void, int, float, double. "
        "Use outputs: for other types.".format(
            return_type, sig_str, path))
```

**Verification:** Add a regression test to `test_regression_fixes.py` that:
1. Calls `_parse_c_sig("uint32_t crc32(const uint8_t *data)", "test")` and asserts it raises `ValueError`.
2. Calls `_parse_c_sig("char get_char(void)", "test")` and asserts it raises `ValueError`.
3. Calls `_parse_c_sig("int64_t compute(void)", "test")` and asserts it raises `ValueError`.
4. Verifies `_parse_c_sig("double norm(const double *a)", "test")` still works (no regression).
5. Verifies `_parse_c_sig("int count(void)", "test")` still works.

Run `python3 tests/test_regression_fixes.py` and `bash tests/run_tests.sh python3`.

---

## TASK F — Store `c_name` in AST, eliminate re-parsing (P2)

**Files:**
- `/home/worker/c2py23/c2py23/parser.py`
- `/home/worker/c2py23/c2py23/generator.py`

**Issue:** Both `parser.py` (line 990-992) and `generator.py` (line 83-85) have identical copies of:
```python
def _extract_c_name(sig_str):
    """Extract the C function name from a sig string."""
    return sig_str.split('(')[0].strip().split()[-1]
```
The `COverload` and `CVariant` namedtuples store `sig_str` but not the extracted name. Every call site re-parses the signature to extract the name. This is error-prone — if the parsing logic changes, the two copies can diverge. There are ~12 call sites across generator.py.

**Fix:**

Step 1 — In `parser.py`, add `'c_name'` to the `COverload` namedtuple fields (line ~83-86):
```python
class COverload(namedtuple('_COverload', [
    'sig_str', 'params', 'return_type', 'map_exprs',
    'when_expr', 'name', 'group_name', 'variants', 'c_name'
])):
```

And to `CVariant` (line ~113-116):
```python
class CVariant(namedtuple('CVariant', [
    'name', 'sig_str', 'params', 'return_type',
    'when_expr', 'outputs', 'c_name'
])):
```

Step 2 — In `_parse_c_sig` (parser.py), the function already parses the name from the C signature around line 320-328 and returns it as the first element of the tuple `(name, params, return_type)`. Extract it earlier and store it. The callees that create `COverload` and `CVariant` objects need to pass this extracted name.

Find where `COverload` and `CVariant` are constructed in parser.py and pass `c_name=<extracted name>`.

Step 3 — In `generator.py`, update all call sites that use `_extract_c_name(ol.sig_str)` to use `ol.c_name` instead. Search for `_extract_c_name` in generator.py to find all occurrences (approximately at lines 62, 67, 80, 94, 111, 114, 527, 1622, 1627).

Step 4 — Remove the `_extract_c_name` function from generator.py (lines 83-85).

Step 5 — Remove the `_extract_c_name` function from parser.py (lines 990-992).

Step 6 — In parser.py's `_validate_module`, update the call sites at lines 939, 941, 978 to use `v.c_name` / `ol.c_name` instead of `_extract_c_name(v.sig_str)`.

**Verification:** Run `python3 tests/test_regression_fixes.py` and `bash tests/run_tests.sh python3`. All existing tests must pass — this is a pure refactor with no behavioral change.

---

## TASK G — Fix expression parser backslash handling (P2)

**File:** `/home/worker/c2py23/c2py23/parser.py`

**Issue:** `_parse_string()` at lines 569-582 handles backslash by skipping the next character (`self.pos += 2`), but then returns the raw substring `val = self.s[start:self.pos]` without unescaping. So `"a\nb"` yields the literal characters `a`, `\`, `n`, `b` — not `a`, newline, `b`. If later code generation assumes C string semantics (e.g., passing the value into C code as a string literal), this could produce surprising behavior. The current behavior is both a parse error and a potential semantic bug.

**Fix:** Choose one of these options depending on the intent:

**Option A** (recommended — decode escapes properly): Modify `_parse_string` to build a decoded string. Track a list of decoded characters, append normally, and when `\` is seen, skip past it and decode the next character (`\n` → newline, `\t` → tab, `\\` → backslash, `\"` / `\'` → quote, etc.). This is ~15 lines of code.

**Option B** (simpler — reject unescaped backslashes): After the string is extracted, check if it contains `\\` and raise `ValueError("Escape sequences are not supported in expression strings")` or alternatively, allow `\\` for literal backslash and reject everything else.

**Option C** (document-only): Add a comment at the top of `_parse_string` stating: "Backslash is treated as a literal character, not as an escape prefix. Use YAML escapes if needed." But this is the weakest fix.

Prefer Option A since it's most correct and most useful. Implement at least `\\`, `\"`, `\'`, `\n`, `\t`.

**Verification:** Add a regression test to `test_regression_fixes.py` that:
1. Parses `"hello\\tworld"` and checks the resulting string value (should contain a tab).
2. Parses `"hello\\"world\\""` and checks embedded quotes work.
3. Parses `"path\\\\to\\\\file"` and checks backslash literals work.
4. Tests that `"unterminated` raises `ValueError` (existing behavior validation).

Run `python3 tests/test_regression_fixes.py`.

---

## TASK H — Validate template expansion values are strings (P2)

**File:** `/home/worker/c2py23/c2py23/parser.py`

**Issue:** `_expand_func_template` (lines 614-652) builds a `vars_map` from the expansion values and passes it to `_strsubst` (lines 596-611). `_strsubst` does:
```python
s = s.replace('${' + var + '}', val)
```
where `val` is whatever value is in the YAML. If the value is a non-string (e.g., a dict `{foo: bar}` or an integer `42`), `str.replace()` raises `TypeError` with an unhelpful traceback. No validation checks that expansion values are strings.

**Fix:** In `_expand_func_template`, after building `vars_map` (around line 649), iterate over the values and check each is a string:
```python
for var, val in vars_map.items():
    if not isinstance(val, str):
        raise ValueError(
            "Template expansion value for '${}{}{}' must be a string, "
            "got {}".format('{', var, '}', type(val).__name__))
```

**Verification:** Add a regression test to `test_regression_fixes.py` that:
1. Creates a function template with `expand: {VAR: [42]}` and asserts it raises `ValueError` with a helpful message containing "must be a string".
2. Verifies normal string expansion still works.
3. Check existing tests are not affected: `bash tests/run_tests.sh python3`.

---

## TASK I — Improve error messages for unsupported C return types (P3)

**File:** `/home/worker/c2py23/c2py23/parser.py`

**Issue:** `_parse_c_sig` (line 329-330) raises:
```python
raise ValueError("Cannot parse C signature '{}' in {}".format(sig_str, path))
```
This is the catch-all error. Users who try `unsigned int func()`, `long long func()`, or `const double *func()` get this generic message. The subset of supported types is intentionally narrow, but the error message doesn't explain why the signature was rejected.

**Fix:** Before raising the generic error, try to identify the specific cause. If the `before_parts` count is not exactly 1 or 2, or if the expected type position contains a type that's not in `_C_TYPES`, produce a more specific message. For example:

- `len(before_parts) > 2` with a recognized type as the first word → likely a multi-word return type like `unsigned int`: suggest using a typedef or wrapping.
- `len(before_parts) == 2` but `before_parts[0] not in _C_TYPES` → unknown return type.

Add additional checks before the generic error:
```python
if len(before_parts) > 2 and before_parts[0] in _C_TYPES:
    raise ValueError(
        "Unsupported C signature '{}' in {}: "
        "multi-word return types (e.g. 'unsigned int', 'long long') "
        "are not supported. Use a typedef or a single-word type.".format(
            sig_str, path))
elif len(before_parts) == 2 and before_parts[0] not in _C_TYPES:
    raise ValueError(
        "Unsupported return type '{}' in C signature '{}' in {}. "
        "Supported: void, int, float, double.".format(
            before_parts[0], sig_str, path))
```

**Verification:** Add a regression test:
1. `_parse_c_sig("unsigned int func(void)", "test")` → expect `ValueError` mentioning "multi-word return types".
2. `_parse_c_sig("size_t func(void)", "test")` → expect `ValueError` mentioning "Unsupported return type".
3. Normal signatures still parse correctly.

Run `python3 tests/test_regression_fixes.py`.

---

## TASK J — Add static assertions for runtime ABI assumptions (P3)

**File:** `/home/worker/c2py23/c2py23/runtime/c2py_runtime.c`

**Issue:** The referee flagged that the runtime hardcodes object sizes and offsets after detection (e.g., `C2PY.pyobject_size = 32; C2PY.ob_refcnt_offset = 16;` for FT builds). There are no runtime sanity checks that the detected values are self-consistent. Future CPython versions could change FT layout and the detection logic might produce wrong values without any hard error.

**Fix:** After the object layout detection code completes (after all the `C2PY.*` assignments), add C `assert()` calls to verify invariants. For example:

```c
/* Sanity-check detected layout */
assert(C2PY.pyobject_size > 0);
assert(C2PY.ob_refcnt_offset < C2PY.pyobject_size);
assert(C2PY.ob_type_offset < C2PY.pyobject_size);
/* ob_refcnt and ob_type must not overlap */
assert(C2PY.ob_refcnt_offset + (Py_ssize_t)sizeof(Py_ssize_t) <= C2PY.ob_type_offset ||
       C2PY.ob_type_offset + (Py_ssize_t)sizeof(void*) <= C2PY.ob_refcnt_offset);
```

Also, after FT detection, verify that `Py_BUFFER_SIZE` is a known good value for the detected version, and that `PyUnstable_Module_SetGIL` is resolved (or NULL, which is valid).

**Verification:** Run `bash tests/run_tests.sh python3`. The assertions should hold for all supported Python versions. If any assertion fails, fix the detection logic. Also run on python3.14t (free-threaded) via the test_all.py container.

---

## TASK K — Improve free-threading detection robustness (P3)

**File:** `/home/worker/c2py23/c2py23/runtime/c2py_runtime.c`

**Issue:** FT detection currently uses two methods:
1. Check if `Py_GetVersion()` string contains `"free-threading"`
2. Check if `_Py_IsGILEnabled()` exists and returns 0

The referee notes that `_Py_IsGILEnabled()` is not a public API. There's no explicit environment variable override. If the detection logic is wrong, there's no way for the user to force the correct behavior.

**Fix:** Add an environment variable override:

1. Before any detection logic, check `getenv("C2PY_FORCE_FT")`. If set to `"1"`, force free-threading mode. If set to `"0"`, force standard mode.
2. Add a comment documenting the public vs. internal API note.
3. When `_Py_IsGILEnabled` is not found (Python < 3.13 or non-FT build), default to standard mode. When found and returns 0, enable FT mode.

Pseudo-code:
```c
char *force_ft = getenv("C2PY_FORCE_FT");
if (force_ft) {
    if (force_ft[0] == '1') {
        C2PY.is_free_threading = 1;
        /* Set FT-specific sizes/offsets */
    } else {
        C2PY.is_free_threading = 0;
    }
    goto ft_detection_done;
}
/* existing detection logic ... */
ft_detection_done:
    ;
```

**Verification:** 
1. `C2PY_FORCE_FT=0 python3 -c "import arraysummod"` should work.
2. `C2PY_FORCE_FT=1 python3 -c "import arraysummod"` should work (or produce a clear error if FT cannot be enabled).
3. Without the env var, existing behavior is unchanged.

---

## TASK L — Remove stale documentation sentence (P4)

**File:** `/home/worker/c2py23/docs/specification.md`

**Issue:** Line 1054 says:
```
`c2py23 does not yet expose a YAML option to add the Py_mod_gil slot.`
```
But lines 1069-1075 document `free_threading: true` as exactly that YAML option. This is a stale sentence left from before the feature was implemented.

**Fix:** Remove or update line 1054. Replace it with something like:
```
`c2py23 exposes `free_threading: true` as a top-level YAML option to opt into free-threading support.`
```

**Verification:** Search for the stale phrase in the docs: `grep -r "does not yet expose" docs/` should return no results after the fix. Also check `audit/full_repo_audit.md` which may contain a copy — update there too if the line exists.

---

## TASK M — Document buffer writability limitation (P4)

**Files:** 
- `/home/worker/c2py23/c2py23/generator.py` — add code comment
- `/home/worker/c2py23/AGENTS.md` — add safety note

**Issue:** Buffer writability is computed per-function, scanning all overloads. If *any* overload writes to a buffer, the buffer is acquired with `PyBUF_WRITABLE` for all dispatch paths. This means a const-only overload forces callers to provide writable buffers if another overload writes. This is a known design limitation without a code comment, documented only in the audit file.

**Fix:**
1. In `generator.py`, at the `_get_buf_flags` function (around line 1052), add a comment above the function:
```python
# NOTE: Buffer writability is determined per-function, not per-selected-overload.
# If any overload (including variants) has a non-const pointer mapping to a buffer
# parameter, the buffer is acquired as PyBUF_WRITABLE for ALL dispatch paths.
# Callers must provide writable buffers even when the selected overload only reads.
# This is a performance tradeoff: per-overload buffer re-acquisition would add
# overhead to the hot path.
```

2. In `AGENTS.md`, add a note in the "Writing Safe .c2py Definitions" section under the existing safety guidelines:
```markdown
### Buffer writability and overload dispatch

When a function has multiple overloads, the wrapper acquires each buffer with
`PyBUF_WRITABLE` if *any* overload writes to it. If you add a const-only
overload alongside a writable overload for the same buffer parameter, callers
will be forced to provide writable buffers for the read-only path. Keep this
in mind when mixing read and write overloads.
```

**Verification:** No test changes needed. Verify the comment is present in the source.

---

## TASK N — Document `_c2py_dec_ref_manual` limitation (P4)

**File:** `/home/worker/c2py23/c2py23/runtime/c2py_runtime.h`

**Issue:** `_c2py_dec_ref_manual` at lines 332-340 is a fallback when `Py_DecRef` cannot be resolved via dlsym (Python < 3.12). When refcount reaches zero, it only prints a diagnostic to stderr but does NOT call the object destructor — the object is leaked. This was flagged as B2 in the referee reports and marked "MITIGATED" because the path is unreachable in practice (all supported versions that lack `Py_DecRef` use shared refcounts where zero-is-special does not apply).

**Fix:** Add a detailed comment above the function:
```c
/*
 * _c2py_dec_ref_manual: Fallback dec-ref implementation for Python versions
 * that do not export Py_DecRef (pre-3.12). On these versions, CPython uses
 * shared refcounts where the zero-is-special invariant does not apply --
 * PyObject refcounts never reach zero through normal INCREF/DECREF alone.
 *
 * WARNING: This function only decrements the refcount and prints a diagnostic
 * if it reaches zero. It does NOT call the object destructor (Py_DECREF's
 * tp_dealloc equivalent). This is acceptable because the fallback path is
 * only active on Python < 3.12 where zero-refcount cannot occur in normal
 * operation. If you are porting to a platform where this invariant does not
 * hold, you must implement proper deallocation.
 */
```

**Verification:** No test changes needed. Confirm the comment is present in the header.

---

## TASK O — Add golden-file test infrastructure (P5)

**File:** Create `/home/worker/c2py23/tests/test_golden.py`

**Issue:** The generator assembles C code via string concatenation (`out.append(...)`). Generators of this style often fail through omission — a line is forgotten, an output clause is skipped. The referees strongly recommend golden-file tests: generate C for every overload form and compare against expected output.

**Fix:** Create a new test file that:
1. For each `.c2py` file in `tests/cases/**/*.c2py`, parse it and generate C code.
2. Compare the generated C against a stored expected output file (e.g., `tests/cases/<name>/expected_wrapper.c`).
3. If the expected file doesn't exist, write it (in a "record" mode) so the first run bootstraps the golden files.
4. If the expected file exists, assert the generated code matches byte-for-byte (or with a normalized whitespace comparison).

If writing full-file comparison is too heavy, at minimum verify key patterns are present in the generated output for each test case:
- Forward declarations exist for each C function
- Buffer acquisition uses correct flags
- Format checks are emitted
- Size/length checks are emitted
- The C call is emitted
- Buffer release is emitted
- Return value is properly constructed

**Suggested structure:**
```python
"""Golden-file tests for generated C wrapper output."""
from __future__ import print_function
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from c2py23.parser import load_module
from c2py23.generator import generate

def test_golden_arraysum():
    mod = load_module(os.path.join(ROOT, 'tests/cases/arraysum/arraysum.c2py'))
    code = generate(mod)
    # Verify critical patterns exist
    assert '_arraysum_impl' in code
    assert 'PyBUF_WRITABLE' in code
    assert 'C2PY.AcquireBuffer' in code
    assert 'C2PY.ReleaseBuffer' in code
    # etc.
```

**Verification:** Run `python3 tests/test_golden.py`. If golden files differ, the test must fail.

---

## TASK P — Add exception path stress tests (P5)

**File:** `/home/worker/c2py23/tests/test_error_paths.py` (extend existing)

**Issue:** The referees want dedicated stress testing for every path where a buffer acquisition or check can fail, verifying all buffer releases occur and no refcount leaks.

**Fix:** Add these test scenarios to the existing `test_error_paths.py`:

1. **Partial buffer acquisition:** Call a function that takes 3 buffers. Monkey-patch or use a custom module where the 2nd buffer acquisition fails. Verify the 1st buffer is released.
   - Approach: pass a buffer with wrong format for the 2nd parameter, verify no leak on the 1st parameter, and verify error message.

2. **Check failure mid-evaluation:** A function with multiple checks where the 2nd check fails. Verify no leaks from the 1st check's side effects.

3. **Overload resolution failure:** No overload matches (all `when:` conditions false). Verify `default_raise` is called, buffers are released.

4. **C function raises Python error:** A C function that sets a Python exception and returns an error indicator. Verify the wrapper propagates the error correctly and releases buffers.

5. **10x repeated error paths:** For each scenario above, repeat the failing call 10x and verify `sys.getrefcount()` of the returned exception is stable (no leak).

**Verification:** Run `python3 tests/test_error_paths.py`. All existing and new tests must pass. For refcount-based tests, be aware of Python 3.14 biased refcounting (guard with version check as existing tests do).

---

## TASK Q — Add subinterpreter test (P5)

**File:** Create or extend `/home/worker/c2py23/tests/test_interpreters.py`

**Issue:** Python 3.12+ introduced subinterpreters. The c2py23 runtime bypasses normal extension module mechanics (`PyInit_*` via `dlopen`). Subinterpreters are where global state often becomes visible. The `pthread_once` init pattern needs to be tested under subinterpreter conditions.

**Fix:** Write a test that:
1. Checks if `interpreters` module is available (`sys.version_info >= (3, 12)`). Skip otherwise.
2. Creates a subinterpreter.
3. In the subinterpreter, imports a c2py23 module and calls a simple function.
4. Verifies the function returns the correct result.
5. Destroys the subinterpreter and creates another one — repeat the test.
6. Verifies that global state is properly re-initialized (or properly shared, depending on design).

**Verification:** Run on Python 3.12+. Ensure no crashes, no leaked objects, correct return values.

---

## TASK R — Add re-import cycle test (P5)

**File:** Create a new test or add to `test_error_paths.py`

**Issue:** Module reload/unload cycles can reveal refcount leaks, stale state, and double-free bugs. The pattern: import a module, delete it from `sys.modules`, run garbage collection, re-import it.

**Fix:** Write a test that:
1. Imports a c2py23 module (e.g., `arraysummod`).
2. Uses the module.
3. Deletes it from `sys.modules`: `del sys.modules["arraysummod"]`.
4. Runs `gc.collect()`.
5. Re-imports the module.
6. Uses it again and verifies correct behavior.
7. Repeat the cycle 5-10 times.
8. Verify no crashes, no memory growth (check RSS with `/proc/self/statm`).

**Verification:** Run `python3` with this test. Must not segfault or leak.

---

## TASK S — Add concurrent import test (P5)

**File:** Create a new test file `tests/test_concurrent_import.py`

**Issue:** The `pthread_once` initialization pattern in `c2py_runtime.c` is designed to protect against multiple threads initializing the runtime simultaneously. This needs testing.

**Fix:** Write a test that:
1. Uses `threading` module (Python 2.7 and 3.x compatible with `.start()` / `.join()`).
2. Spawns 10+ threads that each import the same c2py23 module.
3. Each thread calls a function on the module and checks the result.
4. Verifies no crashes, no corrupted results, all threads complete successfully.
5. Run this test multiple times to catch rare race conditions.

Also test concurrent initial import of *different* modules from different threads.

**Verification:** Run `python3 tests/test_concurrent_import.py`. Run multiple times to verify reproducibility.

---

## TASK T — Audit mutable globals for free-threading safety (P5)

**Files:** `/home/worker/c2py23/c2py23/generator.py` + new test

**Issue:** The referee identified these mutable globals as race-prone under free-threading:
- `_c2py_gil_release_enabled` (line 142) — writable via module attribute
- `_c2py_timing_enabled` — similar writable global
- Per-function `_gil_release_*` flags (line 145)
- Variant index variables `_var_<name>_<gi>` (line 190) — written by `_rebind_*` functions
- Variant name variables `_vname_<name>_<gi>` (line 191)

Under the GIL, toggling these is safe. Under free-threading (`free_threading: true`), multiple threads calling `_rebind_*` or toggling the gil_release flag creates a data race — the writes and reads to these globals are non-atomic.

**Fix — Part 1: Generator audit:** Review each mutable global in `generator.py` and:
1. Document in a comment whether it's GIL-protected or FT-safe.
2. For `_c2py_gil_release_enabled` and per-function flags: since these are set from Python at module init time (before threads exist), they're effectively immutable at runtime. Document this.
3. For `_rebind_*` functions that modify `_var_*` / `_vname_*`: these are inherently racy under FT. Add a comment documenting that `_rebind_*` is not thread-safe under free-threading and should only be called during initialization.
4. Add a warning in the docstring generation for functions that use grouped dispatch + `free_threading: true`.

**Fix — Part 2: Test:** Add a test to `tests/cases/freethreading/` (or a pure Python test) that:
1. Under `PYTHON_GIL=0` (true free-threading), calls `_rebind_*` from multiple threads.
2. Verifies that concurrent rebinding does not crash (even if behavior is undefined).

**Verification:** Run existing tests. Run threading_bench example. Run freethreading tests.

---

## TASK U — Add manylinux images request to snakepit (P6)

**No code changes in c2py23.** This is an infrastructure request for the snakepit container project.

**Request:** Add `manylinux2014_x86_64` and `manylinux2014_aarch64` container images to the snakepit project (`../snakepit/` relative to c2py23 root).

**Purpose:** Verify that c2py23-built `.so` files import correctly across the full Python version matrix under manylinux glibc constraints (glibc 2.17 for manylinux2014). The "one binary across Python versions" trick solves the Python ABI problem but does not solve the platform / glibc versioning problem. Before investing in wheel infrastructure, we need to verify binary compatibility on multi-Python manylinux images.

**Acceptance criteria:**
- `manylinux2014_x86_64.sif` exists in `../snakepit/`
- `manylinux2014_aarch64.sif` exists in `../snakepit/`
- `test_all.py` can be extended to build and test inside these containers
- Generated `.so` files import correctly on all supported Python versions within the manylinux constraints

---

## TASK V — Update wheel/packaging status documentation (P6)

**File:** `/home/worker/c2py23/PLAN.md`

**Issue:** The P4 "Binary Wheel Distribution" entry in PLAN.md currently says:
```
P4: Binary Wheel Distribution -- Severity: Low -- Status: Deferred, design TBD
```
This is overly optimistic. The referees identified concrete open questions that need resolution before wheel building is practical:
- Wheel tagging for ABI-neutral .so files (no standard tag exists for "links to nothing, works on all CPython ABIs")
- Symbol export requirement: `dlopen(NULL)` with `RTLD_GLOBAL` depends on the running interpreter being built with `--enable-shared` / exporting dynamic symbols (not guaranteed on musllinux/Alpine, conda, embedded/frozen Python)
- No build-backend integration: `cli.py` shells out to `gcc` directly; no `setuptools`/`meson`/`scikit-build-core` hookup for `pip wheel` or `cibuildwheel`
- musllinux incompatibility: Alpine uses musl, not glibc; different CRT

**Fix:** Update the P4 entry in PLAN.md to acknowledge these open questions:
```markdown
### P4: Binary Wheel Distribution

**Status: Deferred -- design TBD, implement later.**

**Open design questions (from referee review):**

1. **Wheel tagging:** The c2py23 .so uses the nimpy trick — one binary works
   on CPython 2.7-3.14 without linking libpython. Standard wheel tags
   (cp312-cp312-*, cp37-abi3-*, etc.) assume a specific CPython ABI. A
   bare `modulename.so` with no Python link dependency has no standard
   wheel tag. Need to investigate whether `py3-none` tag can be used.

2. **Symbol export dependency:** `c2py_runtime_init()` does `dlopen(NULL,
   RTLD_GLOBAL)` and expects CPython API symbols already loaded. This
   depends on the interpreter being built with `--enable-shared`. Not
   guaranteed for: musllinux/Alpine, some conda builds, embedded/frozen
   Python, PyPy.

3. **Build-backend integration:** Current `cli.py` shells out to `gcc`
   directly. No `setuptools build_ext` / meson-python / scikit-build-core
   hookup for `pip wheel .` or `cibuildwheel`. This integration layer
   must be built from scratch.

4. **Platform matrix:** Need verification on manylinux2014 x86_64 and
   aarch64, musllinux, macOS, and Windows before distribution.

**Next steps before implementation:**
- Build and test on manylinux2014 containers (Task U)
- Evaluate `py3-none-any` vs. platform-specific wheel tags
- Evaluate setuptools vs. meson-python vs. scikit-build-core for build backend
```

**Verification:** Review the updated PLAN.md for accuracy.

---

## Verification Checklist

After all tasks A-V are complete, run the full verification:

```bash
# Unit tests
python3 tests/test_regression_fixes.py

# Full test suite on current Python
bash tests/run_tests.sh python3

# Full test suite across all Python versions (requires snakepit containers)
python3 tests/test_all.py

# Valgrind leak check
valgrind --leak-check=full python3 tests/test_leaks.py

# Lint check (if available)
# ruff check c2py23/ tests/

# Verify 7-bit ASCII compliance
python3 -c "
import os
for d, _, fs in os.walk('c2py23'):
    for f in fs:
        if f.endswith(('.py', '.c', '.h')):
            with open(os.path.join(d, f), 'rb') as fh:
                c = fh.read()
                nb = [b for b in c if b > 127]
                if nb:
                    print('NON-ASCII:', os.path.join(d, f), nb[:10])
"
```

## Report Format

For each task, produce a short report with this structure:

```markdown
### Task X: <title>

**Issue:** <one-line summary of the bug/gap>

**Change:** <what file, what line, what was changed>

**Verification:** <test results, e.g. "All 14 test_uniform tests pass", "Regression test added and passes">
```
