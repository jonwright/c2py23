#!/usr/bin/env python3
"""
c2py23 manylinux build + cross-test suite.

Implements a two-phase strategy to minimize combinatorial testing:

Phase 1 (build verification):
  Verify `c2py23 build` works on every Python version inside the
  manylinux2014 container (3.9, 3.10, 3.11, 3.12, 3.13, 3.14).
  No tests run here -- just make sure compilation succeeds.

Phase 2 (master build):
  Build all .so files once with Python 3.12 on manylinux2014.

Phase 3 (cross-test):
  Copy the pre-built .so files to every other container (ubuntu20.04,
  ubuntu24.04, ubuntu26.04, debian10) and run the full test suite
  with each Python version (2.7 through 3.15).
"""

from __future__ import print_function

import os
import sys
import shutil
import subprocess
import glob as globmod
from datetime import datetime

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SNAKEPIT_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "snakepit")
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, "test_workspace")
LOG_FILE = os.path.join(SCRIPT_DIR, "test_manylinux_results.log")

# Python versions available in the manylinux2014 container
MANYLINUX_VERSIONS = ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"]
MANYLINUX_SIF = "manylinux2014.sif"

# Cross-test targets (all non-manylinux containers from the existing matrix)
CROSS_TEST_TARGETS = [
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
]

_log_file = None

_SIGNAL_NAMES = {
    1: "SIGHUP",
    2: "SIGINT",
    3: "SIGQUIT",
    4: "SIGILL",
    5: "SIGTRAP",
    6: "SIGABRT",
    7: "SIGBUS",
    8: "SIGFPE",
    9: "SIGKILL",
    10: "SIGUSR1",
    11: "SIGSEGV",
    12: "SIGUSR2",
    13: "SIGPIPE",
    14: "SIGALRM",
    15: "SIGTERM",
    16: "SIGSTKFLT",
    17: "SIGCHLD",
    18: "SIGCONT",
    19: "SIGSTOP",
    20: "SIGTSTP",
    21: "SIGTTIN",
    22: "SIGTTOU",
    23: "SIGURG",
    24: "SIGXCPU",
    25: "SIGXFSZ",
    26: "SIGVTALRM",
    27: "SIGPROF",
    28: "SIGWINCH",
    29: "SIGIO",
    30: "SIGPWR",
    31: "SIGSYS",
}


def _signal_name(sig):
    return _SIGNAL_NAMES.get(sig, "signal {}".format(sig))


def log_write(message):
    if _log_file:
        _log_file.write(message + "\n")
        _log_file.flush()


def print_header(message):
    line = "=" * 70
    print("\n" + line)
    print(message)
    print(line + "\n")
    log_write(line)
    log_write(message)
    log_write(line + "\n")


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
    """Run a command inside an Apptainer container."""
    sif_path = os.path.join(SNAKEPIT_DIR, sif_file)
    if not os.path.exists(sif_path):
        print_error("SIF file not found: {}".format(sif_path))
        return 1, "", "SIF file not found"

    apptainer_cmd = [
        "apptainer",
        "exec",
        "-e",
        "-B",
        WORKSPACE_DIR + ":/workspace",
        "--pwd",
        "/workspace",
        sif_path,
        "/bin/bash",
        "-c",
        command,
    ]

    try:
        if capture_output:
            proc = subprocess.Popen(apptainer_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                print_error("Command timed out after {}s -- killing".format(timeout))
                proc.kill()
                stdout, stderr = proc.communicate()
                return -9, "", "TIMEOUT after {}s".format(timeout)
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
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


def _clean_so_files():
    """Remove all .so files from the workspace (test cases + examples)."""
    so_patterns = [
        os.path.join(WORKSPACE_DIR, "tests", "cases", "*", "*.so"),
        os.path.join(WORKSPACE_DIR, "examples", "*", "*.so"),
    ]
    for pattern in so_patterns:
        for path in globmod.iglob(pattern):
            try:
                os.unlink(path)
            except OSError:
                pass


def prepare_workspace():
    """Prepare the test workspace: copy c2py23 project, exclude existing .so files."""
    print_step("Preparing test workspace...")

    if os.path.exists(WORKSPACE_DIR):
        shutil.rmtree(WORKSPACE_DIR)
    os.makedirs(WORKSPACE_DIR)

    # Copy everything except .git, __pycache__, *.pyc, *.so, test_workspace
    for item in os.listdir(PROJECT_DIR):
        src = os.path.join(PROJECT_DIR, item)
        dst = os.path.join(WORKSPACE_DIR, item)
        if item in (".git", "__pycache__", "test_workspace", "*.egg-info"):
            continue
        if os.path.isdir(src):
            if item == "tests":
                shutil.copytree(
                    src,
                    dst,
                    ignore=shutil.ignore_patterns(
                        "test_venv",
                        "test_workspace",
                        "__pycache__",
                        "*.pyc",
                        "*.egg-info",
                        "*.so",
                    ),
                )
            else:
                shutil.copytree(
                    src,
                    dst,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.so"),
                )
        else:
            if not item.endswith(".pyc") and not item.endswith(".so"):
                shutil.copy2(src, dst)

    for script in ["tests/build_all.sh", "tests/run_tests_only.sh"]:
        sp = os.path.join(WORKSPACE_DIR, script)
        if os.path.exists(sp):
            os.chmod(sp, 0o755)

    print_success("Workspace prepared at " + WORKSPACE_DIR)


def phase1_build_verify(python_version):
    """Phase 1: Verify building works for one Python version on manylinux."""
    print_header("Phase 1 [{}]: Build verification on manylinux2014".format(python_version))

    system_py = "python" + python_version
    build_cmd = "cd /workspace && bash tests/build_all.sh " + system_py

    retcode, stdout, stderr = run_apptainer(MANYLINUX_SIF, build_cmd)

    if retcode != 0:
        if retcode == -9:
            reason = "TIMED OUT"
        elif retcode < 0:
            reason = "KILLED by signal {}".format(-retcode)
        elif retcode > 128:
            sig = retcode - 128
            reason = "CRASHED with signal {} ({})".format(sig, _signal_name(sig))
        else:
            reason = "exit code {}".format(retcode)
        print_error("Build failed for Python {} on manylinux2014: {}".format(python_version, reason))
        log_write("STDOUT:\n" + stdout)
        log_write("STDERR:\n" + stderr)
        print("--- STDOUT ---")
        print(stdout)
        print("--- STDERR ---")
        print(stderr)
        print("--- END ---")
        return False

    print_success("Build succeeded for Python {} on manylinux2014".format(python_version))
    log_write("Build output:\n" + stdout)

    # Clean .so files so the next version builds from scratch
    _clean_so_files()
    return True


def phase2_master_build():
    """Phase 2: Build all .so with Python 3.12 on manylinux (the master build)."""
    print_header("Phase 2: Master build with Python 3.12 on manylinux2014")

    # Ensure no stale .so files
    _clean_so_files()

    build_cmd = "cd /workspace && bash tests/build_all.sh python3.12"
    retcode, stdout, stderr = run_apptainer(MANYLINUX_SIF, build_cmd)

    if retcode != 0:
        if retcode == -9:
            reason = "TIMED OUT"
        elif retcode < 0:
            reason = "KILLED by signal {}".format(-retcode)
        elif retcode > 128:
            sig = retcode - 128
            reason = "CRASHED with signal {} ({})".format(sig, _signal_name(sig))
        else:
            reason = "exit code {}".format(retcode)
        print_error("Master build failed: {}".format(reason))
        log_write("STDOUT:\n" + stdout)
        log_write("STDERR:\n" + stderr)
        print("--- STDOUT ---")
        print(stdout)
        print("--- STDERR ---")
        print(stderr)
        print("--- END ---")
        return False

    print_success("Master build complete")
    log_write("Build output:\n" + stdout)
    return True


def phase3_cross_test(python_version, sif_file):
    """Phase 3: Test the pre-built .so files on a different container."""
    print_header("Phase 3: Cross-test Python {} on {}".format(python_version, sif_file))

    system_py = "python" + python_version
    test_cmd = "cd /workspace && bash tests/run_tests_only.sh " + system_py

    retcode, stdout, stderr = run_apptainer(sif_file, test_cmd)

    if retcode != 0:
        if retcode == -9:
            reason = "TIMED OUT"
        elif retcode < 0:
            reason = "KILLED by signal {}".format(-retcode)
        elif retcode > 128:
            sig = retcode - 128
            reason = "CRASHED with signal {} ({})".format(sig, _signal_name(sig))
        else:
            reason = "exit code {}".format(retcode)
        print_error("Cross-test failed for Python {} on {}: {}".format(python_version, sif_file, reason))
        log_write("STDOUT:\n" + stdout)
        log_write("STDERR:\n" + stderr)
        print("--- STDOUT ---")
        print(stdout)
        print("--- STDERR ---")
        print(stderr)
        print("--- END ---")
        return False

    print_success("Cross-test passed for Python {} on {}".format(python_version, sif_file))
    print(stdout.strip())
    log_write("Test output:\n" + stdout)
    return True


def main():
    global _log_file

    _log_file = open(LOG_FILE, "w")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_write("c2py23 Manylinux Test Suite - " + timestamp + "\n")

    try:
        print_header("c2py23 Manylinux + Cross-Test Suite")
        print("Logging to: " + LOG_FILE)

        # Prep workspace once; all phases share it
        prepare_workspace()

        results = {}

        # --- Phase 1: Build verification on all manylinux Python versions ---
        print_header("=== Phase 1: Build Verification on manylinux2014 ===")
        for pyver in MANYLINUX_VERSIONS:
            ok = phase1_build_verify(pyver)
            results["Phase1-" + pyver] = ok
            if not ok:
                print_error("Phase 1 failed for Python " + pyver)
                return 1

        # --- Phase 2: Master build with 3.12 on manylinux ---
        print_header("=== Phase 2: Master Build (3.12) on manylinux2014 ===")
        ok = phase2_master_build()
        results["Phase2-master"] = ok
        if not ok:
            print_error("Phase 2 (master build) failed")
            return 1

        # --- Phase 3: Cross-test on all other containers ---
        print_header("=== Phase 3: Cross-Test on All Containers ===")
        for pyver, sif_file in CROSS_TEST_TARGETS:
            ok = phase3_cross_test(pyver, sif_file)
            results["Phase3-{}-{}".format(pyver, sif_file)] = ok
            if not ok:
                print_error("Phase 3 failed for Python {} on {}".format(pyver, sif_file))
                print("\nStopping to debug this target first.")
                print("To debug, run:")
                sif_path = os.path.join(SNAKEPIT_DIR, sif_file)
                print("  apptainer shell -e -B {}:/workspace {}".format(WORKSPACE_DIR, sif_path))
                return 1

        # --- Summary ---
        print_header("Manylinux Test Summary")
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        for key, ok in sorted(results.items()):
            if ok:
                print_success(key)
            else:
                print_error(key)
        summary = "\nResults: {}/{} passed\n".format(passed, total)
        print(summary)
        log_write(summary)
        return 0 if passed == total else 1

    finally:
        if _log_file:
            _log_file.close()


if __name__ == "__main__":
    sys.exit(main())
