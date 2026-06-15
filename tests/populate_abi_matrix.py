#!/usr/bin/env python3
"""Populate tests/abi_matrix.json by running check_abi.c inside each
snakepit container for all supported Python versions.

Requires: snakepit containers in ../snakepit/ and Apptainer installed.
"""
from __future__ import print_function

import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SNAKEPIT_DIR = os.path.join(os.path.dirname(PROJECT_DIR), 'snakepit')
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, 'test_workspace')
MATRIX_FILE = os.path.join(SCRIPT_DIR, 'abi_matrix.json')
CHECK_ABI_C = os.path.join(SCRIPT_DIR, 'check_abi.c')

PYTHON_VERSIONS = [
    ("2.7",  "ubuntu20.04.sif"),
    ("3.6",  "debian10.sif"),
    ("3.7",  "ubuntu24.04.sif"),
    ("3.8",  "ubuntu20.04.sif"),
    ("3.9",  "ubuntu24.04.sif"),
    ("3.10", "ubuntu24.04.sif"),
    ("3.11", "ubuntu24.04.sif"),
    ("3.12", "ubuntu24.04.sif"),
    ("3.13", "ubuntu24.04.sif"),
    ("3.14", "ubuntu24.04.sif"),
]


def run_apptainer(sif_file, command):
    sif_path = os.path.join(SNAKEPIT_DIR, sif_file)
    if not os.path.exists(sif_path):
        return 1, "", "SIF file not found: " + sif_path
    cmd = [
        "apptainer", "exec", "-e",
        "-B", WORKSPACE_DIR + ":/workspace",
        "--pwd", "/workspace",
        sif_path,
        "/bin/bash", "-c", command
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8', errors='replace')
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='replace')
        return proc.returncode, stdout, stderr
    except Exception as e:
        return 1, "", str(e)


def prepare_workspace():
    import shutil
    if os.path.exists(WORKSPACE_DIR):
        shutil.rmtree(WORKSPACE_DIR)
    os.makedirs(WORKSPACE_DIR)
    shutil.copy2(CHECK_ABI_C, WORKSPACE_DIR)


def collect_abi(python_version, sif_file):
    py = "python" + python_version
    print("  Collecting ABI for Python %s ..." % python_version)

    # Build and run inside container.
    # Some Python configs omit -lpythonN; add it explicitly if missing.
    build_and_run = (
        "cd /workspace && "
        "CFG=$(echo $(%s-config --includes --ldflags 2>/dev/null)) && "
        "if echo \"$CFG\" | grep -qv -- '-lpython'; then "
        "  CFG=\"$CFG -lpython%s\"; "
        "fi && "
        "gcc -o /tmp/check_abi check_abi.c $CFG -ldl 2>&1 && "
        "/tmp/check_abi 2>&1" % (py, python_version)
    )
    ret, stdout, stderr = run_apptainer(sif_file, build_and_run)

    if ret != 0:
        print("  [FAIL] Python %s: %s" % (python_version, stderr.strip()))
        return None

    # Parse output: CATEGORY label value
    entries = []
    pyver_full = None
    for line in stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        category = parts[0]
        label = parts[1].strip()
        val = parts[2].strip() if len(parts) > 2 else ""
        if category == "PYVER":
            pyver_full = line[len("PYVER "):]
        entries.append((category, label, val))

    if pyver_full is None:
        pyver_full = python_version
    return {"python_version": pyver_full, "entries": entries}


def main():
    if not os.path.exists(SNAKEPIT_DIR):
        print("Error: snakepit directory not found at " + SNAKEPIT_DIR)
        return 1

    print("Populating ABI matrix...")
    prepare_workspace()

    matrix = {}
    arch = "Linux-x86_64"

    for pyver, sif in PYTHON_VERSIONS:
        entry = collect_abi(pyver, sif)
        if entry is None:
            print("  [SKIP] Python %s (build failed)" % pyver)
            continue
        if arch not in matrix:
            matrix[arch] = {}
        abi_entry = {}
        for category, label, val in entry["entries"]:
            abi_entry[category + "_" + label] = val
        matrix[arch][pyver] = {
            "python_version": entry["python_version"],
            "abi": abi_entry
        }
        print("  [OK] Python %s" % pyver)

    # Write output
    with open(MATRIX_FILE, 'w') as f:
        json.dump(matrix, f, indent=2, sort_keys=True)
    print("\nABI matrix written to " + MATRIX_FILE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
