# meson.build -- SIMD dispatch example with multi-flag compilation
#
# Demonstrates integrating c2py23 into a meson build:
#   1. Compile kernel.c multiple times with different -m flags
#   2. Run c2py23 generate to produce the wrapper .c
#   3. Link everything into a shared module
#
# Usage:
#   meson setup builddir
#   meson compile -C builddir
#   meson test -C builddir
#
# Prerequisites:
#   pip install c2py23 meson
#
# NOTE: This is a build-system demonstration.  The same result can be
# achieved with the simple Makefile or a single `c2py23 build` call.
# This demo is for users who must integrate c2py23 into an existing
# meson project with custom compilation flags per source file.

project('polysimd', 'c',
  version: '0.1.0',
  default_options: ['warning_level=3', 'buildtype=release'])

cc = meson.get_compiler('c')
c2py = find_program('c2py23', required: true)
python3 = find_program('python3', 'python', required: false)

# Runtime files from the installed c2py23 package
r = run_command(python3, '-c',
  'import c2py23, os; print(os.path.join(os.path.dirname(c2py23.__file__), "runtime"))',
  check: true)
runtime_dir = r.stdout().strip()
runtime_c = join_paths(runtime_dir, 'c2py_runtime.c')
runtime_h = join_paths(runtime_dir, 'c2py_runtime.h')
amd64_h = join_paths(runtime_dir, 'c2py_amd64.h')

cflags = ['-O3', '-fPIC', '-ffast-math']

# --- Multi-flag compilation ---
poly_avx512 = static_library('poly_avx512', 'poly_kernel.c',
  c_args: cflags + ['-DKERNEL_FN=poly_f32_avx512', '-mavx512f'],
  install: false)

poly_avx2 = static_library('poly_avx2', 'poly_kernel.c',
  c_args: cflags + ['-DKERNEL_FN=poly_f32_avx2', '-mavx2'],
  install: false)

poly_scalar = static_library('poly_scalar', 'poly_kernel.c',
  c_args: cflags + ['-DKERNEL_FN=poly_f32_scalar'],
  install: false)

# --- c2py23 generate ---
wrapper_c = custom_target('polysimd_wrapper',
  input: 'polysimd.c2py',
  output: 'polysimd_wrapper.c',
  command: [c2py, 'generate', '@INPUT@', '-o', '@OUTPUT@'])

# --- Link shared module ---
polysimd = shared_module('polysimd',
  wrapper_c, runtime_c,
  link_with: [poly_avx512, poly_avx2, poly_scalar],
  include_directories: include_directories(runtime_dir, '.'),
  dependencies: [cc.find_library('dl', required: false)],
  install: true,
  install_dir: meson.current_source_dir())
