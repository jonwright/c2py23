I read through the core pipeline (`parser.py`, `generator.py`, the runtime C/H files), the referee-report doc, and the test suite to see what's already known vs. what's not. Good news: it's a well-built system with real defensive engineering (alias detection, contiguity checks, runtime ABI-layout probing instead of compile-time assumptions, etc.) and the referee-report doc shows the maintainer already caught and fixed a batch of real bugs. But I found a couple of things worth fixing before you go further, plus one structural issue around your stated goal of wheel-building.

## 1. Real bug: multi-output tuples silently drop `int64_t` values

In `generator.py`, `_emit_c_call`'s output-tuple builder (the `n > 1` branch, around where it handles `outputs:`) has per-type branches that each create a `PyObject*`, NULL-check it, and call `PyTuple_SetItem`. Every branch does this **except** `int64_t`:

```python
elif ctype == 'int64_t':
    out.append(indent + 'PyObject *_c2py_obj{0} = PyLong_FromLongLong((long long){1});'.format(i, val))
elif ctype == 'uint64_t':
    out.append(indent + 'PyObject *_c2py_obj{0} = PyLong_FromLongLong... ')
    out.append(indent + 'if (_c2py_obj{0} == NULL) {{'...
    ...
    out.append(indent + 'PyTuple_SetItem(...)')
```

The `int64_t` branch creates the object and then does nothing — no NULL check, and critically **no `PyTuple_SetItem` call**. `PyTuple_New` returns a tuple with NULL slots; that slot never gets filled. The result: if a function has 2+ `outputs:` and one of them is `int64_t`, you get a tuple with a NULL item handed back to Python — that's a guaranteed crash (or worse) the moment Python touches that tuple element, plus a leaked PyObject for the value that was created but never attached.

This is the single-output case (`return PyLong_FromLongLong(...)`) which is fine — only the multi-output tuple path is broken. It's not caught by tests because the only multi-output test case (`scalar_output/stats.c2py`) uses `double` for both outputs, and the only `int64_t`/`uint64_t` test usage is for buffer element types, not `outputs:`. So this is real and untested. Easy fix — just copy the `uint64_t` branch's NULL-check/SetItem lines into the `int64_t` branch.

## 2. Validation gap: C return types the generator doesn't actually support

`_parse_c_sig` in `parser.py` accepts any of `_C_TYPES` (`int8_t`...`uint64_t`, `char`, `void`) as a function's return type and happily validates it. But `_emit_c_call` in the generator only has real handling for `int`, `float`, `double` as direct return values — everything else falls into an `/* unknown return type */` branch that **calls the function, discards the result, and returns `Py_RETURN_NONE`** (for `outputs:`-less functions) or fabricates a zero (for the `outputs:` case). `_validate_module` checks param-count and format-vs-pointer-type consistency, but never cross-checks that a declared return type is one the generator can actually emit.

So if you write a C overload like `uint32_t crc32(...)` (very plausible if you wrap something like LZ4/zlib-style code) without an `outputs:` entry, it'll parse, validate, and compile cleanly — and silently return `None` to Python instead of the checksum. That's the kind of failure mode the project's own "Writing Safe .c2py Definitions" section explicitly warns against (silent wrong behavior vs. a loud error), so it's worth closing.

## 3. Before you build wheels — the project's own roadmap flags this as unsolved

You said you want to "kick the tires before wheel building" — this is the part I'd actually pause on. `PLAN.md`/`README.md` both list:

> **P4: Binary Wheel Distribution** — Severity: Low — **Status: Deferred — design TBD, implement later.**

That's not false modesty — there are real open questions baked into the architecture:

- **Wheel tagging**: the whole point of the nimpy trick is one `.so` that works on Python 2.7–3.14 without linking `libpython`. But wheel filenames need a tag (`cp312-cp312-...`, `cp37-abi3-...`, etc.), and "works on every CPython ABI because it never links against one" doesn't map cleanly onto current wheel conventions. You'd likely want the bare `modulename.so` naming (still a valid entry in `EXTENSION_SUFFIXES` on Linux) plus some non-standard tag choice, and you'll need to verify pip/auditwheel actually do something sane with that rather than assuming it.
- **Symbol export at runtime**: `c2py_runtime_init()` does `dlopen(NULL, RTLD_LAZY | RTLD_GLOBAL)` and expects to find CPython's API symbols already loaded in the process. That depends on the *running* interpreter being built with `--enable-shared`/exporting dynamic symbols. That's true for most distro Pythons but isn't guaranteed for every environment a wheel might land in (musllinux/Alpine, some embedded/frozen interpreters, certain conda builds). This is exactly the kind of thing that's invisible in your own dev environment and only bites once you're distributing broadly.
- **No build-backend integration yet**: `cli.py`'s `_compile_wrapper` shells out to `gcc` directly. There's no `setup.py build_ext`/meson-python/scikit-build-core hookup that `pip wheel .` or `cibuildwheel` would know how to drive — you'd be building that integration layer essentially from scratch.

None of this means the design is wrong, just that "wheel building" is genuinely the next unsolved layer, not a packaging formality on top of a finished system. I'd treat it as its own design spike rather than assuming `setup.py bdist_wheel` will basically work.

## A few smaller things

- **`Unstable_Module_SetGIL` type mismatch**: the struct field is declared `void (*Unstable_Module_SetGIL)(PyObject*, int)`, but the real CPython function is `int PyUnstable_Module_SetGIL(PyObject*, void*)`. The call site passes `1` correctly meaning `Py_MOD_GIL_NOT_USED` (I checked — that constant really is `(void*)1`), so the *value* is right, but calling through a function pointer typed with a mismatched parameter (`int` vs `void*`) is technically UB in C even though it'll almost certainly work fine in practice on x86-64/AArch64 (a 32-bit immediate move zero-extends to the full register). Cheap fix: type it as `void*` and cast the call site.
- **Buffer writability/alias checks are computed per-function, not per-selected-overload**: `_get_buf_flags`/`_emit_restrict_checks` mark a buffer "writable" if *any* overload writes to it, and request `PyBUF_WRITABLE` / run alias checks unconditionally. Fine today because none of your examples mix a const-only overload and a writable overload on the same buffer param — but if you ever add one, callers would be forced to pass writable buffers even for the call path that only reads. Worth keeping in mind as you add overloads.
- **`_rebind_<func>` is a data race under `free_threading: true`**: it overwrites the plain (non-atomic) `_var_<name>_<gi>` globals that the dispatch `switch` reads, with no lock. Fine under the GIL; if you actually combine `free_threading: true` with runtime rebinding from multiple threads, that's a genuine race. Not covered by `tests/cases/freethreading`.
- Already known and tracked, just flagging for completeness: the referee-report doc itself lists **B2** (`_c2py_dec_ref_manual` has no real destructor call on hitting zero refcount — diagnostic only) and **P3** (32-bit `Py_buffer` layout unverified, no CI target) as open. Worth remembering both before you broaden platform support.

Overall: the codebase is in noticeably good shape for something this clever/low-level — the runtime ABI probing in particular is the kind of thing people normally get wrong, and it's handled carefully here. The two generator bugs above are concrete and fixable in minutes. The wheel-building question is the one I'd actually spend design time on before writing code.