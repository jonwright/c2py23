#include <stdint.h>
/* arraysum.c - element-wise addition of double arrays */
extern int array_sum(const double *a, const double *b, double *result, intptr_t n);

int array_sum(const double *a, const double *b, double *result, intptr_t n) {
    int i;
    for (i = 0; i < n; i++) {
        result[i] = a[i] + b[i];
    }
    return n;
}
