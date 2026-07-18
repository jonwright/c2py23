#include <stdint.h>
/* arraysum.c - element-wise addition of double arrays */
/* C2PY_BEGIN
{
    "free_threading": true,
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "a": "a.ptr",
                        "b": "b.ptr",
                        "n": "a.n",
                        "result": "result.ptr"
                    },
                    "sig": "array_sum(const double *a, const double *b, double *result, intptr_t n) -> int"
                }
            ],
            "checks": [
                "a.format == 'd'",
                "b.format == 'd'",
                "result.format == 'd'",
                "a.n == b.n",
                "a.n == result.n"
            ],
            "py_sig": "array_sum(a: buffer, b: buffer, result: buffer) -> int"
        }
    ],
    "module": "arraysum",
    "source": [
        "arraysum.c"
    ]
}
C2PY_END */

extern int array_sum(const double *a, const double *b, double *result, intptr_t n);

int array_sum(const double *a, const double *b, double *result, intptr_t n) {
    int i;
    for (i = 0; i < n; i++) {
        result[i] = a[i] + b[i];
    }
    return n;
}
