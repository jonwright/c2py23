#!/bin/bash
# ppc64le-test.sh - run c2py23 test suite on a ppc64le machine
# Prerequisites: gcc, python3 (>= 3.11), git, wget or curl
# Usage: bash ppc64le-test.sh

set -euo pipefail

REPO_URL="https://github.com/jonwright/c2py23.git"
BRANCH="issue-25"
SILX="https://www.silx.org/pub/wheelhouse"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/ppc64le_venv"

# ---- python venv ----
if [ ! -x "$VENV/bin/python" ]; then
    echo "Creating virtualenv at $VENV ..."
    python3 -m venv "$VENV"
fi
. "$VENV/bin/activate"
echo "Using: $(which python3) ($(python3 --version))"

# ---- clone ----
if [ -d "$SCRIPT_DIR/c2py23_test" ]; then
    echo "Updating existing clone ..."
    (cd "$SCRIPT_DIR/c2py23_test" && git fetch origin && git checkout "$BRANCH" && git pull origin "$BRANCH")
else
    echo "Cloning c2py23 $BRANCH ..."
    git clone -b "$BRANCH" --recurse-submodules "$REPO_URL" "$SCRIPT_DIR/c2py23_test"
fi
cd "$SCRIPT_DIR/c2py23_test"

# ---- install c2py23 + pytest ----
echo "Installing c2py23 ..."
pip install -e . --quiet
pip install pytest --quiet

# ---- numpy (silx wheelhouse, expired SSL cert) ----
DOWNLOADER=""
if command -v wget &>/dev/null; then
    DOWNLOADER="wget"
elif command -v curl &>/dev/null; then
    DOWNLOADER="curl"
else
    echo "ERROR: need wget or curl"
    exit 1
fi

echo "Looking for numpy wheel at $SILX ..."
if [ "$DOWNLOADER" = "wget" ]; then
    INDEX_HTML=$(wget --no-check-certificate -qO- "$SILX/" 2>/dev/null || true)
else
    INDEX_HTML=$(curl -k -s "$SILX/" 2>/dev/null || true)
fi

NUMPY_WHL=$(echo "$INDEX_HTML" | grep -oP 'href="\K\.?/?[^"]*numpy-[^"]*cp311[^"]*ppc64le[^"]*\.whl' | head -1 | sed 's|^\./||' || true)

if [ -n "$NUMPY_WHL" ]; then
    echo "  found: $NUMPY_WHL"
    NUMPY_DST="/tmp/$NUMPY_WHL"
    if [ "$DOWNLOADER" = "wget" ]; then
        wget --no-check-certificate -q "$SILX/$NUMPY_WHL" -O "$NUMPY_DST" 2>/dev/null || true
    else
        curl -k -s "$SILX/$NUMPY_WHL" -o "$NUMPY_DST" 2>/dev/null || true
    fi
    if [ -f "$NUMPY_DST" ]; then
        pip install "$NUMPY_DST" --quiet
        rm -f "$NUMPY_DST"
        echo "  numpy installed"
    else
        echo "  WARNING: download failed"
    fi
else
    echo "  WARNING: numpy wheel not found at silx wheelhouse"
    echo "  Tests requiring numpy will be skipped (peer_review, aos_soa)"
fi

# ---- run tests ----
echo ""
echo "Running c2py23 test suite ..."
pytest tests/ -v --tb=short
