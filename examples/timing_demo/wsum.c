#include <stdint.h>

/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "data": "data.ptr",
                        "n": "data.n",
                        "weight": "weight"
                    },
                    "name": "double",
                    "sig": "weighted_sum_double(const double *data, intptr_t n, float weight) -> double",
                    "when": "data.format == 'd'"
                },
                {
                    "map": {
                        "data": "data.ptr",
                        "n": "data.n",
                        "weight": "weight"
                    },
                    "name": "float",
                    "sig": "weighted_sum_float(const float *data, intptr_t n, float weight) -> double",
                    "when": "data.format == 'f'"
                }
            ],
            "default_raise": "TypeError: expected float or double buffer",
            "doc": "Weighted sum with automatic dispatch. Supports double and float buffers.",
            "py_sig": "wsum(data: buffer, weight: float) -> float"
        }
    ],
    "module": "timing_demomod",
    "source": [
        "wsum.c"
    ],
    "timing": true
}
C2PY_END */

double weighted_sum_double(const double *data, intptr_t n, float weight) {
    double total = 0.0;
    intptr_t i;
    for (i = 0; i < n; i++) {
        total += data[i] * (double)weight;
    }
    return total;
}

double weighted_sum_float(const float *data, intptr_t n, float weight) {
    double total = 0.0;
    intptr_t i;
    for (i = 0; i < n; i++) {
        total += (double)data[i] * (double)weight;
    }
    return total;
}
