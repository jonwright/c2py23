#include <stdint.h>
/* fill.c - fill an array with a constant value */

/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_f(float *arr, intptr_t n, float value)",
                    "when": "arr.format == 'f'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_d(double *arr, intptr_t n, double value)",
                    "when": "arr.format == 'd'"
                }
            ],
            "default_raise": "TypeError: expected float or double buffer",
            "py_sig": "fill(arr: buffer, value: float) -> void"
        }
    ],
    "module": "fillmod",
    "source": [
        "fill.c"
    ]
}
C2PY_END */

void fill_f(float *arr, intptr_t n, float value) {
    int i;
    for (i = 0; i < n; i++) {
        arr[i] = value;
    }
}

void fill_d(double *arr, intptr_t n, double value) {
    int i;
    for (i = 0; i < n; i++) {
        arr[i] = value;
    }
}
