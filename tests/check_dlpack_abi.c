/* check_dlpack_abi.c - Verify DLPack struct layout against c2py23's
 * hardcoded definitions in c2py_runtime.h.
 *
 * This does NOT include any external DLPack headers -- it uses the
 * same struct definitions that c2py_runtime.h uses.  It verifies:
 *   1. field offsets match expected values
 *   2. sizeof matches expected values
 *   3. alignment assumptions hold
 *
 * Compile:  gcc -std=c99 -Wall check_dlpack_abi.c -o check_dlpack_abi
 * Usage:    ./check_dlpack_abi
 */

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

/* --- Exact definitions from c2py_runtime.h --- */

typedef struct {
    uint8_t code;
    uint8_t bits;
    uint16_t lanes;
} c2py_dl_dtype_t;

typedef struct {
    int32_t device_type;
    int32_t device_id;
} c2py_dl_device_t;

typedef struct {
    void *data;
    c2py_dl_device_t device;
    int32_t ndim;
    c2py_dl_dtype_t dtype;
    int64_t *shape;
    int64_t *strides;
    int64_t byte_offset;
} c2py_dl_tensor_t;

typedef struct c2py_dl_managed_tensor {
    c2py_dl_tensor_t dl_tensor;
    void *manager_ctx;
    void (*deleter)(struct c2py_dl_managed_tensor *);
} c2py_dl_managed_tensor;

#define EXPECT(label, val, expected) do { \
    printf("%-35s %-6s (expected %s, got %s)\n", \
           label, \
           ((val) == (expected)) ? "OK" : "MISMATCH", \
           #expected, \
           _fmt_sz((size_t)(val))); \
    if ((val) != (expected)) ok = 0; \
} while(0)

static char _fmt_buf[32];
static const char *_fmt_sz(size_t v) {
    sprintf(_fmt_buf, "%zu", v);
    return _fmt_buf;
}

int main(void) {
    int ok = 1;
    c2py_dl_dtype_t dt = {0};
    c2py_dl_device_t dv = {0};
    c2py_dl_tensor_t t = {0};
    c2py_dl_managed_tensor m = {0};

    printf("DLPACK_ABI 1.0\n");
    printf("\n=== DLDataType ===\n");
    EXPECT("SIZEOF c2py_dl_dtype_t", sizeof(c2py_dl_dtype_t), 4);
    EXPECT("OFF code",   offsetof(c2py_dl_dtype_t, code),   0);
    EXPECT("OFF bits",   offsetof(c2py_dl_dtype_t, bits),   1);
    EXPECT("OFF lanes",  offsetof(c2py_dl_dtype_t, lanes),  2);

    printf("\n=== DLDevice ===\n");
    EXPECT("SIZEOF c2py_dl_device_t", sizeof(c2py_dl_device_t), 8);
    EXPECT("OFF device_type", offsetof(c2py_dl_device_t, device_type), 0);
    EXPECT("OFF device_id",   offsetof(c2py_dl_device_t, device_id),   4);

    printf("\n=== DLTensor ===\n");
    printf("SIZEOF c2py_dl_tensor_t = %zu\n", sizeof(c2py_dl_tensor_t));
    EXPECT("OFF data",        offsetof(c2py_dl_tensor_t, data),        0);
    EXPECT("OFF device",      offsetof(c2py_dl_tensor_t, device),      8);
    EXPECT("OFF ndim",        offsetof(c2py_dl_tensor_t, ndim),       16);
    EXPECT("OFF dtype",       offsetof(c2py_dl_tensor_t, dtype),      20);
    EXPECT("OFF shape",       offsetof(c2py_dl_tensor_t, shape),      24);
    EXPECT("OFF strides",     offsetof(c2py_dl_tensor_t, strides),    32);
    EXPECT("OFF byte_offset", offsetof(c2py_dl_tensor_t, byte_offset), 40);

    printf("\n=== DLManagedTensor ===\n");
    printf("SIZEOF c2py_dl_managed_tensor = %zu\n",
           sizeof(c2py_dl_managed_tensor));
    EXPECT("OFF dl_tensor",   offsetof(c2py_dl_managed_tensor, dl_tensor),   0);
    EXPECT("OFF manager_ctx", offsetof(c2py_dl_managed_tensor, manager_ctx),
           sizeof(c2py_dl_tensor_t));
    EXPECT("OFF deleter",     offsetof(c2py_dl_managed_tensor, deleter),
           sizeof(c2py_dl_tensor_t) + sizeof(void*));

    printf("\n---\n");
    if (ok) {
        printf("DLPACK_ABI_OK 1\n");
        return 0;
    } else {
        printf("DLPACK_ABI_OK 0\n");
        return 1;
    }
}
