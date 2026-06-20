#!/usr/bin/env python3
"""
c2py23 test suite across all Python versions via snakepit containers.

Mirrors snakepit's test_images.py pattern:
1. Copies c2py23 project + test cases into workspace
2. For each Python version (2.7-3.15), runs run_tests.sh inside
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
    ("3.14t", "ubuntu24.04.sif"),
    ("3.15", "ubuntu26.04.sif"),
    ("3.15t", "ubuntu26.04.sif"),
]

_log_file = None

# Common signal names for crash diagnostics
_SIGNAL_NAMES = {
    1: 'SIGHUP', 2: 'SIGINT', 3: 'SIGQUIT', 4: 'SIGILL',
    5: 'SIGTRAP', 6: 'SIGABRT', 7: 'SIGBUS', 8: 'SIGFPE',
    9: 'SIGKILL', 10: 'SIGUSR1', 11: 'SIGSEGV', 12: 'SIGUSR2',
    13: 'SIGPIPE', 14: 'SIGALRM', 15: 'SIGTERM', 16: 'SIGSTKFLT',
    17: 'SIGCHLD', 18: 'SIGCONT', 19: 'SIGSTOP', 20: 'SIGTSTP',
    21: 'SIGTTIN', 22: 'SIGTTOU', 23: 'SIGURG', 24: 'SIGXCPU',
    25: 'SIGXFSZ', 26: 'SIGVTALRM', 27: 'SIGPROF', 28: 'SIGWINCH',
    29: 'SIGIO', 30: 'SIGPWR', 31: 'SIGSYS',
}


def _signal_name(sig):
    return _SIGNAL_NAMES.get(sig, 'signal {}'.format(sig))


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


def run_apptainer(sif_file, command, capture_output=True, timeout=600):
    """Run a command inside an Apptainer container.

    Args:
        sif_file: Name of the .sif container file
        command: Bash command to run inside the container
        capture_output: If True, capture stdout/stderr
        timeout: Maximum seconds before forcibly killing (default 600s = 10 min)

    Returns:
        (returncode, stdout, stderr) - stderr may contain error info on crash
    """
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
            proc = subprocess.Popen(
                apptainer_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                print_error("Command timed out after {}s -- killing".format(timeout))
                proc.kill()
                stdout, stderr = proc.communicate()
                return -9, "", "TIMEOUT after {}s (possibly infinite loop or hang)".format(timeout)
            if isinstance(stdout, bytes):
                stdout = stdout.decode('utf-8', errors='replace')
            if isinstance(stderr, bytes):
                stderr = stderr.decode('utf-8', errors='replace')
            return proc.returncode, stdout, stderr
        else:
            ret = subprocess.call(apptainer_cmd, timeout=timeout)
            return ret, "", ""
    except subprocess.TimeoutExpired:
        print_error("Command timed out after {}s (no-capture mode)".format(timeout))
        return -9, "", "TIMEOUT after {}s".format(timeout)
    except OSError as e:
        print_error("OS error running apptainer: " + str(e))
        return 1, "", str(e)
    except Exception as e:
        print_error("Error running apptainer: " + str(e))
        return 1, "", str(e)


def test_python_version(python_version, sif_file):
    """Test c2py23 with a specific Python version inside a container."""
    print_header("Testing Python " + python_version)

    system_py = "python" + python_version
    # ubuntu26.04 has packages pre-installed at system level
    if sif_file == "ubuntu26.04.sif":
        test_cmd = "cd /workspace && bash tests/run_tests.sh " + system_py + " preinstalled"
    else:
        test_cmd = "cd /workspace && bash tests/run_tests.sh " + system_py

    retcode, stdout, stderr = run_apptainer(sif_file, test_cmd)

    if retcode != 0:
        if retcode == -9:
            reason = "TIMED OUT (possible infinite loop or hang)"
        elif retcode < 0:
            reason = "KILLED by signal {}".format(-retcode)
        elif retcode > 128:
            sig = retcode - 128
            reason = "CRASHED with signal {} ({})".format(sig, _signal_name(sig))
        else:
            reason = "exit code {}".format(retcode)
        print_error("Test failed for Python {}: {}".format(python_version, reason))
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
