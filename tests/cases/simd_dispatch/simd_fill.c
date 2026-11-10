#include <stddef.h>
#include <string.h>
#include "c2py_amd64.h"

/* Read a runtime CPU flag by name.  The flags themselves are hidden, so
 * tests/test_cpu_features.py reaches them through this exported function
 * (user C code linked into the module can see them).  Returns -1 for an
 * unknown name. */
int simd_fill_amd64_flag(const char *name)
{
#define F(n) if (strcmp(name, #n) == 0) return c2py_amd64_##n;
    F(sse2)
    F(sse3)
    F(ssse3)
    F(sse4_1)
    F(sse4_2)
    F(avx)
    F(avx2)
    F(fma)
    F(f16c)
    F(avx_vnni)
    F(avx512f)
    F(avx512cd)
    F(avx512dq)
    F(avx512bw)
    F(avx512vl)
    F(avx512ifma)
    F(avx512vbmi)
    F(avx512vbmi2)
    F(avx512vnni)
    F(avx512bitalg)
    F(avx512vpopcntdq)
    F(aes)
    F(pclmulqdq)
    F(sha_ni)
    F(gfni)
    F(vaes)
    F(vpclmulqdq)
    F(adx)
    F(movbe)
    F(bmi1)
    F(bmi2)
    F(popcnt)
    F(lzcnt)
    F(vendor_intel)
    F(vendor_amd)
#undef F
    return -1;
}

#ifdef __x86_64__
#include <emmintrin.h>
#endif

#ifdef __aarch64__
#include <arm_neon.h>
#endif

void fill_scalar(float *buf, int n, float val) {
    int i;
    for (i = 0; i < n; i++) buf[i] = val;
}

#ifdef __x86_64__
void fill_sse2(float *buf, int n, float val) {
    __m128 v = _mm_set1_ps(val);
    int i;
    for (i = 0; i + 3 < n; i += 4)
        _mm_storeu_ps(buf + i, v);
    for (; i < n; i++)
        buf[i] = val;
}
#else
void fill_sse2(float *buf, int n, float val) { fill_scalar(buf, n, val); }
#endif

#ifdef __aarch64__
void fill_neon(float *buf, int n, float val) {
    float32x4_t v = vdupq_n_f32(val);
    int i;
    for (i = 0; i + 3 < n; i += 4)
        vst1q_f32(buf + i, v);
    for (; i < n; i++)
        buf[i] = val;
}
#else
void fill_neon(float *buf, int n, float val) { fill_scalar(buf, n, val); }
#endif

#ifdef __powerpc64__
#include <altivec.h>
void fill_altivec(float *buf, int n, float val) {
    vector float v = vec_splats(val);
    int i;
    for (i = 0; i + 3 < n; i += 4)
        vec_st(v, 0, buf + i);
    for (; i < n; i++)
        buf[i] = val;
}
#else
void fill_altivec(float *buf, int n, float val) { fill_scalar(buf, n, val); }
#endif
