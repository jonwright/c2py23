# Repository Audit

The audit tooling exports the entire codebase into flat Markdown documents
for review by humans or LLMs. It catches the failure mode where iterative
development accumulates internal contradictions.

## The Problem

When an LLM (or human) develops a codebase over multiple reasoning steps,
earlier conclusions are rarely revisited when new ones supersede them.
The pattern:

1. Early sections written with a temporary or superseded conclusion
2. Later sections written with the corrected conclusion
3. Both co-exist, creating internal contradictions

This produces:
- **Orphaned prose**: claims in docs that nothing in the code references
- **Conflicting claims**: two files asserting different facts about the same thing
- **Drifted docstrings**: code changed but its documentation didn't
- **Abandoned ideas**: TODO items in PLAN.md that will never be done

## Single Source of Truth

The audit enforces a simple rule: **the code IS the specification.**

- Documentation cites the code; it does not reinvent it
- Key design decisions appear in exactly ONE file (usually `docs/design.md`)
- When a new attempt supersedes an old one, the old text is removed -- not
  left sitting below the new conclusion
- Derived documents (spec, user guide) reference canonical sources; they
  don't duplicate them

## The Audit Files

Two scripts produce flat Markdown exports of the entire repository:

| Script | Output | Size (approx) |
|--------|--------|---------------|
| `export_full_repo.py` | `tools/audit/full_repo_audit.md` | ~830 KB / ~25K lines |
| `export_wrappers.py` | `tools/audit/wrappers_combined.md` | ~500 KB / ~15K lines |

Both files fit within a 200K-token context window, making them suitable
for direct LLM review. The full repo audit contains every tracked text
file grouped by component. The wrappers audit contains generated C
extensions one cannot read without the runtime headers.

### Running the Audit

```bash
# Full source audit (all tracked text files)
python3 tools/audit/export_full_repo.py

# Wrapper module audit (generated C extensions)
python3 tools/audit/export_wrappers.py

# Skip build/test pre-checks if .so files already exist
python3 tools/audit/export_wrappers.py --skip-build --skip-tests
```

Both scripts require a clean `git status --porcelain` and exclude
submodules (`examples/kissfft`, `examples/lz4`) and binary artifacts.

## What to Look For

When reviewing the audit output, focus on these patterns:

### 1. Cross-file contradictions

Search for the same factual claim appearing in multiple files with
different values. Example: if `docs/specification.md` says the maximum
buffer dimensionality is 3 but `c2py23/parser.py` allows 4, there's a bug.

### 2. Orphaned claims

If `docs/specification.md` describes a feature (e.g., "keyword arguments")
but the parser has no code to handle it, the spec is aspirational, not
accurate. Either implement the feature or remove the claim.

### 3. Outdated PLAN.md / AGENTS.md

Check every item in `PLAN.md` under "Outstanding" and `AGENTS.md` under
"Next Steps." If an item has been done but still lists as pending, remove
it. If an item has been deferred so long it will never happen, either do it
or close the tracking issue.

### 4. Docstring vs. docs drift

The Python modules in `c2py23/` should have docstrings that match the
published documentation in `docs/`. If a function signature changed but
the docstring still shows the old one, update it.

### 5. Abandoned working notes

Files like the old `audit/20260620_resolved/` were working notes from a
one-time refactoring session. If the code they reference no longer exists,
the notes should be archived or removed. This watch folder was deleted
during the `audit/` -> `tools/audit/` migration.

## Periodic Review Cadence

Run the audit before each release and after any major refactoring:

```bash
python3 tools/audit/export_full_repo.py
python3 tools/audit/export_wrappers.py --skip-build --skip-tests
```

Review the output manually or feed it to an LLM. File issues for every
inconsistency found. Treat an audit with zero findings as the release
gate -- no release goes out with known contradictions.
