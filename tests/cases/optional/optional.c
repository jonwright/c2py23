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
                        "stride": "stride",
                        "verbose": "verbose"
                    },
                    "sig": "process_data(const double *data, intptr_t n, int stride, int verbose) -> int"
                }
            ],
            "checks": [
                "data.format == 'd'"
            ],
            "py_sig": "process(data: buffer, stride: int = 1, verbose: int = 0) -> int"
        }
    ],
    "module": "optmod",
    "source": [
        "optional.c"
    ]
}
C2PY_END */

int process_data(const double *data, intptr_t n, int stride, int verbose)
{
    int i;
    int result = 0;
    if (verbose) {
        /* side-effect to prove verbose was used */
        result += 1000;
    }
    for (i = 0; i < n; i += stride) {
        result += (int)data[i];
    }
    return result;
}
