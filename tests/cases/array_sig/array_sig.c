#include <stdint.h>
/* array_sig.c -- test array dimension notation in sig: */
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
