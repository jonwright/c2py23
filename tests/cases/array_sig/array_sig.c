#include <stdint.h>

/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "gv": "data.ptr",
                        "ng": "data.shape[0]"
                    },
                    "sig": "double sum_rows(const double gv[][3], intptr_t ng)"
                }
            ],
            "py_sig": "sum_rows(data: buffer) -> float"
        },
        {
            "c_overloads": [
                {
                    "map": {
                        "ubi": "data.ptr"
                    },
                    "sig": "double sum_33(const double ubi[3][3])"
                }
            ],
            "py_sig": "sum_33(data: buffer) -> float"
        },
        {
            "c_overloads": [
                {
                    "map": {
                        "arr": "data.ptr"
                    },
                    "sig": "double sum_1d_fixed(const double arr[5])"
                }
            ],
            "checks": [
                "data.format == 'd'"
            ],
            "py_sig": "sum_1d_fixed(data: buffer) -> float"
        },
        {
            "c_overloads": [
                {
                    "map": {
                        "blk": "data.ptr",
                        "nblk": "data.shape[0]"
                    },
                    "sig": "double sum_3d(const double blk[][5][5], intptr_t nblk)"
                }
            ],
            "py_sig": "sum_3d(data: buffer) -> float"
        }
    ],
    "module": "arraymod",
    "source": [
        "array_sig.c"
    ]
}
C2PY_END */

double sum_rows(const double gv[][3], intptr_t ng)
{
    double s = 0.0;
    int i, j;
    for (i = 0; i < ng; i++) {
        for (j = 0; j < 3; j++) {
            s += gv[i][j];
        }
    }
    return s;
}

double sum_33(const double ubi[3][3])
{
    double s = 0.0;
    int i, j;
    for (i = 0; i < 3; i++) {
        for (j = 0; j < 3; j++) {
            s += ubi[i][j];
        }
    }
    return s;
}

double sum_1d_fixed(const double arr[5])
{
    double s = 0.0;
    int i;
    for (i = 0; i < 5; i++) {
        s += arr[i];
    }
    return s;
}

double sum_3d(const double blk[][5][5], intptr_t nblk)
{
    double s = 0.0;
    int i, j, k;
    for (i = 0; i < nblk; i++) {
        for (j = 0; j < 5; j++) {
            for (k = 0; k < 5; k++) {
                s += blk[i][j][k];
            }
        }
    }
    return s;
}
