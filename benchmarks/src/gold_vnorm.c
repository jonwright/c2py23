/* gold_vnorm.c -- handwritten CPython extension: vector norm.
 * Takes a (N,3) double input buffer and an (N,) double output buffer.
 * Uses the buffer protocol (PEP 3118) for zero-copy access.
 * Also provides a METH_FASTCALL variant on Python >= 3.12.
 */
#include <Python.h>
#include <math.h>

/* ---- METH_VARARGS variant (works on all Python versions) ---- */
static PyObject *
gold_vnorm_varargs(PyObject *self, PyObject *args)
{
    Py_buffer vec_buf, mods_buf;
    PyObject *vec_obj, *mods_obj;
    int n;

    if (!PyArg_ParseTuple(args, "OO", &vec_obj, &mods_obj))
        return NULL;

    if (PyObject_GetBuffer(vec_obj, &vec_buf,
                           PyBUF_FORMAT | PyBUF_C_CONTIGUOUS) < 0)
        return NULL;
    if (PyObject_GetBuffer(mods_obj, &mods_buf,
                           PyBUF_FORMAT | PyBUF_C_CONTIGUOUS | PyBUF_WRITABLE) < 0)
    {
        PyBuffer_Release(&vec_buf);
        return NULL;
    }

    if (vec_buf.format[0] != 'd' || mods_buf.format[0] != 'd') {
        PyErr_SetString(PyExc_ValueError, "expected double format 'd'");
        goto error;
    }
    if (vec_buf.ndim != 2 || mods_buf.ndim != 1) {
        PyErr_SetString(PyExc_ValueError, "expected vec(2d), mods(1d)");
        goto error;
    }
    if (vec_buf.shape[1] != 3) {
        PyErr_SetString(PyExc_ValueError, "vec.shape[1] must be 3");
        goto error;
    }
    n = (int)vec_buf.shape[0];
    if (n != mods_buf.shape[0]) {
        PyErr_SetString(PyExc_ValueError, "vec.shape[0] != mods.shape[0]");
        goto error;
    }

    {
        const double (*vec)[3] = (const double (*)[3])vec_buf.buf;
        double *mods = (double *)mods_buf.buf;
        int i;
        for (i = 0; i < n; i++) {
            mods[i] = sqrt(vec[i][0] * vec[i][0] +
                           vec[i][1] * vec[i][1] +
                           vec[i][2] * vec[i][2]);
        }
    }

    PyBuffer_Release(&mods_buf);
    PyBuffer_Release(&vec_buf);
    Py_RETURN_NONE;

error:
    PyBuffer_Release(&mods_buf);
    PyBuffer_Release(&vec_buf);
    return NULL;
}

/* ---- METH_FASTCALL variant (Python >= 3.12 only) ---- */
#if PY_VERSION_HEX >= 0x030C0000
static PyObject *
gold_vnorm_fastcall(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    Py_buffer vec_buf, mods_buf;
    int n;

    if (nargs != 2) {
        PyErr_SetString(PyExc_TypeError, "vnorm expects 2 arguments");
        return NULL;
    }

    if (PyObject_GetBuffer(args[0], &vec_buf,
                           PyBUF_FORMAT | PyBUF_C_CONTIGUOUS) < 0)
        return NULL;
    if (PyObject_GetBuffer(args[1], &mods_buf,
                           PyBUF_FORMAT | PyBUF_C_CONTIGUOUS | PyBUF_WRITABLE) < 0)
    {
        PyBuffer_Release(&vec_buf);
        return NULL;
    }

    if (vec_buf.format[0] != 'd' || mods_buf.format[0] != 'd') {
        PyErr_SetString(PyExc_ValueError, "expected double format 'd'");
        goto error;
    }
    if (vec_buf.ndim != 2 || mods_buf.ndim != 1) {
        PyErr_SetString(PyExc_ValueError, "expected vec(2d), mods(1d)");
        goto error;
    }
    if (vec_buf.shape[1] != 3) {
        PyErr_SetString(PyExc_ValueError, "vec.shape[1] must be 3");
        goto error;
    }
    n = (int)vec_buf.shape[0];
    if (n != mods_buf.shape[0]) {
        PyErr_SetString(PyExc_ValueError, "vec.shape[0] != mods.shape[0]");
        goto error;
    }

    {
        const double (*vec)[3] = (const double (*)[3])vec_buf.buf;
        double *mods = (double *)mods_buf.buf;
        int i;
        for (i = 0; i < n; i++) {
            mods[i] = sqrt(vec[i][0] * vec[i][0] +
                           vec[i][1] * vec[i][1] +
                           vec[i][2] * vec[i][2]);
        }
    }

    PyBuffer_Release(&mods_buf);
    PyBuffer_Release(&vec_buf);
    Py_RETURN_NONE;

error:
    PyBuffer_Release(&mods_buf);
    PyBuffer_Release(&vec_buf);
    return NULL;
}
#endif

static PyMethodDef gold_vnorm_methods[] = {
    {"varargs",  gold_vnorm_varargs,  METH_VARARGS, ""},
#if PY_VERSION_HEX >= 0x030C0000
    {"fastcall", (PyCFunction)gold_vnorm_fastcall,
                                       METH_FASTCALL, ""},
#endif
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "gold_vnorm",
    "gold standard: vnorm via buffer protocol",
    -1,
    gold_vnorm_methods,
    NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit_gold_vnorm(void)
{
    return PyModule_Create(&moduledef);
}
