#!/bin/bash
# tests/test_all_wasm.sh -- build and test all c2py23 modules in Pyodide/WASM
#
# Prerequisites (one-time setup):
#   sudo apt install nodejs npm emscripten
#   cd tests/wasm/pyodide_pkg && npm install
#   pip install -e .
#
# Usage:
#   bash tests/test_all_wasm.sh
#
# Environment:
#   CC        emcc path (auto-detected if unset: system emcc, then xbuildenv)
#   WASM_OUT  output directory (default: /tmp/c2py_wasm_test)
set -e

cd "$(dirname "$0")/.."
ROOT="$PWD"

echo "=== c2py23 WASM/Pyodide test suite ==="

# ---- Prerequisites ----
NODE_RUNNER="$ROOT/tests/run_wasm_tests.js"
PYODIDE_LIB="$ROOT/tests/wasm/pyodide_pkg/node_modules/pyodide"

if [ ! -f "$PYODIDE_LIB/package.json" ]; then
    echo "ERROR: Pyodide npm package not found."
    echo "  Fix:  cd tests/wasm/pyodide_pkg && npm install"
    exit 1
fi
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js not found. Install: sudo apt install nodejs"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 1; }
echo "  node:    $(node --version)"
echo "  python:  $(python3 --version)"

# ---- Find emcc ----
if [ -z "$CC" ] || ! command -v "$CC" >/dev/null 2>&1; then
    CC=""
    # 1. System emcc
    if command -v emcc >/dev/null 2>&1; then
        CC="$(command -v emcc)"
    fi
    # 2. Pyodide xbuildenv (Emscripten 3.1.58)
    if [ -z "$CC" ]; then
        xbdir=""
        if xbdir=$(python3 -c "from pyodide_build.build_env import default_xbuildenv_path; print(default_xbuildenv_path())" 2>/dev/null) \
           && [ -f "$xbdir/0.27.2/emsdk/emsdk_env.sh" ]; then
            # shellcheck source=/dev/null
            source "$xbdir/0.27.2/emsdk/emsdk_env.sh" 2>/dev/null
            CC="$(command -v emcc 2>/dev/null || true)"
        fi
    fi
fi

if [ -z "$CC" ] || ! command -v "$CC" >/dev/null 2>&1; then
    cat >&2 <<'EOF'
ERROR: emcc (Emscripten) not found.

Install one of:
  sudo apt install emscripten
  # or via emsdk:
  #   git clone https://github.com/emscripten-core/emsdk.git
  #   cd emsdk && ./emsdk install latest && ./emsdk activate latest
  #   source ./emsdk_env.sh
  # or use the CC env var:
  #   CC=/path/to/emcc bash tests/test_all_wasm.sh
EOF
    exit 1
fi
export CC="$CC"
echo "  emcc:    $($CC --version | head -1)"
echo ""

# ---- Build all WASM modules ----
WASM_OUT="${WASM_OUT:-/tmp/c2py_wasm_test}"
rm -rf "$WASM_OUT" 2>/dev/null || true
mkdir -p "$WASM_OUT"

_parse_c2py() {
    python3 -c "
from c2py23.parser import load_c2py
import os
m = load_c2py('$1')
print(m.name)
for s in m.sources:
    print(s)
for h in m.headers:
    # only .c headers need to be compiled
    if h.endswith('.c'):
        print(h)
"
}

build_one() {
    local c2py="$1"
    local out="$2"
    local label
    label="$(basename "$out" .wasm)"
    local c2py_dir
    c2py_dir="$(dirname "$c2py")"

    # Parse module name and source files from .c2py
    local parsed
    parsed=$(_parse_c2py "$c2py" 2>/dev/null) || true
    if [ -z "$parsed" ]; then
        printf "  %-22s" "$label"
        echo " FAIL (parse c2py)"
        return 1
    fi
    local mod_name="${parsed%%$'\n'*}"
    local source_list="${parsed#*$'\n'}"
    local wrapper="$c2py_dir/${mod_name}_wrapper.c"

    printf "  %-22s" "$mod_name"
    local logfile="/tmp/_build_${mod_name}.log"

    # 1. Generate wrapper (module name from c2py, not label)
    if ! python3 -m c2py23 "$c2py" -o "$wrapper" >"$logfile" 2>&1; then
        echo " FAIL (generate)"
        cat "$logfile"
        rm -f "$logfile"
        return 1
    fi

    # 2. Collect all source files
    local runtime="$ROOT/c2py23/runtime/c2py_runtime.c"
    local includes="-I $ROOT/c2py23/runtime -I $c2py_dir"
    local src_files=""
    for src in $source_list; do
        local sp="$c2py_dir/$src"
        if [ ! -f "$sp" ]; then
            sp="$ROOT/$src"
        fi
        src_files="$src_files $sp"
    done

    # 3. Compile with emcc for WASM
    if "$CC" -s SIDE_MODULE=1 $includes "$runtime" "$wrapper" $src_files -o "$out" >>"$logfile" 2>&1; then
        echo " OK"
        rm -f "$logfile"
        return 0
    else
        echo " FAIL (compile)"
        cat "$logfile"
        rm -f "$logfile"
        return 1
    fi
}

echo "Building 23 WASM modules..."
CASES="$ROOT/tests/cases"
BENCH="$ROOT/benchmarks/src"
FAILED_BUILDS=0

# 17 uniform test modules (order matches test runner)
for pair in \
    "fill|$CASES/fill/fill.c" \
    "arraysum|$CASES/arraysum/arraysum.c" \
    "dot|$CASES/dot/dot.c2py" \
    "types|$CASES/types/types.c2py" \
    "optional|$CASES/optional/optional.c2py" \
    "scalar_output|$CASES/scalar_output/stats.c2py" \
    "template|$CASES/template/template.c2py" \
    "constants|$CASES/constants/constants.c2py" \
    "docstring|$CASES/docstring/docstring.c2py" \
    "timing|$CASES/timing/timing.c2py" \
    "typedispatch|$CASES/typedispatch/typedispatch.c2py" \
    "address|$CASES/address/address.c2py" \
    "array_sig|$CASES/array_sig/array_sig.c2py" \
    "simd_dispatch|$CASES/simd_dispatch/simd_fill.c2py" \
    "freethreading|$CASES/freethreading/freethread.c2py" \
    "transform|$CASES/transform/transform.c2py" \
    "gil_release|$CASES/gil_release/sleep_fill.c2py" \
; do
    label="${pair%%|*}"
    c2py="${pair##*|}"
    build_one "$c2py" "$WASM_OUT/$label.wasm" || FAILED_BUILDS=$((FAILED_BUILDS + 1))
done

# 6 benchmark modules (ndarray backend tests)
for pair in \
    "c2py_vnorm|$BENCH/c2py_vnorm.c2py" \
    "c2py_vnorm_bare|$BENCH/c2py_vnorm_bare.c2py" \
    "c2py_vnorm_ndarray|$BENCH/c2py_vnorm_ndarray.c2py" \
    "c2py_vnorm_buffer|$BENCH/c2py_vnorm_buffer.c2py" \
    "c2py_vnorm_dlpack|$BENCH/c2py_vnorm_dlpack.c2py" \
    "c2py_getitem|$BENCH/c2py_getitem.c2py" \
; do
    label="${pair%%|*}"
    c2py="${pair##*|}"
    build_one "$c2py" "$WASM_OUT/$label.wasm" || FAILED_BUILDS=$((FAILED_BUILDS + 1))
done

echo ""
if [ "$FAILED_BUILDS" -gt 0 ]; then
    echo "ERROR: $FAILED_BUILDS build(s) failed"
    exit 1
fi
echo "  All 23 modules built"
echo ""

# ---- Run tests in Pyodide (Node.js) ----
echo "=== Running tests in Pyodide ==="
echo ""

NODE_DIR="$ROOT/tests/wasm/pyodide_pkg"
(
    cd "$NODE_DIR"
    NODE_PATH="$NODE_DIR/node_modules" node "$ROOT/tests/run_wasm_tests.js"
)
EXIT=$?

echo ""
if [ "$EXIT" -eq 0 ]; then
    echo "=== ALL TESTS PASSED ==="
else
    echo "=== SOME TESTS FAILED (exit code $EXIT) ==="
fi

rm -rf "$WASM_OUT"
exit "$EXIT"
