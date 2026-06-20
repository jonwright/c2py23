project('arraysum', 'c')

# --- Platform detection for c2py_loader naming convention ---
r = run_command('python3', '-c',
  'import sys, platform; p=sys.platform; m=platform.machine(); print("linux_x86_64" if "linux" in p and m in ("x86_64","AMD64") else f"{p}_{m}")',
  check: true)
platform_key = r.stdout().strip()
so_name = '_arraysum.c2py23-' + platform_key + '.so'

# --- Find c2py23 runtime ---
r = run_command('python3', '-c',
  'import c2py23, os; print(os.path.join(os.path.dirname(c2py23.__file__), "runtime"))',
  check: true)
runtime_dir = r.stdout().strip()

# --- Generate wrapper from .c2py ---
c2py_wrapper = custom_target('arraysum_wrapper',
  output : '_arraysum_wrapper.c',
  input : 'arraysum.c2py',
  command : ['c2py23', 'generate', '@INPUT@', '-o', '@OUTPUT@'],
)

# --- Build the .so ---
# Using shared_module with bare name (no Python EXT_SUFFIX).
# meson-python would normally use python.extension_module() which
# adds the cpython-312- tag.  Here we want the untagged c2py_loader
# name, so we use shared_module() directly.
shared_module('_arraysum',
  c2py_wrapper,
  'arraysum.c',
  files(runtime_dir / 'c2py_runtime.c'),
  name_prefix : '',
  name_suffix : 'so',
  include_directories : include_directories(runtime_dir, '.'),
  link_args : ['-ldl', '-lm'],
  install : true,
  install_dir : meson.current_source_dir() / 'arraysum',
)

# Rename installed .so to the c2py_loader convention
meson.add_install_script(
  find_program('python3'),
  '-c',
  'import os; ' +
  'src = os.path.join(os.environ["MESON_INSTALL_DESTDIR_PREFIX"], ' +
  '  "arraysum", "_arraysum.so"); ' +
  'dst = os.path.join(os.environ["MESON_INSTALL_DESTDIR_PREFIX"], ' +
  '  "arraysum", "' + so_name + '"); ' +
  'if os.path.exists(src): os.rename(src, dst)',
)
