#include <stdint.h>
/* fill.c - fill an array with a constant value */

/* C2PY_BEGIN
{
    "module": "fillmod",
    "source": ["fill.c"],
    "functions": [
        {
            "py_sig": "fill(arr: buffer, value: float) -> void",
            "c_overloads": [
                {
                    "sig": "fill_f(float *arr, intptr_t n, float value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'f'",
                },
                {
                    "sig": "fill_d(double *arr, intptr_t n, double value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'd'",
                },
            ],
            "default_raise": "TypeError: expected float or double buffer",
        },
    ],
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
