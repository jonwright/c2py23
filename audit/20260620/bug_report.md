# Bug: Python 3.15t refuses non-FT PyModuleDef (m_slots missing Py_mod_gil)

## Status: FIXED

## Root cause

Python 3.14t silently auto-enables the GIL for modules whose `PyModuleDef` does
not declare free-threading support.  Python 3.15t hard-rejects them at
`PyModule_Create2` time.

The c2py23 generated FT module def set `m_slots = NULL`:

The post-creation `PyUnstable_Module_SetGIL(module, Py_MOD_GIL_NOT_USED)` call
ran AFTER `PyModule_Create2`, by which point 3.15t had already rejected the
module.

## Fix applied (branch audit_20260620)

1. Added `PyModuleDef_Slot` typedef, `Py_mod_gil` and `Py_MOD_GIL_NOT_USED`
   constants to `c2py_runtime.h`:
   ```c
   typedef struct { int slot; void *value; } PyModuleDef_Slot;
   #define Py_mod_gil 2
   #define Py_MOD_GIL_NOT_USED ((void*)1)
   ```

2. Generator emits `_slots` array and points `_module_def_ft.m_slots` at it
   when `free_threading: true`:
   ```c
   static PyModuleDef_Slot _slots[] = {
       {Py_mod_gil, Py_MOD_GIL_NOT_USED},
       {0, NULL}
   };
   ```
   `_module_def_ft.m_slots = _slots;`

3. The post-creation `PyUnstable_Module_SetGIL` call is kept as a redundant
   fallback for 3.14t (harmless, no-op when slots already declare FT support).

4. Applied to both generators (`generator.py`, `generator_builder.py`).

## Verification

- All 62 tests pass including `freethreading` test case with `free_threading: true`
- Generated C code for FT modules now contains the `_slots` array
- Non-FT modules unchanged (no slots)
