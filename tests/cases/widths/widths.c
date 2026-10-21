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

/* Pointer-width receivers: 32 bits on ILP32, so the wrapper must range-check
   a long long scalar before narrowing. */
void echo_size(size_t v, size_t *out)
{
    *out = v;
}

void echo_iptr(intptr_t v, intptr_t *out)
{
    *out = v;
}

void echo_pdiff(ptrdiff_t v, ptrdiff_t *out)
{
    *out = v;
}

/* Overflow-checked expression arithmetic: the wrapper must reject
   rows * cols, data.len / 0 and data.len * k that do not fit long long. */
void fill_grid(uint8_t *out, int64_t n)
{
    int64_t i;
    for (i = 0; i < n; i++)
        out[i] = 1;
}

void chunk_len(const uint8_t *data, int64_t n, int64_t *out)
{
    (void)data;
    *out = n;
}

void pick_half(const uint8_t *data, int32_t *out)
{
    (void)data;
    *out = 1;
}

void pick_none(const uint8_t *data, int32_t *out)
{
    (void)data;
    *out = 0;
}
