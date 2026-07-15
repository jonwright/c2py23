/* check_numpy_abi.c - Verify NumPy ndarray struct layout across versions.
 *
 * Compile:  gcc check_numpy_abi.c $(python3-config --includes) \
 *               -I$(python3 -c 'import numpy; print(numpy.get_include())') \
 *               $(python3-config --ldflags) -o check_numpy_abi
 * Usage:    ./check_numpy_abi
 *
 * Prints key-value pairs for machine parsing.  Run across numpy
 * versions (1.9.3 through 2.x) to verify c2py23's hardcoded
 * offsets in c2py_pin_ndarray remain correct.
 */

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/ndarrayobject.h>
#include <stdio.h>
#include <stddef.h>

static void check_offset(const char *label, ptrdiff_t offset) {
    printf("OFFSET %-35s %td\n", label, offset);
}

static void check_sizeof(const char *label, size_t sz) {
    printf("SIZEOF %-35s %zu\n", label, sz);
}

static void check_flag(const char *label, int val) {
    printf("FLAG %-35s 0x%04x\n", label, val);
}

static void check_val(const char *label, int val) {
    printf("VAL %-35s %d\n", label, val);
}

static void check_ptr(const char *label, void *val) {
    printf("PTR %-35s %p\n", label, val);
}

int main(void) {
    Py_Initialize();
    import_array();

    printf("NUMPY_ABI %s\n", "1.0");

    /* --- PyArrayObject layout --- */
    {
        PyArrayObject *tmp = (PyArrayObject*)PyArray_ZEROS(
            1, (npy_intp[]){1}, PyArray_DescrFromType(NPY_DOUBLE), 0);
        if (!tmp) { printf("ERROR: PyArray_ZEROS failed\n"); return 1; }

        char *base = (char*)tmp;
        check_sizeof("PyObject_HEAD", sizeof(PyObject));
        check_sizeof("PyArrayObject", sizeof(PyArrayObject));
        check_sizeof("PyArrayObject_fields", sizeof(PyArrayObject_fields));

        check_offset("PyArrayObject.data",       base + offsetof(PyArrayObject_fields, data) - base);
        check_offset("PyArrayObject.nd",         base + offsetof(PyArrayObject_fields, nd) - base);
        check_offset("PyArrayObject.dimensions", base + offsetof(PyArrayObject_fields, dimensions) - base);
        check_offset("PyArrayObject.strides",    base + offsetof(PyArrayObject_fields, strides) - base);
        check_offset("PyArrayObject.base",       base + offsetof(PyArrayObject_fields, base) - base);
        check_offset("PyArrayObject.descr",      base + offsetof(PyArrayObject_fields, descr) - base);
        check_offset("PyArrayObject.flags",      base + offsetof(PyArrayObject_fields, flags) - base);
        check_offset("PyArrayObject.weakreflist", base + offsetof(PyArrayObject_fields, weakreflist) - base);

        /* Verify our hardcoded relative offsets from data_off */
        ptrdiff_t data_off = offsetof(PyArrayObject_fields, data);
        printf("REL_OFF nd_from_data       %ld\n",
               (long)(offsetof(PyArrayObject_fields, nd) - data_off));
        printf("REL_OFF dims_from_data     %ld\n",
               (long)(offsetof(PyArrayObject_fields, dimensions) - data_off));
        printf("REL_OFF strides_from_data  %ld\n",
               (long)(offsetof(PyArrayObject_fields, strides) - data_off));
        printf("REL_OFF descr_from_data    %ld\n",
               (long)(offsetof(PyArrayObject_fields, descr) - data_off));
        printf("REL_OFF flags_from_data    %ld\n",
               (long)(offsetof(PyArrayObject_fields, flags) - data_off));

        /* Verify PyArray_DATA macro actually returns the data pointer */
        check_ptr("PyArray_DATA_value", PyArray_DATA(tmp));
        check_ptr("PyArray_DATA_vs_field",
                  (void*)(*(void**)(base + data_off)) == PyArray_DATA(tmp)
                  ? (void*)1 : (void*)0);

        Py_DECREF(tmp);
    }

    /* --- PyArray_Descr layout --- */
    {
        PyArray_Descr *d = PyArray_DescrFromType(NPY_DOUBLE);
        if (!d) { printf("ERROR: PyArray_DescrFromType failed\n"); return 1; }

        char *base = (char*)d;
        check_sizeof("PyArray_Descr", sizeof(PyArray_Descr));

        check_offset("PyArray_Descr.typeobj",   base + offsetof(PyArray_Descr, typeobj) - base);
        check_offset("PyArray_Descr.kind",      base + offsetof(PyArray_Descr, kind) - base);
        check_offset("PyArray_Descr.type",      base + offsetof(PyArray_Descr, type) - base);
        check_offset("PyArray_Descr.byteorder", base + offsetof(PyArray_Descr, byteorder) - base);
        check_offset("PyArray_Descr.flags",     base + offsetof(PyArray_Descr, flags) - base);
        check_offset("PyArray_Descr.type_num",  base + offsetof(PyArray_Descr, type_num) - base);
        check_offset("PyArray_Descr.elsize",    base + offsetof(PyArray_Descr, elsize) - base);
        check_offset("PyArray_Descr.alignment", base + offsetof(PyArray_Descr, alignment) - base);

        /* Verify the type char at offset 25 (our hardcoded assumption) */
        check_val("type_char_at_25", ((char*)d)[25] == d->type ? 1 : 0);
        check_val("type_char_val", (int)(unsigned char)d->type);
        check_val("elsize_val", d->elsize);

        Py_DECREF(d);
    }

    /* --- Type constants --- */
    check_val("NPY_DOUBLE", NPY_DOUBLE);
    check_val("NPY_FLOAT32", NPY_FLOAT32);
    check_val("NPY_INT32", NPY_INT32);
    check_val("NPY_INT64", NPY_INT64);

    /* --- Flags --- */
    check_flag("NPY_ARRAY_WRITEABLE", NPY_ARRAY_WRITEABLE);
    check_flag("NPY_ARRAY_C_CONTIGUOUS", NPY_ARRAY_C_CONTIGUOUS);
    check_flag("NPY_ARRAY_ALIGNED", NPY_ARRAY_ALIGNED);

    printf("NUMPY_ABI_OK 1\n");
    Py_Finalize();
    return 0;
}
