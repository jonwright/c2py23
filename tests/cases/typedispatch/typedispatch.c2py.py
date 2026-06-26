# Python dict format equivalent of typedispatch.c2py
{
    "module": "dispatchmod",
    "source": ["typedispatch.c"],
    "headers": ["stdint.h"],
    "functions": [
        {
            "py_sig": "fill(arr: buffer, value: float) -> void",
            "c_overloads": [
                {
                    "sig": "fill_u8(uint8_t *arr, intptr_t n, uint8_t value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'B'",
                },
                {
                    "sig": "fill_i8(int8_t *arr, intptr_t n, int8_t value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'b'",
                },
                {
                    "sig": "fill_u16(uint16_t *arr, intptr_t n, uint16_t value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'H'",
                },
                {
                    "sig": "fill_i16(int16_t *arr, intptr_t n, int16_t value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'h'",
                },
                {
                    "sig": "fill_u32(uint32_t *arr, intptr_t n, uint32_t value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'I' or arr.format == 'L'",
                },
                {
                    "sig": "fill_i32(int32_t *arr, intptr_t n, int32_t value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'i' or arr.format == 'l'",
                },
                {
                    "sig": "fill_u64(uint64_t *arr, intptr_t n, uint64_t value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'Q'",
                },
                {
                    "sig": "fill_i64(int64_t *arr, intptr_t n, int64_t value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'q'",
                },
                {
                    "sig": "fill_f32(float *arr, intptr_t n, float value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'f'",
                },
                {
                    "sig": "fill_f64(double *arr, intptr_t n, double value)",
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "value": "value",
                    },
                    "when": "arr.format == 'd'",
                },
            ],
            "default_raise": "TypeError: expected buffer of type B,b,H,h,I/i/L/l,Q,q,f,d",
        },
    ],
}
