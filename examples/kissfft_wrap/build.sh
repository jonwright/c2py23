#!/bin/bash
set -euo pipefail
# Build the kissfftmod wrapper.
#
# Prerequisites:
#   pip install -e ../..
#   git submodule update --init ../kissfft

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

c2py23 build kissfft.c2py

echo "Build complete. Run: python example.py"
