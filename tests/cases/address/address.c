#include <stdint.h>
#include <stddef.h>

int address_store(void *ptr, int value, int offset) {
    int *p = (int *)ptr;
    if (!ptr) return -1;
    p[offset] = value;
    return 0;
}

/* Return an opaque pointer: (char*)ptr + offset, delivered to Python as int. */
void *address_offset(void *ptr, int offset) {
    return (void *)((char *)ptr + offset);
}

/* Return NULL, delivered to Python as 0. */
void *address_null(void) {
    return (void *)NULL;
}

/* Prefix-form const pointer return: pass the same pointer straight back. */
const void *address_same(const void *ptr) {
    return ptr;
}

/* Return void * AND write an output scalar (value delivered second in tuple). */
void *address_with_out(void *ptr, int marker, int *out) {
    if (!ptr) return (void *)NULL;
    *out = marker + 7;
    return ptr;
}

/* Two variants of one group, both returning void *. */
void *address_var_a(void *ptr) {
    return (void *)((char *)ptr + 1);
}

void *address_var_b(void *ptr) {
    return (void *)((char *)ptr + 2);
}

/* void * return that releases the GIL around the call. */
void *address_gil(void *ptr, int offset) {
    return (void *)((char *)ptr + offset);
}
