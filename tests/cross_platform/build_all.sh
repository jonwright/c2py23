#!/bin/bash
# brainstorm/tests/run_all.sh -- build and run gold benchmarks on all platforms
set -e
cd "$(dirname "$0")"

BENCH="../../benchmarks/src"
GRAALPY="../graalpy-install/bin/graalpy"
GRAALPY_INC=$($GRAALPY -c "import sysconfig; print(sysconfig.get_config_var('INCLUDEPY'))")

echo "=== Cleaning ===" && rm -f gold_*.so gold_*.wasm

echo "=== Building ==="
echo "--- CPython ---"
gcc -O2 -fPIC $(python3-config --includes) $(python3-config --ldflags) -shared -o gold_noargs.cpython-312-x86_64-linux-gnu.so $BENCH/gold_noargs.c
gcc -O2 -fPIC $(python3-config --includes) $(python3-config --ldflags) -shared -o gold_vnorm.cpython-312-x86_64-linux-gnu.so $BENCH/gold_vnorm.c -lm

echo "--- PyPy ---"
gcc -O2 -fPIC -I/usr/include/pypy3.9 -shared -o gold_noargs.pypy39-pp73-x86_64-linux-gnu.so $BENCH/gold_noargs.c
gcc -O2 -fPIC -I/usr/include/pypy3.9 -shared -o gold_vnorm.pypy39-pp73-x86_64-linux-gnu.so $BENCH/gold_vnorm.c -lm

echo "--- GraalPy ---"
gcc -O2 -fPIC -I$GRAALPY_INC -shared -o gold_noargs.graalpy250-312-native-x86_64-linux.so $BENCH/gold_noargs.c
gcc -O2 -fPIC -I$GRAALPY_INC -shared -o gold_vnorm.graalpy250-312-native-x86_64-linux.so $BENCH/gold_vnorm.c -lm

echo "--- Pyodide (WASM) ---"
XBDIR=$(python3 -c "import pyodide_build; from pyodide_build.build_env import _get_xbuildenv_path; print(_get_xbuildenv_path())")
source "$XBDIR/emsdk/emsdk_env.sh" 2>/dev/null
PYROOT=$XBDIR/xbuildenv/pyodide-root/cpython/installs/python-3.12.7
emcc -O2 -s SIDE_MODULE=1 -I$PYROOT/include/python3.12 -o gold_noargs.wasm $BENCH/gold_noargs.c
emcc -O2 -s SIDE_MODULE=1 -I$PYROOT/include/python3.12 -o gold_vnorm.wasm $BENCH/gold_vnorm.c -lm

echo && echo "=== Built ===" && ls -la gold_* && echo

echo "=== Running benchmarks ==="
python3 run_bench.py
