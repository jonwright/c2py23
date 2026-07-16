#!/bin/bash
# tests/test_all_wasm.sh -- build all c2py23 test modules for WASM
# then run them in Pyodide via Node.js
set -e
cd "$(dirname "$0")/.."

echo "=== c2py23 WASM/Pyodide smoke test ==="

# Source the xbuildenv Emscripten
XBDIR=$(python3 -c "from pyodide_build.build_env import default_xbuildenv_path; print(default_xbuildenv_path())")
source "$XBDIR/0.27.2/emsdk/emsdk_env.sh" 2>/dev/null

WASM_OUT="/tmp/c2py_wasm_test"
mkdir -p "$WASM_OUT"
CASES_DIR="$PWD/tests/cases"

# Map: label -> [c2py_dir, c2py_file, module_name]
# Names match test_uniform.py expectations
build_one() {
    local label="$1"
    local dir="$2"
    local file="$3"
    local c2py="$CASES_DIR/$dir/$file"
    local out="$WASM_OUT/${label}.wasm"
    echo "  Building $label ($file)..."
    CC=emcc python3 -m c2py23.cli build --target wasm "$c2py" -o "$out" 2>&1 | grep -E "Success|ERROR|WARNING|warning:" || true
}

echo "Building WASM modules..."
build_one "fill"            "fill"            "fill.c2py"
build_one "arraysum"        "arraysum"        "arraysum.c2py"
build_one "dot"             "dot"             "dot.c2py"
build_one "types"           "types"           "types.c2py"
build_one "optional"        "optional"        "optional.c2py"
build_one "scalar_output"   "scalar_output"   "stats.c2py"
build_one "template"        "template"        "sum.c2py"
build_one "constants"       "constants"       "constants.c2py"
build_one "docstring"       "docstring"       "docstring.c2py"
build_one "timing"          "timing"          "timing.c2py"
build_one "typedispatch"    "typedispatch"    "typedispatch.c2py"
build_one "address"         "address"         "address.c2py"
build_one "array_sig"       "array_sig"       "array_sig.c2py"
build_one "simd_dispatch"   "simd_dispatch"   "simd_fill.c2py"
build_one "freethreading"   "freethreading"   "freethread.c2py"
build_one "transform"       "transform"       "transform.c2py"
build_one "gil_release"     "gil_release"     "sleep_fill.c2py"

echo ""
echo "=== Build complete ==="
ls -lh "$WASM_OUT"/*.wasm 2>/dev/null || echo "No .wasm files found"
echo ""
echo "Build output in: $WASM_OUT"
echo ""

echo "=== Running WASM tests in Pyodide (Node.js) ==="
ROOT="$PWD"
(cd "$ROOT/brainstorm/tests" && node "$ROOT/tests/run_wasm_tests.js")
