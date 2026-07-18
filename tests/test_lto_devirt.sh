#!/bin/bash
# tests/test_lto_devirt.sh -- Prove LTO devirtualizes C2PY function pointers
# See tests/test_lto_devirt.md for documentation and benchmark results.
# Local-only  --  not in CI (depends on GCC -flto semantics + objdump).
set -e

cd "$(dirname "$0")/.."
WASM_DIR="/tmp/c2py_lto_test"
rm -rf "$WASM_DIR"
mkdir -p "$WASM_DIR"

echo "=== LTO Devirtualization Test ==="

# Generate the wrapper once
python3 -m c2py23.cli generate tests/cases/fill/fill.c2py \
    -o "$WASM_DIR/fill_wrapper.c" 2>/dev/null
WRAPPER="$WASM_DIR/fill_wrapper.c"
RUNTIME="c2py23/runtime/c2py_runtime.c"
FILL_C="tests/cases/fill/fill.c"
INCLUDES="-I c2py23/runtime -I tests/cases/fill"

# ---- Build 1: Nimpy, -O2 (no LTO) ----
echo ""
echo "--- Nimpy -O2 ---"
gcc -S -O2 $INCLUDES "$WRAPPER" -o "$WASM_DIR/fill_nimpy.s" 2>/dev/null
NIMPY_INDIRECT=$(grep -c "call.*\*%r" "$WASM_DIR/fill_nimpy.s" || true)
echo "  Indirect calls (call *%r..): $NIMPY_INDIRECT"

# ---- Build 2: Pythonh, -O2 (no LTO) ----
echo ""
echo "--- Pythonh -O2 ---"
PY_INC=$(python3-config --includes)
gcc -S -DC2PY_USE_PYTHON_H -O2 $PY_INC $INCLUDES \
    "$WRAPPER" -o "$WASM_DIR/fill_ph_o2.s" 2>/dev/null
PH_O2_INDIRECT=$(grep -c "call.*\*%r" "$WASM_DIR/fill_ph_o2.s" || true)
echo "  Indirect calls (call *%r..): $PH_O2_INDIRECT"

# ---- Build 3: Pythonh, -O2 -flto (wholetarogram) ----
echo ""
echo "--- Pythonh -O2 -flto ---"
# Compile wrapper to LTO object
gcc -c -DC2PY_USE_PYTHON_H -O2 -flto $PY_INC $INCLUDES \
    "$WRAPPER" -o "$WASM_DIR/wrapper.o" 2>/dev/null
gcc -c -DC2PY_USE_PYTHON_H -O2 -flto $PY_INC $INCLUDES \
    "$RUNTIME" -o "$WASM_DIR/runtime.o" 2>/dev/null
gcc -c -O2 -flto $INCLUDES \
    "$FILL_C" -o "$WASM_DIR/fill.o" 2>/dev/null
# Link with LTO, dump assembly
gcc -shared -flto -O2 \
    "$WASM_DIR/wrapper.o" "$WASM_DIR/runtime.o" "$WASM_DIR/fill.o" \
    -lm $(python3-config --ldflags --embed 2>/dev/null || python3-config --ldflags) \
    -o "$WASM_DIR/fill_ph_lto.so" 2>/dev/null
objdump -d "$WASM_DIR/fill_ph_lto.so" > "$WASM_DIR/fill_ph_lto.s" 2>/dev/null
# Count indirect calls but exclude glibc stubs (__gmon_start__, PLT)
PH_LTO_INDIRECT=$(grep -c "call.*\*%r" "$WASM_DIR/fill_ph_lto.s" || true)
PH_LTO_INDIRECT_REAL=$(grep -c "call.*\*%r" "$WASM_DIR/fill_ph_lto.s" || true)
# Exclude glibc _init stub  --  it calls __gmon_start__@Base via *%rax
GLIBC_STUB=$(grep -B3 "call.*\*%r" "$WASM_DIR/fill_ph_lto.s" | grep -c "__gmon_start__" || true)
PH_LTO_INDIRECT_REAL=$((PH_LTO_INDIRECT - GLIBC_STUB))
PH_LTO_DIRECT=$(grep -c "call.*<Py[A-Z]" "$WASM_DIR/fill_ph_lto.s" || true)
echo "  Indirect calls (call *%r..):       $PH_LTO_INDIRECT"
echo "  Indirect calls (excl. glibc):      $PH_LTO_INDIRECT_REAL"
echo "  Direct CPython calls:              $PH_LTO_DIRECT"

# ---- Verify ----
echo ""
echo "=== Results ==="
PASS=0
FAIL=0

# Nimpy must have indirect calls (that's how dlsym works)
if [ "$NIMPY_INDIRECT" -gt 0 ]; then
    echo "PASS: Nimpy has $NIMPY_INDIRECT indirect calls (dlsym function pointers)"
    PASS=$((PASS + 1))
else
    echo "FAIL: Nimpy has ZERO indirect calls  --  expected >0"
    FAIL=$((FAIL + 1))
fi

# Pythonh -O2 has indirect calls (compiler can't prove immutability cross-TU)
if [ "$PH_O2_INDIRECT" -gt 0 ]; then
    echo "PASS: Pythonh -O2 has $PH_O2_INDIRECT indirect calls (no cross-TU proof)"
    PASS=$((PASS + 1))
else
    echo "PASS: Pythonh -O2 has zero indirect calls (compiler devirtualized anyway)"
    PASS=$((PASS + 1))
fi

# Pythonh+LTO must have zero (or near-zero) C2PY indirect calls
if [ "$PH_LTO_INDIRECT_REAL" -eq 0 ]; then
    echo "PASS: Pythonh+LTO has 0 C2PY indirect calls (all devirtualized)"
    PASS=$((PASS + 1))
else
    echo "FAIL: Pythonh+LTO has $PH_LTO_INDIRECT_REAL C2PY indirect calls  --  expected 0"
    FAIL=$((FAIL + 1))
fi

# Pythonh+LTO must have direct CPython API calls
if [ "$PH_LTO_DIRECT" -gt 2 ]; then
    echo "PASS: Pythonh+LTO has $PH_LTO_DIRECT direct CPython calls"
    PASS=$((PASS + 1))
else
    echo "FAIL: Pythonh+LTO has only $PH_LTO_DIRECT direct CPython calls  --  expected >=3"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "$PASS passed, $FAIL failed"

# ---- Bonus: show actual call sites with interleaved source ----
echo ""
echo "=== Call site detail ==="

# Build pythonh+LTO with debug symbols + interleaved source
gcc -c -g -DC2PY_USE_PYTHON_H -O2 -flto $PY_INC $INCLUDES \
    "$WRAPPER" -o "$WASM_DIR/wd.o" 2>/dev/null
gcc -c -g -DC2PY_USE_PYTHON_H -O2 -flto $PY_INC $INCLUDES \
    "$RUNTIME" -o "$WASM_DIR/rd.o" 2>/dev/null
gcc -c -g -O2 -flto $INCLUDES \
    "$FILL_C" -o "$WASM_DIR/fd.o" 2>/dev/null
gcc -shared -g -flto -O2 \
    "$WASM_DIR/wd.o" "$WASM_DIR/rd.o" "$WASM_DIR/fd.o" \
    -lm $(python3-config --ldflags --embed 2>/dev/null || python3-config --ldflags) \
    -o "$WASM_DIR/fill_g.so" 2>/dev/null

# Show the c2py_pin call site in pythonh+LTO: should be direct call
echo ""
echo "--- Pythonh+LTO: c2py_pin() call site ---"
objdump -d -l --no-show-raw-insn "$WASM_DIR/fill_g.so" 2>/dev/null \
    | grep -A8 "c2py_pin" | head -20

echo ""
echo "--- Nimpy -O2: c2py_pin() call site (indirect) ---"
objdump -d -l --no-show-raw-insn "$WASM_DIR/fill_nimpy.s" 2>/dev/null \
    | grep "call\|GetBuffer\|c2py_pin" | head -10

rm -rf "$WASM_DIR"
exit $FAIL
