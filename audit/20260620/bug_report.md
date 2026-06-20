# Bug: PyModule_Create2 ABI version is wrong (1013 vs 3)

## Root cause

c2py23's generator emits `PyModule_Create2((PyModuleDef*)&_module_def_ft, 1013)`.

`1013` is `PYTHON_API_VERSION` (from `patchlevel.h`).  `PyModule_Create2` takes
`PYTHON_ABI_VERSION` which is `3` across all CPython versions (>= 3.10
confirmed; defined in `modsupport.h`, value unchanged since PEP 384).

On Python 3.14t the wrong value is silently tolerated.  On Python 3.15t it
triggers:

```
SystemError: invalid PyModuleDef, extension possibly compiled for
non-free-threaded Python
```

## Where

Generated code line (wrapper):

```c
module = C2PY.Module_Create2((PyModuleDef*)&_module_def_ft, 1013);
```

Generator (`c2py23/generator.py` lines 1757, 1763, 1770): hardcoded literal `1013` passed to `Module_Create2`.

## Fix

Change `1013` to `3` in the generator.  `PYTHON_ABI_VERSION` is stable since
PEP 384 (Python 3.2+) and is `3` on all interpreters.

## Verification

- Python 3.15t: currently fails with `SystemError` (above)
- Python 3.14t: works despite wrong value (lenient check)
- All GIL-enabled pythons: works (use `PyModule_Create2` via dlsym, not
  necessarily guarded strictly)

## Reproducer

```c
// Compile against any Python 3.15+ headers, run on 3.15t:
PyObject *m = PyModule_Create2(&moddef, PYTHON_ABI_VERSION);  // OK
PyObject *m = PyModule_Create2(&moddef, 1013);                // FAILS
```
