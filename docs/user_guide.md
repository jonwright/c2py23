# c2py23 User Guide

## Introduction

c2py23 wraps C99 functions as Python C extensions using the buffer protocol.
One compiled `.so` works on Python 2.7 through 3.15 with no recompilation.

## Quick Reference

```yaml
# mymod.c2py
module: mymod
source: [mymod.c]
timing: false                           # enable perf timing (optional)
free_threading: false                   # declare module safe for 3.14t (optional)

functions:
  - py_sig: "myfunc(a: buffer, n: int) -> int"
    checks:
      - "a.format == 'd'"
      - "a.n > 0"
    c_overloads:
      - sig: "myfunc_c(const double *a, int n) -> int"
        map: {a: "a.ptr", n: n}
```

## Thread Safety Guide

### Standard CPython (2.7 through 3.15)

The GIL serializes all Python bytecode. When a C wrapper function is called,
the GIL is held by default. Other Python threads cannot run until the call
returns. Use `gil_release: true` to release the GIL during pure-C computation,
allowing other Python threads to execute in parallel.

### Free-Threading (3.14t)

Free-threaded CPython (`--disable-gil`, `python3.14t`) eliminates the GIL
at the interpreter level. However, c2py23 modules do NOT declare
`Py_MOD_GIL_NOT_USED` by default (safe default). This triggers CPython to
re-enable the GIL **globally** on module load -- all Python threads are
serialized, exactly as on standard CPython.

See `docs/specification.md` for the full technical breakdown.

### Enabling True Free-Threading

Set `free_threading: true` in your `.c2py` file:

```yaml
module: mymod
source: [mymod.c]
free_threading: true
```

This causes the generated wrapper to call `PyUnstable_Module_SetGIL(module, 1)`
at init time (resolved via dlsym -- only available on FT builds). The GIL is
NOT re-enabled when this module loads, and other Python threads can run in
true parallelism.

**You must verify that your C code is thread-safe before enabling this.**
c2py23 does not analyze your C code for thread safety.

### Migrating from 3.13 to 3.14t

| Aspect | Python 3.13 | Python 3.14t |
|--------|-------------|---------------|
| GIL state | Always enabled | Disabled by default; re-enabled globally by c2py23 modules |
| `gil_release: true` | Releases the GIL | Releases the re-enabled GIL (same effect) |
| `free_threading: true` | No-op (ignored) | Prevents GIL re-enablement |
| Thread parallelism | Only via GIL release | True parallelism if `free_threading: true` |

On 3.13, `free_threading: true` has zero effect -- the GIL is always on,
`PyUnstable_Module_SetGIL` is not exported, and the dlsym returns NULL.
The option is purely forward-looking for 3.14t.

**Testing workflow:**
1. Develop and test on standard 3.13 with `gil_release: true` for parallel C
2. Set `free_threading: true` and test on `python3.14t`
3. If you see data races or wrong results, your C code has thread-safety bugs
4. Fall back to `free_threading: false` (GIL re-enabled) while fixing them

### Global State Audit

All mutable global state in c2py23 generated wrappers and runtime is
race-safe by design. Here is the complete inventory:

**Timing perf structs** (`_perf_*`, `c2py_perf_t`):
Race condition: concurrent calls lose increments on `call_count`,
corrupt `t_c_min`/`t_c_max` comparisons, mis-accumulate `t_c_total`.
Impact: **Harmless** -- diagnostic data only. No Python objects, no
pointers (variant_name is a compile-time string literal set once).

**Timing toggle** (`_c2py_timing_enabled`, `static int`):
Race condition: two threads writing simultaneously may see stale values.
Impact: **Harmless** -- at worst timing is spuriously on or off for one
call. No safety implications.

**GIL release toggle** (`_c2py_gil_release_enabled`, `_gil_release_*`):
Race condition: thread reads stale toggle value, decides to hold/release
GIL based on stale state.
Impact: **Harmless** -- the toggle is a hint, not a correctness mechanism.

**Variant dispatch cache** (`_var_*`, `_vname_*`):
Race condition: two threads on first dispatch both compute variant and
write the cache; second writer wins.
Impact: **Harmless** -- worst case a suboptimal variant is selected.

**CPU feature flags, API table, tick frequency**:
Written once via `pthread_once`, then read-only.
Impact: **Safe** -- no race possible.

**No pathological global state exists.** No mutable static can produce a
segfault, use-after-free, or type confusion in the wrapper itself. The only
source of hard crashes is user C code with thread-safety bugs.

### Dangerous Patterns in User C Code

For pure array computations (no file I/O), these patterns become unsafe
when `free_threading: true` is set and multiple threads call into the
same function:

**1. Static scratch buffers**

```c
/* UNSAFE: two threads clobber each other */
static double workspace[1024];
void compute(const double *in, double *out, int n) {
    for (int i = 0; i < n; i++)
        workspace[i] = in[i] * 2.0;  // race!
    for (int i = 0; i < n; i++)
        out[i] = workspace[i] + 1.0;
}
```

Fix: allocate on the stack or pass a buffer from Python.

```c
/* SAFE: stack allocation (up to reasonable size) */
void compute(const double *in, double *out, int n) {
    double workspace[1024];  // per-thread stack
    for (int i = 0; i < n; i++)
        workspace[i] = in[i] * 2.0;
    for (int i = 0; i < n; i++)
        out[i] = workspace[i] + 1.0;
}
```

**2. Global/static accumulators**

```c
/* UNSAFE: two threads race on the accumulator */
static double grand_total = 0.0;
void accumulate(const double *vals, int n) {
    for (int i = 0; i < n; i++)
        grand_total += vals[i];  // lost update
}
```

Fix: return the partial sum and let Python combine, or use atomics.

```c
/* SAFE: return partial result */
double accumulate(const double *vals, int n) {
    double sum = 0.0;  // local variable, per-thread
    for (int i = 0; i < n; i++)
        sum += vals[i];
    return sum;
}
```

**3. One-time initialization with static flag**

```c
/* UNSAFE: two threads race on initialization */
static int table_initialized = 0;
static double lookup[256];
static void ensure_table(void) {
    if (!table_initialized) {
        for (int i = 0; i < 256; i++)
            lookup[i] = some_expensive_computation(i);
        table_initialized = 1;  // double-init, or use before init
    }
}
```

Fix: use `call_once` / `pthread_once`, or a static const initializer.

```c
/* SAFE: compile-time constant */
static const double lookup[256] = { /* precomputed values */ };
```

**4. Non-reentrant C library functions**

```c
/* UNSAFE: strtok uses internal static state */
void tokenize(double *out, char *str) {
    char *tok = strtok(str, ",");  // not reentrant!
}
```

Fix: use the `_r` variants (`strtok_r`, `rand_r`, etc.) or thread-local
alternatives.

**5. Lazy-populated global caches**

```c
/* UNSAFE: two threads can both compute and write the same slot */
static double *cache = NULL;
static int cache_size = 0;
double get_cached(int idx) {
    if (idx >= cache_size) {
        cache = realloc(cache, (idx + 1) * sizeof(double));
        cache[idx] = expensive_calc(idx);  // two threads race
        cache_size = idx + 1;
    }
    return cache[idx];
}
```

Fix: pre-allocate at init time, or use a thread-local cache.

**6. SIMD control register manipulation**

```c
/* UNSAFE: other thread's FP operations may interleave */
void set_denormals_zero(void) {
    unsigned int mxcsr;
    asm("stmxcsr %0" : "=m"(mxcsr));
    mxcsr |= (1 << 15);  // set DAZ flag
    asm("ldmxcsr %0" : : "m"(mxcsr));  // affects other threads
}
```

Fix: accept default FP behavior, or use per-thread control (most OSes
save/restore FP state on context switch so this is actually per-thread
on Linux, but it is still fragile).

**7. Assuming GIL protects C global state**

```c
/* UNSAFE without GIL: global counter relies on GIL serialization */
static int call_count = 0;
int myfunc(...) {
    call_count++;  // not atomic on FT builds without GIL
}
```

Fix: use C11 atomics (`atomic_fetch_add`) if you need a counter, or
remove the global counter.

## Performance Timing

See `docs/specification.md` for the full timing documentation.

## Building and Testing

```bash
# Build
c2py23 build mymod.c2py

# Single Python version
bash tests/run_tests.sh python3.12

# All versions via containers
python3 tests/test_all.py

# Valgrind
valgrind --leak-check=full python3 tests/test_leaks.py
```

## Packaging as a Wheel

c2py23 modules can be distributed as multi-platform `py3-none-any` wheels.
One wheel containing .so files for multiple architectures -- pip installs
the same artifact everywhere, the loader selects the right binary at import
time.

### Filename Convention

Each .so is named `_module.c2py23-{os}_{arch}.so`:

```
mymodule/_mymodule.c2py23-linux_x86_64.so
mymodule/_mymodule.c2py23-linux_aarch64.so
mymodule/_mymodule.c2py23-linux_ppc64le.so
```

### Loader

The package's `__init__.py` uses `c2py_loader` to load the right .so
by explicit path.  No `EXTENSION_SUFFIXES` monkeypatching, no `sys.path`
hacking.

```python
import os
from c2py23.c2py_loader import load_native

_mod = load_native(os.path.dirname(os.path.abspath(__file__)), '_mymodule')
for k, v in _mod.__dict__.items():
    if k.startswith('__') and k.endswith('__'):
        continue
    globals()[k] = v
```

Set `C2PY_TRACE=1` to see which .so file was loaded.

### Wheel Setup

The `setup.py` overrides `bdist_wheel.get_tag()` to produce `py3-none-any`:

```python
from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

class BdistWheel(_bdist_wheel):
    def finalize_options(self):
        super().finalize_options(self)
        self.root_is_pure = True

    def get_tag(self):
        return ('py3', 'none', 'any')
```

The .so files are declared as `package_data`, not `ext_modules`, so
`EXT_SUFFIX` is never applied and the filenames are preserved.

### Building

Build the .so inside a manylinux2014 container (glibc 2.17) for
maximum portability:

```bash
c2py23 generate mymodule.c2py -o wrapper.c
gcc -shared -fPIC wrapper.c mymodule.c c2py_runtime.c -ldl -lm \
    -o mymodule/_mymodule.c2py23-linux_x86_64.so
python3 -m build
```

Compile per-architecture in each target container, collect all .so files
into the package directory, then run `python3 -m build` once.  The
resulting wheel installs on any platform.

Python 2.7 users install from sdist (the wheel is `py3`-tagged).

### Complete Example

See `examples/wheel_demo/` for a minimal working project.  Also
`examples/meson_demo/` and `examples/cmake_demo/` for meson and
cmake build system integration.

## See Also

- `docs/specification.md` -- Full grammar, architecture, runtime internals
- `AGENTS.md` -- Contributor guidelines
- `PLAN.md` -- Roadmap and future work
