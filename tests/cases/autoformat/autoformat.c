/* autoformat.c - kernels whose buffers carry no format check in the
 * .c2py: the element type check is derived from the C pointee type. */
#include <stdint.h>
#include <string.h>

void sum_f64(const double *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_f32(const float *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_i8(const int8_t *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_u8(const uint8_t *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_char(const char *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_i16(const int16_t *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_u16(const uint16_t *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_i32(const int32_t *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_int(const int *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_u32(const uint32_t *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_i64(const int64_t *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void sum_u64(const uint64_t *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0;
    for (i = 0; i < n; i++) s += (double)a[i];
    *out = s;
}

void filld(double *a, intptr_t n, double v)
{
    intptr_t i;
    for (i = 0; i < n; i++) a[i] = v;
}

/* Reads doubles through memcpy, so an unaligned pointer is well defined. */
void sum_raw(const double *a, intptr_t n, double *out)
{
    intptr_t i;
    double s = 0.0, x;
    for (i = 0; i < n; i++) {
        memcpy(&x, (const char *)a + i * (intptr_t)sizeof(double), sizeof(double));
        s += x;
    }
    *out = s;
}

void scale_f32(float *a, intptr_t n, double v, int64_t *out)
{
    intptr_t i;
    for (i = 0; i < n; i++) a[i] = (float)(a[i] * v);
    *out = 32;
}

void scale_f64(double *a, intptr_t n, double v, int64_t *out)
{
    intptr_t i;
    for (i = 0; i < n; i++) a[i] = a[i] * v;
    *out = 64;
}

void count_bytes(const void *a, intptr_t n, int64_t *out)
{
    (void)a;
    *out = (int64_t)n;
}
