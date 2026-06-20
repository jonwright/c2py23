#include <stdint.h>

void fill_u16(uint16_t *arr, int n, uint16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_u32(uint32_t *arr, int n, uint32_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i32(int32_t *arr, int n, int32_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i64(int64_t *arr, int n, int64_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i8(int8_t *arr, int n, int8_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = (int8_t)value;
}

void fill_i16(int16_t *arr, int n, int16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = (int16_t)value;
}
