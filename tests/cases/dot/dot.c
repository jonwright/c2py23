#include <stdint.h>
/* dot.c - dot product of float or double arrays */

/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "a": "a.ptr",
                        "b": "b.ptr",
                        "n": "a.n"
                    },
                    "sig": "dot_f(const float *a, const float *b, intptr_t n) -> float",
                    "when": "a.format == 'f'"
                },
                {
                    "map": {
                        "a": "a.ptr",
                        "b": "b.ptr",
                        "n": "a.n"
                    },
                    "sig": "dot_d(const double *a, const double *b, intptr_t n) -> double",
                    "when": "a.format == 'd'"
                }
            ],
            "checks": [
                "a.format == b.format",
                "a.n == b.n"
            ],
            "default_raise": "TypeError: expected float or double buffer",
            "py_sig": "dot(a: buffer, b: buffer) -> float"
        }
    ],
    "module": "dotmod",
    "source": [
        "dot.c"
    ]
}
C2PY_END */

float dot_f(const float *a, const float *b, intptr_t n) {
    float sum = 0.0f;
    int i;
    for (i = 0; i < n; i++) {
        sum += a[i] * b[i];
    }
    return sum;
}

double dot_d(const double *a, const double *b, intptr_t n) {
    double sum = 0.0;
    int i;
    for (i = 0; i < n; i++) {
        sum += a[i] * b[i];
    }
    return sum;
}
