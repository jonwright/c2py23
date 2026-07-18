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
                    "sig": "weighted_sum(const double *data, intptr_t n, double weight) -> double"
                }
            ],
            "py_sig": "wsum(data: buffer, weight: float) -> float"
        }
    ],
    "module": "timedmod",
    "source": [
        "timing.c"
    ],
    "timing": true
}
C2PY_END */

double weighted_sum(const double *data, intptr_t n, double weight)
{
    int i;
    double s = 0.0;
    for (i = 0; i < n; i++) {
        s += data[i] * weight;
    }
    return s;
}
