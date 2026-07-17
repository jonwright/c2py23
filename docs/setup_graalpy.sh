#!/bin/bash
# brainstorm/tests/setup_graalpy.sh -- setup GraalPy for cross-platform benchmarks
set -e
echo "=== Setting up GraalPy for benchmark reproduction ==="
echo ""
echo "1. Download GraalPy binary:"
echo "   wget https://github.com/oracle/graalpython/releases/download/graal-25.1.3/graalpy3.12-community-25.1.3-linux-amd64.tar.gz"
echo "   tar xzf graalpy3.12-community-25.1.3-linux-amd64.tar.gz"
echo "   mv graalpy3.12-community-25.1.3 ../graalpy-install"
echo ""
GRAALPY="../graalpy-install/bin/graalpy"
if [ -x "$GRAALPY" ]; then
    echo "GraalPy found: $($GRAALPY --version 2>&1 | head -1)"
    echo ""
    echo "Installing pip and numpy for GraalPy..."
    $GRAALPY -m ensurepip 2>/dev/null || true
    $GRAALPY -m pip install "numpy<2.0" 2>&1 | tail -3
else
    echo "GraalPy not found at $GRAALPY"
    echo "Please download and extract to brainstorm/graalpy-install/"
fi
echo ""
echo "GraalPy setup complete."
echo "Run: bash run_all.sh && python3 run_bench.py"
