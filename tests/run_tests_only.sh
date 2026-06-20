#!/usr/bin/env bash
# run_tests_only.sh - Run c2py23 tests without rebuilding.
# Usage: bash run_tests_only.sh [python_binary]
#
# Expects pre-built .so files in tests/cases/*/ and examples/*/.
# Uses PYTHONPATH so c2py23 package is importable without a venv.
# Each test suite runs independently so a single failure (e.g. Python 2.7
# subprocess.call timeout incompatibility in regression tests) does not
# prevent the remaining suites from running.
set -o pipefail

PYTHON="${1:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
ALL_PASS=0

echo "=== c2py23 test-only ==="
echo "Python: $($PYTHON --version 2>&1)"

# Ensure PyYAML is available (needed by test_regression_fixes.py -> parser -> yaml).
if "$PYTHON" -c "import yaml" 2>/dev/null; then
    echo "PyYAML already available"
else
    echo "Installing PyYAML..."
    "$PYTHON" -m pip install --break-system-packages pyyaml 2>/dev/null || \
    "$PYTHON" -m pip install pyyaml 2>&1 | tail -3
fi

# Run test suites -- each runs independently
echo ""
echo "Running tests..."
cd "$SCRIPT_DIR"
"$PYTHON" test_uniform.py || ALL_PASS=1

echo ""
echo "Running regression tests..."
"$PYTHON" test_regression_fixes.py || ALL_PASS=1

echo ""
echo "Running error path refcount tests..."
"$PYTHON" test_error_paths.py || ALL_PASS=1

echo ""
echo "Running leak stress test..."
"$PYTHON" test_leaks.py || ALL_PASS=1

echo ""
echo "Running lifecycle tests..."
"$PYTHON" test_lifecycle.py || ALL_PASS=1

# Run example tests
echo ""
echo "Running example tests..."
cd "$PROJECT_DIR"

echo "  Test: kissfft_wrap"
"$PYTHON" examples/kissfft_wrap/example.py || ALL_PASS=1

echo "  Test: lz4_wrap"
"$PYTHON" examples/lz4_wrap/example.py || ALL_PASS=1

echo "  Test: simd_dispatch"
"$PYTHON" examples/simd_dispatch/test_polysimd.py || ALL_PASS=1

echo "  Test: threading_bench"
"$PYTHON" examples/threading_bench/bench_mc_pi.py || ALL_PASS=1

echo ""
if [ "$ALL_PASS" -eq 0 ]; then
    echo "=== All tests complete ==="
else
    echo "=== Some tests FAILED (see above) ==="
fi
exit $ALL_PASS
