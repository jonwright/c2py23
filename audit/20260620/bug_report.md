# Bug: Py_mod_gil is 87 on Python 3.15t, not 2

## Root cause (confirmed)

`Py_mod_gil` changed from `2` (Python 3.13/3.14t) to `87` (Python 3.15t).

`c2py_runtime.h` hardcodes `#define Py_mod_gil 2`.  Python 3.15t's
`PyModule_Create2` checks the slots array for `Py_mod_gil == 87`, doesn't find
it, and rejects the module with `SystemError: invalid PyModuleDef`.

Verified by compiling a probe against 3.15t headers:

```
sizeof(PyObject)       = 32    (matches c2py_runtime)
sizeof(PyModuleDef)    = 120   (matches c2py_runtime)
Py_mod_gil             = 87    (c2py_runtime says 2!)
offset ob_ref_shared   = 16    (matches c2py_runtime)
```

3.14t has `Py_mod_gil = 2` (not verified with probe, but confirmed by 3.14t
test suite passing).  Both values need to be supported.

The earlier `m_slots = NULL` fix in `main` was necessary but insufficient:
3.15t does check `m_slots`, but it checks for the *correct* slot number (87).

## Where

- `c2py23/runtime/c2py_runtime.h`: `#define Py_mod_gil 2`
- `c2py23/generator.py`: emits static `_slots[]` with `{Py_mod_gil, ...}`

## Fix required

The `_slots` array is static data embedded in the .so.  Since `Py_mod_gil`
is a `#define` (not a symbol), it cannot be resolved via dlsym.  Two options:

### Option A: version-gate the slot value

Emit two slots arrays and select at runtime:

```c
static PyModuleDef_Slot _slots_v2[] = {
    {2, Py_MOD_GIL_NOT_USED},
    {0, NULL}
};
static PyModuleDef_Slot _slots_v87[] = {
    {87, Py_MOD_GIL_NOT_USED},
    {0, NULL}
};

// In PyInit_:
_module_def_ft.m_slots = (C2PY.version_major == 3 && C2PY.version_minor >= 15)
    ? _slots_v87 : _slots_v2;
```

### Option B: dynamic slot table

Populate `_slots` at runtime:

```c
static PyModuleDef_Slot _slots[2];

// In PyInit_:
_slots[0].slot  = C2PY.py_mod_gil_value;   // set during c2py_runtime_init()
_slots[0].value = Py_MOD_GIL_NOT_USED;
_slots[1].slot  = 0;
_slots[1].value = NULL;
```

Option A is simpler (no runtime coordination needed) but wastes ~32 bytes of
static data.  Option B requires setting `py_mod_gil_value` in the runtime.

## Additional (already fixed)

- `PyModule_Create2` ABI version was `1013`, now `3` (correct)
- `m_slots = NULL` fixed; now emits `_slots[]` array (main branch)
