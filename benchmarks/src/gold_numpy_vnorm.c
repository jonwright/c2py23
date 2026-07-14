/* gold_numpy_vnorm.c -- handwritten CPython extension using NumPy C API.
 * Bypasses the generic buffer protocol (PyObject_GetBuffer) entirely.
 * Uses PyArray_FromAny + PyArray_DATA for direct pointer access.
 * This is the absolute fastest path for numpy arrays -- what f2py uses.
 */

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/arrayobject.h>
#include <math.h>

static PyObject *
gold_numpy_vnorm_varargs(PyObject *self, PyObject *args)
{
    PyObject *vec_obj = NULL, *mods_obj = NULL;
    PyArrayObject *vec_arr = NULL, *mods_arr = NULL;
    int n;

    if (!PyArg_ParseTuple(args, "OO", &vec_obj, &mods_obj))
        return NULL;

    vec_arr = (PyArrayObject *)PyArray_FromAny(
        vec_obj, PyArray_DescrFromType(NPY_DOUBLE), 2, 2,
        NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);
    mods_arr = (PyArrayObject *)PyArray_FromAny(
        mods_obj, PyArray_DescrFromType(NPY_DOUBLE), 1, 1,
        NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED | NPY_ARRAY_WRITEABLE,
        NULL);

    if (!vec_arr || !mods_arr) {
        Py_XDECREF(vec_arr);
        Py_XDECREF(mods_arr);
        return NULL;
    }

    /* shape check */
    if (PyArray_DIMS(vec_arr)[1] != 3) {
        PyErr_SetString(PyExc_ValueError, "vec.shape[1] must be 3");
        goto error;
    }
    n = (int)PyArray_DIMS(vec_arr)[0];
    if (n != (int)PyArray_DIMS(mods_arr)[0]) {
        PyErr_SetString(PyExc_ValueError, "vec.shape[0] != mods.shape[0]");
        goto error;
    }

    /* Direct pointer access -- no buffer protocol overhead */
    {
        const double (*v)[3] = (const double (*)[3])PyArray_DATA(vec_arr);
        double *m = (double *)PyArray_DATA(mods_arr);
        int i;
        for (i = 0; i < n; i++) {
            m[i] = sqrt(v[i][0] * v[i][0] +
                        v[i][1] * v[i][1] +
                        v[i][2] * v[i][2]);
        }
    }

    Py_DECREF(vec_arr);
    Py_DECREF(mods_arr);
    Py_RETURN_NONE;

error:
    Py_DECREF(vec_arr);
    Py_DECREF(mods_arr);
    return NULL;
}

#if PY_VERSION_HEX >= 0x030C0000
static PyObject *
gold_numpy_vnorm_fastcall(PyObject *self, PyObject *const *args, Py_ssize_t nargs_fc)
{
    PyArrayObject *vec_arr = NULL, *mods_arr = NULL;
    int n;

    if (nargs_fc != 2) {
        PyErr_SetString(PyExc_TypeError, "vnorm expects 2 arguments");
        return NULL;
    }

    vec_arr = (PyArrayObject *)PyArray_FromAny(
        args[0], PyArray_DescrFromType(NPY_DOUBLE), 2, 2,
        NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);
    mods_arr = (PyArrayObject *)PyArray_FromAny(
        args[1], PyArray_DescrFromType(NPY_DOUBLE), 1, 1,
        NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED | NPY_ARRAY_WRITEABLE,
        NULL);

    if (!vec_arr || !mods_arr) {
        Py_XDECREF(vec_arr);
        Py_XDECREF(mods_arr);
        return NULL;
    }

    if (PyArray_DIMS(vec_arr)[1] != 3) {
        PyErr_SetString(PyExc_ValueError, "vec.shape[1] must be 3");
        goto error;
    }
    n = (int)PyArray_DIMS(vec_arr)[0];
    if (n != (int)PyArray_DIMS(mods_arr)[0]) {
        PyErr_SetString(PyExc_ValueError, "vec.shape[0] != mods.shape[0]");
        goto error;
    }

    {
        const double (*vec)[3] = (const double (*)[3])PyArray_DATA(vec_arr);
        double *mods = (double *)PyArray_DATA(mods_arr);
        int i;
        for (i = 0; i < n; i++) {
            mods[i] = sqrt(vec[i][0] * vec[i][0] +
                           vec[i][1] * vec[i][1] +
                           vec[i][2] * vec[i][2]);
        }
    }

    Py_DECREF(vec_arr);
    Py_DECREF(mods_arr);
    Py_RETURN_NONE;

error:
    Py_XDECREF(vec_arr);
    Py_XDECREF(mods_arr);
    return NULL;
}
#endif

static PyMethodDef gold_numpy_vnorm_methods[] = {
    {"varargs",  gold_numpy_vnorm_varargs,  METH_VARARGS, ""},
#if PY_VERSION_HEX >= 0x030C0000
    {"fastcall", (PyCFunction)gold_numpy_vnorm_fastcall,
                                             METH_FASTCALL, ""},
#endif
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "gold_numpy_vnorm",
    "gold standard: vnorm via NumPy C API (no buffer protocol)",
    -1,
    gold_numpy_vnorm_methods,
    NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit_gold_numpy_vnorm(void)
{
    import_array();
    return PyModule_Create(&moduledef);
}
