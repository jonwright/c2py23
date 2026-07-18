#!/usr/bin/env python
"""Generate README.md files for each example with captured live output.

Builds each example, runs its demo script, captures stdout/stderr,
and writes a README.md that embeds the source files and output.

Usage:
    python3 tools/generate_example_readmes.py
    python3 tools/generate_example_readmes.py --dry-run
    python3 tools/generate_example_readmes.py threading_bench
"""

from __future__ import print_function

import os
import subprocess
import sys
import time

IS_PY3 = sys.version_info[0] >= 3

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(PROJECT_DIR, "examples")


def _cmd(cmd_args, cwd, timeout_sec=120):
    """Run a command, return (returncode, stdout_str, stderr_str)."""
    try:
        if IS_PY3:
            p = subprocess.Popen(
                cmd_args,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        else:
            p = subprocess.Popen(
                cmd_args,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        stdout, stderr = p.communicate(timeout=timeout_sec)
        out = stdout.decode("utf-8", errors="replace") if stdout else ""
        err = stderr.decode("utf-8", errors="replace") if stderr else ""
        return p.returncode, out, err
    except Exception as e:
        return -1, "", str(e)


def _find_c2py_file(example_dir):
    for fn in sorted(os.listdir(example_dir)):
        if fn.endswith(".c2py") and not fn.endswith(".c2py.py"):
            return fn
    return None


def _find_c_file(example_dir):
    for fn in sorted(os.listdir(example_dir)):
        if fn.endswith(".c") and not fn.endswith("_wrapper.c"):
            return fn
    return None


def _find_py_script(example_dir):
    candidates = []
    for fn in sorted(os.listdir(example_dir)):
        if fn.endswith(".py") and fn != "setup.py":
            if fn.startswith("bench_") or fn.startswith("test_") or fn.startswith("example"):
                candidates.append(fn)
    return candidates


def _read_or_empty(path):
    if os.path.isfile(path):
        with open(path) as f:
            return f.read()
    return ""


def _module_name(c2py_path):
    """Parse .c2py file and return the module name."""
    try:
        from c2py23.parser import load_c2py

        return load_c2py(c2py_path).name
    except Exception:
        return None


def _source_block(path, lang, label):
    content = _read_or_empty(path)
    if not content:
        return "*(%s not found)*\n" % label
    return "```%s\n%s\n```\n" % (lang, content.rstrip())


def build_and_demo(example_dir, example_name):
    c2py_file = _find_c2py_file(example_dir)
    if not c2py_file:
        return False, "No .c2py file found in %s" % example_dir, "", {}, []

    c_file = _find_c_file(example_dir)
    py_scripts = _find_py_script(example_dir)

    source_dir = example_dir
    for sub in ["kissfft", "lz4"]:
        candidate = os.path.join(example_dir, "..", sub)
        if os.path.isdir(candidate):
            source_dir = None
            if c_file:
                c_path = os.path.join(example_dir, c_file)
                if os.path.isfile(c_path):
                    source_dir = example_dir
            break

    # Generate wrapper
    rc, gen_stdout, gen_stderr = _cmd(
        [sys.executable, "-m", "c2py23", c2py_file, "-o", c2py_file.replace(".c2py", "") + "_wrapper.c"],
        example_dir,
        timeout_sec=120,
    )
    gen_output = gen_stdout + gen_stderr

    demo_results = []
    for py_script in py_scripts:
        demo_cmd = [sys.executable, py_script]
        demo_dir = example_dir
        rc_d, demo_out, demo_err = _cmd(demo_cmd, demo_dir, timeout_sec=120)
        demo_output = demo_out + demo_err
        demo_results.append((py_script, demo_output))

    return True, gen_output, c2py_file, c_file, demo_results


def generate_readme(example_dir, example_name, build_output, c2py_file, c_file, demo_results):
    lines = []
    title = example_name.replace("_", " ").title()
    lines.append("# %s\n" % title)

    lines.append("## Interface\n")
    c2py_path = os.path.join(example_dir, c2py_file)
    lines.append(_source_block(c2py_path, "yaml", c2py_file))

    if c_file:
        lines.append("## C Source\n")
        c_path = os.path.join(example_dir, c_file)
        lines.append(_source_block(c_path, "c", c_file))

    mod_name = _module_name(os.path.join(example_dir, c2py_file))
    wrapper = (mod_name or c2py_file.replace(".c2py", "")) + "_wrapper.c"

    lines.append("## Build\n")
    lines.append("```bash\n$ c2py23 %s -o %s\n```\n\n" % (c2py_file, wrapper))
    lines.append("Compile:\n")
    lines.append(
        "```bash\n$ cc -shared -fPIC c2py23/runtime/c2py_runtime.c %s %s -I c2py23/runtime -o %s.so -ldl -lm\n```\n"
        % (wrapper, c_file or "*.c", mod_name or "module")
    )
    lines.append("See [docs/building](building) for cmake, meson, and setuptools options.\n")

    if demo_results:
        lines.append("## Run\n")
        for py_script, output in demo_results:
            lines.append("```bash\n$ python %s\n%s\n```\n" % (py_script, output.rstrip()))

    readme_path = os.path.join(example_dir, "README.md")
    content = "\n".join(lines) + "\n"
    with open(readme_path, "w") as f:
        f.write(content)
    return readme_path


def generate_static_readme(example_dir, example_name):
    """Generate README without building (for examples that need special setup)."""
    c2py_file = _find_c2py_file(example_dir)
    c_file = _find_c_file(example_dir)
    py_scripts = _find_py_script(example_dir)

    lines = []
    title = example_name.replace("_", " ").title()
    lines.append("# %s\n" % title)

    lines.append("## Interface\n")
    if c2py_file:
        c2py_path = os.path.join(example_dir, c2py_file)
        lines.append(_source_block(c2py_path, "yaml", c2py_file))

    if c_file:
        lines.append("## C Source\n")
        c_path = os.path.join(example_dir, c_file)
        lines.append(_source_block(c_path, "c", c_file))

    mod_name = _module_name(os.path.join(example_dir, c2py_file)) if c2py_file else None
    wrapper = (mod_name or (c2py_file or "module").replace(".c2py", "")) + "_wrapper.c"

    lines.append("## Build\n")
    lines.append("```bash\n$ c2py23 %s -o %s\n```\n\n" % (c2py_file or "*.c2py", wrapper))
    lines.append("Compile:\n")
    lines.append(
        "```bash\n$ cc -shared -fPIC c2py23/runtime/c2py_runtime.c %s %s -I c2py23/runtime -o %s.so -ldl -lm\n```\n"
        % (wrapper, c_file or "*.c", mod_name or "module")
    )
    lines.append("See [docs/building](building) for cmake, meson, and setuptools options.\n")

    if py_scripts:
        lines.append("## Run\n")
        for py_script in py_scripts:
            script_path = os.path.join(example_dir, py_script)
            lines.append("```python\n%s\n```\n" % _read_or_empty(script_path).rstrip())

    readme_path = os.path.join(example_dir, "README.md")
    content = "\n".join(lines) + "\n"
    with open(readme_path, "w") as f:
        f.write(content)
    return readme_path


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("examples", nargs="*", help="Specific examples to regenerate")
    ap.add_argument("--build", action="store_true", help="Build and capture output")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = ap.parse_args()

    all_examples = {}
    if os.path.isdir(EXAMPLES_DIR):
        for name in sorted(os.listdir(EXAMPLES_DIR)):
            example_dir = os.path.join(EXAMPLES_DIR, name)
            if not os.path.isdir(example_dir):
                continue
            if name in ("kissfft", "lz4"):
                continue
            all_examples[name] = example_dir

    if args.examples:
        examples_to_process = {k: v for k, v in all_examples.items() if k in args.examples}
    else:
        examples_to_process = all_examples

    buildable = {"kissfft_wrap", "lz4_wrap", "threading_bench", "timing_demo", "mp_bench"}

    pkgs_needed = ["kissfft_wrap", "lz4_wrap"]

    errors = []
    for name in sorted(examples_to_process):
        example_dir = examples_to_process[name]
        print("Processing: %s" % name)

        if args.dry_run:
            print("  (dry run, skipping)")
            continue

        if name in buildable and args.build:
            if name in pkgs_needed:
                sub_dir = name.replace("_wrap", "")
                sub_path = os.path.join(EXAMPLES_DIR, sub_dir)
                if not os.path.isdir(sub_path):
                    print("  SKIP: submodule %s not initialized" % sub_dir)
                    continue

            success, build_output, c2py_file, c_file, demo_results = build_and_demo(example_dir, name)
            if success:
                readme_path = generate_readme(example_dir, name, build_output, c2py_file, c_file, demo_results)
                print("  OK: %s" % readme_path)
            else:
                print("  FAIL: %s" % build_output)
                errors.append(name)
        else:
            readme_path = generate_static_readme(example_dir, name)
            print("  OK: %s (static)" % readme_path)

    if errors:
        print("\nErrors in: %s" % ", ".join(errors))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
