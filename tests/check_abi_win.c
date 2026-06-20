/* check_abi_win.c - Verify Python C ABI on Windows.
 *
 * Compile: cl check_abi_win.c /I<Python include> /link python3.lib
 * Usage:   check_abi_win.exe
 *
 * Output format matches check_abi.c for cross-platform comparison.
 */
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <Python.h>
#include <stdio.h>
#include <stddef.h>

static void check_sym(HMODULE h, const char *name) {
    void *p = (void*)GetProcAddress(h, name);
    printf("SYM %-35s %s\n", name, p ? "FOUND" : "MISSING");
}

int main(void) {
    HMODULE h = GetModuleHandleA("python3.dll");
    if (!h) h = GetModuleHandleA(NULL);

    printf("PYVER %s\n", Py_GetVersion());

#ifdef Py_GIL_DISABLED
    printf("FREE_THREADED %d\n", Py_GIL_DISABLED ? 1 : 0);
#else
    printf("FREE_THREADED 0\n");
#endif

    printf("SIZEOF void*:       %zu\n", sizeof(void*));
    printf("SIZEOF long:        %zu\n", sizeof(long));
    printf("SIZEOF long long:   %zu\n", sizeof(long long));
    printf("SIZEOF Py_ssize_t:  %zu\n", sizeof(Py_ssize_t));
    printf("SIZEOF PyObject:    %zu\n", sizeof(PyObject));
    printf("SIZEOF Py_buffer:   %zu\n", sizeof(Py_buffer));
    printf("SIZEOF PyMethodDef: %zu\n", sizeof(PyMethodDef));
    printf("SIZEOF PyModuleDef: %zu\n", sizeof(PyModuleDef));

    printf("OFFSET ob_refcnt:   %zu\n", offsetof(PyObject, ob_refcnt));
    printf("OFFSET ob_type:     %zu\n", offsetof(PyObject, ob_type));

    check_sym(h, "PyObject_GetBuffer");
    check_sym(h, "PyBuffer_Release");
    check_sym(h, "PyArg_ParseTuple");
    check_sym(h, "PyLong_FromLong");
    check_sym(h, "PyLong_AsLong");
    check_sym(h, "PyLong_AsLongLong");
    check_sym(h, "PyFloat_FromDouble");
    check_sym(h, "PyFloat_AsDouble");
    check_sym(h, "PyErr_SetString");
    check_sym(h, "PyErr_Format");
    check_sym(h, "PyTuple_New");
    check_sym(h, "PyTuple_SetItem");
    check_sym(h, "PyEval_SaveThread");
    check_sym(h, "PyEval_RestoreThread");
    check_sym(h, "PyModule_Create2");
    check_sym(h, "Py_IncRef");
    check_sym(h, "Py_DecRef");
    check_sym(h, "Py_GetVersion");
    check_sym(h, "PyLong_FromVoidPtr");
    check_sym(h, "PyObject_SetAttrString");
    check_sym(h, "PyLong_FromLongLong");
    check_sym(h, "PyLong_FromUnsignedLongLong");
    check_sym(h, "PyExc_TypeError");
    check_sym(h, "PyExc_ValueError");
    check_sym(h, "PyExc_RuntimeError");
    check_sym(h, "PyExc_MemoryError");
    check_sym(h, "_Py_NoneStruct");
    check_sym(h, "Py_None");

    return 0;
}
