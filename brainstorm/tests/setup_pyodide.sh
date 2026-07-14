#!/bin/bash
# brainstorm/tests/setup_pyodide.sh -- setup Pyodide for cross-platform benchmarks
set -e
echo "=== Setting up Pyodide for benchmark reproduction ==="
echo ""
echo "1. System deps: sudo apt install -y emscripten npm"
echo "2. Node.js deps: npm install pyodide  (done from brainstorm/tests/)"
echo "3. Pyodide build: pyodide xbuildenv install 0.27.2"
echo "4. Emscripten:    pyodide xbuildenv install-emscripten --version 3.1.58"
echo ""

if ! command -v npm &>/dev/null; then
    echo "ERROR: npm not found. sudo apt install -y npm"
    exit 1
fi

if ! command -v pyodide &>/dev/null; then
    echo "ERROR: pyodide not found. pip install pyodide-build --break-system-packages"
    exit 1
fi

# Install node deps if not already done
if [ ! -d "node_modules/pyodide" ]; then
    npm install pyodide
fi

# Check xbuildenv
if ! pyodide xbuildenv version 2>/dev/null | grep -q 0.27; then
    echo "Installing Pyodide xbuildenv..."
    pyodide xbuildenv install 0.27.2
    pyodide xbuildenv install-emscripten --version 3.1.58
fi

echo ""
echo "Pyodide setup complete."
echo "Run: bash run_all.sh && node pyodide_test.js && python3 show_results.py"
