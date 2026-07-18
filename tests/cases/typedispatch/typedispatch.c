#include <stdint.h>

/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_u8(uint8_t *arr, intptr_t n, uint8_t value)",
                    "when": "arr.format == 'B'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_i8(int8_t *arr, intptr_t n, int8_t value)",
                    "when": "arr.format == 'b'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_u16(uint16_t *arr, intptr_t n, uint16_t value)",
                    "when": "arr.format == 'H'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_i16(int16_t *arr, intptr_t n, int16_t value)",
                    "when": "arr.format == 'h'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_u32(uint32_t *arr, intptr_t n, uint32_t value)",
                    "when": "arr.format == 'I' or arr.format == 'L'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_i32(int32_t *arr, intptr_t n, int32_t value)",
                    "when": "arr.format == 'i' or arr.format == 'l'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_u64(uint64_t *arr, intptr_t n, uint64_t value)",
                    "when": "arr.format == 'Q'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_i64(int64_t *arr, intptr_t n, int64_t value)",
                    "when": "arr.format == 'q'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_f32(float *arr, intptr_t n, float value)",
                    "when": "arr.format == 'f'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value"
                    },
                    "sig": "fill_f64(double *arr, intptr_t n, double value)",
                    "when": "arr.format == 'd'"
                }
            ],
            "default_raise": "TypeError: expected buffer of type B,b,H,h,I/i/L/l,Q,q,f,d",
            "py_sig": "fill(arr: buffer, value: float) -> void"
        }
    ],
    "headers": [
        "stdint.h"
    ],
    "module": "dispatchmod",
    "source": [
        "typedispatch.c"
    ]
}
C2PY_END */

void fill_u8(uint8_t *arr, intptr_t n, uint8_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i8(int8_t *arr, intptr_t n, int8_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_u16(uint16_t *arr, intptr_t n, uint16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i16(int16_t *arr, intptr_t n, int16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_u32(uint32_t *arr, intptr_t n, uint32_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i32(int32_t *arr, intptr_t n, int32_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_u64(uint64_t *arr, intptr_t n, uint64_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i64(int64_t *arr, intptr_t n, int64_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_f32(float *arr, intptr_t n, float value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_f64(double *arr, intptr_t n, double value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}
