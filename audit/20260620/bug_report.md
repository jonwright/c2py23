# Bug: Python 3.15t refuses non-FT PyModuleDef (m_slots missing Py_mod_gil)

## Root cause

Python 3.14t silently auto-enables the GIL for modules whose `PyModuleDef` does
not declare free-threading support.  Python 3.15t hard-rejects them at
`PyModule_Create2` time.

The c2py23 generated FT module def sets `m_slots = NULL`:

```c
static PyModuleDef_FT _module_def_ft = {
    PyModuleDef_HEAD_INIT_FT,
    "_cImageD11",
    "...",
    -1,
    NULL,        /* methods set at init */
    NULL, NULL, NULL, NULL   /* m_slots = NULL  <--- PROBLEM */
};
```

The post-creation `PyUnstable_Module_SetGIL(module, Py_MOD_GIL_NOT_USED)` call
(line 48627 in the wrapper) runs AFTER `PyModule_Create2`, by which point 3.15t
has already rejected the module.

## Additional bug (also fixed)

The `PyModule_Create2` ABI version was `1013` (`PYTHON_API_VERSION`) instead of
`3` (`PYTHON_ABI_VERSION`).  Fixed in generator.py (commit on branch).  This
was not the root cause on 3.15t (3.14t tolerated the wrong value).

## Where

- `c2py23/generator.py`: generates `_module_def_ft` with `m_slots = NULL` and
  calls `PyUnstable_Module_SetGIL` after module creation.
- `c2py23/runtime/c2py_runtime.h`: `m_slots` typed as `void*`, no `Py_mod_gil`
  or `PyModuleDef_Slot` defined.

## Fix required

When `free_threading: true`:

1. Define `PyModuleDef_Slot` struct and `Py_mod_gil`/`Py_MOD_GIL_NOT_USED`
   constants in c2py_runtime.h:
   ```c
   typedef struct { int slot; void *value; } PyModuleDef_Slot;
   #define Py_mod_gil 2
   #define Py_MOD_GIL_NOT_USED ((void*)1)
   ```

2. In the generator, emit a static slots array and point `m_slots` at it:
   ```c
   static PyModuleDef_Slot _slots[] = {
       {Py_mod_gil, Py_MOD_GIL_NOT_USED},
       {0, NULL}
   };
   ```
   and set `_module_def_ft.m_slots = _slots`.

3. The post-creation `PyUnstable_Module_SetGIL` call is redundant once m_slots
   declares FT support (can be kept as fallback for 3.14t).

## Verification

- Python 3.15t: `PyModule_Create2` rejects module with `m_slots = NULL`
- Python 3.14t: tolerated `m_slots = NULL` (auto-enables GIL)
- Minimal reproducer with `#include <Python.h>` and `m_slots` pointing to
  `(PyModuleDef_Slot[]){{Py_mod_gil, Py_MOD_GIL_NOT_USED}, {0, NULL}}` imports
  successfully on 3.15t (confirmed).
