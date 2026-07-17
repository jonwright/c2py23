# Design Decisions

This page documents what c2py23 does and does not do, with references
to the GitHub issues where each decision was made.

## What c2py23 Does

- **Zero-copy buffer access** -- acquires raw C pointers from Python buffer
  objects via PEP 3118, with Python 2.7 old-buffer fallback
- **One `.so` everywhere** -- uses `dlopen(NULL)` + `dlsym()` (the nimpy trick)
  rather than linking `-lpython`.  No `#include <Python.h>` anywhere.
  For runtimes where this fails (GraalPy) or for debugging, use
  `--pythonh` instead ([docs](pythonh.md)).
- **Format dispatch** -- route to different C overloads based on PEP 3118 format
  characters: `'d'` (float64), `'f'` (float32), `'i'` (int32), etc.
- **CPU feature dispatch** -- compile the same C source with different `-m` flags
  and select at runtime via `when: c2py_amd64_avx2`
- **Auto-derived array checks** -- `const double gv[][3]` in a C sig generates
  ndim, shape, and contiguity checks automatically
- **Auto-generated docstrings** -- Python `help()` shows sigs, params, checks,
  and overloads
- **GIL release** -- opt-in per-function `gil_release: true`
- **Free-threading** -- module-level `free_threading: true` for Python 3.14t

## What c2py23 Does NOT Do

### No keyword arguments (#44)

C99 has no keyword arguments -- function parameters are positional, matched
by order at the call site.  c2py23 maps directly to the C calling model, so
all wrapped functions are positional-only.

C99 does have `<stdarg.h>` for variadic functions, which is the C equivalent
of optional arguments.  c2py23 supports this pattern through default values
on positional parameters (`py_sig: "fn(a: buffer, n: int = 1) -> int"`),
but callers must pass arguments in order: `fn(data, 5)` works, `fn(data, n=5)`
raises `TypeError`.

Keyword argument support would also introduce `METH_KEYWORDS` in the generated
CPython wrappers, which causes undefined behavior when cast to `PyCFunction`.
Deferred until Python 2.7 is dropped and the minimum can be raised to 3.12
where `METH_FASTCALL` avoids this issue natively.

### No memory allocation in wrappers

Generated wrapper code never calls `malloc`, `calloc`, `realloc`, or `free`.
All memory is owned by Python.  User C code may allocate internally, but must
free before returning.

### No complex type (#53)

C99 `_Complex` and C++ `std::complex<T>` have incompatible ABIs and
different calling conventions across compilers.  gcc/clang return C99
complex values via SSE registers; MSVC does not support C99 `_Complex`
at all and uses a C++ struct convention that passes via pointer.

The interleaved real/imag layout (AoS) also complicates SIMD
vectorization -- most SIMD kernels prefer separate real and imaginary
arrays (SoA) or custom layouts.

Users handle complex data in their C wrapper code with plain `float*`
or `double*` buffers and interleaved pairs.  The kissfft example
demonstrates this: declare `buffer` with format `'f'`, validate
`buf.n % 2 == 0`, and cast to `(kiss_fft_cpx*)buf.ptr` in the C
wrapper.  For SIMD-friendly layouts, split into separate real and
imaginary arrays (SoA or structure-of-arrays) in your C code.

This mirrors the Python 2 + Python 3 subset approach: where C99 and
C++ conflict, c2py23 uses the common-denominator feature set that
all platforms agree on.

### GPU support (#40)

Under investigation.  For CPU arrays, c2py23 already gets a raw pointer
via PEP 3118 at zero cost -- C function pointer dispatch via the
`tp_as_buffer` slot, no allocation on repeated calls, no dict lookup,
no release path.

For GPU arrays, DLPack provides the mechanism: a PyCapsule containing
a device pointer, device type, shape, and strides.  NumPy's C source
shows `__dlpack__()` returns the same `PyArray_DATA()` pointer as
getbuffer for CPU arrays (`device_type = kDLCPU`), and device-typed
pointers for GPU tensors from CuPy, PyTorch, etc.

The open question is not buffer access -- it's whether you have a C99
function compiled for a GPU to call.  All GPU libraries (cuBLAS,
cuFFT, ROCm) require JIT compilation or pre-compiled device code.
Until there is a GPU-compiled C function to wrap, DLPack vs PEP 3118
is a moot point.

Deferred for future research.  Related: HPy (#49).

### No async/await (#41)

Deferred until the Python 2.7 compatibility floor is raised (coroutines are
3.5+).

### No named-tuple returns (#42)

Functions return positional tuples.  Wrap in a namedtuple on the Python side
if needed.

### No numpy dependency (#15)

c2py23 uses PEP 3118 directly.  `buf.contiguous` (`'C'`/`'F'`) was removed
as a numpy-ism.  Use `buf.strides` and `buf.slow_axis` / `buf.fast_axis`
instead.

### No keyword arguments in dispatch expressions

`when:` and `checks:` expressions are compiled to C, not Python.  They
support a limited grammar: comparisons, arithmetic, `and`/`or`/`not`,
attribute access (`buf.n`, `buf.format`), and subscript (`buf.shape[1]`).

## Alternative Python Wrapper Generators

c2py23 is deliberately incomplete and inflexible -- it maps a narrow set of
C99 function signatures onto Python buffers, with no copies, no allocations,
and no type conversion overhead.  Most alternatives below aim for broader
coverage.

- **[ctypes](https://docs.python.org/3/library/ctypes.html)** -- built into
  Python, no build step, but no buffer-protocol shape/format checking
- **[cffi](https://cffi.readthedocs.io/)** -- richer C type system, ABI and API
  modes, but Python 2.7 is sunsetting
- **[pybind11](https://pybind11.readthedocs.io/)** -- C++ native, rich type
  conversion, Python 3.6+ only
- **[Cython](https://cython.org/)** -- Python-like syntax for C extensions,
  Python 2.7-3.x support
- **[f2py](https://numpy.org/doc/stable/f2py/)** -- wraps Fortran 77/90 and C
  functions, generates C/API wrappers, numpy-aware
- **[SWIG](https://www.swig.org/)** -- multi-language wrapper generator
  (C/C++ to Python, Java, Ruby, etc.), mature and feature-rich
- **[HPy](https://hpyproject.org/)** -- universal C extension API for CPython,
  PyPy, and GraalPy.  HPy has first-class buffer support and is a serious option
  for multi-interpreter portability.  See #49.
