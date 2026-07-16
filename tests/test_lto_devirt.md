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

### Benchmark: measuring the cost of portability

The dlsym-based nimpy approach adds overhead per C2PY function
pointer call.  To measure it, build with and without `--pythonh`
using `-flto -O2`, then compare:

```bash
# Build both variants
CFLAGS="-flto -O2" LDFLAGS="-flto" \
  c2py23 build benchmarks/src/c2py_noargs.c2py -o /tmp/nimpy.so
CFLAGS="-flto -O2" LDFLAGS="-flto" \
  c2py23 build --pythonh benchmarks/src/c2py_noargs.c2py -o /tmp/py.so

# Run benchmark (timing numbers go to stdout, not into source)
python3 -c "
import sys, time; sys.path.insert(0,'/tmp')
import importlib.machinery, importlib.util
for n,p in [('nimpy','/tmp/nimpy.so'),('pythonh','/tmp/py.so')]:
    sys.modules.pop('c2py_noargs',None)
    l=importlib.machinery.ExtensionFileLoader('c2py_noargs',p)
    s=importlib.util.spec_from_file_location('c2py_noargs',p,loader=l)
    m=importlib.util.module_from_spec(s)
    sys.modules['c2py_noargs']=m; l.exec_module(m)
    for _ in range(1000): m.noargs()
    N=5000000; t0=time.perf_counter_ns()
    for _ in range(N): m.noargs()
    ns=(time.perf_counter_ns()-t0)/N
    print('%s: %.1f ns/call'%(n,ns))
"
```

The delta is the cost of portability — one load through the C2PY
function pointer table per CPython API call.  On a typical buffer
computation (vnorm, 3-element vectors) this is a fraction of a
percent of total runtime.
