/* c2py_runtime.c - nimpy-style CPython API loader
 *
 * Uses dlopen(NULL, ...) + dlsym() to resolve all CPython C API
 * function pointers at module load time. This eliminates the need
 * to link against -lpython, allowing one .so to work across
 * Python 2.7 through 3.14.
 *
 * Compile: gcc -c c2py_runtime.c -o c2py_runtime.o
 * Link:    gcc -shared ... c2py_runtime.o -ldl -o module.so
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include "c2py_runtime.h"

/* Global API table */
c2py_api_t C2PY = {0};

static int _resolve(void **ptr, const char *name)
{
    *ptr = dlsym(C2PY.dl_handle, name);
    if (*ptr == NULL) {
        /* Some symbols may legitimately not exist on old Python versions.
         * We only warn for critical ones. */
        return -1;
    }
    return 0;
}

#define RESOLVE(ptr, name) _resolve((void**)&(ptr), name)
#define RESOLVE_REQ(ptr, name) do { \
    if (_resolve((void**)&(ptr), name) != 0) { \
        fprintf(stderr, "c2py_runtime: FATAL - missing symbol: %s\n", name); \
        return -1; \
    } \
} while(0)

/* Python 2.7 module init helper */
static PyObject*
_init_module_2_7(const char *name, PyMethodDef *methods)
{
    void *dl = C2PY.dl_handle;

    /* Try Py_InitModule4 first (Python 2.7 preferred) */
    typedef PyObject* (*init4_fn)(const char*, PyMethodDef*, const char*,
                                   PyObject*, int);
    init4_fn fn4 = (init4_fn)dlsym(dl, "Py_InitModule4_64");
    if (fn4 == NULL) fn4 = (init4_fn)dlsym(dl, "Py_InitModule4");
    if (fn4 != NULL) {
        return fn4(name, methods, NULL, NULL, 1013 /* PYTHON_API_VERSION */);
    }

    /* Fallback: Py_InitModule3 */
    typedef PyObject* (*init3_fn)(const char*, PyMethodDef*, const char*);
    init3_fn fn3 = (init3_fn)dlsym(dl, "Py_InitModule3");
    if (fn3 != NULL) {
        return fn3(name, methods, NULL);
    }

    fprintf(stderr, "c2py_runtime: could not find module init function\n");
    return NULL;
}


int c2py_runtime_init(void)
{
    if (C2PY.dl_handle != NULL) {
        return 0; /* Already initialized */
    }

    C2PY.dl_handle = dlopen(NULL, RTLD_LAZY | RTLD_GLOBAL);
    if (C2PY.dl_handle == NULL) {
        fprintf(stderr, "c2py_runtime: dlopen(NULL) failed: %s\n", dlerror());
        return -1;
    }

    void *dl = C2PY.dl_handle;

    /* --- Detect Python version --- */
    {
        typedef const char* (*ver_fn)(void);
        ver_fn getver = (ver_fn)dlsym(dl, "Py_GetVersion");
        if (getver) {
            const char *v = getver();
            if (v) sscanf(v, "%d.%d", &C2PY.version_major, &C2PY.version_minor);
        }
        if (C2PY.version_major == 0) {
            /* Fallback: check for Py3-only symbol */
            if (dlsym(dl, "PyModule_Create2")) {
                C2PY.version_major = 3;
            } else {
                C2PY.version_major = 2;
            }
            C2PY.version_minor = 0;
        }
    }

    /* --- Buffer protocol (required) --- */
    RESOLVE_REQ(C2PY.GetBuffer, "PyObject_GetBuffer");
    RESOLVE_REQ(C2PY.ReleaseBuffer, "PyBuffer_Release");

    /* --- Old buffer protocol (Python 2.x only) --- */
    C2PY.AsReadBuffer = (int (*)(PyObject*, const void**, Py_ssize_t*))
        dlsym(dl, "PyObject_AsReadBuffer");
    C2PY.AsWriteBuffer = (int (*)(PyObject*, void**, Py_ssize_t*))
        dlsym(dl, "PyObject_AsWriteBuffer");
    C2PY.Err_Clear = (void (*)(void))dlsym(dl, "PyErr_Clear");
    C2PY.buffer_api_is_pep3118 = (C2PY.version_major >= 3);

    /* --- Argument parsing (required) --- */
    RESOLVE_REQ(C2PY.ParseTuple, "PyArg_ParseTuple");
    RESOLVE(C2PY.ParseTupleAndKeywords, "PyArg_ParseTupleAndKeywords");

    /* --- Value construction (required) --- */
    RESOLVE_REQ(C2PY.Long_FromLong, "PyLong_FromLong");
    RESOLVE(C2PY.Long_FromLongLong, "PyLong_FromLongLong");
    RESOLVE_REQ(C2PY.Float_FromDouble, "PyFloat_FromDouble");

    /* --- Scalar conversion --- */
    RESOLVE_REQ(C2PY.Long_AsLong, "PyLong_AsLong");
    RESOLVE_REQ(C2PY.Float_AsDouble, "PyFloat_AsDouble");

    /* --- Exception handling (required) --- */
    RESOLVE_REQ(C2PY.exc_TypeError, "PyExc_TypeError");
    RESOLVE_REQ(C2PY.exc_ValueError, "PyExc_ValueError");
    RESOLVE_REQ(C2PY.exc_RuntimeError, "PyExc_RuntimeError");
    RESOLVE_REQ(C2PY.exc_MemoryError, "PyExc_MemoryError");
    RESOLVE_REQ(C2PY.Err_SetString, "PyErr_SetString");

    /* --- Module creation --- */
    {
        void *mc = dlsym(dl, "PyModule_Create2");
        C2PY.Module_Create2 = (PyObject* (*)(PyModuleDef*, int))mc;
    }
    C2PY.InitModule_2_7 = _init_module_2_7;

    /* --- Reference counting --- */
    RESOLVE_REQ(C2PY.IncRef, "Py_IncRef");
    RESOLVE(C2PY.DecRef, "Py_DecRef");

    /* --- None singleton ---
     * _Py_NoneStruct is a static PyObject; dlsym returns &_Py_NoneStruct,
     * which is the same as Py_None (the macro: (&_Py_NoneStruct)).
     * Py_None is immortal so INCREF/DECREF is unnecessary but harmless.
     */
    {
        void *none = dlsym(dl, "_Py_NoneStruct");
        if (none == NULL) {
            /* On some platforms Py_None is a pointer variable pointing
             * to the struct. Try loading it and dereferencing. */
            void **pnone = (void**)dlsym(dl, "Py_None");
            if (pnone) none = *pnone;
        }
        C2PY.none_obj = (PyObject*)none;
        if (C2PY.none_obj == NULL) {
            fprintf(stderr, "c2py_runtime: could not resolve Py_None\n");
            return -1;
        }
    }

    return 0;
}
