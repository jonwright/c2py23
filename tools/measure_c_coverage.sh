#!/usr/bin/env bash
# Measure C coverage of the c2py23 generated wrappers + runtime via gcov.
#
# Builds every test module with --coverage, runs the pytest suite, then
# aggregates gcov line/branch coverage across all modules into
# tests/coverage_report.md (see tools/measure_c_coverage.py for details).
# Restores a normal (non-instrumented) build afterwards.
#
# Usage:
#   bash tools/measure_c_coverage.sh
#
# Requires: gcc, make, gcov, and a python3 with pytest on PATH.
set -euo pipefail
cd "$(dirname "$0")/.."

export CC=gcc
export CFLAGS="--coverage -O0 -g -Wall"
export LDFLAGS="--coverage"

echo "[c-cov] instrumented build..."
make -f tests/Makefile clean all

echo "[c-cov] running test suite on instrumented modules..."
"${PYTHON:-python3}" tests/runner.py --no-build

echo "[c-cov] aggregating gcov coverage..."
"${PYTHON:-python3}" tools/measure_c_coverage.py

echo "[c-cov] restoring normal build..."
unset CFLAGS LDFLAGS
make -f tests/Makefile clean all

echo "[c-cov] removing gcov artifacts..."
find tests examples benchmarks -name '*.gcno' -o -name '*.gcda' -o -name '*.gcov' 2>/dev/null | xargs -r rm -f

echo "[c-cov] done -- report at tests/coverage_report.md"
