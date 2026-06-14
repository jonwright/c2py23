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
VENV_DIR="$SCRIPT_DIR/test_venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info[0])" 2>/dev/null || echo "3")
    if [ "$MAJOR" = "2" ]; then
        # Python 2.7 uses virtualenv
        virtualenv "$VENV_DIR" 2>/dev/null || "$PYTHON" -m virtualenv "$VENV_DIR" 2>/dev/null || {
            echo "ERROR: Could not create venv. Install virtualenv for Python 2.7."
            exit 1
        }
    else
        # Python 3.x uses venv
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

# Build all test modules
echo ""
echo "Building test modules..."
for c2py_file in "$SCRIPT_DIR"/cases/*/*.c2py; do
    echo "  Building: $c2py_file"
    c2py23 build "$c2py_file"
done

# Run tests
echo ""
echo "Running tests..."
cd "$SCRIPT_DIR"
python test_uniform.py

echo ""
echo "=== All tests complete ==="
