/* saxpy_kernel.c -- single-precision SAXPY: out[i] = a[i] * scale + b[i]
 *
 * This file is compiled multiple times with different -m flags and
 * -DKERNEL_FN=<name> to produce ISA-specific variants.  The kernel
 * itself is plain C99; the compiler auto-vectorizes based on the
 * -m flags supplied at compile time.
 *
 * Build (see Makefile):
 *   gcc -c -O3 -mavx512f -DKERNEL_FN=saxpy_f32_avx512 saxpy_kernel.c -o ...
 *   gcc -c -O3 -mavx2   -DKERNEL_FN=saxpy_f32_avx2   saxpy_kernel.c -o ...
 *   gcc -c -O3          -DKERNEL_FN=saxpy_f32_scalar  saxpy_kernel.c -o ...
 *
 * c2py23 wraps the renamed function via variants: in the .c2py file
 * with when: conditions keyed on c2py_amd64_* feature flags.
 */

#include <stddef.h>

#ifndef KERNEL_FN
#define KERNEL_FN saxpy_f32
#endif

void KERNEL_FN(const float *a, float scale, const float *b, float *out, int n)
{
    int i;
    for (i = 0; i < n; i++)
        out[i] = a[i] * scale + b[i];
}
