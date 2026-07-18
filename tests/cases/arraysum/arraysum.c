#include <stdint.h>
/* arraysum.c - element-wise addition of double arrays */
/* C2PY_BEGIN
{
    "module": "arraysum",
    "source": ["arraysum.c"],
    "free_threading": True,
    "functions": [
        {
            "py_sig": "array_sum(a: buffer, b: buffer, result: buffer) -> int",
            "checks": [
                "a.format == 'd'",
                "b.format == 'd'",
                "result.format == 'd'",
                "a.n == b.n",
                "a.n == result.n",
            ],
            "c_overloads": [
                {
                    "sig": "array_sum(const double *a, const double *b, double *result, intptr_t n) -> int",
                    "map": {
                        "a": "a.ptr",
                        "b": "b.ptr",
                        "result": "result.ptr",
                        "n": "a.n",
                    },
                },
            ],
        },
    ],
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
