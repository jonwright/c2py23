/* gold_noargs.c -- handwritten CPython extension: no-arg returning None.
 * This is the zero-overhead gold standard.
 * Two calling conventions: METH_NOARGS (CPython 2.7+) and METH_FASTCALL (3.12+).
 */
#include <Python.h>

/* ---- METH_NOARGS variant ---- */
static PyObject *
gold_noargs_noargs(PyObject *self, PyObject *args)
{
    Py_RETURN_NONE;
}

/* ---- METH_FASTCALL variant (Python >= 3.12 only) ---- */
#if PY_VERSION_HEX >= 0x030C0000
static PyObject *
gold_noargs_fastcall(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    Py_RETURN_NONE;
}
#endif

/* ---- METH_VARARGS variant (no-arg but through VARARGS, for fair comparison) ---- */
static PyObject *
gold_noargs_varargs(PyObject *self, PyObject *args)
{
    if (PyTuple_GET_SIZE(args) != 0) {
        PyErr_SetString(PyExc_TypeError, "noargs expects 0 arguments");
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyMethodDef gold_noargs_methods[] = {
    {"noargs",       gold_noargs_noargs,   METH_NOARGS,  ""},
    {"varargs",      gold_noargs_varargs,  METH_VARARGS, ""},
#if PY_VERSION_HEX >= 0x030C0000
    {"fastcall",     (PyCFunction)gold_noargs_fastcall,
                                           METH_FASTCALL, ""},
#endif
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "gold_noargs",
    "gold standard: no-arg functions returning None",
    -1,
    gold_noargs_methods,
    NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit_gold_noargs(void)
{
    return PyModule_Create(&moduledef);
}
