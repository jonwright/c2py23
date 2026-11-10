#include <stdint.h>
/* shapeguard.c - kernels whose map: reads shape[k] / strides[k] */

void get_cols(const double *a, int64_t n, int64_t *out) { (void)a; *out = n; }

void get_stride1(const double *a, int64_t s, int64_t *out) { (void)a; *out = s; }

void tag_three(const double *a, int64_t *out) { (void)a; *out = 3; }

void tag_vec(const double *a, int64_t n, int64_t *out) { (void)a; *out = n; }

void tag_mat3(const double *a, int64_t rows, int64_t *out) { (void)a; *out = 1000 + rows; }
