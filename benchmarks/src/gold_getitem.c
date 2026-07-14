/* gold_getitem.c -- gold standard: element extraction from a double buffer.
 * Performs PyObject_GetBuffer / PyBuffer_Release on EVERY call,
 * matching c2py23's per-call semantics exactly.
 *
 * Also provides a "_batched" variant that pre-acquires the buffer
 * to show the cost difference.
 */
#include <Python.h>
#include <string.h>

/* ---- Per-call acquire/release (matches c2py23) ---- */
static PyObject *
gold_getitem_fastcall(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    Py_buffer buf;
    int i;

    if (nargs != 2) {
        PyErr_SetString(PyExc_TypeError, "getitem expects 2 arguments");
        return NULL;
    }

    if (PyObject_GetBuffer(args[0], &buf,
                           PyBUF_FORMAT | PyBUF_C_CONTIGUOUS) < 0)
        return NULL;

    if (buf.format[0] == '\0' || buf.format[strlen(buf.format)-1] != 'd') {
        PyBuffer_Release(&buf);
        PyErr_SetString(PyExc_ValueError, "expected double format 'd'");
        return NULL;
    }
    if (buf.ndim != 1) {
        PyBuffer_Release(&buf);
        PyErr_SetString(PyExc_ValueError, "expected 1D array");
        return NULL;
    }

    i = (int)PyLong_AsLong(args[1]);
    if (i < 0 || i >= buf.shape[0]) {
        PyBuffer_Release(&buf);
        PyErr_SetString(PyExc_IndexError, "index out of range");
        return NULL;
    }

    {
        double val = ((const double *)buf.buf)[i];
        PyBuffer_Release(&buf);
        return PyFloat_FromDouble(val);
    }
}

/* ---- Pre-acquire for fair comparison (fast path, cheat mode) ---- */
static PyObject *
gold_getitem_batched(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    Py_buffer buf;
    int i;
    Py_ssize_t N;
    PyObject *result = NULL;

    if (nargs != 2) {
        PyErr_SetString(PyExc_TypeError, "getitem_batched expects 2 arguments");
        return NULL;
    }

    if (PyObject_GetBuffer(args[0], &buf,
                           PyBUF_FORMAT | PyBUF_C_CONTIGUOUS) < 0)
        return NULL;

    if (buf.format[0] != 'd' || buf.ndim != 1) {
        PyBuffer_Release(&buf);
        PyErr_SetString(PyExc_ValueError, "expected double 1D array");
        return NULL;
    }

    N = buf.shape[0];
    i = 0;
    if (PyLong_Check(args[1])) {
        i = (int)PyLong_AsLong(args[1]);
    }

    result = PyTuple_New(1);
    PyObject *val = PyFloat_FromDouble(((const double *)buf.buf)[i % N]);
    PyTuple_SetItem(result, 0, val);

    PyBuffer_Release(&buf);
    return result;
}

static PyObject *
gold_getitem_batched_fastcall(PyObject *self, PyObject *const *args,
                               Py_ssize_t nargs)
{
    return gold_getitem_batched(self, (PyObject *const *)args, nargs);
}

static PyMethodDef gold_getitem_methods[] = {
    {"fastcall",         (PyCFunction)gold_getitem_fastcall,
                                       METH_FASTCALL, ""},
    {"batched_fastcall", (PyCFunction)gold_getitem_batched_fastcall,
                                       METH_FASTCALL, ""},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "gold_getitem",
    "gold standard: getitem via buffer protocol",
    -1,
    gold_getitem_methods,
    NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit_gold_getitem(void)
{
    return PyModule_Create(&moduledef);
}
