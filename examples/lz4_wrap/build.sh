#!/bin/bash
set -euo pipefail
# Build the lz4mod wrapper.
#
# Prerequisites:
#   pip install -e ../..
#   git submodule update --init ../lz4

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

c2py23 build lz4.c2py

echo "Build complete. Run: python example.py"
