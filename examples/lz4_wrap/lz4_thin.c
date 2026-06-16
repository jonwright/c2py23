#include <stdint.h>
#include "../lz4/lib/lz4.h"

int lz4_compress(const uint8_t *src, uint8_t *dst, int srcSize, int dstCapacity) {
    return LZ4_compress_default((const char *)src, (char *)dst, srcSize, dstCapacity);
}

int lz4_decompress(const uint8_t *src, uint8_t *dst, int compressedSize, int dstCapacity) {
    return LZ4_decompress_safe((const char *)src, (char *)dst, compressedSize, dstCapacity);
}
