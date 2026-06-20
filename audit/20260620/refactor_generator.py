#!/usr/bin/env python3
"""Refactor generator.py: unify emit style, drop _builder suffix, reorganize sections."""
from __future__ import print_function
import sys, re

with open('c2py23/generator.py') as f:
    src = f.read()

# ================================================================
# Option A: Convert appendix functions from out.append() to b.emit()
# ================================================================

# Functions that take `out` (list) and call `out.append()`.
# These get converted to take `b: CBuilder` and call `b.emit()`.

# 1. _emit_check(out, check, buf_params, scalar_params) -> (b, ...)
src = src.replace(
    'def _emit_check(out, check, buf_params, scalar_params):',
    'def _emit_check(b, check, buf_params, scalar_params):')
src = src.replace(
    '_emit_check(b.lines, check, buf_params, scalar_params)',
    '_emit_check(b, check, buf_params, scalar_params)')

# 2. _emit_constants(out, mod) -> (b, mod)
src = src.replace(
    'def _emit_constants(out, mod):',
    'def _emit_constants(b, mod):')
src = src.replace(
    '_emit_constants(b.lines, module_def)',
    '_emit_constants(b, module_def)')

# 3. _emit_contiguity_checks(out, buf_params) -> (b, buf_params)
src = src.replace(
    'def _emit_contiguity_checks(out, buf_params):',
    'def _emit_contiguity_checks(b, buf_params):')
src = src.replace(
    '_emit_contiguity_checks(b.lines, buf_params)',
    '_emit_contiguity_checks(b, buf_params)')

# 4. _emit_default_raise_body(out, default_raise) -> (b, default_raise)
src = src.replace(
    'def _emit_default_raise_body(out, default_raise):',
    'def _emit_default_raise_body(b, default_raise):')
# call site already uses b.lines -> needs to be b
src = src.replace(
    '_emit_default_raise_body(b.lines, default_raise)',
    '_emit_default_raise_body(b, default_raise)')

# 5. _emit_restrict_checks(out, buf_params, func) -> (b, buf_params, func)
src = src.replace(
    'def _emit_restrict_checks(out, buf_params, func):',
    'def _emit_restrict_checks(b, buf_params, func):')
src = src.replace(
    '_emit_restrict_checks(b.lines, buf_params, func)',
    '_emit_restrict_checks(b, buf_params, func)')

# 6. _emit_varargs_wrapper(out, func, buf_params, scalar_params, timing) -> (b, ...)
src = src.replace(
    'def _emit_varargs_wrapper(out, func, buf_params, scalar_params, timing):',
    'def _emit_varargs_wrapper(b, func, buf_params, scalar_params, timing):')
src = src.replace(
    'def _emit_varargs_wrapper_builder',
    'def _emit_varargs_wrapper_builder_DELETEME')

# 7. _emit_fastcall_wrapper(out, ...) -> (b, ...)
src = src.replace(
    'def _emit_fastcall_wrapper(out, func, buf_params, scalar_params, timing):',
    'def _emit_fastcall_wrapper(b, func, buf_params, scalar_params, timing):')

# 8. _emit_wrapper_body(out, ...) -> (b, ...)
src = src.replace(
    'def _emit_wrapper_body(out, func, buf_params, scalar_params, name, timing=False):',
    'def _emit_wrapper_body(b, func, buf_params, scalar_params, name, timing=False):')

# 9. _emit_wrapper_locals(out, buf_params, scalar_params, func, timing=False) -> (b, ...)
src = src.replace(
    'def _emit_wrapper_locals(out, buf_params, scalar_params, func, timing=False):',
    'def _emit_wrapper_locals(b, buf_params, scalar_params, func, timing=False):')

# 10. _emit_timing_decls(out, mod) -> (b, mod)
src = src.replace(
    'def _emit_timing_decls(out, mod):',
    'def _emit_timing_decls(b, mod):')
src = src.replace(
    '_emit_timing_decls(b.lines, module_def)',
    '_emit_timing_decls(b, module_def)')

# Now replace all `out.append(` with `b.emit(` in the entire file
# This is safe because the only remaining `out` params are in the converted functions
# and they all use `out = b.lines` bridging which we're removing.
# The call sites all pass `b` now.

# Not all out.append calls use b.emit style — but let's be surgical.
# Actually, the pattern is: in the converted functions, change each `out.append(x)` to `b.emit(x)`.
# Let's do this for the specific functions.
# Since we changed the function signatures, the `out` variable inside them now refers to
# whatever was passed. We changed the first parameter from `out` to `b`, so inside
# the function body, `out` doesn't exist anymore — we need `b.emit()`.

# Replace out.append with b.emit in function bodies
# This is safe: any remaining `out.append` that was NOT in a converted function
# will cause a NameError at import time, which test will catch.
src = src.replace('out.append(', 'b.emit(')

# Also fix any remaining `b.lines` pass-through patterns
# (some call sites might still use b.lines)
# These should all be converted to just `b`
src = src.replace('b.lines,', 'b,')

# ================================================================
# Option B: Drop _builder suffix from 7 functions
# ================================================================

rename_pairs = [
    ('_emit_function_builder', '_emit_function'),
    ('_emit_static_dispatch_builder', '_emit_static_dispatch'),
    ('_emit_impl_func_builder', '_emit_impl_func'),
    ('_emit_overload_dispatch_builder', '_emit_overload_dispatch'),
    ('_emit_flat_dispatch_builder', '_emit_flat_dispatch'),
    ('_emit_c_call_builder', '_emit_c_call'),
    ('_emit_module_init_builder', '_emit_module_init'),
]

for old_name, new_name in rename_pairs:
    # Rename calls
    src = src.replace(old_name + '(', new_name + '(')
    # Also rename definition patterns
    src = src.replace('def ' + old_name + '(', 'def ' + new_name + '(')

# Remove the appendix version of _emit_module_init since it's now a duplicate
# (the renamed _emit_module_init_builder becomes the new _emit_module_init)
# Find and remove the appendix version

# ================================================================
# Option C: Reorganize appendix into labeled sections
# ================================================================

# The appendix starts at a comment marker. Find it and reorganize.
# We'll add section headers above each function group.

section_groups = [
    # (section title, list of function names in order)
    ('Expression transpilation', [
        '_FORMAT_TO_CTYPE', '_FORMAT_CHAR_TO_NAME',
        '_is_ptr_expr', '_expr_is_count_or_len',
        '_expr_refers_to', '_expr_to_c', '_expr_to_source',
        '_extract_fmt_from_expr',
    ]),
    ('Expression helpers', [
        '_is_simple_expr', '_build_parse_format',
    ]),
    ('Check emission and diagnostics', [
        '_make_compare_diag', '_make_check_diag',
        '_emit_check', '_emit_default_raise_body',
    ]),
    ('Buffer and wrapper helpers', [
        '_collect_void_ptr_names',
        '_emit_wrapper_locals', '_get_buf_flags',
        '_emit_restrict_checks', '_emit_contiguity_checks',
        '_emit_wrapper_body',
        '_emit_varargs_wrapper', '_emit_fastcall_wrapper',
    ]),
    ('Module support', [
        '_emit_timing_decls',
        '_emit_constants', '_emit_module_init',
    ]),
    ('Docstring generation', [
        '_derive_param_info', '_overload_map_lines',
        '_mod_doc', '_doc',
    ]),
    ('Invariant checker', [
        '_verify_c_invariants',
        '_check_balanced_braces', '_check_buffer_invariants',
        '_check_one_wrapper', '_check_output_scalar_invariants',
    ]),
    ('String and numeric formatting', [
        '_escape_c_str', '_float_literal',
    ]),
]

# We'll add section headers by finding each function's def and inserting
# a comment before it. We need to insert new lines.
# Rather than trying to parse and reorganize, let's just inject section
# comments as a labeling pass.

# Build a mapping from function name to section title
func_to_section = {}
for title, names in section_groups:
    for name in names:
        func_to_section[name] = title

# Add section headers before each function's def
# We do this from end to start to preserve line positions
lines = src.split('\n')
insertions = []
for i, line in enumerate(lines):
    m = re.match(r'^def (\w+)\(', line)
    if m:
        name = m.group(1)
        if name in func_to_section:
            title = func_to_section[name]
            # Check if there's already a section header above (within 3 lines)
            has_header = False
            for j in range(max(0, i-5), i):
                if '# ---- ' in lines[j]:
                    has_header = True
                    break
            if not has_header:
                insertions.append((i, '\n# ---- ' + title + ' ----'))

# Apply insertions from end to start
for i, text in sorted(insertions, reverse=True):
    lines.insert(i, text)

src = '\n'.join(lines)

# ================================================================
# Write result
# ================================================================

with open('c2py23/generator.py', 'w') as f:
    f.write(src)

print('Generator refactored.')
print('Lines:', src.count('\n'))
print()

# Quick sanity check
try:
    import_pat = r'^from c2py23\.generator import'
    if re.search(import_pat, src, re.MULTILINE):
        print('WARNING: self-import still present!')
    if 'generator_reference' in src:
        print('WARNING: reference import still present!')
    if 'b.lines,' in src or 'b.lines)' in src:
        # Check only in non-comment lines
        for i, l in enumerate(src.split('\n'), 1):
            if 'b.lines' in l and not l.strip().startswith('#') and 'b.emit' not in l:
                print('WARNING: remaining b.lines at line %d: %s' % (i, l.strip()[:80]))
    if re.search(r'def _emit_\w+_builder\(', src):
        print('WARNING: _builder functions remain!')
    if '_emit_varargs_wrapper_builder_DELETEME' in src:
        print('NOTE: marker still present (should be deleted)')
    print('Sanity check complete.')
except Exception as e:
    print('Sanity check failed:', e)
