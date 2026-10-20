#include <stdint.h>
#include <stddef.h>

/* Byte count and last byte of a buffer that may exceed 2 GiB. */
void last_byte(const uint8_t *data, size_t n, int64_t *nbytes, uint8_t *last)
{
    *nbytes = (int64_t)n;
    *last = n ? data[n - 1] : 0;
}

/* Byte count received in a narrow uint8_t: range-checked by the wrapper. */
void small_len(const uint8_t *data, uint8_t n, int32_t *got)
{
    (void)data;
    *got = (int32_t)n;
}

void echo_u32(uint32_t v, uint32_t *out)
{
    *out = v;
}

void echo_i64(int64_t v, int64_t *out)
{
    *out = v;
}

void echo_u64(uint64_t v, uint64_t *out)
{
    *out = v;
}
