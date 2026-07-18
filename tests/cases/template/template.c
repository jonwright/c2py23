#include <stdint.h>

/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "data": "data.ptr",
                        "n": "data.n"
                    },
                    "sig": "int sum_${SUFFIX}(const ${TYPE} *data, intptr_t n)"
                }
            ],
            "checks": [
                "data.len >= 0"
            ],
            "expand": {
                "SUFFIX": [
                    "u8",
                    "u16",
                    "i32"
                ],
                "TYPE": [
                    "uint8_t",
                    "uint16_t",
                    "int32_t"
                ]
            },
            "py_sig": "sum_${SUFFIX}(data: buffer) -> int"
        }
    ],
    "module": "summod",
    "source": [
        "template.c"
    ]
}
C2PY_END */

int sum_u8(const uint8_t *data, intptr_t n) {
    int s = 0, i;
    for (i = 0; i < n; i++) s += data[i];
    return s;
}

int sum_u16(const uint16_t *data, intptr_t n) {
    int s = 0, i;
    for (i = 0; i < n; i++) s += data[i];
    return s;
}

int sum_i32(const int32_t *data, intptr_t n) {
    int s = 0, i;
    for (i = 0; i < n; i++) s += data[i];
    return s;
}
