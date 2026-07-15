#!/usr/bin/env bash
# run_tests.sh - Build and test c2py23 for one Python version
# Usage: bash run_tests.sh [python_binary]
#
# This script:
# 1. Creates a virtual environment (if needed)
# 2. Installs c2py23 as a package
# 3. Builds all .so modules from .c2py files
# 4. Runs the uniform test suite
set -e

PYTHON="${1:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== c2py23 test runner ==="
echo "Python: $($PYTHON --version 2>&1)"
echo "Script dir: $SCRIPT_DIR"
echo "Project dir: $PROJECT_DIR"

# Create and activate virtual environment
PYVER=$("$PYTHON" -c "import sys; print('%d.%d' % (sys.version_info[0], sys.version_info[1]))" 2>/dev/null || echo "unknown")
IS_FT=$("$PYTHON" -c "import sysconfig; print(1 if sysconfig.get_config_var('Py_GIL_DISABLED') else 0)" 2>/dev/null || echo "0")

if [ "$IS_FT" = "1" ]; then
    # Free-threaded Python (3.14t): skip venv entirely.
    # uv-installed 3.14t venvs cannot find the stdlib; install and run
    # directly using --break-system-packages.
    echo "Free-threaded Python detected -- skipping venv, installing directly"
    "$PYTHON" -m pip install --break-system-packages -e "$PROJECT_DIR" 2>&1 | tail -3
    "$PYTHON" -m pip install --break-system-packages PyYAML pytest 2>&1 | tail -3
else
    VENV_DIR="$SCRIPT_DIR/test_venv_${PYVER}"
    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating virtual environment at $VENV_DIR..."
        rm -rf "$VENV_DIR"
        MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info[0])" 2>/dev/null || echo "3")
        if [ "$MAJOR" = "2" ]; then
            # Python 2.7 uses virtualenv
            virtualenv "$VENV_DIR" 2>/dev/null || "$PYTHON" -m virtualenv "$VENV_DIR" 2>/dev/null || {
                echo "ERROR: Could not create venv. Install virtualenv for Python 2.7."
                exit 1
            }
        else
            "$PYTHON" -m venv "$VENV_DIR"
        fi
    fi

    # Activate
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
    else
        echo "ERROR: venv activate script not found"
        exit 1
    fi

    echo "Installing c2py23..."
    pip install -e "$PROJECT_DIR" 2>&1 | tail -3
    pip install PyYAML pytest 2>&1 | tail -3
fi

# Helper: run c2py23 build with the right python for FT vs normal
_c2py_build() {
    local c2py_path="$1"
    shift
    if [ "$IS_FT" = "1" ]; then
        "$PYTHON" -m c2py23.cli build "$c2py_path" "$@"
    else
        c2py23 build "$c2py_path" "$@"
    fi
}

# Build all test modules
echo ""
echo "Building test modules..."
for c2py_file in "$SCRIPT_DIR"/cases/*/*.c2py; do
    echo "  Building: $c2py_file"
    _c2py_build "$c2py_file"
done

# Build examples
echo ""
echo "Building examples..."

echo "  Building: kissfft_wrap"
_c2py_build "$PROJECT_DIR/examples/kissfft_wrap/kissfft.c2py"

echo "  Building: lz4_wrap"
_c2py_build "$PROJECT_DIR/examples/lz4_wrap/lz4.c2py"

echo "  Building: simd_dispatch"
cd "$PROJECT_DIR/examples/simd_dispatch"
gcc -c -O3 -Wall -Werror -fPIC -ffast-math -mavx512f -DKERNEL_FN=poly_f32_avx512 poly_kernel.c -o poly_f32_avx512.o
gcc -c -O3 -Wall -Werror -fPIC -ffast-math -mavx2 -DKERNEL_FN=poly_f32_avx2 poly_kernel.c -o poly_f32_avx2.o
gcc -c -O3 -Wall -Werror -fPIC -ffast-math -DKERNEL_FN=poly_f32_scalar poly_kernel.c -o poly_f32_scalar.o
MACHINE=$(uname -m | sed 's/x86_64/x86_64/;s/aarch64/aarch64/;s/ppc64le/ppc64le/')
mkdir -p polysimd
rm -f polysimd/_polysimd.c2py23-*.so
_c2py_build polysimd.c2py -o "polysimd/_polysimd.c2py23-linux_${MACHINE}.so"
cd "$PROJECT_DIR"

echo "  Building: threading_bench"
CFLAGS="-fopenmp" _c2py_build "$PROJECT_DIR/examples/threading_bench/mc_pi.c2py"

# Run tests
RUN_PY="python"
if [ "$IS_FT" = "1" ]; then
    RUN_PY="$PYTHON"
fi
echo ""
echo "Running tests..."
cd "$SCRIPT_DIR"
$RUN_PY test_uniform.py

# Run peer review tests (alias + contiguity, numpy required)
echo ""
echo "Running peer review tests..."
if [ "$IS_FT" = "1" ]; then
    "$PYTHON" -m pip install --break-system-packages numpy 2>&1 | tail -1 || echo "(numpy install skipped)"
else
    pip install numpy 2>&1 | tail -1 || echo "(numpy install skipped - tests will SKIP)"
fi
$RUN_PY test_peer_review.py

# Run regression tests for referee report bug fixes
echo ""
echo "Running regression tests..."
$RUN_PY test_regression_fixes.py

# Run error path refcount tests
echo ""
echo "Running error path refcount tests..."
$RUN_PY test_error_paths.py

# Run leak stress test
echo ""
echo "Running leak stress test..."
$RUN_PY test_leaks.py

# Build benchmark modules and run ndarray/DLPack backend tests
echo ""
echo "Running ndarray backend tests..."
(cd "$PROJECT_DIR/benchmarks" && make all 2>&1 | tail -1) || echo "(benchmark build skipped)"
PYTHONPATH="$PROJECT_DIR/benchmarks/build" $RUN_PY test_ndarray_backends.py

# Run lifecycle tests (re-import, concurrent import, subinterpreters)
echo ""
echo "Running lifecycle tests..."
$RUN_PY test_lifecycle.py

# Run example tests
echo ""
echo "Running example tests..."
cd "$PROJECT_DIR"
echo "  Test: kissfft_wrap"
$RUN_PY examples/kissfft_wrap/example.py
echo "  Test: lz4_wrap"
$RUN_PY examples/lz4_wrap/example.py
echo "  Test: simd_dispatch"
$RUN_PY examples/simd_dispatch/test_polysimd.py
echo "  Test: threading_bench"
$RUN_PY examples/threading_bench/bench_mc_pi.py

echo ""
echo "=== All tests complete ==="
