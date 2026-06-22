#include <stdint.h>

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
