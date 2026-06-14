#!/usr/bin/env python3
"""
c2py23 test suite across all Python versions via snakepit containers.

Mirrors snakepit's test_images.py pattern:
1. Copies c2py23 project + test cases into workspace
2. For each Python version (2.7-3.14), runs run_tests.sh inside
   the appropriate Apptainer container
3. Collects pass/fail results
"""
from __future__ import print_function

import os
import sys
import shutil
import subprocess
from datetime import datetime

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SNAKEPIT_DIR = os.path.join(os.path.dirname(PROJECT_DIR), 'snakepit')
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, 'test_workspace')
LOG_FILE = os.path.join(SCRIPT_DIR, 'test_results.log')

# Python versions to test
PYTHON_VERSIONS = [
    ("2.7", "ubuntu20.04.sif"),
    ("3.6", "debian10.sif"),
    ("3.7", "ubuntu24.04.sif"),
    ("3.8", "ubuntu20.04.sif"),
    ("3.9", "ubuntu24.04.sif"),
    ("3.10", "ubuntu24.04.sif"),
    ("3.11", "ubuntu24.04.sif"),
    ("3.12", "ubuntu24.04.sif"),
    ("3.13", "ubuntu24.04.sif"),
    ("3.14", "ubuntu24.04.sif"),
]

_log_file = None


def log_write(message):
    if _log_file:
        _log_file.write(message + '\n')
        _log_file.flush()


def print_header(message):
    line = "=" * 70
    print("\n" + line)
    print(message)
    print(line + "\n")
    log_write(line)
    log_write(message)
    log_write(line + '\n')


def print_success(message):
    print("[OK] " + message)
    log_write("[OK] " + message)


def print_error(message):
    print("[FAIL] " + message)
    log_write("[FAIL] " + message)


def print_step(message):
    print(">> " + message)
    log_write(">> " + message)


def run_apptainer(sif_file, command, capture_output=True):
    """Run a command inside an Apptainer container."""
    sif_path = os.path.join(SNAKEPIT_DIR, sif_file)
    if not os.path.exists(sif_path):
        print_error("SIF file not found: {}".format(sif_path))
        return 1, "", "SIF file not found"

    apptainer_cmd = [
        "apptainer", "exec",
        "-e",
        "-B", WORKSPACE_DIR + ":/workspace",
        "--pwd", "/workspace",
        sif_path,
        "/bin/bash", "-c", command
    ]

    try:
        if capture_output:
            result = subprocess.run(
                apptainer_cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(apptainer_cmd, timeout=300)
            return result.returncode, "", ""
    except subprocess.TimeoutExpired:
        print_error("Command timed out after 300 seconds")
        return 1, "", "timeout"
    except Exception as e:
        print_error("Error running apptainer: " + str(e))
        return 1, "", str(e)


def test_python_version(python_version, sif_file):
    """Test c2py23 with a specific Python version inside a container."""
    print_header("Testing Python " + python_version)

    system_py = "python" + python_version
    test_cmd = "cd /workspace && bash run_tests.sh " + system_py

    retcode, stdout, stderr = run_apptainer(sif_file, test_cmd)

    if retcode != 0:
        print_error("Test failed for Python " + python_version)
        log_write("STDOUT:\n" + stdout)
        log_write("STDERR:\n" + stderr)
        print("--- STDOUT ---")
        print(stdout)
        print("--- STDERR ---")
        print(stderr)
        print("--- END ---")
        return False

    print_success("All tests passed for Python " + python_version)
    print(stdout.strip())
    log_write("Test output:\n" + stdout)
    return True


def prepare_workspace():
    """Prepare the test workspace: copy c2py23 project and test files."""
    print_step("Preparing test workspace...")

    # Clean workspace
    if os.path.exists(WORKSPACE_DIR):
        shutil.rmtree(WORKSPACE_DIR)
    os.makedirs(WORKSPACE_DIR)

    # Copy c2py23 source (excluding .git, __pycache__, test_workspace)
    for item in os.listdir(PROJECT_DIR):
        src = os.path.join(PROJECT_DIR, item)
        dst = os.path.join(WORKSPACE_DIR, item)
        if item in ('.git', '__pycache__', '*.pyc', 'test_workspace',
                     '*.egg-info'):
            continue
        if os.path.isdir(src):
            if item == 'tests':
                # Copy tests but not test_workspace subdir
                shutil.copytree(src, dst,
                                ignore=shutil.ignore_patterns(
                                    'test_venv', 'test_workspace',
                                    '__pycache__', '*.pyc', '*.egg-info'))
            else:
                shutil.copytree(src, dst,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            if not item.endswith('.pyc'):
                shutil.copy2(src, dst)

    # Make scripts executable
    for script in ['tests/run_tests.sh']:
        sp = os.path.join(WORKSPACE_DIR, script)
        if os.path.exists(sp):
            os.chmod(sp, 0o755)

    print_success("Workspace prepared at " + WORKSPACE_DIR)


def main():
    global _log_file

    _log_file = open(LOG_FILE, 'w')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_write("c2py23 Test Suite - " + timestamp + "\n")

    try:
        print_header("c2py23 Multi-Version Test Suite")
        print("Logging to: " + LOG_FILE)

        prepare_workspace()

        results = {}
        for python_version, sif_file in PYTHON_VERSIONS:
            success = test_python_version(python_version, sif_file)
            results[python_version] = success

            if not success:
                print_error("Python " + python_version + " test FAILED")
                log_write("Python " + python_version + " test FAILED")
                print("\nStopping to debug this version first.")
                print("To debug, run:")
                sif_path = os.path.join(SNAKEPIT_DIR, sif_file)
                print("  apptainer shell -e -B {}:/workspace {}".format(
                    WORKSPACE_DIR, sif_path))
                return 1

        # Summary
        print_header("Test Summary")
        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for version, success in results.items():
            if success:
                print_success("Python " + version)
            else:
                print_error("Python " + version)

        summary = "\nResults: {}/{} passed\n".format(passed, total)
        print(summary)
        log_write(summary)

        return 0 if passed == total else 1

    finally:
        if _log_file:
            _log_file.close()


if __name__ == '__main__':
    sys.exit(main())
