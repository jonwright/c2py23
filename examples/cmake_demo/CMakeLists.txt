cmake_minimum_required(VERSION 3.16)
project(arraysum C)

# --- Platform detection for c2py_loader naming convention ---
execute_process(
  COMMAND python3 -c
    "import sys, platform; p=sys.platform; m=platform.machine(); print('linux_x86_64' if 'linux' in p and m in ('x86_64','AMD64') else f'{p}_{m}')"
  OUTPUT_VARIABLE PLATFORM_KEY
  OUTPUT_STRIP_TRAILING_WHITESPACE
)
set(SO_NAME "_arraysum.c2py23-${PLATFORM_KEY}.so")

# --- Find c2py23 runtime ---
execute_process(
  COMMAND python3 -c
    "import c2py23, os; print(os.path.join(os.path.dirname(c2py23.__file__), 'runtime'))"
  OUTPUT_VARIABLE RUNTIME_DIR
  OUTPUT_STRIP_TRAILING_WHITESPACE
)

# --- Generate wrapper from .c2py ---
add_custom_command(
  OUTPUT _arraysum_wrapper.c
  COMMAND c2py23 generate arraysum.c2py -o _arraysum_wrapper.c
  DEPENDS arraysum.c2py
  COMMENT "c2py23 generate arraysum.c2py"
)

# --- Build the .so with bare name (no EXT_SUFFIX) ---
add_library(_arraysum SHARED
  _arraysum_wrapper.c
  arraysum.c
  ${RUNTIME_DIR}/c2py_runtime.c
)

set_target_properties(_arraysum PROPERTIES
  PREFIX ""
  SUFFIX ".so"
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/arraysum"
  OUTPUT_NAME "${SO_NAME}"
)

target_include_directories(_arraysum PRIVATE
  ${RUNTIME_DIR}
  ${CMAKE_SOURCE_DIR}
)

target_link_libraries(_arraysum PRIVATE dl m)
