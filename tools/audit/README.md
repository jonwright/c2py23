# c2py23 Audit Tooling

Export the c2py23 codebase into Markdown documents suitable for review by
human experts or LLM models. The repo's `git ls-files` is the source of
truth for what gets included -- no hardcoded manifests.

## Philosophy

The audit exists to catch the failure mode where a codebase accumulates
contradictions from iterative development. When conclusions change mid-stream,
earlier text is rarely revisited. The pattern is:

1. Early sections written with a temporary or superseded conclusion
2. Later sections written with the corrected conclusion
3. Both co-exist, creating internal contradictions

The audit produces a single, flat Markdown document containing every
source file. This makes inconsistencies visible: a claim in the docs
that contradicts the code, a docstring that doesn't match the behavior,
a limitation listed in one place but not another.

**Principles:**

- **One source of truth.** The code IS the spec. Documentation cites it,
  doesn't reinvent it. Key claims should appear in exactly one file.
- **Separate derivation from specification.** Working notes from exploration
  are clearly labeled; when superseded, they are removed, not appended below.
- **No orphaned prose.** If a claim appears nowhere else, it's suspect.
- **No internal contradictions.** Two files must not make conflicting
  factual claims about the same thing.

## Output Files (in .gitignore -- regenerated on each run)

| File | Contents |
|------|----------|
| `tools/audit/full_repo_audit.md` | Every tracked text file, grouped by component |
| `tools/audit/wrappers_combined.md` | All wrapper modules + runtime header (one file) |
| `tools/audit/wrappers/<name>.md` | One file per module (runtime NOT included) |

## Quick Start

```bash
pip install -e .                             # install c2py23 in dev mode
bash tests/run_tests.sh python3              # build + test everything
python3 tools/audit/export_full_repo.py       # full source audit
python3 tools/audit/export_wrappers.py        # wrapper module audit
```

Both scripts refuse to run if `git status --porcelain` is not clean
(untracked audit output files are allowed). Submodules (`examples/kissfft`,
`examples/lz4`) are excluded.

## How the Audit Is Driven

**Full repo audit** (`export_full_repo.py`):
1. `git ls-files` -- all tracked files
2. Filter: exclude submodule paths, exclude binary extensions (.so, .o, .sif)
3. Classify files into sections by path prefix
4. Render each text file in a fenced code block

**Wrapper module audit** (`export_wrappers.py`):
1. Discover module directories from `tests/cases/*/` and `examples/*/`
   (any directory with a `.c2py` file)
2. For each module: `git ls-files <dir>` gives tracked source + test files
3. Append the generated `_wrapper.c` from disk (not tracked by git)
4. Skip `.so` files (binary)

Adding a new test case? Create the directory, add `.c2py` + `.c` files,
commit them -- the audit picks them up automatically.

## export_wrappers.py -- Options

```
--skip-build        Skip build check (use existing .so / wrapper)
--skip-tests        Skip test verification
--combined-only     Only write wrappers_combined.md
--individual-only   Only write per-module wrappers/*.md
--output-dir DIR    Write output to DIR (default: tools/audit/)
```

The pre-check runs three phases before exporting:
1. **Build**: any module missing a `_wrapper.c` or `.so` gets built
2. **Test**: `test_uniform.py`, `test_error_paths.py`, `test_regression_fixes.py`,
   `test_leaks.py` must all pass
3. **Snakepit**: if containers exist at `../snakepit/`, the log
   (`tests/test_results.log`) is checked for failures

---

## LLM Peer Review Workflow

The audit files are designed for continuous LLM-based peer review.
The previous review (three referee reports, June 2026) is documented in
`tools/audit/referee_reports_2026-06-15.md`. The workflow below can be
repeated for each new revision of the code.

### Step 1: Upload the Runtime Support Code

Start a fresh LLM session and upload the runtime section from
`wrappers_combined.md` (the `## Runtime Support Code` block). This
contains `c2py_runtime.h`, `c2py_runtime.c`, and the three arch-specific
headers (`c2py_amd64.h`, `c2py_arm64.h`, `c2py_ppc64.h`).

Tell the LLM:

> "Here is the C runtime support library for a CPython C-extension wrapper
> generator called c2py23. It uses the nimpy trick -- all CPython API is
> resolved at runtime via dlopen(NULL)/dlsym(). Please keep this code in
> context throughout our session. I will now show you individual wrapper
> modules one at a time, and I want you to review each for correctness,
> safety, and adherence to the CPython C API contract."

### Step 2: Review One Wrapper at a Time

Upload each file from `tools/audit/wrappers/<name>.md` sequentially. Each
file contains the interface definition, the C implementation, the
generated wrapper, and any test scripts for that module.

For each wrapper, ask the LLM:

> "Review this generated wrapper module. Check for:
> - Buffer bounds validation (are format/ndim/n checks present?)
> - Buffer aliasing detection (are writable outputs checked for overlap?)
> - GIL handling (is save/restore correctly paired?)
> - INT_MAX overflow guards on buffer element counts
> - Correct refcounting (Py_INCREF/DECREF balance)
> - Python 2.7--3.14 ABI compatibility
> - Any undefined behavior in the generated C"

### Step 3: Aggregate Findings

Keep a running list of issues found. For each issue note:
- Which module
- Severity (HIGH / MEDIUM / LOW)
- Exact file and line reference
- Proposed fix

Use the summary table format from
`tools/audit/referee_reports_2026-06-15.md` (lines 17--33).

### Step 4: Re-Review After Fixes

After addressing issues, regenerate the audit files and repeat the review
session. Compare the new findings against the previous list to confirm
resolutions and check for regressions.

### Alternative: Full-Repo Review

For a holistic review, upload `tools/audit/full_repo_audit.md` instead.
This contains the Python generator source (parser, generator, CLI)
alongside the C runtime, so the LLM can review the entire pipeline
end-to-end.

---

## Stress Testing & Debugging

### Memory Safety

| Tool | Command | Catches |
|------|---------|---------|
| ASan | `CC=gcc CFLAGS="-fsanitize=address -g -O1" LDFLAGS="-fsanitize=address" python tests/runner.py` | Buffer overflows, use-after-free |
| Valgrind | `valgrind --leak-check=full python3 tests/test_leaks.py` | Memory leaks, uninitialized reads |
| Debug | `CC=gcc CFLAGS="-g -O0 -Wall -Werror" python tests/runner.py` + GDB | Segfault root cause |

### Cross-Version Compatibility

| Tool | Command | Catches |
|------|---------|---------|
| Single version | `bash tests/run_tests.sh python3` | Tests on current Python |
| All versions | `python3 tests/test_all.py` | 2.7, 3.6--3.14t via snakepit |

### Generator Robustness

| Technique | Approach |
|-----------|----------|
| Malformed input | Feed broken `.c2py` to the parser |
| Edge cases | 0-length arrays, max `Py_ssize_t`, negative sizes |
| Large buffers | 1 GB+ arrays to stress overflow guards |
| Aliasing | Same buffer as input+output, verify detection |

### Static Analysis

```bash
cppcheck --enable=all tests/cases/fill/fillmod_wrapper.c
clang-tidy tests/cases/fill/fillmod_wrapper.c -- -I c2py23/runtime/
```
