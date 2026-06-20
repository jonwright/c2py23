#!/usr/bin/env bash
# build.sh - Build arraysum wheel using meson + c2py_loader convention.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PY="${PYTHON:-python3}"
for c in "$PY" python3.12 python3.11 python3.10 python3.9 python3; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
done

echo "=== arraysum (meson) wheel build ==="

# 1. Generate wrapper + build .so via meson
echo "1. Building with meson..."
"$PY" -m pip install -q meson meson-python 2>/dev/null || true

meson setup builddir --prefix=/tmp/arraysum_install 2>&1 | tail -1
meson compile -C builddir 2>&1 | tail -1
meson install -C builddir --destdir /tmp/arraysum_destdir 2>&1 | tail -1

# Copy .so from install tree to package dir
cp /tmp/arraysum_destdir/tmp/arraysum_install/arraysum/_arraysum.c2py23-*.so \
   arraysum/ 2>/dev/null || \
cp /tmp/arraysum_destdir/tmp/arraysum_install/arraysum/_arraysum.so \
   arraysum/ 2>/dev/null || true

# 2. Assemble wheel
echo ""
echo "2. Building wheel..."
"$PY" setup.py bdist_wheel 2>&1 | tail -3

echo ""
echo "=== Done ==="
ls -la dist/*.whl 2>/dev/null || echo "(no wheel produced)"
