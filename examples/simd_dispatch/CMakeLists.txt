# CMakeLists.txt -- SIMD dispatch example with multi-flag compilation
#
# Demonstrates integrating c2py23 into a CMake build:
#   1. Compile kernel.c multiple times with different -m flags
#   2. Run c2py23 generate to produce the wrapper .c
#   3. Link everything into a shared module (Python extension)
#
# Usage:
#   mkdir build && cd build
#   cmake ..
#   cmake --build .
#   cd .. && python3 test_polysimd.py
#
# Prerequisites:
#   pip install c2py23 cmake
#
# NOTE: This is a build-system demonstration.  The same result can be
# achieved with the simple Makefile or a single `c2py23 build` call.
# This demo is for users integrating c2py23 into an existing CMake project.

cmake_minimum_required(VERSION 3.16)
project(polysimd LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O3 -fPIC -ffast-math")

# Find c2py23
find_program(C2PY23 c2py23 REQUIRED)

# Find runtime files from installed c2py23 package
execute_process(
  COMMAND python3 -c "import c2py23,os;print(os.path.join(os.path.dirname(c2py23.__file__),'runtime'))"
  OUTPUT_VARIABLE C2PY_RUNTIME_DIR
  OUTPUT_STRIP_TRAILING_WHITESPACE
)

# --- Multi-flag compilation ---
add_library(poly_f32_avx512 OBJECT poly_kernel.c)
target_compile_options(poly_f32_avx512 PRIVATE -mavx512f)
target_compile_definitions(poly_f32_avx512 PRIVATE KERNEL_FN=poly_f32_avx512)

add_library(poly_f32_avx2 OBJECT poly_kernel.c)
target_compile_options(poly_f32_avx2 PRIVATE -mavx2)
target_compile_definitions(poly_f32_avx2 PRIVATE KERNEL_FN=poly_f32_avx2)

add_library(poly_f32_scalar OBJECT poly_kernel.c)
target_compile_definitions(poly_f32_scalar PRIVATE KERNEL_FN=poly_f32_scalar)

# --- c2py23 generate ---
add_custom_command(
  OUTPUT polysimd_wrapper.c
  COMMAND ${C2PY23} generate ${CMAKE_CURRENT_SOURCE_DIR}/polysimd.c2py -o polysimd_wrapper.c
  DEPENDS polysimd.c2py
  COMMENT "Generating c2py23 wrapper"
)

# --- Link shared module ---
add_library(polysimd SHARED
  polysimd_wrapper.c
  ${C2PY_RUNTIME_DIR}/c2py_runtime.c
)
target_include_directories(polysimd PRIVATE ${C2PY_RUNTIME_DIR} ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(polysimd PRIVATE ${CMAKE_DL_LIBS} m)
set_target_properties(polysimd PROPERTIES
  PREFIX ""
  SUFFIX ".so"
  LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)
