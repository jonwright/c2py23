## test_lto_devirt.sh

**Local-only test — not run in CI.** Requires `gcc`, `objdump`, `python3-config`.

Proves that `--pythonh` + `-flto` devirtualizes all C2PY function
pointer calls to direct CPython API calls.

### What it tests

Builds `tests/cases/fill/fill.c2py` in three configurations and
inspects the generated assembly:

| Config | Expected indirect calls | Reality |
|--------|------------------------|---------|
| Nimpy `-O2` | >0 (dlsym requires function pointers) | 2 |
| Pythonh `-O2` | — (compiler can see C2PY fields) | 0 |
| Pythonh `-O2 -flto` | 0 (LTO proves C2PY never mutates) | 0 (excl. glibc _init stub) |

### Usage

```bash
bash tests/test_lto_devirt.sh
```

### Why not CI

- Depends on GCC-specific `-flto` semantics. Clang, MSVC, and older
  GCC versions may produce different results.
- `objdump` output format varies across distros/binutils versions.
- The assertion that LTO devirtualizes is a compiler quality
  property, not a c2py23 correctness property.

### Measuring portability overhead

The benchmark suite at `benchmarks/` has a `pythonh` target.  Build and run:

```bash
cd benchmarks && make bench
```

This builds all modules for both nimpy (dlsym) and pythonh (direct),
runs the same benchmark code against both, prints results to stdout,
and writes `docs/benchmarks.md`.  The delta between nimpy and pythonh
columns is the cost of cross-version portability.  All numbers are
printed at runtime — none are embedded in source.

```bash
cd benchmarks && python3 generate_docs.py
```
