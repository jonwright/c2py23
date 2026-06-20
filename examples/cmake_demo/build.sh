#!/usr/bin/env bash
# build.sh - Build arraysum wheel using cmake + c2py_loader convention.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PY="${PYTHON:-python3}"
for c in "$PY" python3.12 python3.11 python3.10 python3.9 python3; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
done

echo "=== arraysum (cmake) wheel build ==="

# 1. Generate wrapper + build .so via cmake
echo "1. Building with cmake..."
cmake -B builddir -S . 2>&1 | tail -1
cmake --build builddir 2>&1 | tail -1

# 2. Assemble wheel
echo ""
echo "2. Building wheel..."
"$PY" setup.py bdist_wheel 2>&1 | tail -3

echo ""
echo "=== Done ==="
ls -la dist/*.whl 2>/dev/null || echo "(no wheel produced)"
