#include <stdint.h>
/* C2PY_BEGIN
{
    "constants": {
        "ALPHA": 1,
        "BETA": 2,
        "GAMMA": 3,
        "LARGE": 2147483647,
        "NEG": -1,
        "ZERO": 0
    },
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "data": "data.ptr",
                        "factor": "factor",
                        "n": "data.n"
                    },
                    "sig": "scale_and_sum(const double *data, intptr_t n, int factor) -> double"
                }
            ],
            "py_sig": "scale_sum(data: buffer, factor: int) -> float"
        }
    ],
    "module": "constmod",
    "source": [
        "constants.c"
    ]
}
C2PY_END */

double scale_and_sum(const double *data, intptr_t n, int factor)
{
    int i;
    double s = 0.0;
    for (i = 0; i < n; i++) {
        s += data[i] * (double)factor;
    }
    return s;
}
