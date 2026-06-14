/* dot.c - dot product of float or double arrays */

float dot_f(const float *a, const float *b, int n) {
    float sum = 0.0f;
    int i;
    for (i = 0; i < n; i++) {
        sum += a[i] * b[i];
    }
    return sum;
}

double dot_d(const double *a, const double *b, int n) {
    double sum = 0.0;
    int i;
    for (i = 0; i < n; i++) {
        sum += a[i] * b[i];
    }
    return sum;
}
