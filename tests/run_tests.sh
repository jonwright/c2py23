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
fi

# Build all test modules
echo ""
echo "Building test modules..."
BUILD_PY="${IS_FT:+$PYTHON -m}"
for c2py_file in "$SCRIPT_DIR"/cases/*/*.c2py; do
    echo "  Building: $c2py_file"
    if [ "$IS_FT" = "1" ]; then
        "$PYTHON" -m c2py23.cli build "$c2py_file"
    else
        c2py23 build "$c2py_file"
    fi
done

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

echo ""
echo "=== All tests complete ==="
