#include <stdint.h>
/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "data": "data.ptr",
                        "n": "data.n"
                    },
                    "outputs": {
                        "maxval": "double",
                        "minval": "double"
                    },
                    "sig": "stats(const double *data, intptr_t n, double *minval, double *maxval)"
                }
            ],
            "checks": [
                "data.format == 'd'"
            ],
            "py_sig": "stats(data: buffer) -> void"
        }
    ],
    "module": "statmod",
    "source": [
        "stats.c"
    ]
}
C2PY_END */

void stats(const double *data, intptr_t n, double *minval, double *maxval)
{
    int i;
    double mn = data[0];
    double mx = data[0];
    for (i = 1; i < n; i++) {
        if (data[i] < mn) mn = data[i];
        if (data[i] > mx) mx = data[i];
    }
    *minval = mn;
    *maxval = mx;
}
