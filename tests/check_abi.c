/* check_abi.c - Verify Python C ABI across versions and platforms.
 *
 * Compile:  gcc check_abi.c $(python3-config --includes --ldflags) -ldl -o check_abi
 * Usage:    ./check_abi
 *
 * Output format is key-value pairs suitable for machine parsing.
 * Collect results over snakepit containers into abi_matrix.json.
 */

#define _GNU_SOURCE
#include <Python.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stddef.h>

static void check_sym(const char *name) {
    void *p = dlsym(RTLD_DEFAULT, name);
    printf("SYM %-35s %s\n", name, p ? "FOUND" : "MISSING");
}

int main(void) {
    /* --- Basic info --- */
    printf("PYVER %s\n", Py_GetVersion());

    /* --- Type sizes --- */
    printf("SIZEOF void_ptr      %zu\n", sizeof(void*));
    printf("SIZEOF Py_ssize_t    %zu\n", sizeof(Py_ssize_t));
    printf("SIZEOF int           %zu\n", sizeof(int));
    printf("SIZEOF long          %zu\n", sizeof(long));

    /* --- PyObject layout (for manual refcount fallback) --- */
    {
        PyObject *tmp = Py_None;
        printf("OFFSET PyObject.ob_refcnt  %td\n",
               (char*)&tmp->ob_refcnt - (char*)tmp);
        printf("OFFSET PyObject.ob_type    %td\n",
               (char*)&tmp->ob_type - (char*)tmp);
        printf("SIZEOF PyObject            %zu\n", sizeof(PyObject));
    }

    /* --- Py_buffer layout --- */
    {
        Py_buffer b;
        printf("SIZEOF Py_buffer           %zu\n", sizeof(Py_buffer));
        printf("OFFSET Py_buffer.buf       %td\n",
               (char*)&b.buf - (char*)&b);
        printf("OFFSET Py_buffer.obj       %td\n",
               (char*)&b.obj - (char*)&b);
        printf("OFFSET Py_buffer.len       %td\n",
               (char*)&b.len - (char*)&b);
        printf("OFFSET Py_buffer.itemsize  %td\n",
               (char*)&b.itemsize - (char*)&b);
        printf("OFFSET Py_buffer.readonly  %td\n",
               (char*)&b.readonly - (char*)&b);
        printf("OFFSET Py_buffer.ndim      %td\n",
               (char*)&b.ndim - (char*)&b);
        printf("OFFSET Py_buffer.format    %td\n",
               (char*)&b.format - (char*)&b);
        printf("OFFSET Py_buffer.shape     %td\n",
               (char*)&b.shape - (char*)&b);
        printf("OFFSET Py_buffer.strides   %td\n",
               (char*)&b.strides - (char*)&b);
        printf("OFFSET Py_buffer.suboffsets %td\n",
               (char*)&b.suboffsets - (char*)&b);
        /* smalltable presence inferred from internal offset:
         * < 3.12: internal at 88 (with smalltable[2] in between)
         * >= 3.12: internal at 72 (smalltable removed) */
        printf("OFFSET Py_buffer.internal  %td\n",
               (char*)&b.internal - (char*)&b);
    }

    /* --- PyMethodDef flags --- */
    printf("FLAG METH_VARARGS    0x%04x\n", METH_VARARGS);
    printf("FLAG METH_KEYWORDS   0x%04x\n", METH_KEYWORDS);
    printf("FLAG METH_NOARGS     0x%04x\n", METH_NOARGS);
    printf("FLAG METH_O          0x%04x\n", METH_O);
    printf("FLAG METH_CLASS      0x%04x\n", METH_CLASS);
    printf("FLAG METH_STATIC     0x%04x\n", METH_STATIC);
#ifdef METH_FASTCALL
    printf("FLAG METH_FASTCALL   0x%04x\n", METH_FASTCALL);
#endif

    /* --- PyBUF flags --- */
    printf("FLAG PyBUF_SIMPLE    0x%04x\n", PyBUF_SIMPLE);
    printf("FLAG PyBUF_WRITABLE  0x%04x\n", PyBUF_WRITABLE);
    printf("FLAG PyBUF_FORMAT    0x%04x\n", PyBUF_FORMAT);
    printf("FLAG PyBUF_ND        0x%04x\n", PyBUF_ND);
    printf("FLAG PyBUF_STRIDES   0x%04x\n", PyBUF_STRIDES);

    /* --- Symbol availability (resolved at runtime by c2py_runtime.c) --- */
    check_sym("Py_IncRef");
    check_sym("_Py_IncRef");
    check_sym("Py_DecRef");
    check_sym("_Py_DecRef");
    check_sym("PyObject_Vectorcall");
    check_sym("PyObject_GetBuffer");
    check_sym("PyBuffer_Release");
    check_sym("PyErr_Occurred");
    check_sym("PyErr_SetString");
    check_sym("PyErr_Clear");
    check_sym("PyArg_ParseTuple");
    check_sym("PyArg_ParseTupleAndKeywords");
    check_sym("PyModule_Create2");
    check_sym("PyLong_FromLong");
    check_sym("PyLong_FromLongLong");
    check_sym("PyFloat_FromDouble");
    check_sym("PyLong_AsLong");
    check_sym("PyFloat_AsDouble");
    check_sym("PyExc_TypeError");
    check_sym("PyExc_ValueError");
    check_sym("PyExc_RuntimeError");
    check_sym("PyExc_MemoryError");
    check_sym("_Py_NoneStruct");
    check_sym("Py_None");
    check_sym("PyObject_AsReadBuffer");
    check_sym("PyObject_AsWriteBuffer");
    check_sym("Py_GetVersion");

    return 0;
}
