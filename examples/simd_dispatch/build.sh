#!/usr/bin/env bash
# build.sh - Build polysimd wheel using Makefile + c2py_loader convention.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    for c in python3.12 python3.11 python3.10 python3.9 python3; do
        command -v "$c" >/dev/null 2>&1 && PY="$c" && break
    done
fi

echo "=== polysimd wheel build ==="

# 1. Compile .o files + .so via Makefile
echo "1. Building native .so..."
make PYTHON="$PY" C2PY="$PY -m c2py23.cli"

# 2. Assemble wheel
echo ""
echo "2. Building wheel..."
"$PY" -m pip install -q wheel 2>/dev/null || true
"$PY" setup.py bdist_wheel 2>&1 | tail -3

echo ""
echo "=== Done ==="
ls -la dist/*.whl 2>/dev/null || echo "(no wheel produced)"
echo ""
echo "Wheel tag: py3-none-any"
echo "To test: pip install dist/*.whl && python3 test_polysimd.py"
