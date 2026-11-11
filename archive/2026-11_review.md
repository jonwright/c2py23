# c2py23 -- peer review

Reviewer: Claude (Fable 5.2), 2026-11-10, at commit 469886e (main).
Scope: crash/segfault hunting in the runtime and generated wrappers,
CPython 3.x and free-threaded builds first.  PyPy/GraalPy/WASM not reviewed.

Status: first pass complete.  Section E lists what was and was not covered.

## Summary

The central claim holds: the .so files in the tree, built under CPython
3.12, pass the full test suite (279 passed, 1 skipped) on free-threaded
CPython 3.14, and a 16-thread stress run found no crash in the wrapper
path.  Error handling for bad arguments is thorough.

The segfaults I could produce all come from the interface file, not from
the runtime: a wrapper generated without a format check passes any buffer
as double* (B1, heap corruption reproduced), shape[k] is emitted without
an ndim guard (B2, segfault reproduced), and the timing accessors
dereference an integer from Python (B3, segfault reproduced).  Two more
are wrong-result or undefined-behaviour rather than crashes on x86:
pointer arithmetic on .ptr is in bytes (B8) and unaligned buffers are
accepted (B9).

In the runtime I found no crash reachable today, but several latent or
dead special cases (A1, A3, A4, A5) that support your suspicion that the
wide version/platform range has added branches rather than removed them;
see D5 for where that is and is not true.

Main recommendation: make the generator derive type, alignment and ndim
checks from the C signature, so that a .c2py file with no checks: block
is safe by default (D2, and section F for an ordered list).

## Findings

Severity: [HIGH] can crash or corrupt in plausible use, [MED] crash needs an
unusual but legitimate situation, [LOW] latent / robustness / misleading.
"Read" = found by reading the code; "Run" = reproduced by running it.

### A. Runtime (c2py_runtime.h, c2py_runtime.c, c2py_dlsym.c/.h)

A1 [LOW, latent crash] PyExc_BufferError is never dereferenced in dlsym mode.
  c2py_dlsym.c:449 dereferences C2PY.exc_BufferError, but the symbol is only
  resolved later at line 498.  So line 449 always yields NULL and line 498
  leaves the ADDRESS of the PyExc_BufferError variable in the table (a
  PyObject**, not the exception object).  Nothing in the generator uses
  PyExc_BufferError today, so it is latent; the first use would hand
  PyErr_SetString a bogus object.  Fix: resolve before line 449, or delete
  the field.  (Read)

A2 [MED] Runtime globals have default ELF visibility.
  C2PY, C2PY_NDARRAY, c2py_runtime_init, _c2py_use_cycle_counter,
  c2py_tick_frequency_hz and all c2py_amd64_* flags are plain extern globals
  compiled into every module.  Python normally loads extensions RTLD_LOCAL,
  so each module gets its own copy.  But if the process uses
  sys.setdlopenflags(RTLD_GLOBAL) (still seen in MPI / HPC stacks), a second
  c2py23 module binds to the FIRST module's C2PY table.  If the two modules
  were built with different c2py23 versions the struct layouts differ and
  every API call goes through the wrong slot.  Fix: build with
  -fvisibility=hidden (only PyInit_* exported), or mark the globals
  __attribute__((visibility("hidden"))), or make them static in the
  single-header build.  (Read; see section D for what the build helpers do.)

A3 [LOW] _c2py_inc_ref_manual / _c2py_dec_ref_manual are dead code with a
  wrong premise.  The comment says Py_IncRef/Py_DecRef are not exported
  before 3.12.  They are: both have been exported functions since Python
  2.4.  So the fallback can never be taken on CPython, and if it ever were,
  the decref prints to stderr at zero instead of deallocating (a leak that
  is described as "acceptable").  Recommend: make Py_IncRef/Py_DecRef
  RESOLVE_REQ and delete both functions and ob_refcnt_offset's use in them.
  This is exactly the "special case instead of simplification" you were
  worried about.  (Read)

A4 [LOW] The "runtime PyObject layout probe" (c2py_dlsym.c:396-416) cannot
  detect a free-threaded build.  It reads the word at offset 8 of
  PyLong(1) and treats "non-NULL and >= 0x100000" as "this is ob_type, GIL
  layout".  On a free-threaded build offset 8 holds ob_flags / ob_mutex /
  ob_gc_bits / ob_ref_local, and the small int 1 is immortal with
  ob_ref_local = 0xFFFFFFFF, so the word is huge and non-NULL: the probe
  "confirms" the GIL layout.  Detection really rests on the
  "free-threading" substring of Py_GetVersion() (which is reliable).  The
  probe gives false comfort; delete it or replace it with a real check
  (e.g. compare the word at ob_type_offset with the address of PyLong_Type
  resolved by dlsym).  (Read)

A5 [LOW] Py_buffer size handling is more complicated than needed and the
  comments are wrong.  smalltable[2] was removed in Python 3.3, not 3.12,
  so "PRE312/POST312" and "present on CPython 2.7-3.11" are misnomers (the
  runtime probe at :531 gets the right answer anyway).  Since c2py_buf_pin
  already pads the Py_buffer by 1200 bytes, memset(&pin->buf, 0, 96)
  unconditionally would remove pybuffer_size, both constants and the probe.
  (Read)

A6 [LOW] ndarray fast path reads PyArrayObject fields without the buffer
  protocol.  It INCREFs the array, which is as good as a buffer export for
  keeping the data alive (numpy's resize() refcheck).  Two residual gaps
  versus PEP 3118, both only reachable with another thread mutating the
  same array while the C function runs (free-threading or gil_release):
  (a) info->shape / info->strides point INTO the array object, so an
  in-place "a.shape = ..." from another thread changes or frees them under
  the wrapper; (b) the WRITEABLE flag is sampled once.  PEP 3118 exports
  give a private copy of shape/strides.  Suggest copying shape/strides into
  pin->shape_buf / pin->stride_buf (already there for DLPack) -- cheap, and
  removes the only pointer the wrapper holds into mutable numpy state.
  (Read)

A7 [LOW] ndarray type is recognised by tp_name == "numpy.ndarray" and the
  data pointer offset by scanning the object for the buffer address.  Works,
  and the exact-type check keeps subclasses on the PEP 3118 path.  But all
  other offsets (nd, dims, strides, descr, flags, descr->type) are hard
  coded, so the scan buys nothing: if data moved, everything else would be
  wrong too.  A NumPy 3 that reorders PyArrayObject_fields would produce
  garbage reads, not a clean decline.  Suggest validating the probe against
  the PEP 3118 answer on first encounter (ndim, itemsize, format char,
  shape[0..nd)) rather than only "nd in range and descr != NULL", and
  declining forever if they disagree.  (Read)

A8 [LOW] DLPack: PyTuple_SetItem(ver, i, PyLong_FromLong(..)) results are
  unchecked (OOM only).  All exceptions from __dlpack__ are swallowed and
  turned into "decline", including MemoryError / KeyboardInterrupt.  (Read)

A9 [LOW] Windows lazy InitializeCriticalSection in c2py_runtime_init is
  itself racy (two threads can both see _c2py_init_cs_ready == FALSE).
  Import locking makes this unreachable in practice; InitOnceExecuteOnce or
  a static SRWLOCK would be correct by construction.  (Read)

A10 [LOW, by design] dlopen(NULL) only finds CPython when its symbols are in
  the global scope.  Hosts that embed Python by dlopen("libpython",
  RTLD_LOCAL) will fail at import with a stderr message.  Worth a line in
  docs/design.md under known limitations.  (Read)

A11 [LOW] Timing structs (c2py_perf_t) are updated without locks or atomics.
  With gil_release or free-threading two threads race on call_count / min /
  max.  Not a crash, but the numbers are unreliable there and TSan will
  flag it.  (Read)

### B. Generated wrappers (generator.py and its output)

Experiments for this section live outside the repo (scratch directory); the
module was built with gcc -O1 from a 5-function .c2py and run on system
CPython 3.12.3 + numpy 2.5.3, and on uv's CPython 3.14.8 free-threaded +
numpy 2.5.4.

B1 [HIGH] No element-type check unless the user writes one.  (Run)
  A function declared as
      sig: "sumd(const double *a, intptr_t n) -> double"
      map: {a: a.ptr, n: a.n}
  with no "a.format == 'd'" check generates, with no warning, a wrapper
  that casts ANY buffer to double*.  a.n counts elements of the caller's
  itemsize, so a uint8 array of 1000 elements is passed as 1000 doubles:
      hz.filld(np.zeros(1000, np.uint8), 1.0)
  wrote 8000 bytes into a 1000 byte buffer and the process died in
  "malloc(): invalid size (unsorted)".  AGENTS.md documents this as the
  .c2py author's job.  As a reviewer I think that is the wrong default for
  a tool whose pitch is safety: the generator knows the C pointee type
  (double) and knows the map expression is <buf>.ptr, so it can derive the
  check itself.  Suggested rule: for every overload, every "<buf>.ptr"
  mapped to a non-void, non-char pointer gets an implicit
  format/itemsize test for that overload (as an implied when: term, or a
  hard check when there is a single overload).  Opt out explicitly
  ("unchecked: true") for the rare reinterpret-cast case.  At the very
  least, make the generator print a warning and make invariant_checker
  reject it.

B2 [HIGH] shape[k] is emitted without an ndim guard.  (Run)
  map: {n: "a.shape[1]"} with only a format check compiles to
  info_a->shape[1] regardless of ndim.  Results:
      rows(np.zeros(5))            -> segfault (1-D ndarray)
      rows(array.array('d',[1,2,3]) -> returns 1655813264 (out-of-bounds
                                       read used as a length -- in a real
                                       kernel this is the loop bound)
  The same applies to shape[k] in when: and checks:.  The generator sees
  every Subscript on .shape/.strides with a literal index, so it can emit
  "ndim > k" automatically (or refuse to generate without an explicit
  ndim check).  The committed example (transform.c2py) is correct only
  because its author remembered "points.ndim == 2".

B3 [MED] The perf accessors dereference an integer supplied from Python.
  (Run)  _c2py_perf_read / _c2py_perf_meta / _c2py_perf_reset take a raw
  address ("K") and cast it to c2py_perf_t*.  mod._c2py_perf_reset(12345)
  segfaults; _c2py_perf_reset(addr) is an arbitrary 100-byte write.  The
  addresses are also published as module attributes (_c2py_perf_ptr_*).
  They are underscore-private and perf.py passes correct values, but
  every timing-enabled module carries this.  Use an index into a static
  table of perf structs (bounds-checked) instead of an address; this
  also removes PyLong_FromVoidPtr and the module attributes.

B4 [LOW] pin.kind is read uninitialised on the error path.  (Read)
  Wrappers memset only pin.buf (C2PY.pybuffer_size bytes), not the rest of
  c2py_buf_pin.  When the 2nd or later buffer fails to pin, the wrapper
  jumps to cleanup and c2py_unpin_buffer() switches on pin.kind, which
  c2py_pin() never wrote on failure (only the DLPack backend sets NONE).
  It is harmless today because every branch then tests pin->buf.obj, which
  is NULL -- but it is undefined behaviour, valgrind/MSan will report it,
  and it depends on every backend leaving buf.obj NULL on failure.  Fix:
  set pin->kind = C2PY_PIN_NONE at the top of c2py_pin() (one store).

B5 [LOW] Reference leaks at module init.  (Read)
  c2py_set_module_attr(module, name, PyLong_FromVoidPtr(...)) and the
  PyLong_FromUnsignedLongLong variant never DECREF the new object
  (SetAttrString does not steal) and do not check for NULL.  One-off
  leak per import, but ASan/valgrind leak runs will carry it.
  Similarly PyTuple_New() is unchecked in _variants_<name>().

B6 [LOW] Variant rebind bypasses the when: guard.  (Read)
  _rebind_<name>("avx512") selects the variant by name without evaluating
  its when: condition, so Python code can force an AVX-512 kernel on a CPU
  without it (SIGILL).  Probably intended for benchmarking; either
  evaluate when: and raise, or document it as a sharp edge.  The variant
  selectors (_var_*, _vname_*, _active_perf_*) are plain statics written
  without synchronisation; a rebind racing with calls on a free-threaded
  build is a data race (benign for the int, but _vname/_active_perf are
  set in separate statements so a reader can see a mixed state).

B7 [LOW, by design] "int" parameters mapped to void* accept any integer as
  an address.  This is the documented "address" feature; it is a raw
  pointer hole and deserves a prominent warning in the user guide.

B8 [MED] Arithmetic on <buf>.ptr is accepted and means bytes.  (Run)
  map: {a: "a.ptr + off"} generates "(info_a->ptr + c_off)": arithmetic on
  void* (a GNU extension, so it will not compile with MSVC), in BYTES, and
  with no cast to the C parameter type.  sumo(np.arange(8.0), 2) summed
  from 2 bytes into the buffer and returned 1.7e-309 instead of 27.0.
  Nothing in the docs or tests uses this form, so I believe it is an
  accident of the expression grammar.  Either reject BinOp on .ptr in the
  parser, or define it (cast to the parameter's pointer type first, so the
  offset is in elements, and require a bounds check).

B9 [MED] No alignment check on buffer pointers.  (Run)
  np.frombuffer(bytearray(33), dtype="f8", offset=1) passes
  "format == 'd'" and is handed to C as double* with ptr % 8 == 1.  UBSan:
  "store to misaligned address ... for type 'double', which requires 8
  byte alignment".  x86 scalar code tolerates it; an auto-vectorised
  kernel that assumes natural alignment, or a strict-alignment target,
  need not.  AGENTS.md lists alignment under "additional checks to
  consider" for SIMD; I would make "ptr % itemsize == 0" an automatic
  check next to contiguity (one AND and a compare), since the wrapper is
  the only place that can do it.

B10 [LOW] Import failure is reported as SystemError.  (Read)
  When c2py_runtime_init() fails (Python 3.16+, missing symbol, RTLD_LOCAL
  host) PyInit_<mod> returns NULL with no exception set; the comment says
  "Python will raise ImportError" but CPython raises "SystemError:
  initialization of <mod> failed without raising an exception", with the
  real reason only on stderr.  PyErr_SetString and PyExc_ImportError are
  resolvable in almost every failure case: set ImportError with the same
  text.  This matters because the version ceiling means every released
  wheel will hit this path the day Python 3.16 appears.  (The Python 2
  init<mod> ignores the init result and would call a NULL function
  pointer; not a priority.)

What held up (Run, ASan+UBSan build, CPython 3.12): reversed, strided and
non-contiguous 2-D slices are rejected; Fortran order, 0-d, empty,
subclasses (matrix, masked array -- note the mask is silently ignored) and
memoryviews work; non-native byte order, read-only destinations, short
destinations, overlapping buffers, wrong argument counts, keywords, float
for int, out-of-range ints all raise clean Python exceptions.  Narrow C
integer receivers are range-checked and check/map arithmetic is
overflow-checked.  No sanitizer reports other than B9.  The argument
handling around the unsafe core is careful work.

### C. Free-threaded Python

Tested on CPython 3.14.8 free-threaded (uv build) with numpy 2.5.4:

- The repo test suite, run with --no-build against the .so files already
  in the tree (built under 3.12): 279 passed, 1 skipped.  The same binaries
  import and run on 3.12 and 3.14t, which is the project's central claim,
  and the GIL stays disabled after import.
- 16 threads x 20000 iterations of sum / copy / alias-error / type-error
  calls released simultaneously on a barrier (so the first-ndarray probe
  is raced): no errors, no crash.
- 6 reader threads calling the wrapper while a 7th reassigns a.shape in
  place 600000 times (finding A6): no crash observed.  A6 remains a
  theoretical use-after-free; I could not trigger it.

Assessment.  The wrapper itself keeps no per-call shared state: pins and
infos are on the stack, the API table is written once under pthread_once,
and the ndarray layout cache is published with acquire/release ordering.
I found no free-threading crash in the wrapper path.  The remaining shared
mutable state is: perf counters (A11), variant selectors (B6),
_c2py_timing_enabled / _c2py_gil_release_enabled / tick-source globals
(plain ints, racy but benign).  None of these is a memory-safety problem;
all would be reported by ThreadSanitizer, which I did not run.

What free-threading does change is the cost of B1/B2/A6-style mistakes:
"free_threading: true" is a promise about the USER's C code (no hidden
statics, no non-reentrant library calls), and nothing checks it.  The
docs should say plainly that the flag asserts reentrancy of every wrapped
function, and that two threads writing one array is a data race c2py23
will not detect (the alias check is per call, not across calls).

The structural risk for free-threading is not concurrency but layout.
dlsym mode hard-codes PyObject_FT, PyModuleDef_FT and its immortal
static header initialiser, tp_name's offset, and (for the fast path)
PyArrayObject and PyArray_Descr offsets.  None of these are covered by
any ABI promise on free-threaded builds before abi3t (PEP 803, 3.15).
The comment in c2py_dlsym.h already records one such break (the header
initialiser that 3.14t tolerated and 3.15t rejects).  The version ceiling
is the right mitigation and I would keep it strict.

### D. Peer-review comments on design and presentation

D1. The core idea works and is demonstrated.  One binary across CPython
  versions including free-threaded builds, no Python.h, no numpy at build
  time, and a declarative interface file that produces readable C.  For
  the stated audience (numeric kernels over contiguous buffers, HPC sites
  with many interpreters) this is a genuine niche, and the two downstream
  users are the right kind of evidence.

D2. The safety story is inverted relative to the pitch.  The wrapper is
  meticulous about things callers rarely get wrong (integer narrowing,
  arithmetic overflow in checks, DLPack field validation) and leaves the
  two things .c2py authors will get wrong -- element type and
  dimensionality -- to a convention in AGENTS.md.  The array notation
  "const double gv[][3]" already auto-derives ndim/shape checks; extending
  auto-derivation to plain "T *p" <- "buf.ptr" (format, itemsize,
  alignment) and to shape[k] (ndim > k) would make the default safe and
  the explicit checks: block an addition rather than the only defence.
  This is my main recommendation (B1, B2, B9).

D3. Missing comparison with the Limited API / abi3.  docs/design.md lists
  ctypes, cffi, pybind11, Cython, f2py, SWIG and HPy but not the
  mainstream answer to "one binary, many Pythons": abi3 wheels, and abi3t
  for free-threaded builds from 3.15.  A reader will ask why not that.
  The honest answer seems to be: 2.7 support, a single binary spanning
  GIL and free-threaded 3.13/3.14 (which abi3 cannot do), and no Python
  headers at build time.  Say so, and say what is given up (reliance on
  undocumented layouts, a hard version ceiling that needs a rebuild per
  new Python).  nanobind is also missing.  Some entries are dated (cffi:
  "Python 2.7 is sunsetting"; pybind11's floor is no longer 3.6).

D4. One stated rationale does not hold.  design.md says METH_KEYWORDS
  "causes undefined behavior when cast to PyCFunction".  That cast is the
  documented CPython idiom, and the generated code already performs the
  equivalent cast for METH_FASTCALL functions.  "Positional-only keeps
  the wrapper small and maps to C" is a sufficient reason on its own.

D5. Does Python 2.7-3.15 support make the code cleaner?  Partly.
  In generator.py it clearly does: 2.7 / PyPy / Windows / free-threading
  each appear 2-3 times in 2300 lines, and the FASTCALL + thin VARARGS
  shim is a clean way to serve both calling conventions.  The constraint
  has kept the generated C simple.
  In the runtime it does not: about 30-40 conditional sites each for
  PyPy, for version/2.7, for Windows/MSVC and for free-threading, in
  roughly 2900 lines.  Several are dead or mistaken, which is the usual
  sign of special cases that nobody can test:
    - manual refcount fallback for a situation that cannot occur (A3)
    - Py_buffer size probing made unnecessary by the pad (A5)
    - a layout probe that cannot fail (A4)
    - exc_BufferError resolved after its use (A1)
    - PyPy 2.7 module-attribute workaround applied to all of Python 2
  Suggestion: keep "one binary 3.x + free-threaded" in the dlsym backend
  and move PyPy/GraalPy wholly to --pythonh mode, which already exists
  and is required for GraalPy.  That would delete is_pypy, the PyPy_
  symbol renaming, _ds_pypy_workaround and the 1200-byte pad.  If 2.7
  must stay, it costs little in the generator but the old-buffer fallback
  and initNAME path deserve the same pruning question.

D6. Private numpy internals.  The ndarray struct-cast path saves the
  PyObject_GetBuffer round trip.  It is on by default (acquire order
  NDARRAY, PEP3118) and depends on PyArrayObject / PyArray_Descr field
  offsets that numpy does not promise.  The benchmark numbers should
  justify that as a default; I would make PEP 3118 the default and the
  struct cast opt-in per module, with the stronger first-use validation
  in A7.

D7. Small things.  AGENTS.md is a good operational document but it is
  where the safety rules for .c2py authors live; those belong in the user
  guide.  Global timing state and address-based perf accessors (B3) are
  more machinery than a wrapper generator needs in every module; consider
  making timing a separate optional runtime piece.

### E. Coverage and limits of this review

Read in full: c2py_runtime.h, c2py_runtime.c, c2py_dlsym.c, c2py_dlsym.h,
the committed xfrm_wrapper.c, docs/design.md.  Read in part: generator.py
(call emission, wrappers, variant dispatch, buffer flags), generated
wrappers for the gil_release case and for my own test interfaces.
Not read: parser.py, perf.py, invariant_checker.py, c2py_loader.py,
harvester.py, setuptools_helper.py, c2py_pythonh.*, the merged c2py.h,
the CI workflows, the examples, ../c2ImageD11 and ../bslz4_to_sparse.
Not run: Windows, macOS, aarch64, ILP32, Python < 3.12, 3.13t, 3.15,
valgrind, ThreadSanitizer, the container matrix.  PyPy, GraalPy and WASM
were out of scope by request.  I did not check the PyPI release or the
GitHub CI state.

### F. Suggested order of work

1. B2: automatic ndim guard for shape[k]/strides[k].  Small, mechanical,
   removes a segfault that needs no malice.
2. B1 (+B9): derive format/itemsize/alignment checks from the C pointee
   type for <buf>.ptr mappings; opt-out flag.  Warn in the generator and
   fail in invariant_checker until then.
3. B8: reject or define arithmetic on .ptr.
4. B3: perf accessors by index, not address.
5. B4, A1, B10: one-line fixes (init pin.kind; resolve BufferError before
   use; raise ImportError on init failure).
6. A2: -fvisibility=hidden (or hidden attributes) in every documented
   build recipe and in setuptools_helper.
7. A3, A4, A5 and D5: delete the dead fallbacks; decide whether PyPy
   belongs in dlsym mode at all.
8. A6, A7, D6: copy shape/strides in the ndarray fast path, validate the
   probe against PEP 3118, reconsider it as the default.
9. D3, D4: design.md -- add the abi3/abi3t comparison, fix the
   METH_KEYWORDS rationale.

## Status after fixups (2026-11-11, branch fable-review)

Each finding against the commit that addressed it.  "Doc" means documented
rather than changed, by decision.

| Finding | Status | Commit |
|---|---|---|
| A1 BufferError resolved after use | fixed | 303e682 (WP5) |
| A2 runtime globals exported | fixed | 39b69e5 (WP6) |
| A3 dead manual refcount fallback | removed | 8de81b3 (WP7) |
| A4 layout probe that cannot fail | replaced by a real check | 8de81b3 (WP7) |
| A5 Py_buffer size probing | removed | 8de81b3 (WP7) |
| A6 fast path points into the array | shape/strides copied; race narrowed, not closed | 76cfbd0 (WP8) |
| A7 probe not validated | validated against PEP 3118 | 76cfbd0 (WP8) |
| A8 DLPack allocation checks | fixed | 303e682 (WP5) |
| A9 Windows init race | not done (unreachable, untestable here) | -- |
| A10 dlopen(NULL) needs global symbols | Doc | d965704 (WP10) |
| A11 perf counters not thread-safe | Doc | d965704 (WP10) |
| B1 no element-type check by default | fixed (derived checks, opt-out key) | fd447cf (WP2) |
| B2 shape[k] without ndim guard | fixed | 82be3ec (WP1) |
| B3 perf accessors take raw addresses | fixed | 1d9b5cb (WP4) |
| B4 pin.kind read uninitialised | fixed | 303e682 (WP5), 8de81b3 (WP7) |
| B5 reference leaks at module init | fixed (valgrind confirmed) | 303e682 (WP5) |
| B6 rebind bypasses when: | Doc | d965704 (WP10) |
| B7 int -> void* is a raw address | Doc | d965704 (WP10) |
| B8 arithmetic on .ptr | rejected; "ptr % N" made to work | 3eb8a7d (WP3), 303e682 (WP5) |
| B9 no alignment check | fixed (opt-out key) | fd447cf (WP2) |
| B10 init failure gives SystemError | fixed (ImportError with reason) | 303e682 (WP5) |
| D3 no abi3 comparison | Doc | d965704 (WP10) |
| D4 METH_KEYWORDS rationale | Doc | d965704 (WP10) |
| D5 PyPy in dlsym mode | parked (WP9 not run) | -- |
| D6 PEP 3118 as default | rejected by owner (performance) | -- |

Verification on the finished branch: 352 tests pass with gcc, gcc -O0 -Wall
-Werror and clang on CPython 3.12; the container matrix passes on 2.7,
3.6-3.15, 3.14t and 3.15t (13/13); manylinux2014 cross-test 14/14; valgrind
shows no invalid or uninitialised reads and no leaks in c2py23 frames.
Two downstream projects build and pass their test suites unchanged.
Not verified: Windows, macOS, aarch64 (needs CI), PyPy, GraalPy, WASM.
