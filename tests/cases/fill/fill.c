#include <stdint.h>
/* fill.c - fill an array with a constant value */

void fill_f(float *arr, intptr_t n, float value) {
    int i;
    for (i = 0; i < n; i++) {
        arr[i] = value;
    }
}

void fill_d(double *arr, intptr_t n, double value) {
    int i;
    for (i = 0; i < n; i++) {
        arr[i] = value;
    }
}
