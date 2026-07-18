#include <stdint.h>
/* dot.c - dot product of float or double arrays */

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
