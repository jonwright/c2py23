#include <stddef.h>

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
