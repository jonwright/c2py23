#include <stdint.h>
/* Simple C function for free-threading test */
/* C2PY_BEGIN
{
    "free_threading": true,
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "a": "a.ptr",
                        "n": "a.n",
                        "result": "result.ptr"
                    },
                    "sig": "double_it(const double *a, double *result, intptr_t n) -> int"
                }
            ],
            "checks": [
                "a.format == 'd'",
                "result.format == 'd'",
                "result.n >= a.n"
            ],
            "py_sig": "double_it(a: buffer, result: buffer) -> int"
        }
    ],
    "module": "freethreadmod",
    "source": [
        "freethread.c"
    ]
}
C2PY_END */

int double_it(const double *in, double *out, intptr_t n) {
    for (int i = 0; i < n; i++) out[i] = in[i] * 2.0;
    return n;
}
