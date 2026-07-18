#include <stddef.h>

/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "buf": "buf.ptr",
                        "n": "buf.n",
                        "val": "val"
                    },
                    "sig": "void fill_sse2(float *buf, int n, float val)",
                    "when": "c2py_amd64_sse2"
                },
                {
                    "map": {
                        "buf": "buf.ptr",
                        "n": "buf.n",
                        "val": "val"
                    },
                    "sig": "void fill_neon(float *buf, int n, float val)",
                    "when": "c2py_arm64_asimd"
                },
                {
                    "map": {
                        "buf": "buf.ptr",
                        "n": "buf.n",
                        "val": "val"
                    },
                    "sig": "void fill_altivec(float *buf, int n, float val)",
                    "when": "c2py_ppc64_altivec"
                },
                {
                    "map": {
                        "buf": "buf.ptr",
                        "n": "buf.n",
                        "val": "val"
                    },
                    "sig": "void fill_scalar(float *buf, int n, float val)"
                }
            ],
            "checks": [
                "buf.format == 'f'",
                "buf.n > 0"
            ],
            "py_sig": "fill(buf: buffer, val: float=3.14) -> void"
        }
    ],
    "headers": [
        "c2py_amd64.h",
        "c2py_arm64.h",
        "c2py_ppc64.h"
    ],
    "module": "simd_fillmod",
    "source": [
        "simd_fill.c"
    ],
    "timing": true
}
C2PY_END */

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
