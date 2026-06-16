# c2py23 Remaining Work

## Not Yet Implemented

### P1: SIMD dispatch / CPU feature detection

**Severity: High** -- Phase 3 blocker for ImageD11

Select C functions based on CPU feature detection at module load time.
Evaluated once at init, not per call. Supports runtime rebinding so the
user can force a specific variant (for benchmarking or bug workarounds).

#### 1. CPU Feature Detection -- Standard Headers

Rather than baking feature names into the parser, c2py23 ships standard
C header files declaring `extern int c2py_<arch>_<feature>` globals.
These are populated during `c2py_runtime_init()` via direct instruction
probing. Users include them via the `headers:` field or from their own
C code.

**Three standard headers** in `c2py23/runtime/`:

| Header | Architecture | Detection mechanism |
|--------|-------------|-------------------|
| `c2py_amd64.h` | x86_64 | `__get_cpuid()` inline asm (leaves 1, 7.0, 7.1) |
| `c2py_arm64.h` | AArch64 | `getauxval(AT_HWCAP)` + `getauxval(AT_HWCAP2)` |
| `c2py_ppc64.h` | POWER | `getauxval(AT_HWCAP)` + `getauxval(AT_HWCAP2)` |

**Feature naming convention**: mirrors gcc/clang's `__builtin_cpu_supports()`
names, prefixed with arch:

```
c2py_amd64_sse2        c2py_amd64_sse3        c2py_amd64_ssse3
c2py_amd64_sse4_1      c2py_amd64_sse4_2      c2py_amd64_avx
c2py_amd64_avx2        c2py_amd64_fma         c2py_amd64_avx512f
c2py_amd64_avx512bw    c2py_amd64_avx512dq    c2py_amd64_avx512vl
c2py_amd64_bmi1        c2py_amd64_bmi2        c2py_amd64_popcnt
c2py_amd64_lzcnt

c2py_arm64_neon        c2py_arm64_asimd       c2py_arm64_aes
c2py_arm64_pmull       c2py_arm64_sha1        c2py_arm64_sha256
c2py_arm64_crc32       c2py_arm64_sve         c2py_arm64_sve2

c2py_ppc64_altivec     c2py_ppc64_vsx         c2py_ppc64_power8
c2py_ppc64_power9
```

**Probing logic**: On x86_64, 3-4 `cpuid` instructions cover all feature
leaves; results are stored once as static int globals. On ARM64/POWER
Linux, `getauxval(AT_HWCAP)` and `getauxval(AT_HWCAP2)` give HWCAP
bitmasks in 1-2 calls. At dispatch time, it's a single truthiness check
(`if (c2py_amd64_avx2)`) -- no bit-testing in the hot path.

#### 2. Two-Level Dispatch Model -- Explicit Nesting

Functions that select on both buffer properties (`.format`, `.n`) and
CPU features (`c2py_amd64_avx2`) need two distinct decision levels:

- **Outer level**: buffer-type dispatch. Selects C types (float* vs double*).
  These casts differ per branch, so no single function pointer can abstract
  over them. Evaluated per-call. Think of each outer entry as a *group*.
- **Inner level**: CPU-variant dispatch. Selects between implementations
  that share the same C signature. Evaluated once at init, pre-resolved.
  Within a group, all variants take the same C parameter types.

The YAML expresses this explicitly rather than relying on auto-detection:

```yaml
functions:
  - py_sig: "fill(data: buffer, value: float) -> void"
    c_overloads:
      # ---- float group ----
      - when: "data.format == 'f'"
        map: {data: "data.ptr", n: "data.n", value: "value"}
        variants:
          - name: "avx512"
            sig: "void fill_avx512(float *data, int n, float value)"
            when: "c2py_amd64_avx512f"
          - name: "avx2"
            sig: "void fill_avx2(float *data, int n, float value)"
            when: "c2py_amd64_avx2"
          - name: "scalar"
            sig: "void fill_scalar_f(float *data, int n, float value)"

      # ---- double group ----
      - when: "data.format == 'd'"
        map: {data: "data.ptr", n: "data.n", value: "value"}
        variants:
          - name: "avx512"
            sig: "void fill_avx512_d(double *data, int n, double value)"
            when: "c2py_amd64_avx512f"
          - name: "scalar"
            sig: "void fill_scalar_d(double *data, int n, double value)"
```

**YAML rules for groups and variants**:

| Field | Level | Required | Semantics |
|-------|-------|----------|-----------|
| `when:` | Group (outer) | Yes on all but last | Per-call dynamic condition (buffer types, sizes) |
| `map:` | Group (outer) | Yes | Shared argument preparation; all variants in the group must use the same C types |
| `variants:` | Group (outer) | Yes | Ordered list of CPU-variant implementations |
| `name:` | Variant (inner) | Yes | Identifier for rebind, docstring, timing |
| `sig:` | Variant (inner) | Yes | C function signature (must match group's map types) |
| `when:` | Variant (inner) | Optional on last | Static CPU-feature condition, resolved once at init |

The outer `when:` on the *last* group may be omitted (catch-all default).
The inner `when:` on the *last* variant may be omitted (catch-all default).

**Generated C**:

```c
/* ---- Level 1: buffer-type dispatch (per-call) ---- */
if (/* data.format == 'f' */) {
    /* float group -- argument prep */
    float *data = (float*)buf_data->buf;
    int n = (int)(buf_data->len / buf_data->itemsize);
    float value = (float)c_value;

    /* Level 2: CPU variant (pre-resolved, see section 3) */
    switch (_fill_float_variant) {
    case 0: fill_avx512(data, n, value); break;
    case 1: fill_avx2(data, n, value);    break;
    default: fill_scalar_f(data, n, value); break;
    }

} else {
    /* double group -- different C types */
    double *data = (double*)buf_data->buf;
    int n = (int)(buf_data->len / buf_data->itemsize);
    double value = c_value;

    switch (_fill_double_variant) {
    case 0: fill_avx512_d(data, n, value); break;
    default: fill_scalar_d(data, n, value); break;
    }
}
```

**Flat functions** (no groups): When there is only one group (e.g., a
function that only takes float), there is no outer if/else. The generated
code is a single flat switch or function pointer. Flat functions can also
use the simpler pre-existing c_overloads syntax without `variants:`:

```yaml
c_overloads:
  - name: "avx512"
    sig: "void fill_avx512(float *data, int n, float value)"
    when: "c2py_amd64_avx512f"
    map: {data: "data.ptr", n: "data.n", value: "value"}
  - name: "avx2"
    sig: "void fill_avx2(float *data, int n, float value)"
    when: "c2py_amd64_avx2"
    map: {data: "data.ptr", n: "data.n", value: "value"}
  - name: "scalar"
    sig: "void fill_scalar(float *data, int n, float value)"
    map: {data: "data.ptr", n: "data.n", value: "value"}
```

When all overloads share the same C signature and all `when:` conditions
are static (CPU features only), the generator resolves them once at init.

#### 3. Switch vs Function Pointer

Within a single *group* (all variants share the same C signature), the
generator picks between two code forms for the pre-resolved dispatch.

**Switch/case (the default)**:

```c
static int _fill_float_variant = -1;
static const char *_fill_float_vname = NULL;

static void _fill_float_resolve(void) {
    if (c2py_amd64_avx512f)  { _fill_float_variant = 0; _fill_float_vname = "avx512"; return; }
    else if (c2py_amd64_avx2) { _fill_float_variant = 1; _fill_float_vname = "avx2";   return; }
    else                      { _fill_float_variant = 2; _fill_float_vname = "scalar";  return; }
}

/* in _impl: */
switch (_fill_float_variant) {
case 0: fill_avx512(data, n, value); break;
case 1: fill_avx2(data, n, value);    break;
default: fill_scalar_f(data, n, value); break;
}
```

**Function pointer (opt-in via `dispatch: static_ptr`)**:

```c
static void (*_fill_float_fn)(float *data, int n, float value) = NULL;
static const char *_fill_float_vname = NULL;

static void _fill_float_resolve(void) {
    if (c2py_amd64_avx512f)  { _fill_float_fn = fill_avx512;    _fill_float_vname = "avx512"; return; }
    else if (c2py_amd64_avx2) { _fill_float_fn = fill_avx2;      _fill_float_vname = "avx2";   return; }
    else                      { _fill_float_fn = fill_scalar_f;   _fill_float_vname = "scalar";  return; }
}

/* in _impl: */
_fill_float_fn(data, n, value);   /* single indirect call, saves ~2-3 cycles */
```

**Switch is the default because**:

| Concern | Switch | Function pointer |
|---------|--------|-----------------|
| Debugging (gdb backtrace) | Shows `fill_avx2` by name | Shows indirect call target as raw address |
| Breakpoints | `b fill_avx2` works directly | Must `b *_fill_float_fn` then step |
| `perf report` symbols | Shows function name per variant | Shows `_fill_float_fn` for all variants |
| SIGILL diagnosis | Fails inside named `fill_avx2` -- obvious which ISA variant is at fault | Fails at anonymous indirect call target -- harder to attribute |
| Signature flexibility | Works with minor signature variation across variants (different arg prep) | Requires identical signatures |
| Branch predictor | Jump table: predicted after first call (~0 cost) | Indirect branch: also predicted after first call |
| Cycles overhead | ~3 for load+index+jump | ~1 for indirect call |

The cycle difference is negligible in practice -- the branch predictor
eliminates it after the first call for both forms. The debuggability
advantages of switch (stack traces, `perf report`, SIGILL attribution)
are the real differentiators. The user opts into function pointers with
`dispatch: static_ptr` at the function level.

#### 4. Runtime Rebinding

Each function with groups or multi-variant dispatch exposes a `.rebind(name_or_group)`
method on its Python function object. Calling `.rebind(None)` re-runs the
CPU-feature-based resolvers for all groups (auto-resolve).

```python
>>> fillmod.fill.rebind('avx2')      # force AVX2 in the active group
>>> fillmod.fill.rebind(None)        # back to auto-resolve for all groups
>>> fillmod.fill.rebind('f:avx512')  # fully qualified: group "f", variant "avx512"
```

Under the hood: `_fill_float_variant` (or `_fill_float_fn`) is a module-level
static variable, adjusted by a C function exposed as a `METH_VARARGS` method.
The rebind method validates the name against the variant `name:` list. If no
group qualifier is given and there is only one group, the unqualified name
selects within that group. If there are multiple groups, the qualifier
`"group:variant"` is required.

**Rebind and timing**: When the user calls `.rebind()`, cached perf state
(min/max/mean) is not reset -- variant selection is an independent dimension
from timing counters. The `variant` field in the perf record shows which
variant was active for the last call.

#### 5. Variant Names

Each variant in a `variants:` list requires a `name:` key for identification in:

- **Docstrings**: Auto-generated doc includes `Variants: avx512, avx2, scalar`
  and `Active: avx2 (forced)` when manually rebound. For multi-group functions,
  variants are listed per group.
- **Rebind API**: `.rebind('avx2')` or `.rebind('f:avx512')` references the name
- **Timing records**: The `variant` field in `c2py_perf_t` records
  which variant handled the last call, and `variant_name` gives the string

```yaml
variants:
  - name: "avx512"
    sig: "..."
    when: "..."
  - name: "avx2"
    sig: "..."
    when: "..."
```

If a user omits `name:` on any variant, the parser raises a validation error.
For flat (non-grouped) overloads with static `when:` conditions, `name:` is
required if any overload has a static condition; optional otherwise.

#### 6. Design Goal: FFTW-Class Flexibility

A key design goal is that c2py23 should allow users to build something as
sophisticated as FFTW's runtime planner without modifying c2py23 itself.
Here is how the plan measures up.

**What FFTW does**: Probes CPU features at init, benchmarks multiple
implementations on sample data, caches the fastest per-size selection
("wisdom"), and dispatches per-call based on problem size.

**What c2py23 supports today in the plan**:

| FFTW capability | Supported? | How |
|-----------------|-----------|-----|
| Multiple ISA variants per operation | Yes | `variants:` list within each group |
| CPU feature detection | Yes | Standard headers + `c2py_cpuid_bit()` for custom bits |
| Init-time variant resolution | Yes | Inner resolve function called at module init |
| Manual variant override | Yes | `.rebind()` method |
| Per-size dispatch (different plan for N=64 vs N=1024) | Yes | Outer groups with `when: "data.n == 64"` etc. |
| Persistence of selections ("wisdom") | No (Python layer) | User calls `.rebind()` from Python after loading saved state |

**What requires user work (not in c2py23, but possible via user C code)**:

1. **Init-time benchmarking**: FFTW runs each variant on sample data at
   init to measure real performance, not just check ISA presence.
   A user can implement this via `__attribute__((constructor))` in their
   C source, running each candidate and writing the result into a static
   global that their `.c2py` file references in `when:` conditions.

2. **Multi-algorithm selection per ISA**: FFTW might choose between two
   different AVX2 implementations based on actual throughput. The user
   can list multiple variants with the same `when:` condition; the
   resolver picks the first that matches CPU features. To select among
   them based on benchmarking, the user's constructor code sets a custom
   global (e.g., `my_best_avx2_variant`) that the variant `when:`
   conditions reference.

3. **Per-size planning data**: FFTW stores per-size wisdom. c2py23's
   outer groups handle per-size dispatch, but the user must write the
   C code that maps sizes to implementations. The outermost `when:`
   conditions on groups can check user-maintained size-to-variant
   lookup tables.

**Gaps -- what would require c2py23 changes**:

- **Automatic benchmarking orchestrator**: A built-in mechanism that
  runs each variant on a caller-supplied test vector at init and
  selects the fastest. This could be a future feature (e.g., a
  `benchmark:` key) but is not in scope for P1.
- **Direct variant-to-variant comparison API**: A way to call two
  variants with the same arguments and compare timings. Users can
  already do this via `.rebind()` + timing records.

**Verdict**: A user *can* build an FFTW-like planner on top of c2py23
without modifying c2py23, by providing their own init-time benchmark
code and mapping results to the variant dispatch chain. The plumbing
is there; the planning intelligence is the user's responsibility.

#### 7. Timing Integration

The `c2py_perf_t` struct gains a `variant` field (uint32_t) set to the
variant index (0-based within its group) before each C call, and a
`group_idx` field identifying which outer group was active. The existing
per-overload `_perf_<func>__<cname>` timing structs continue to work
unchanged.

Python `read_perf()` returns `variant`, `variant_name`, and `group_idx`
in the result dict when the module has variant dispatch.

#### 8. User-Defined Features

Users who need a CPU feature not in the standard headers can provide
their own C file using the runtime's static inline `c2py_cpuid_bit()`:

```c
// my_features.c
#include "c2py_runtime.h"

int my_custom_feature = 0;

#ifdef __x86_64__
__attribute__((constructor))
static void _init_my_features(void) {
    my_custom_feature = c2py_cpuid_bit(7, 0, 3, 31);  // leaf 7, sub 0, EDX[31]
}
#endif
```

`c2py_cpuid_bit()` is a static inline in `c2py_runtime.h` that wraps
the `cpuid` instruction (or returns 0 on non-x86). It does not depend
on `c2py_runtime_init()` having run, so it is safe to call from
`__attribute__((constructor))` functions.

#### 9. GPU Dispatch -- Open Door (Deferred)

GPU pointers and CUDA/OpenCL kernel dispatch are out of scope for P1,
but the dispatch architecture does not close any doors:

- User initializes their GPU context externally (c2py23 does not own it)
- User sets a custom feature flag: `mymod.set_feature('has_cuda', 1)`
- The C overload for the GPU kernel is dispatched via the same
  group/variant mechanism, conditioned on the user's flag
- For now, passing GPU device pointers requires a new Python type
  (`address`) that maps `int` -> `(float*)(intptr_t)` in C. This is a
  separate, future feature.

#### 10. Parser and Generator Changes Required

| Component | Change |
|-----------|--------|
| **Parser** | Accept `variants:` sub-list on overload entries (mutually exclusive with flat `sig:`/`when:`/`map:`) |
| **Parser** | Accept `name:` key on each variant (required in `variants:`, optional in flat overloads with static conditions) |
| **Parser** | Accept `group` key (for explicit group naming, used in rebind qualifiers and docstrings) |
| **Parser** | Accept `dispatch:` key on functions: `"static_ptr"` to opt into function-pointer form (default is switch) |
| **Parser** | Validate that inner `variants:` `when:` conditions are static (no buffer/scalar refs); flag dynamic conditions with a warning |
| **Generator** | For grouped dispatch: emit outer if/else + inner switch (or fn ptr) + per-group resolve functions + rebind method |
| **Generator** | For flat dispatch with static conditions: emit single switch (or fn ptr) + resolve function + rebind method |
| **Generator** | For flat dispatch with dynamic conditions (default): keep existing if/else chain |
| **Generator** | Detect identical C signatures across variants in a group for fn-ptr vs switch choice |
| **Generator** | Emit variant name strings, group indices, and variant indices in timing records |
| **Generator** | Append variant/group info to auto-generated docstrings |
| **Runtime** | Add CPUID/getauxval probing in `c2py_runtime_init()` |
| **Runtime** | Add `variant` and `group_idx` fields to `c2py_perf_t` |
| **Runtime** | Provide `c2py_cpuid_bit()` static inline for user extensibility |
| **New files** | `c2py23/runtime/c2py_amd64.h`, `c2py23/runtime/c2py_arm64.h`, `c2py23/runtime/c2py_ppc64.h` |

**Files**: parser.py, generator.py, c2py_runtime.h, c2py_runtime.c, perf.py,
3 new feature header files.

#### 11. Example: bslz4_to_sparse Port

The existing f2py-based project at `../bslz4_to_sparse` maps to c2py23
as follows. The SIMD dispatch lives inside `bitshuf_decode_block()` (kcb
library uses GNU IFUNC internally), so c2py23 does not dispatch between
SIMD variants at the wrapper level -- it just wraps the top-level function:

```yaml
module: bslz4_to_sparse
source: [bslz4_to_sparse.c, lz4.c, bitshuffle.c]
headers: [c2py_amd64.h]

functions:
  - expand:
      DTYPE: [uint8_t, uint16_t, uint32_t]
      SUFFIX: [u8, u16, u32]
    py_sig: "bslz4_${SUFFIX}(cmp: buffer, num: int, cut: int, mask: buffer, pb: buffer) -> int"
    c_overloads:
      - sig: "int bslz4_${SUFFIX}(const ${DTYPE} *cmp, int num, int cut, const ${DTYPE} *mask, ${DTYPE} *pb)"
        map:
          cmp:  "cmp.ptr"
          num:  "num"
          cut:  "cut"
          mask: "mask.ptr"
          pb:   "pb.ptr"
```

Where the user DOES want c2py23 to dispatch between hand-rolled
microkernels (e.g. NASM assembly functions), the group/variant pattern
with `when: "c2py_amd64_avx2"` handles it.

---

### P2: GIL release via `gil_release: true`

**Severity: High** -- enables true Python-thread parallelism

Add a `gil_release: true` key on functions or per-overload. The wrapper calls
`PyEval_SaveThread` before the C call and `PyEval_RestoreThread` after.

**Safety model -- buffer references, not content locks:**

The wrapper acquires `Py_buffer` structs during argument parsing, before
releasing the GIL. These references keep the underlying Python objects alive
so memory cannot be freed. However, a second Python thread that also holds a
buffer reference to the same object can still write to it. This is the caller's
responsibility, not c2py23's. The philosophy is that a real programmer knows
what they are doing: you tag a function `gil_release: true` if you know the
C code can tolerate concurrent buffer mutation from other Python threads.

**OpenMP is about oversubscription, not correctness:**

OpenMP threads within a single call are safe regardless of GIL state -- the
GIL only serializes Python threads. The concern is oversubscription: if N
Python threads each launch an M-way OpenMP call, N*M threads compete for
cores. The user may choose NOT to release the GIL specifically to prevent
this. The decision depends on the workload.

**Global toggle:**

A module-level runtime flag `_c2py_gil_release_enabled` (similar to the timing
`_c2py_timing_enabled` flag) lets callers globally disable GIL release across
all functions. This allows the same `.so` to work in both serial and parallel
contexts without recompilation. Per-function `get_gil_release` / `set_gil_release`
methods on each Python function object expose the individual toggle.

**Free-threading (P3):** On 3.14+ free-threaded builds the GIL is absent.
The `gil_release` flag becomes a no-op, but the buffer-acquisition path needs
atomic refcounting. See P3 below.

**Files**: parser.py, generator.py, c2py_runtime.h/c.
**Design doc**: docs/specification.md `## GIL Release and Thread Safety`.

---

### P3: Free-threaded Python 3.14+ thread safety

**Severity: Medium** (future-facing)

When the GIL is optional (3.14 free-threaded builds), wrap critical sections
for atomic refcounting and buffer acquisition.

**Files**: c2py_runtime.h/c, generator.py.

---

### P4: Binary wheel distribution

**Severity: Low** -- replaces --no-build-isolation workflow

Publish binary wheels to PyPI: one per platform (linux, windows, macos) and
one per architecture (x86_64, aarch64). Python-version-independent (the .so
works on 2.7-3.14 via nimpy trick). Similar to ctypes-style distribution --
install via pip, import from any Python version. May need a wrapper import
mechanism or `ctypes.CDLL` loader bootstrap.

**Status: DEFERRED** -- design TBD, implement later.

---

## Completed

- P0: Parameter count validation -- raises ValueError on sig mismatch
- P2: GIL release (`gil_release: true`) -- global toggle, per-function enable, tested
- YAML type coercion -- auto-coerce bare int/float in map/when/checks
- Better check failure messages -- include actual runtime values
- Buffer format vs C type compile-time validation -- raises ValueError
- Output scalar convention -- `outputs:` key, auto-alloc, tuple return
- Template expansion -- `expand:` key with `${VAR}` substitution
- Comprehensive dispatch-over-all-types example -- typedispatch test case, Example 4 in spec
- Valgrind/ASan validation -- stress test, cleanup audit, `--asan` flag
- Test coverage -- 10 versions x 13 uniform tests, 10 peer review tests
- GIL release design rationale -- documented in specification.md
- ABI matrix populated across all 10 Python versions
- Arch-specific clocks -- rdtsc (x86), CNTVCT_EL0 (ARM64), mftb (POWER)
- int64_t/uint64_t 32-bit fix -- PyLong_FromLongLong macro
- Py_buffer size fix -- 80 bytes for 3.x, 96 for 2.x (ABI matrix)
- Fixed-width C types (int8_t..uint64_t)
- Optional params with defaults (int/float only)
- Custom docstrings (`doc:` key)
- Module-level integer constants
- Format char dispatch (all single-byte PEP 3118 formats)
- METH_FASTCALL vectorcall for Python 3.11+
- Py_buffer size detection (dynamic, version-based)
- Py_IncRef fallback for pre-3.12 (manual refcount incr)
- `or` operator in when/checks conditions
- Per-function perf timing with ctypes decode
- `__array_struct__` evaluated and removed
- Buffer struct layout mismatch fixed
- `-Wall -Werror` clean on all generated code
- 10 Python versions in test matrix (2.7, 3.6-3.14)
- Contiguity check: rejects strided arrays, negative strides, accepts C/F-contiguous
- Alias detection: rejects buffer aliasing between writable buffers (5 patterns)
- Shared-refcount fix: PyExc_* always dereferenced once (handles pre-3.12 heap-type pointers and 3.12+ static shared-refcount)
- Debug build support: `--asan` flag, `CC`/`CFLAGS`/`LDFLAGS` env vars, `gcc -shared -g -O0`

### Reviewer Response

**Status: Pending** -- A formal response to the three referee reports (2026-06-15,
concatenated in `docs/referee_reports.md`) should be written after all HIGH and
MEDIUM severity items from the reports are resolved. The response will address
each report point-by-point, describing fixes applied and rationale for items
deferred.

The combined bug list and current resolution status is in `docs/referee_reports.md`.
