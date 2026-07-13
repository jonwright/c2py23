#include <stdint.h>

double weighted_sum_double(const double *data, intptr_t n, float weight) {
    double total = 0.0;
    intptr_t i;
    for (i = 0; i < n; i++) {
        total += data[i] * (double)weight;
    }
    return total;
}

double weighted_sum_float(const float *data, intptr_t n, float weight) {
    double total = 0.0;
    intptr_t i;
    for (i = 0; i < n; i++) {
        total += (double)data[i] * (double)weight;
    }
    return total;
}
