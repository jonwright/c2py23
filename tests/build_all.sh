#!/usr/bin/env bash
# build_all.sh - Build all .c2py test modules and examples for one Python version.
# Usage: bash build_all.sh [python_binary]
#
# Uses PYTHONPATH instead of a venv so it works on minimal containers like
# manylinux2014 where only the system Python is available.
set -e

PYTHON="${1:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

echo "=== c2py23 build-all ==="
echo "Python: $($PYTHON --version 2>&1)"

# Ensure PyYAML is available.  Use a workspace-local target dir so we
# never touch the system or .local site-packages.
_PIP_TARGET="$SCRIPT_DIR/.test_pip_target"
if "$PYTHON" -c "import yaml" 2>/dev/null; then
    echo "PyYAML already available"
else
    echo "Installing PyYAML (isolated)..."
    rm -rf "$_PIP_TARGET"
    "$PYTHON" -m pip install --target="$_PIP_TARGET" pyyaml 2>&1 | tail -1
    export PYTHONPATH="$_PIP_TARGET:$PYTHONPATH"
fi

# Build all test case modules
echo ""
echo "Building test modules..."
for c2py_file in "$SCRIPT_DIR"/cases/*/*.c2py; do
    echo "  Building: $c2py_file"
    "$PYTHON" -m c2py23.cli build "$c2py_file"
done

# Build examples that produce .so files
echo ""
echo "Building examples..."

echo "  Building: kissfft_wrap"
"$PYTHON" -m c2py23.cli build "$PROJECT_DIR/examples/kissfft_wrap/kissfft.c2py"

echo "  Building: lz4_wrap"
"$PYTHON" -m c2py23.cli build "$PROJECT_DIR/examples/lz4_wrap/lz4.c2py"

echo "  Building: simd_dispatch"
cd "$PROJECT_DIR/examples/simd_dispatch"
gcc -c -O3 -Wall -Werror -fPIC -ffast-math -mavx512f -DKERNEL_FN=poly_f32_avx512 poly_kernel.c -o poly_f32_avx512.o
gcc -c -O3 -Wall -Werror -fPIC -ffast-math -mavx2 -DKERNEL_FN=poly_f32_avx2 poly_kernel.c -o poly_f32_avx2.o
gcc -c -O3 -Wall -Werror -fPIC -ffast-math -DKERNEL_FN=poly_f32_scalar poly_kernel.c -o poly_f32_scalar.o
"$PYTHON" -m c2py23.cli build polysimd.c2py -o polysimd.so
cd "$PROJECT_DIR"

echo "  Building: threading_bench"
CFLAGS="-fopenmp" "$PYTHON" -m c2py23.cli build "$PROJECT_DIR/examples/threading_bench/mc_pi.c2py"

echo ""
echo "=== Build complete ==="
