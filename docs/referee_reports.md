# Referee Reports

**Received:** 2026-06-15

---

## Report 1

I only got a partial view of the codebase, but there are a few things that immediately stand out as worth checking before you freeze the feature set.

## Potentially serious issues

### 1. GIL restore is not exception-safe in generated wrappers

In `_emit_c_call()` I see patterns like:

```c
if (_c2py_do_gil)
    _c2py_thread_state = PyEval_SaveThread();

... call C ...

if (_c2py_do_gil)
    PyEval_RestoreThread(_c2py_thread_state);

return PyLong_FromLong(...);
```

This is fine if the C function always returns normally.

The thing I'd audit carefully is:

* any generated path that can `return NULL`
* any generated path that can jump to cleanup
* any future feature that may allow C callbacks into Python

If a generated path exits before `PyEval_RestoreThread()`, you have interpreter corruption.

I couldn't see a concrete bug in the snippet, but this is the first place I'd attack with ASan + stress testing.

---

### 2. `PyTuple_SetItem()` return values ignored

I saw code like:

```c
PyTuple_SetItem(_c2py_tup, i,
                PyLong_FromLong(...));
```

No return value is checked.

That means:

* tuple insertion failure is ignored
* object creation failure is ignored

In practice memory allocation failures are rare, but this is still technically incorrect CPython API usage.

Safer pattern:

```c
obj = PyLong_FromLong(...);
if (!obj) goto fail;

if (PyTuple_SetItem(tup, i, obj) != 0) {
    Py_DECREF(obj);
    goto fail;
}
```

---

### 3. Runtime ABI assumptions are the highest-risk part of the project

The entire design depends on:

```c
dlopen(NULL)
dlsym(...)
```

plus hand-rolled definitions of:

```c
PyObject
Py_buffer
PyModuleDef
PyMethodDef
```

This is where I would expect future breakage.

You already mention:

* Python 3.12 immortal/shared-refcount changes
* Py_buffer size differences
* manual refcount fallback

Those are exactly the sort of things that tend to keep appearing.

The project is effectively maintaining a mini CPython ABI layer.

That isn't a reason not to do it, but it is where I'd expect future bugs.

 

---

### 4. Free-threaded Python is probably a larger problem than the plan suggests

Your plan says:

> buffer-acquisition path needs atomic refcounting

I suspect the scope is larger than that.

Things I'd verify against the latest free-threading work:

* manual refcount fallback
* immortal object handling
* exception object access
* global timing structures
* global GIL toggle variables
* any static module state

I would treat free-threaded support as a major compatibility project rather than a small runtime patch.



---

### 5. CPU feature detection via `/proc/cpuinfo`

I would strongly recommend against making `/proc/cpuinfo` the primary mechanism.

Reasons:

* Linux-specific
* container weirdness
* VM weirdness
* future portability problems

Your own planning note already suggests CPUID/MRS as preferred.

I would make:

* x86 → CPUID
* ARM64 → architectural registers
* `/proc/cpuinfo` only as fallback

---

### 6. One detail in the wrapper generator worries me

I saw:

```python
if p.pytype == 'int':
    fmt += 'i'
```

which maps to:

```c
int c_x;
PyArg_ParseTuple(..., "i", &c_x)
```

If you're trying to support scientific/HPC code long term, I'd strongly consider:

```yaml
int32
int64
size_t
ssize_t
```

rather than overloading everything onto C `int`.

You already support fixed-width types internally, so this looks like a place where users may eventually hit limitations.

---

## Things I actually like

A few design choices look unusually sensible:

### Alias checking

The decision to reject writable aliasing and allow generated C to assume:

```c
restrict
```

is a good one.

That is exactly the kind of invariant that pays off later.

### Output scalar convention

The

```yaml
outputs:
```

approach is clean and very f2py-like.

### Compile-time format validation

Checking

```yaml
a.format == 'd'
```

against

```c
double *
```

at generation time is the right direction.

Many wrapper generators leave that until runtime.

---

# Open-source projects I'd use to test c2py23

I'd pick codebases that are:

* small
* numerical
* mostly plain C
* already called from Python

### 1. Cephes

Cephes Mathematical Functions Library

Very good for:

* scalar numerical kernels
* transcendental functions
* mixed float/double APIs

You can wrap individual functions rapidly and test ABI handling.

---

### 2. cminpack

cminpack

Good test cases:

* pointer-heavy APIs
* work arrays
* output parameters

This will exercise your `outputs:` machinery.

---

### 3. FFTPACK

FFTPACK

Excellent for:

* large buffer inputs
* contiguous memory assumptions
* performance timing

---

### 4. KissFFT

KissFFT

Probably my first choice.

Why:

* small codebase
* plain C
* widely used
* easy to understand
* enough complexity to stress the wrapper generator

---

### 5. stb-style numerical modules

stb

Not strictly numerical, but useful because:

* single-header
* lots of pointer-heavy APIs
* easy integration

Good for code generation stress testing.

---

# If I were locking the feature set

I would freeze after:

1. SIMD dispatch
2. GIL release stabilization
3. one serious external codebase validation (KissFFT or cminpack)

and deliberately postpone:

* free-threaded Python
* wheel distribution
* additional DSL features

The generator/runtime boundary already contains most of the complexity. Every new language feature multiplies the number of code paths you need to validate across Python 2.7–3.14.

From what I can see, the biggest technical risk isn't the wrapper generation itself—it's maintaining the hand-rolled CPython ABI compatibility layer over future interpreter changes. That runtime deserves the majority of your testing budget.

---

## Report 2

Based on the documentation, architecture notes, and code snippets provided in your codebase, here is a review of your design, potential blind spots, and suggestions for open-source C libraries to use as stress tests before you freeze your feature set.

### 1. Design Review & Potential Bugs

Your design of using a nimpy-style runtime (`dlopen(NULL)`) with the `PEP 3118` buffer protocol to maintain compatibility from Python 2.7 to 3.14 is highly ambitious and elegant. However, there are a few edge cases and systemic risks to address:

* **Static Linking/Embedded Interpreter Failure (`dlopen(NULL)`):**
The `dlopen(NULL)` and `dlsym()` trick relies on the host executable exporting Python API symbols dynamically. If `c2py23` is loaded into a Python interpreter that was compiled statically (without `--enable-shared` or `export-dynamic`), `dlsym` will fail to resolve standard Python functions like `PyArg_ParseTuple`, resulting in a fatal error or crash on load. You should explicitly check for `NULL` on your primary `dlsym` resolutions during `module_init` and raise a descriptive `ImportError` rather than crashing.
* **Buffer Alignment Constraints (SIMD Hazard):**
In `PLAN.md`, you mention implementing AVX2/AVX512/NEON SIMD dispatch (P1). SIMD instructions frequently require strict memory alignment (e.g., 32-byte alignment for AVX2, 64-byte for AVX512). If a user passes a Python `bytearray` or a sliced `memoryview`, the `a.ptr` might not be properly aligned. The generated wrapper should optionally perform a `(uintptr_t)ptr % alignment == 0` check in the `when:` condition to safely fall back to a scalar loop.
* **The Python 2.7 Buffer Protocol Fallback:**
You fall back to `PyObject_AsReadBuffer` / `PyObject_AsWriteBuffer` for Python 2.7. Keep in mind that this old protocol cannot accurately convey multi-dimensional shapes or strides. If you accept a `memoryview` in Python 2.7 of a non-contiguous slice, `AsReadBuffer` might just hand you the raw underlying pointer, leading your C code to read incorrect, out-of-bounds, or misaligned data. You must ensure that stride validation strictly fails out on Py2.7 if non-C-contiguous strides are detected.
* **Free-Threaded Refcounting (Python 3.14+):**
Your `PLAN.md` correctly identifies this (P3). Without the GIL, doing a standard `Py_INCREF` on the buffer's parent object or exceptions is a race condition. Since you want to freeze the API soon, you should at least add a pre-processor guard `Py_GIL_DISABLED` in `c2py_runtime.c` that forces atomic reference counting (e.g., `_Py_NewRef`) if compiled under a 3.14 free-threaded environment, otherwise it will randomly segfault during heavy load.
* **Output Scalar Tuple Allocation (`outputs:`):**
If the wrapper automatically allocates Python tuple values for scalar outputs, ensure that if your wrapper fails *after* allocating the tuple but *before* returning (e.g., an exception in a subsequent check), you correctly decrement the reference count of the allocated Python objects to prevent a memory leak.

### 2. Recommended Open-Source C Code for Validation

To ensure your system is robust enough for a feature freeze, you should wrap widely used, single-header (or small) C libraries that natively use flat memory arrays. This will test your type generation, optional parameters, and buffer bounds.

#### A. Compression: `lz4`

* **Why it's a good test:** It relies strictly on contiguous `char*` / `uint8_t` memory buffers. It tests `buffer` inputs, `buffer` outputs, and integer return types for the compressed sizes.
* **Function to wrap:** `LZ4_compress_default(const char* src, char* dst, int srcSize, int dstCapacity);`
* **What it proves:** Validation of single-byte elements, output bounds mapping (`dstCapacity`), and validating that your zero-copy setup accurately modifies the `bytearray` or `bytes` object directly.

#### B. Image Processing: `stb_image_resize2`

* **Why it's a good test:** Image manipulation uses huge multi-dimensional flat arrays (`H x W x Channels`), heavy memory access, and has optional stride parameters. It is an ideal stand-in for the `ImageD11` workflows mentioned in your `PLAN.md`.
* **Function to wrap:** `stbir_resize_uint8_linear(const unsigned char *input_pixels, int input_w, int input_h, int input_stride_in_bytes, ...)`
* **What it proves:** Tests your YAML `map:` functionality extensively by mapping Python buffer `.shape[0]` and `.shape[1]` to the width, height, and stride integer arguments dynamically.

#### C. Hashing/Cryptography: `xxHash`

* **Why it's a good test:** Fast, non-cryptographic hashing. It requires strict memory bounds, returns a 64-bit integer, and takes an optional seed integer.
* **Function to wrap:** `XXH64(const void* input, size_t length, unsigned long long seed);`
* **What it proves:** Ensures `uint64_t` scalar returns function correctly (especially verifying the 32-bit `PyLong_FromLongLong` fix you mentioned in `PLAN.md`). It also tests `void*` input buffers if you decide to allow generic buffer acceptance without strict type checking.

#### D. Basic Linear Algebra: `CBLAS` (e.g., from OpenBLAS)

* **Why it's a good test:** The ultimate test for array passing, type constraints (`float` vs `double`), and GIL release scaling.
* **Function to wrap:** `cblas_dgemm(const enum CBLAS_ORDER Order, ... const double *A, int lda, const double *B, int ldb, double *C, int ldc);`
* **What it proves:** Because Matrix Multiplication is computationally intensive, applying your `gil_release: true` tag to this function and hitting it with Python's `threading` module will instantly prove if your GIL management and buffer-reference pinning holds up under high concurrency without leaking or crashing.

---

## Report 3

# c2py23 Code Review

## Executive Summary

This is a well-designed, well-documented project. The nimpy-style dlopen/dlsym approach
is the right call for spanning Python 2.7–3.14 without linking against libpython, and the
ABI matrix validation work is thorough. The buffer protocol handling, contiguity checks,
and alias detection are sound. The issues below are a mix of genuine bugs (a few are
real UB or correctness problems) and design concerns worth addressing before an API freeze.

---

## Confirmed Bugs

### B1: VARARGS wrapper — 3-argument function cast to 2-argument PyCFunction (UB)

**File:** `generator.py`, `_emit_varargs_wrapper`

The generated VARARGS wrapper is declared with a `kwargs` parameter:
```c
static PyObject* _name_wrapper(PyObject *self, PyObject *args, PyObject *kwargs)
```

But it is registered as `METH_VARARGS` and cast to `PyCFunction`:
```c
{"name", (PyCFunction)_name_wrapper, METH_VARARGS, "doc"},
```

`PyCFunction` is `PyObject* (*)(PyObject*, PyObject*)` — only two parameters. Calling
a 3-parameter function through a 2-parameter function pointer is **undefined behaviour**
in C. On x86-64 System V ABI the third argument lands in `rdx`, which contains
whatever was in that register; `kwargs` picks up garbage. In practice it is benign
because `kwargs` is never read, but it is strict UB and will cause warnings with
`-Wall -Werror -Wpedantic` and could theoretically break under LTO or exotic ABIs.

**Fix:** Remove `kwargs` from the VARARGS wrapper signature:
```c
static PyObject* _name_wrapper(PyObject *self, PyObject *args)
```

The generated line to change is in `_emit_varargs_wrapper`:
```python
# Current:
out.append('_' + name + '_wrapper(PyObject *self, PyObject *args, PyObject *kwargs)')
# Fixed:
out.append('_' + name + '_wrapper(PyObject *self, PyObject *args)')
```

---

### B2: `_c2py_dec_ref_manual` does not invoke the destructor

**File:** `c2py_runtime.h`

```c
static inline void _c2py_dec_ref_manual(PyObject *op)
{
    --op->ob_refcnt;
}
```

A correct `Py_DECREF` must call `_Py_Dealloc(op)` when the refcount reaches zero.
This fallback is invoked on Python < 3.12 where `Py_DecRef` / `_Py_DecRef` are not
exported. Currently `Py_DECREF` is only used implicitly via `PyTuple_SetItem` through
the C API (which uses the interpreter's own decref machinery), and `Py_RETURN_NONE`
calls IncRef not DecRef, so the bug is **latent but not currently triggered**.

However, the `DecRef` function pointer is in the exported table, and any future code
that calls `Py_DECREF()` on objects created by c2py23 wrappers (e.g., tuple elements
during error paths) would silently leak. This is a time-bomb.

**Fix:** Either implement proper dealloc dispatch, or add a hard assertion that
`_c2py_dec_ref_manual` must not be reached (since on Python 2.7 the interpreter
handles the decrefs internally through the API calls anyway):
```c
static inline void _c2py_dec_ref_manual(PyObject *op)
{
    if (--op->ob_refcnt == 0) {
        /* We cannot call _Py_Dealloc without knowing its symbol name.
         * This path should be unreachable if the C API is used correctly. */
        fprintf(stderr, "c2py_runtime: _c2py_dec_ref_manual reached zero refcount "
                "for %p -- possible leak\n", (void*)op);
    }
}
```

---

### B3: `_parse_c_sig` — dead code and silent failure on malformed input

**File:** `parser.py`

Two issues in the same function:

**B3a:** `after_paren` is computed from `rfind(')')` (last closing paren) but is never
used. The actual suffix parsing uses `remaining_after`, computed correctly from
`paren_end`. `after_paren` is dead code that also shadows intent by using `rfind`
instead of the proper paren-matched position.

```python
after_paren = sig_str[sig_str.rfind(')') + 1:].strip()  # dead, remove
```

**B3b:** If there is no matching `)` in the input, the loop ends without updating
`paren_end` (it stays at `paren_start`), so:
```python
params_str = sig_str[paren_start + 1:paren_end]  # empty string, silently
```
This produces an empty parameter list instead of a clear parse error.

**Fix:**
```python
# After the loop:
if depth != 0:
    raise ValueError("Unmatched '(' in C signature '{}' in {}".format(sig_str, path))
```

---

### B4: `_FORMAT_TO_CTYPE['L']` maps to `'unsigned int'` which is not in `_C_TYPES_INT`

**File:** `parser.py`

```python
_FORMAT_TO_CTYPE = {
    ...
    'L': 'unsigned int',   # <-- not in _C_TYPES_INT
    ...
}
```

`_C_TYPES_INT` contains `'int'`, `'uint32_t'`, etc., but not `'unsigned int'`.
If a user writes `checks: "arr.format == 'L'"` and uses a `uint32_t *` C parameter,
the P4 validation in `_validate_module` compares `'unsigned int' != 'uint32_t'` and
raises a false `ValueError`. The platform-native `unsigned int` is `uint32_t` on
LP64, so the check should either map `'L'` to `'uint32_t'` or remove it from the
dict (since `'L'` is not a reliably-sized PEP 3118 format — its size is platform
dependent, unlike `'I'` = uint32_t and `'Q'` = uint64_t).

**Fix:** Either map `'L'` to `'uint32_t'` (matching what ctypes uses on LP64), or
remove the entry and document that `'L'` is unsupported:
```python
# 'l': 'int32_t',   # 'l' is platform-sized on PEP 3118; 'i' is fixed int32
# 'L': 'uint32_t',  # same; use 'I' for fixed uint32
```

The same concern applies to `'l'` -> `'int'`, since PEP 3118 defines `'l'` as a
platform-native signed long (not necessarily 32-bit), yet the mapping compares it
against `'int'`. This will be a false positive failure on any ILP64 platform.

---

### B5: `subprocess.run` used in test orchestration scripts despite AGENTS.md rule

**Files:** `tests/populate_abi_matrix.py`, `tests/test_all.py`

AGENTS.md says: *"NO `subprocess.run()` in test runner code (Python 3.5+ only)"*.
Both `populate_abi_matrix.py` and `test_all.py` use `subprocess.run(...)` with
`capture_output=True` (Python 3.7+). These scripts have `#!/usr/bin/env python3`
shebangs, so the rule-vs-practice gap is probably intentional (they run on the
host where Python 3.7+ is assumed). But the blanket AGENTS.md rule should be
narrowed to clarify which files are host-only vs in-container. Otherwise an AI
agent following AGENTS.md will "fix" valid host-side code and introduce bugs.

**Fix:** Add a note to AGENTS.md:
```
# Exception: tests/test_all.py and tests/populate_abi_matrix.py are host-only
# orchestration scripts. They require Python 3.7+ on the host and may use
# subprocess.run(). The 2.7 compat rule applies only to files that run
# inside containers.
```

---

## Potential Issues / Design Risks

### P1: `PyErr_Clear` resolved without `RESOLVE_REQ`

**File:** `c2py_runtime.c`

```c
C2PY.Err_Clear = (void (*)(void))dlsym(dl, "PyErr_Clear");
```

`PyErr_Clear` is part of Python's stable ABI and is exported on all CPython builds
from 2.7 through 3.14. However, it is not guarded with `RESOLVE_REQ`, so if it ever
returns NULL (e.g., a stripped embed build), calling `PyErr_Clear()` in
`c2py_acquire_buffer` on the fallback path would be a NULL function pointer
dereference. Cost of fix is one line:
```c
RESOLVE_REQ(C2PY.Err_Clear, "PyErr_Clear");
```

---

### P2: `c2py_runtime_init()` is not thread-safe

**File:** `c2py_runtime.c`

```c
if (C2PY.dl_handle != NULL) {
    return 0; /* Already initialized */
}
```

Two threads calling `PyInit_<name>()` simultaneously can both pass this check and both
initialize the table concurrently. Python's import lock serializes module imports in
the main GIL-enabled builds, so this is unlikely in practice. But on free-threaded
3.14 builds (P3 work item), the import lock behaviour changes. A simple fix now
(before 3.14 matters) is a static flag with `__atomic_compare_exchange` or
`pthread_once`, or simply document the assumption.

---

### P3: Manual `Py_buffer` struct size on 32-bit platforms is unverified

**File:** `c2py_runtime.h`

```c
#if defined(__LP64__) || defined(_WIN64)
#define C2PY_PYBUFFER_SZ_PRE312   96
#define C2PY_PYBUFFER_SZ_POST312  80
#else
#define C2PY_PYBUFFER_SZ_PRE312   52
#define C2PY_PYBUFFER_SZ_POST312  44
#endif
```

The 32-bit sizes (52/44) are not in the ABI matrix — which only covers `Linux-x86_64`.
If ImageD11 ever runs on 32-bit ARM or x86, these values may be wrong. The `check_abi.c`
tool reports `sizeof(Py_buffer)` directly; consider adding at least one 32-bit container
to the ABI matrix, or adding a runtime assertion:
```c
if (C2PY.pybuffer_size < sizeof(Py_buffer) - 16) {  /* sanity margin */
    fprintf(stderr, "c2py_runtime: Py_buffer size mismatch: expected ~%zu, got %zd\n",
            sizeof(Py_buffer), C2PY.pybuffer_size);
    return -1;
}
```

---

### P4: `_coerce_expr_value` warning message has swapped format arguments

**File:** `parser.py`

```python
warnings.warn(
    "%s value '%s: %s' in %s is %s; auto-coercing to str. ..."
    % (context, val, type(val).__name__, path, val, val))
```

The intent reads as `"map value 'verbose: 0' in foo.c2py is int"`. But `val` is `0`
and `type(val).__name__` is `"int"`, so the quoted portion renders as `'0: int'`
(value then type) rather than the expected `'verbose: 0'` (key then value). The key
name is not passed to the function, so the best fix is to clarify the message:
```python
warnings.warn(
    "{ctx} value in {path} is a bare {typ} ({val!r}); "
    "auto-coercing to string. Quote it: \"{val}\"".format(
        ctx=context, path=path, typ=type(val).__name__, val=val))
```

---

### P5: Generated C files do not end with a newline

**File:** `generator.py`, `generate()`

`'\n'.join(out)` does not append a trailing newline. Most C compilers accept this
but emit `-Wnewline-eof` with Clang, and some static analysis tools flag it. One
extra character:
```python
return '\n'.join(out) + '\n'
```

---

### P6: `format_check` diagnostic uses `strlen` on potentially NULL format

The format check diagnostic in `_make_compare_diag` emits:
```c
const char *_fmt = buf_a->format ? buf_a->format : "";
char _got = _fmt[0] ? _fmt[strlen(_fmt) - 1] : '?';
```

`_fmt` is guaranteed non-NULL after the ternary. The last-char extraction
(`_fmt[strlen(_fmt) - 1]`) correctly handles the PEP 3118 endian-prefix formats
(`"<d"` → `'d'`). This is correct. Just worth documenting the pattern since it's
non-obvious.

---

## Design Observations for API Freeze

### D1: Format characters 'l' and 'L' have platform-dependent widths

PEP 3118 defines `'l'` as `signed long` (4 bytes on LLP64/Windows, 8 bytes on LP64/Linux)
and `'L'` as `unsigned long`. This means a numpy `int64` array on Linux reports format
`'l'`, but on Windows it would report `'q'`. The `_FORMAT_TO_CTYPE` mapping `'l' -> 'int'`
is Linux/LP64-specific. If ImageD11 or any downstream user ever runs on Windows,
dispatch-by-format for 64-bit integers will silently use the wrong C type.

For the API freeze, consider:
- Documenting that `'l'` and `'L'` support is LP64-only
- Or normalising to `'q'`/`'Q'` in the format check recommendation

---

### D2: No negative-integer default value support in `_PY_PARAM_RE`

The parameter regex is:
```python
_PY_PARAM_RE = re.compile(
    r'^(\w+)\s*:\s*(buffer|int|float)\s*(?:=\s*(-?\d+\.?\d*))?\s*$'
)
```

The `(-?\\d+\\.?\\d*)` portion supports `-3.14` but not scientific notation like `1e-5`
or bare `.5`. For an int/float defaulted parameter this is probably fine for ImageD11,
but worth noting.

---

### D3: `outputs:` mapping order determines tuple order — unspecified

The order of `outputs:` values in the Python return tuple follows `ol.params` order
(the C parameter list order), not the `outputs:` dict insertion order. YAML dicts in
PyYAML 5.1+ preserve insertion order on Python 3.7+, but on Python 2.7 (where `dict`
is unordered), the order of output values in the return tuple may vary. If this project
supports Python 2.7, the returned tuple order for multi-output functions is
non-deterministic on that version.

**Fix:** Document that tuple order matches C parameter order (which is always stable),
and in `_emit_c_call`, build `out_items` in `ol.params` order (not `outputs:` dict order).
The current code already does this — just ensure it is documented:
```yaml
# outputs order in the returned tuple ALWAYS matches C parameter order,
# regardless of YAML dict order.
```

---

## Open-Source C Code to Test Against

These are specific open-source modules that stress the features you want to freeze.
Each maps clearly to one or more c2py23 mechanisms.

### 1. Kiss FFT (`github.com/mborgerding/kissfft`)

A minimal, dependency-free FFT in ~500 lines of C99. Wrapping it would test:
- **Complex format dispatch**: `'f'` (float) vs `'d'` (double) overloads
- **Const input / writable output** in the same call
- **`int` return value** (error code)

The `kiss_fft()` signature:
```c
void kiss_fft(kiss_fft_cfg cfg, const kiss_fft_cpx *fin, kiss_fft_cpx *fout);
```
This maps naturally with `checks: fin.n == fout.n`.

### 2. CBLAS-style `daxpy` / `saxpy` (BLAS reference implementation, netlib.org)

The BLAS Level 1 routines (`daxpy`, `saxpy`, `ddot`, `dnrm2`) are pure C99 and
give you:
- **Float vs double dispatch** on a well-understood API
- **Scalar parameter** (`alpha: float`)
- **Optional `incx`/`incy`** stride parameters (default 1) → tests `optional` feature

```c
void daxpy(int n, double da, const double *dx, int incx, double *dy, int incy);
```

You can build a test by wrapping just the 4 double/float variants and comparing
to the reference output.

### 3. A reference histogram kernel (write a 20-line C file)

Wrap a typed histogram accumulator:
```c
void histogram_u16(const uint16_t *data, int n, uint32_t *hist, int nbins, uint16_t lo);
```

Tests:
- **`uint16_t *` read buffer + `uint32_t *` write buffer** in one call
- **Type mismatch detection** via P4 validation (if the check and C type diverge)
- **Alias detection**: passing the same buffer for `data` and `hist` should raise

### 4. 2D median filter (3×3, strided over columns)

A simple 3×3 median filter on `float32` or `uint16` images:
```c
void median3x3_f32(const float *src, float *dst, int rows, int cols);
```

Tests:
- **2D shape dispatch** (`points.ndim == 2`, `points.shape[0]` / `points.shape[1]`)
- **Large n** (megapixel images) to stress GIL release
- **Contiguity enforcement**: strided input should be rejected

This also makes a realistic end-to-end test that matches ImageD11's image processing
patterns.

### 5. A trivial `(n, 3)` coordinate transform (for SIMD dispatch planning)

Write two variants:
```c
void peak_to_lab_scalar(const double *peak, int n, double *lab);
void peak_to_lab_avx2  (const double *peak, int n, double *lab);  /* future */
```

Register both in a `.c2py` with `when: "cpu_has_avx2"` / fallback.
Even before P1 (SIMD dispatch) is implemented, this lets you define the YAML grammar
now and wire in the dispatch logic later — validating that the parser correctly accepts
`cpu_has_*` identifiers in `when:` conditions without choking.

---

## Test Coverage Gaps (before API freeze)

| Gap | Risk | Suggested Test |
|---|---|---|
| `expand:` with zero-length list | `_expand_func_template` returns `[]`; import is a no-op | Add `expand: {VAR: []}` test case |
| `default_raise:` with unknown exception type | `PyExc_<unknown>` is resolved but may be NULL | Test `default_raise: "IndexError: msg"` |
| Optional int param = 0 (falsy default) | `optional: 0` YAML value triggers coerce warning | Check this path in test_uniform.py |
| `outputs:` + GIL release combined | GIL released, then stack-var pointers passed | No test currently covers this combination |
| Keyword argument rejection | METH_VARARGS silently ignores kwargs | Should raise TypeError on `f(arr, fmt='d')` |
| Very large array (`len > INT_MAX`) | `(int)(buf->len / buf->itemsize)` truncates | Map value for `n` should use `Py_ssize_t` cast |

The last entry is worth expanding: if `n` is mapped as `"arr.n"` and the C function
takes `int n`, the generated cast is:
```c
(int)(buf_arr->len / buf_arr->itemsize)
```

On a 4 GB array, `buf->len = 4294967296` and `(int)(...)` silently truncates to 0.
The C function then processes 0 elements. This is silent data corruption. Consider
adding a size check:
```c
if ((buf_arr->len / buf_arr->itemsize) > (Py_ssize_t)INT_MAX) {
    PyErr_SetString(PyExc_ValueError, "buffer too large for int n (> INT_MAX elements)");
    return NULL;
}
```

---

## Summary Table

| ID | Severity | File | Description |
|---|---|---|---|
| B1 | **High** | generator.py | VARARGS wrapper 3-arg function cast to 2-arg PyCFunction — UB |
| B2 | **Medium** | c2py_runtime.h | `_c2py_dec_ref_manual` doesn't call destructor — latent leak |
| B3 | **Medium** | parser.py | `after_paren` dead code; silent failure on missing `)` |
| B4 | **Medium** | parser.py | `'L'` → `'unsigned int'` not in `_C_TYPES_INT` → false P4 error |
| B5 | **Low** | test_all.py / populate_abi_matrix.py | `subprocess.run` contradicts AGENTS.md rule |
| P1 | **Low** | c2py_runtime.c | `PyErr_Clear` not guarded with `RESOLVE_REQ` |
| P2 | **Low** | c2py_runtime.c | `c2py_runtime_init()` has TOCTOU at import time |
| P3 | **Low** | c2py_runtime.h | 32-bit `Py_buffer` sizes unverified against ABI matrix |
| P4 | **Low** | parser.py | Coerce warning message format: args in wrong order |
| P5 | **Low** | generator.py | Generated C files have no trailing newline |
| D1 | Design | parser.py | `'l'`/`'L'` format chars are LP64-specific; undocumented |
| D2 | Design | parser.py | No scientific-notation or leading-dot float defaults |
| D3 | Design | generator.py | `outputs:` tuple order should be documented as C-param-order |
