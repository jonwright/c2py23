#include <stdint.h>

int address_store(void *ptr, int value, int offset) {
    if (!ptr) return -1;
    int *p = (int *)ptr;
    p[offset] = value;
    return 0;
}
