#include <stdint.h>

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
