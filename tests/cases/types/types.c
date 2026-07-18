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
                    "sig": "fill_u16(uint16_t *arr, intptr_t n, uint16_t value)",
                    "when": "arr.format == 'H'"
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
                    "sig": "fill_i64(int64_t *arr, intptr_t n, int64_t value)",
                    "when": "arr.format == 'q'"
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
                    "sig": "fill_i16(int16_t *arr, intptr_t n, int16_t value)",
                    "when": "arr.format == 'h'"
                }
            ],
            "default_raise": "TypeError: expected 'H', 'I'/'L', 'q', 'b', 'i'/'l', or 'h' buffer",
            "py_sig": "fill(arr: buffer, value: int) -> void"
        }
    ],
    "headers": [
        "stdint.h"
    ],
    "module": "typesmod",
    "source": [
        "types.c"
    ]
}
C2PY_END */

void fill_u16(uint16_t *arr, intptr_t n, uint16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_u32(uint32_t *arr, intptr_t n, uint32_t value)
{
    intptr_t i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i32(int32_t *arr, intptr_t n, int32_t value)
{
    intptr_t i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i64(int64_t *arr, intptr_t n, int64_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void fill_i8(int8_t *arr, intptr_t n, int8_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = (int8_t)value;
}

void fill_i16(int16_t *arr, intptr_t n, int16_t value)
{
    int i;
    for (i = 0; i < n; i++) arr[i] = (int16_t)value;
}
