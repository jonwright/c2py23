#include <stdint.h>

typedef struct { uint64_t s; } xrs128_t;

static inline uint64_t xrs128_next(xrs128_t *st) {
    uint64_t x = st->s;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    st->s = x;
    return x;
}

static inline double xrs128_double(xrs128_t *st) {
    return (double)(xrs128_next(st) >> 11) * 0x1.0p-53;
}

static void xrs128_seed(xrs128_t *st, unsigned int seed) {
    st->s = (uint64_t)(seed + 1) * 0x9E3779B97F4A7C15ULL;
    (void)xrs128_next(st);
}

int mc_pi_serial(int n, int seed) {
    int inside = 0;
    int i;
    xrs128_t rng;
    xrs128_seed(&rng, (unsigned int)seed);

    for (i = 0; i < n; i++) {
        double x = xrs128_double(&rng);
        double y = xrs128_double(&rng);
        if (x * x + y * y <= 1.0)
            inside++;
    }
    return inside;
}
