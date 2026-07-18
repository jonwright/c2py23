#!/bin/bash
# tests/test_ph_containers.sh  --  test dlsym + pythonh across snakepit containers
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SNAKEPIT_DIR="$PROJECT_DIR/../snakepit"

PY_VERSIONS=(
    "python2.7|ubuntu20.04.sif|2.7"
    "python3.6|debian10.sif|3.6"
    "python3.7|ubuntu24.04.sif|3.7"
    "python3.8|ubuntu20.04.sif|3.8"
    "python3.9|ubuntu24.04.sif|3.9"
    "python3.10|ubuntu24.04.sif|3.10"
    "python3.11|ubuntu24.04.sif|3.11"
    "python3.12|ubuntu24.04.sif|3.12"
    "python3.13|ubuntu24.04.sif|3.13"
    "python3.14|ubuntu24.04.sif|3.14"
    "python3.14t|ubuntu24.04.sif|3.14t"
    "python3.15|ubuntu26.04.sif|3.15"
    "python3.15t|ubuntu26.04.sif|3.15t"
)

echo "=== c2py23 dlsym + pythonh container test ==="
echo ""

PASS=0
FAIL=0

for entry in "${PY_VERSIONS[@]}"; do
    IFS='|' read -r py sif label <<< "$entry"
    if [ ! -f "$SNAKEPIT_DIR/$sif" ]; then
        printf "  %-6s  SKIP (no %s)\n" "$label" "$sif"
        continue
    fi
    result=$(apptainer exec "$SNAKEPIT_DIR/$sif" bash -c "
mkdir -p /tmp/work && cd /tmp/work
rm -rf /tmp/work/* 2>/dev/null
cp -r '$PROJECT_DIR'/c2py23 '$PROJECT_DIR'/tests '$PROJECT_DIR'/setup.py '$PROJECT_DIR'/pyproject.toml '$PROJECT_DIR'/README.md '/tmp/work/' 2>/dev/null
'$py' -m pip install -e '.' 2>&1 | tail -1 >/dev/null
'$py' -m pip install setuptools wheel 2>&1 | tail -1 >/dev/null
'$py' tests/test_ph_all.py 2>&1
" 2>&1)
    echo "$result"
    if echo "$result" | grep -q "PASS.*PASS"; then
        PASS=$((PASS+1))
    else
        FAIL=$((FAIL+1))
    fi
done

echo ""
echo "$PASS passed, $FAIL failed"
exit $FAIL
