#include "lz4/lib/lz4.h"

int lz4_compress(const char *src, char *dst, int srcSize, int dstCapacity) {
    return LZ4_compress_default(src, dst, srcSize, dstCapacity);
}

int lz4_decompress(const char *src, char *dst, int compressedSize, int dstCapacity) {
    return LZ4_decompress_safe(src, dst, compressedSize, dstCapacity);
}
