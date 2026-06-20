#include <stdint.h>
/* transform.c - in-place 2D transform: AoS vs SoA dispatch */

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
