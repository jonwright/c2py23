#include <stdint.h>

int address_store(void *ptr, int value, int offset) {
    int *p = (int *)ptr;
    if (!ptr) return -1;
    p[offset] = value;
    return 0;
}
