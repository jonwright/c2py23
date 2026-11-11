#include <stdint.h>
/* ptralign.c - an "aligned" kernel and a fallback that tag their result */

void tag_aligned(const double *a, int64_t n, int64_t *out) { (void)a; (void)n; *out = 1; }

void tag_fallback(const double *a, int64_t n, int64_t *out) { (void)a; (void)n; *out = 0; }
