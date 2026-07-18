# Python dict format equivalent of fill.c2py
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
