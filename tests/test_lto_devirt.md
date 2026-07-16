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

### Benchmark: exact cost of portability

The dlsym-based nimpy approach adds a small overhead per C2PY
function pointer call.  Measured with `c2py_noargs.noargs()` (Python
call with no arguments, returns None) at 2M iterations with `-flto`:

| Variant | ns/call | Notes |
|---------|---------|-------|
| Nimpy (dlsym) | 212.3 | One `.so` for Python 2.7–3.15 |
| Pythonh (LTO) | 207.9 | Tied to one Python version |
| **Cost of portability** | **4.4 ns (2.1%)** | One extra load through C2PY table |

For a typical buffer computation (vnorm, ~1200 ns/call on Pyodide),
the 4.4 ns is <0.4% of total runtime.
