#!/usr/bin/env bash
# Measure Python-level coverage of the c2py23 code generator/parser/loader
# (c2py23/*.py) using coverage.py.
#
# The generator and parser are pure Python and platform-independent, so a
# single run on any Python exercises almost all of it.  This report shows
# which codegen branches/spec features are not covered by the test suite.
#
# Usage:
#   bash tools/measure_py_coverage.sh
#
# Requires: coverage.py (`pip install coverage`) and python3 with pytest.
set -euo pipefail
cd "$(dirname "$0")/.."

DATA="${COVERAGE_FILE:-.coverage}"
rm -f "$DATA" htmlcov -r 2>/dev/null || true

coverage run --branch -m pytest tests/ -q \
    --ignore=tests/test_all.py \
    --ignore=tests/test_manylinux.py

echo "[py-cov] report:"
coverage report -m --include="c2py23/*" || true
echo "[py-cov] detail at htmlcov/index.html"
coverage html --include="c2py23/*"
