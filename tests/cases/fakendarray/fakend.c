/* fakend.c - sum of unsigned bytes (see fakend.c2py) */
#include <stdint.h>

void bytesum(const uint8_t *data, int64_t n, int64_t *out);

void bytesum(const uint8_t *data, int64_t n, int64_t *out)
{
    int64_t i, s = 0;
    for (i = 0; i < n; i++)
        s += data[i];
    *out = s;
}
