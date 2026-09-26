#!/bin/bash
# brainstorm/tests/setup_pypy.sh -- install PyPy deps for cross-platform benchmarks
set -e
echo "=== Setting up PyPy for benchmark reproduction ==="
echo "PyPy binary should already be installed (apt install pypy3 pypy3-dev)"
pypy3 --version
echo ""
echo "Installing numpy for PyPy..."
pypy3 -m pip install --force-reinstall numpy --break-system-packages
echo ""
echo "PyPy setup complete."
echo "Run: bash run_all.sh && python3 run_bench.py"
