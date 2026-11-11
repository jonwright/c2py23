# c2py23 fixup plan (from REVIEW.md, 2026-11-10)

Each work package (WP) below is written to be handed to a separate agent.
Finding IDs (A1, B2, ...) refer to REVIEW.md; an agent should read only the
findings named in its package, not the whole review.

## Owner decisions this plan assumes

- Python 2.7 stays.  Generated C stays C89-style (declarations first; the
  existing tests/test_c89_wrappers.py is the gate).
- No C parser.  Derived checks use only what parser.py already records per
  C parameter (base_type, is_pointer, is_const, array_dims) and a fixed
  table of scalar type names.  Unknown pointee types (structs, typedefs)
  get no derived check and a generation-time warning.
- Performance is critical.  The ndarray struct-cast fast path stays the
  default.  Every WP that touches the call path reports benchmarks before
  and after (see "Benchmark gate").
- No work on Python versions still in development.  The version ceiling
  stays at 3.15 and stays strict; nothing in this plan touches 3.16.
- PyPy and GraalPy are not priorities.  WP9 removes PyPy from dlsym mode;
  it is last and independent, so it can be dropped without affecting the
  others.

## Common brief (prepend to every WP prompt)

Repo: c2py23.  Read AGENTS.md first and follow it: 7-bit ASCII only,
Python 2.7-compatible Python (no f-strings, no annotations, no pathlib,
no subprocess.run), never include Python.h, no malloc in wrappers, targeted
edits only, never guard or skip a test, no timing numbers in source.
Workflow: all packages are committed in order onto the single local branch
fable-review (already created).  One commit per package, message starting
"WPn: ".  Do not push, do not open a PR, do not switch branches, never
touch main.  Where a package below says "in the PR", put that material in
your final report instead.  The pre-commit hook regenerates
tests/cases/transform/xfrm_wrapper.c; commit the regenerated file.  If you
change anything under c2py23/runtime/, regenerate the single header with
c2py23/runtime/merge_single_header.py and commit c2py23/runtime/c2py.h.
Do not bump the version number.  Do not fix things outside your package;
list them in the PR description instead.

Standard gate (all must pass, paste the summary lines in the PR):

    python tests/runner.py                       # system python, rebuilds
    CC=gcc CFLAGS="-g -O0 -Wall -Werror" python tests/runner.py
    python3 tests/test_all.py                    # container matrix incl 2.7, 3.14t

tests/test_all.py expects images in ../snakepit (snakepit-legacy.sif,
snakepit-modern.sif).  If an image is missing, say so in the PR and run
what exists; do not edit the matrix.  If no free-threaded Python is
available through the containers, make one with:

    uv python install 3.14t
    uv venv --python 3.14t /tmp/ft314 && uv pip install --python /tmp/ft314/bin/python numpy pytest
    /tmp/ft314/bin/python tests/runner.py --no-build

Benchmark gate (only where a WP says so): on main and on the branch, same
machine, quiet, run

    make -C benchmarks && make -C benchmarks bench

and put both result tables in the PR description.  A WP that slows
noargs/getitem/vnorm overhead by more than run-to-run noise must say why.

New tests: add a case directory under tests/cases/<name>/ (a .c file and
a .c2py; tests/runner.py discovers it) and a tests/test_<name>.py.  Tests
that must show "this used to crash" run the call in a subprocess with
subprocess.Popen and assert on the exit code, so a regression fails the
test instead of killing pytest.  Parser-rejection tests go in
tests/test_parser_errors.py.

## Order and dependencies

    WP1  safe shape access                 generator + runtime    (B2)
    WP2  derived format + alignment checks parser + generator     (B1, B9)
    WP3  reject arithmetic on .ptr         parser                 (B8)
    WP4  perf accessors by index           generator + perf.py    (B3)
    WP5  init and pin one-liners           runtime + generator    (A1, B4, B5, B10, A8)
    WP6  hidden visibility                 runtime headers        (A2)
    WP7  delete dead fallbacks             runtime                (A3, A4, A5)
    WP8  harden ndarray fast path          runtime                (A6, A7)
    WP9  PyPy out of dlsym mode            runtime + CI + docs    (D5)   optional
    WP10 docs                              docs only              (D3, D4, B6, B7, A10, A11, C)
    WP11 downstream check                  no code                (integration)

WP1, WP2, WP4, WP5 all edit generator.py; WP5, WP6, WP7, WP8, WP9 all edit
the runtime.  Run them one at a time in the order given, each branched
from main after the previous PR is merged.  WP3 and WP10 are independent
and can run at any time.  WP11 runs last.

Size guide for choosing a model: WP3, WP5, WP6, WP10 are small and
mechanical.  WP1, WP4, WP7 are medium.  WP2, WP8, WP9 need care.

---

## WP1 -- shape[k] / strides[k] can no longer read out of bounds (B2)

Problem: "a.shape[1]" in map:, when: or checks: compiles to
info_a->shape[1] whatever ndim is.  rows(np.zeros(5)) segfaults.  On 2.7
old-buffer objects shape is NULL even for k == 0.

Change:
1. c2py_runtime.h: add two static inline helpers next to
   c2py_check_contiguity:
     c2py_shape_at(const c2py_ptr_info *info, int k)
       k < 0 or k >= info->ndim            -> -1
       info->shape == NULL (then ndim<=1)  -> len / itemsize for k == 0
                                              (0 if len == 0)
       otherwise                           -> info->shape[k]
     c2py_stride_at(info, k): same bounds rule; when strides == NULL
       return itemsize for k == 0.
2. generator.py: wherever a Subscript on .shape / .strides is turned into
   C (_expr_to_c), emit the helper call instead of the raw index.
3. parser.py or generator.py: when an overload's map: uses buf.shape[k]
   or buf.strides[k], that overload is only eligible if buf.ndim > k.
   Implement as an implied term ANDed in FRONT of the overload's when:
   condition ("(info->ndim > k) && (user when)").  For an overload with
   no when: this makes it conditional; if it was the only overload and
   there is no default_raise, a non-matching call must raise ValueError
   naming the buffer and the required ndim (not fall through to
   "return NULL" with no exception set).
   Do NOT add function-level "ndim >= k+1" checks: functions that dispatch
   on ndim must keep working.

Tests (new case, e.g. tests/cases/shapeguard):
- map uses a.shape[1], checks has only the format: 1-D ndarray, 0-D
  ndarray, array.array('d') and bytearray all raise ValueError (subprocess,
  exit code 0); a 2-D array returns shape[1].
- when: "a.shape[1] == 3" with a 1-D array: not selected, default_raise
  message raised.
- a function with two overloads, when: "a.ndim == 1" and
  when: "a.ndim == 2 and a.shape[1] == 3", still dispatches both ways.
- existing transform case output unchanged in behaviour.

Verify: standard gate; benchmark gate (expect no measurable change);
grep the regenerated wrappers: `grep -n "shape\[" tests/cases/*/*_wrapper.c`
must find no raw index outside the runtime helpers.

## WP2 -- derive element type and alignment checks from the C signature (B1, B9)

Problem: a "double *p" mapped from "buf.ptr" with no user-written format
check accepts any buffer; a uint8 array of 1000 elements is written as
1000 doubles (heap corruption).  Unaligned buffers (np.frombuffer with an
odd offset) are passed as double*.

No C parser: use CParam.base_type as already parsed.  Fixed table,
pointee base type -> accepted buffer element:

    double                          'd'
    float                           'f'
    int8_t, signed char             'b'
    uint8_t, unsigned char          'B'
    char                            itemsize == 1 (any of b, B, c, ?)
    int16_t, short                  'h'
    uint16_t, unsigned short        'H'
    int32_t, int                    'i'  (plus 'l' when sizeof(long)==4)
    uint32_t, unsigned int          'I'  (plus 'L' when sizeof(long)==4)
    int64_t, long long              'q'  (plus 'l' when sizeof(long)==8)
    uint64_t, unsigned long long    'Q'  (plus 'L' when sizeof(long)==8)
    void                            no check
    anything else                   no check; print a warning to stderr at
                                    generation time naming function,
                                    parameter and type

Reuse the existing code that compares formats (it already handles the
'l'/'L' itemsize rule and c2py_format_type); do not write a second
format matcher.  Check the table against how generator.py treats these
names elsewhere (_NARROW_INT_RANGE etc.) and keep the spellings
consistent.

Rule, per overload O and per buffer B whose map expression is exactly
"B.ptr" feeding a pointer parameter with a table entry:
- If the function's checks: or O's when: already constrain B.format or
  B.itemsize, add nothing (existing interfaces must generate byte-for-byte
  the same dispatch for that buffer -- zero added cost).
- Otherwise add the implied term to O's condition, the same way WP1 adds
  its ndim term.  Single unconditional overload: emit it as a
  function-level check so the error message is the normal
  "arg 'x' check failed: x.format == 'd' (got format=...)".
- Opt out per function: "check_format": False (parse it exactly like the
  existing "check_aliasing" key in parser.py; document it in
  docs/specification.md).

Alignment: add c2py_check_alignment(const c2py_ptr_info *info) to
c2py_runtime.h: if len > 0 and itemsize is a power of two in 2..16 and
((uintptr_t)ptr & (itemsize - 1)) != 0, set ValueError "buffer not aligned
to its element size" and return -1.  The generator emits it right after
the contiguity check for every buffer.  Opt out per function:
"check_alignment": False.

Also update AGENTS.md "Writing Safe .c2py Definitions" (targeted edit):
format checks are now derived; explicit ones are still allowed.

Tests (new case, e.g. tests/cases/autoformat):
- sumd(const double*) with no checks: float32, uint8, int64 arrays raise
  (ValueError or TypeError, assert which); float64 works.  The uint8 fill
  case from REVIEW.md B1 runs in a subprocess and exits 0 with an
  exception, not a crash.
- one case per row of the table (reuse tests/cases/types or widths if
  they already cover a type).
- "check_format": False restores the old behaviour.
- a struct-pointer parameter generates with a warning on stderr and no
  check (assert on the CLI's stderr).
- np.frombuffer(bytearray(33), dtype="f8", offset=1) raises ValueError;
  with "check_alignment": False it is accepted.
- every existing test case and example still generates, and
  `git diff --stat tests/cases/*/` shows wrapper changes only where a
  format check was genuinely missing.  List those in the PR.

Verify: standard gate; benchmark gate (the alignment test is the only
added work on already-checked interfaces; report the numbers);
`python tests/test_peer_review.py` (needs numpy).

## WP3 -- reject arithmetic on .ptr (B8)

Problem: map: {"a": "a.ptr + off"} is accepted and emits void* arithmetic
in bytes with no cast; wrong results, and not C89/MSVC-compilable.

Change: in parser.py, when parsing map:, when: and checks: expressions,
raise ValueError if a ".ptr" attribute appears as an operand of any
arithmetic operator (it may appear bare in map:, and inside the existing
alignment idiom "(uintptr_t)buf.ptr % N == 0" if the grammar supports
that today -- check tests/cases/simd_dispatch and keep whatever it uses
working).  Message: say that pointer offsets belong in the C function
(pass the offset as a separate argument).

Tests: tests/test_parser_errors.py -- "a.ptr + off", "a.ptr - 1",
"off + a.ptr" each raise ValueError mentioning the function name; bare
"a.ptr" still parses; the SIMD alignment idiom still parses.

Verify: `python -m pytest tests/test_parser_errors.py -q`, then the
standard gate.  No benchmark needed.

## WP4 -- perf accessors take an index, not an address (B3)

Problem: _c2py_perf_read / _c2py_perf_meta / _c2py_perf_reset cast an
integer from Python to c2py_perf_t*.  mod._c2py_perf_reset(12345)
segfaults.

Change (generator.py: _emit_perf_accessors, _emit_timing_decls,
_emit_module_init; c2py23/perf.py):
- Emit one static table per module:
    static c2py_perf_t * const _c2py_perf_table[] = { &_perf_f, ... };
  and its length.
- The module attributes _c2py_perf_ptr_<f> and _c2py_ol_ptr_<f>__<name>
  keep their names but hold the table index (small int).
- The three accessors parse a long long, range-check it against the table
  length, raise ValueError("invalid perf handle") when out of range, then
  index the table.
- perf.py treats the attribute as an opaque handle; it should need little
  or no change.  Update its docstring ("pointer" -> "handle").
- Remove PyLong_FromVoidPtr use for these attributes.  If nothing else
  uses C2PY.Long_FromVoidPtr afterwards, leave the table entry alone
  (WP7 owns runtime deletions).

Tests: extend tests/test_perf_read.py -- for a timing-enabled module,
_c2py_perf_reset / _read / _meta with -1, table length, 12345 and 2**62
raise ValueError (run in a subprocess, exit code 0); the normal perf.py
API still returns the same numbers as before for a known call count.

Verify: standard gate; run the timing example notebook's module if the
examples test covers it (`python -m pytest tests/test_examples.py -q`).

## WP5 -- init and pin one-liners (A1, B4, B5, B10, A8)

1. A1: c2py_dlsym.c -- resolve PyExc_BufferError BEFORE the block that
   dereferences the exception pointers, and dereference it there (leave
   NULL if the symbol is missing).  Delete the later assignment.
2. B4: c2py_pin() sets pin->kind = C2PY_PIN_NONE as its first statement.
   (WP7 later replaces the generated memset; do not change it here.)
3. B5: module init -- every c2py_set_module_attr(module, name, <new
   object>) leaks the object and ignores NULL.  Emit a small static helper
   in the wrapper (or runtime) that takes ownership: if the value is NULL
   return failure, set the attribute, DECREF the value.  On failure the
   init function DECREFs the module and returns NULL (exception already
   set).  Check PyTuple_New in _variants_<name> and in the perf / tick
   helpers the same way.
4. A8: in c2py_pin_dlpack, check PyLong_FromLong results before
   PyTuple_SetItem; on failure go to the fail label with the exception
   left set (MemoryError must not be turned into "decline").
5. B10: when c2py_runtime_init() fails, PyInit_<mod> must raise
   ImportError with the reason.  Keep the reason text in a static char
   buffer filled where the stderr messages are printed today; in
   PyInit_<mod>, if PyErr_SetString and PyExc_ImportError resolved, set
   ImportError(reason); keep the stderr line as a fallback only when they
   did not.  Python 2 init<mod>: check the init result, and do not call
   through C2PY.InitModule_2_7 when init failed.

Tests:
- B10: build a test module, then run it with the ceiling tripped.  Do not
  invent a fake Python: add a test-only environment variable is NOT
  acceptable either.  Instead compile the runtime for this one test with
  -DC2PY_TEST_FORCE_INIT_FAIL (guard a single early "return failure" in
  _c2py_runtime_init_once with that macro) and assert that importing
  raises ImportError whose message contains the reason, in a subprocess.
- B4: no behavioural test is possible; show in the PR that valgrind is
  clean on the error path:
      valgrind --error-exitcode=1 python3 tests/test_error_paths.py
  (if valgrind is not installed, say so; do not skip silently).
- B5: `valgrind --leak-check=full python3 tests/test_leaks.py` and
  tests/test_lifecycle.py show no new "definitely lost" from module init
  compared with main.

Verify: standard gate, plus the ASan build from AGENTS.md:
    CC=gcc CFLAGS="-fsanitize=address -g -O1" LDFLAGS="-fsanitize=address" \
      python tests/runner.py
Rebuild without ASan afterwards so the tree is left usable.

## WP6 -- hide runtime globals (A2)

Problem: C2PY, C2PY_NDARRAY, c2py_runtime_init, the tick globals and all
c2py_amd64_* / c2py_arm64_* / c2py_ppc64_* flags are exported from every
module.  Under sys.setdlopenflags(RTLD_GLOBAL) a second c2py23 module
binds to the first module's table.

Change: define in c2py_runtime.h (both backends)

    #if (defined(__GNUC__) || defined(__clang__)) && !defined(_WIN32)
    #define C2PY_HIDDEN __attribute__((visibility("hidden")))
    #else
    #define C2PY_HIDDEN
    #endif

and put C2PY_HIDDEN on every extern declaration and matching definition
of a runtime global or function, including the CPU flag headers
(c2py_amd64.h, c2py_arm64.h, c2py_ppc64.h).  This must not depend on the
user's compiler flags.  Windows needs nothing (no export without
dllexport).  User C code linked into the same .so can still reference the
flags.

Tests (new tests/test_visibility.py, Linux/macOS):
- After the build, `nm -D --defined-only <mod>.so` (use `nm -gU` on macOS)
  for two test modules lists no symbol starting with C2PY, c2py_ or
  _c2py_.
- In a subprocess: import ctypes, os, sys;
  sys.setdlopenflags(os.RTLD_NOW | os.RTLD_GLOBAL); import two different
  test modules; call a function in each; each returns the right answer.

Verify: standard gate; tests/test_single_header.py passes (the
single-header build must be hidden too).

## WP7 -- delete dead fallbacks (A3, A4, A5)

1. A3: Py_IncRef and Py_DecRef become required symbols (same pattern as
   the other RESOLVE_REQ entries, with the PyPy-prefixed fallback that
   _resolve already does).  Delete _c2py_inc_ref_manual,
   _c2py_dec_ref_manual and the free-threaded special case around them.
   Keep ob_refcnt_offset: the None-immortality probe uses it.
2. A4: delete the "Runtime PyObject layout probe" block that inspects
   PyLong(1).  Free-threading detection stays as the Py_GetVersion
   substring plus _Py_IsGILEnabled.  Add in its place a real consistency
   check: resolve PyLong_Type (address of the type object) and
   PyLong_FromLong(1); the pointer at C2PY.ob_type_offset in the int must
   equal the address of PyLong_Type (on Python 2 PyLong_FromLong returns a
   long: compare against PyLong_Type there too).  If it does not match,
   init fails with a reason string ("PyObject layout mismatch").  This
   turns a wrong layout guess into ImportError instead of a crash.
3. A5: Py_buffer size.  Add static inline c2py_pin_init(c2py_buf_pin *p)
   that zeroes the whole Py_buffer member with sizeof and sets
   kind = C2PY_PIN_NONE, ctx = NULL.  The generator emits c2py_pin_init()
   instead of memset(&pin.buf, 0, C2PY.pybuffer_size) (also in
   _c2py_perf_read).  c2py_acquire_buffer zeroes sizeof(Py_buffer).
   Remove C2PY.pybuffer_size, C2PY_PYBUFFER_SZ_PRE312/POST312 and the
   runtime size probe from both backends.  Fix the comments: smalltable
   was removed in Python 3.3, not 3.12.  Keep _buf_pad as it is (WP9
   decides its fate).

Tests: no new behaviour.  The existing suite on 2.7, 3.6, 3.12, 3.14t is
the test; all four must be in the PR output.  Add one assertion to
tests/test_ndarray_backends.py or similar only if something was
previously untested.

Verify: standard gate (test_all.py is mandatory here, including 2.7 and
3.14t); `python3 tests/populate_abi_matrix.py` and commit the result if
it changed; `python3 tools/check_runtime_symbols.py` if it applies;
benchmark gate (expect none or a small improvement).

## WP8 -- harden the ndarray fast path without slowing it (A6, A7)

Keep it the default.  Two changes in c2py_pin_ndarray:

1. A6: in the fill path, if nd > C2PY_MAX_NDIM decline (return -1, no
   exception).  Copy nd shape values and nd stride values into
   pin->shape_buf / pin->stride_buf and point info->shape / info->strides
   at the copies.  Compute len from the copies.  After this the wrapper
   holds no pointer into the array object other than the data pointer.
2. A7: on the first encounter (probe path) the PEP 3118 answer is in
   pin->buf.  Before publishing the layout, require that the struct-cast
   reading agrees with it: nd == buf.ndim; c2py_format_itemsize(type char)
   == buf.itemsize when non-zero; type char == c2py_format_type(buf.format)
   when both are known; and for i < nd, dims[i] == buf.shape[i].  If any
   disagree, store probed = 1 with ndarray_type left NULL so the fast path
   is permanently off for this process, and continue on the PEP 3118
   result already acquired.  If the first array is unsuitable for
   comparison (nd == 0, or NULL data pointer) keep the present behaviour:
   learn nothing, retry on a later array.  Preserve the store ordering
   and the atomics exactly as they are.

Tests (tests/test_ndarray_backends.py):
- existing first-probe thread test still passes on 3.14t.
- an array with 33 dimensions (shape (1,)*33) is accepted through the
  PEP 3118 path or rejected with a clean exception, never a crash.
- thread test on 3.14t: readers call a wrapped function while another
  thread reassigns a.shape between (4096,), (2, 2048), (2, 2, 2, 512);
  no crash, and every successful call returns the right sum.
- If there is a practical way to feed the probe a fake type named
  "numpy.ndarray" with a different layout (a small C test module in
  tests/cases that defines such a type with tp_name "numpy.ndarray" and a
  working buffer protocol), add it: the first call must succeed through
  PEP 3118 and later real ndarrays must still work.  If this cannot be
  done in the time available, say so in the PR rather than weakening it.

Verify: standard gate; benchmark gate is the acceptance criterion here --
vnorm with ndarray arguments must stay within noise of main for 1-D and
2-D inputs; report the tables.  Also run the NumPy ABI probe from
AGENTS.md ("Check NumPy ndarray ABI").

## WP9 (optional) -- PyPy out of dlsym mode (D5)

Only run this if the owner confirms.  It deletes working, CI-tested code.

Change: dlsym mode detects PyPy (PyPy_IncRef / PyPy_GetVersion present)
and fails init with the reason "PyPy is not supported in dlsym mode;
build with --pythonh".  Then delete from the dlsym backend and shared
runtime: C2PY.is_pypy and every branch on it, the PyPy_ symbol-name
fallback in _resolve / _resolve_raw, the libpypy dlopen / DLL candidate
lists, C2PY_TARGET_PYPY, ob_pypy_link, _ds_pypy_workaround (Python 2 then
uses PyObject_SetAttrString like Python 3; confirm on CPython 2.7),
the PyPy branch of _init_module_2_7, and c2py_buf_pin._buf_pad.  Remove
or convert the PyPy jobs in .github/workflows/linux.yml to --pythonh if
that already passes there; otherwise remove them.  Update AGENTS.md,
README.md, docs/building.md, docs/index.md, docs/design.md by targeted
edits, and PLAN.md.

Tests: CPython suite unchanged.  If a PyPy container exists locally,
show that importing a dlsym module gives ImportError with the message
above.

Verify: standard gate including 2.7; `grep -rn "pypy\|PyPy\|PYPY"
c2py23/` returns only the detection-and-refuse code and c2py_pythonh.*;
benchmark gate.

## WP10 -- documentation (D3, D4, B6, B7, A10, A11, section C)

Docs only, targeted edits:
- docs/design.md: add the comparison with the Limited API (abi3, and
  abi3t from 3.15) and nanobind.  State what dlsym mode buys (2.7; one
  binary across GIL and free-threaded 3.13/3.14; no Python headers at
  build time) and what it costs (reliance on object layouts not covered
  by an ABI promise; a hard version ceiling, so each new Python needs an
  audit and a rebuild).  State the policy: no support for Python versions
  still in development.  Replace the METH_KEYWORDS "undefined behavior"
  rationale with the real one (positional-only maps to C and keeps the
  wrapper small).  Refresh the dated entries (cffi, pybind11).
- docs/user_guide.md: move the "Writing Safe .c2py Definitions" material
  here from AGENTS.md (leave a pointer in AGENTS.md).  Add:
  free_threading: true asserts that every wrapped C function is reentrant
  and that the alias check is per call, not across threads; int -> void*
  parameters are raw addresses; _rebind_<name> selects a variant without
  evaluating its when: (can SIGILL on the wrong CPU); timing counters are
  not thread-safe; masked arrays are passed without their mask.
- docs/building.md or design.md: dlopen(NULL) needs the interpreter's
  symbols in the global scope; hosts that load libpython RTLD_LOCAL are
  not supported in dlsym mode.

Verify: the docs build (`mkdocs build --strict` if mkdocs is installed;
otherwise say so), the ASCII check (`git ls-files docs | python3
tools/check_ascii.py`), and no source file changed
(`git diff --stat main` lists only .md files).

## WP11 -- downstream check (integration, no c2py23 code changes)

After WP1-WP8 are merged: with the new c2py23 installed in development
mode, regenerate and rebuild ../c2ImageD11 and ../bslz4_to_sparse on
branches there (do not push), run their test suites, and report:
- interfaces that no longer generate (WP3) or now warn (WP2 unknown
  pointee types);
- calls that now raise where they used to succeed (derived format or
  alignment checks), with the function and argument;
- wall-clock of their own benchmarks, if they have any, before and after.
Change nothing in c2py23 from this package; the output is a short report
for the owner, who decides between fixing the interface file, using an
opt-out key, or revisiting a rule.

---

## Not planned (and why)

- A9 (Windows init race): unreachable under the import lock, and not
  testable here.  Fold into any future Windows work.
- B6 (rebind bypasses when:): documented in WP10 rather than changed,
  because forcing a variant is useful for benchmarking.
- A11 (perf counters racy): documented in WP10.  Making them atomic would
  cost on the call path.
- D6 (PEP 3118 as default): rejected by the owner on performance grounds;
  WP8 hardens the fast path instead.
