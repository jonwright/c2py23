# LZ4 Compression

Wraps the [LZ4](https://github.com/lz4/lz4) compression library using c2py23.
Demonstrates uint8 buffer handling with dynamic output sizing.

--8<-- "examples/lz4_wrap/README.md"

## How It Works

### uint8 buffers

LZ4 operates on `char*` data.  The thin wrapper casts `const uint8_t*` to
`const char*` and back.  The format check is `'B'` (uint8).

### Dynamic output size

`compress` returns the actual compressed byte count.  The Python caller
reads this and slices the destination buffer to the actual size before
passing to `decompress`.
