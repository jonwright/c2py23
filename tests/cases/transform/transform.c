#include <stdint.h>
/* transform.c - in-place 2D transform: AoS vs SoA dispatch */

/* C2PY_BEGIN
{
    "free_threading": true,
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "n": "points.shape[0]",
                        "out": "out.ptr",
                        "points": "points.ptr"
                    },
                    "sig": "transform_aos(double *points, intptr_t n, double *out)",
                    "when": "points.shape[1] == 3"
                },
                {
                    "map": {
                        "n": "points.shape[1]",
                        "out": "out.ptr",
                        "points": "points.ptr"
                    },
                    "sig": "transform_soa(double *points, intptr_t n, double *out)",
                    "when": "points.shape[0] == 3"
                }
            ],
            "checks": [
                "points.format == 'd'",
                "out.format == 'd'",
                "out.n == points.n",
                "points.ndim == 2",
                "points.slow_axis == 0"
            ],
            "default_raise": "ValueError: expected [N,3] or [3,N] buffer",
            "py_sig": "transform(points: buffer, out: buffer) -> void"
        }
    ],
    "module": "xfrm",
    "source": [
        "transform.c"
    ],
    "timing": true
}
C2PY_END */

void transform_aos(double *points, intptr_t n, double *out) {
    /* points: [n, 3] layout (array of structs) */
    int i;
    for (i = 0; i < n; i++) {
        double x = points[i * 3 + 0];
        double y = points[i * 3 + 1];
        double z = points[i * 3 + 2];
        out[i * 3 + 0] = x * 2.0;
        out[i * 3 + 1] = y * 2.0;
        out[i * 3 + 2] = z * 2.0;
    }
}

void transform_soa(double *points, intptr_t n, double *out) {
    /* points: [3, n] layout (struct of arrays) */
    int i;
    for (i = 0; i < n; i++) {
        double x = points[0 * n + i];
        double y = points[1 * n + i];
        double z = points[2 * n + i];
        out[0 * n + i] = x * 2.0;
        out[1 * n + i] = y * 2.0;
        out[2 * n + i] = z * 2.0;
    }
}
