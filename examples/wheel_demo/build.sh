#!/usr/bin/env bash
# build.sh - Build a c2py23 wheel using the c2py_loader naming convention.
#
#   _arraysum.c2py23-linux_x86_64.so    (on x86_64)
#   _arraysum.c2py23-linux_aarch64.so   (cross-compiled)
#   _arraysum.c2py23-linux_ppc64le.so   (cross-compiled)
#
# Usage:
#   bash build.sh                        # build for host arch, produce wheel
#   bash build.sh --arch linux_aarch64   # cross-compile for aarch64
#   bash build.sh --pack-only            # assemble wheel from pre-built .so files
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

MODULE="arraysum"
PKG_DIR="$MODULE"
C2PY_MODULE="_$MODULE"

# --- parse args ---
ARCH=""
PACK_ONLY=false
while [ $# -gt 0 ]; do
    case "$1" in
        --arch) ARCH="$2"; shift 2 ;;
        --pack-only) PACK_ONLY=true; shift ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

# --- find python ---
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    # manylinux2014: Pythons are /opt/python/cp3X-cp3X/bin/python3.X
    for candidate in python3.12 python3.11 python3.10 python3.9 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            PY="$candidate"; break
        fi
    done
fi

# --- detect platform ---
if [ -z "$ARCH" ]; then
    _OS=$("$PY" -c "import sys; p=sys.platform; print('linux' if p.startswith('linux') else p)")
    _ARCH=$("$PY" -c "import platform; m=platform.machine(); print('x86_64' if m=='AMD64' else m)")
    ARCH="${_OS}_${_ARCH}"
fi

echo "=== c2py23 wheel demo ==="
echo "Target: $ARCH"

if [ "$PACK_ONLY" = false ]; then
    # --- generate wrapper ---
    echo ""
    echo "1. Generating wrapper..."
    "$PY" -m c2py23.cli generate "$MODULE.c2py" -o "${C2PY_MODULE}_wrapper.c"

    # --- find runtime ---
    RUNTIME_DIR=$("$PY" -c "import c2py23, os; print(os.path.join(os.path.dirname(c2py23.__file__), 'runtime'))")

    # --- pick compiler ---
    CC="${CC:-gcc}"
    case "$ARCH" in
        linux_aarch64)  CC="${CC:-aarch64-linux-gnu-gcc}" ;;
        linux_ppc64le)  CC="${CC:-powerpc64le-linux-gnu-gcc}" ;;
        win_amd64)      CC="${CC:-x86_64-w64-mingw32-gcc}" ;;
    esac

    CFLAGS="${CFLAGS:--O3 -Wall -Werror -fPIC}"

    # --- compile ---
    SO_NAME="${C2PY_MODULE}.c2py23-${ARCH}.so"
    echo ""
    echo "2. Compiling $SO_NAME..."
    echo "   $CC -shared $CFLAGS -I $RUNTIME_DIR ... -o $PKG_DIR/$SO_NAME"

    $CC -shared $CFLAGS \
        -I "$RUNTIME_DIR" \
        -o "$PKG_DIR/$SO_NAME" \
        "${C2PY_MODULE}_wrapper.c" \
        "$MODULE.c" \
        "$RUNTIME_DIR/c2py_runtime.c" \
        -ldl -lm

    echo "   -> $PKG_DIR/$SO_NAME"
fi

# --- assemble wheel ---
echo ""
echo "3. Building wheel..."
"$PY" -m pip install -q wheel 2>/dev/null || true
"$PY" setup.py bdist_wheel 2>&1 | tail -3

echo ""
echo "=== Done ==="
ls -la dist/*.whl 2>/dev/null || echo "(no wheel produced)"
echo ""
echo "Wheel tag: py3-none-any"
echo "To test: pip install dist/*.whl && python3 -c 'import $MODULE; print($MODULE.array_sum)'"
