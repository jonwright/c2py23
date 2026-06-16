/* poly_kernel.c -- compute-bound polynomial: out[i] = f(a[i], b[i])
 *
 * Each element does many arithmetic operations per memory load to
 * make the kernel compute-bound rather than memory-bound.  This
 * ensures SIMD width differences (SSE 4-wide, AVX2 8-wide,
 * AVX-512 16-wide) translate to visible throughput differences.
 *
 * This file is compiled multiple times with different -m flags and
 * -DKERNEL_FN=<name> to produce ISA-specific variants.  The kernel
 * itself is plain C99; the compiler auto-vectorizes based on the
 * -m flags supplied at compile time.
 *
 * Build (see Makefile):
 *   gcc -c -O3 -ffast-math -mavx512f -DKERNEL_FN=poly_f32_avx512 poly_kernel.c -o ...
 *   gcc -c -O3 -ffast-math -mavx2   -DKERNEL_FN=poly_f32_avx2   poly_kernel.c -o ...
 *   gcc -c -O3 -ffast-math          -DKERNEL_FN=poly_f32_scalar  poly_kernel.c -o ...
 */

#include <stddef.h>

#ifndef KERNEL_FN
#define KERNEL_FN poly_f32
#endif

/* Horner-like repeated squaring: x = a[i], then x = x*x + b[i] many times.
 * Each inner iteration: 1 mul + 1 add, 0 extra memory accesses.
 * Arithmetic intensity: ~16:1 (16 mul+add per 2 loads + 1 store). */
#define POLY_DEPTH 16

void KERNEL_FN(const float *a, const float *b, float *out, int n)
{
    int i;
    for (i = 0; i < n; i++) {
        float x = a[i];
        float y = b[i];
        int k;
        for (k = 0; k < POLY_DEPTH; k++)
            x = x * x + y;
        out[i] = x;
    }
}
