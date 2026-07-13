# LZ4 Compression

Wraps the [LZ4](https://github.com/lz4/lz4) compression library using c2py23.
Demonstrates uint8 buffer handling with dynamic output sizing.

## Interface

```yaml
--8<-- "examples/lz4_wrap/lz4.c2py"
```

## C Source

```c
--8<-- "examples/lz4_wrap/lz4_thin.c"
```

## Build

```bash
git submodule update --init lz4
pip install -e .                # from repo root
cd examples/lz4_wrap
bash build.sh
```

## Run

```python
--8<-- "examples/lz4_wrap/example.py"
```

## Output

```
Compressed 1400 -> 29 bytes
Decompressed: 1400 bytes, match=True
```

## How It Works

### uint8 buffers

LZ4 operates on `char*` data.  The thin wrapper casts `const uint8_t*` to
`const char*` and back.  The format check is `'B'` (uint8).

### Dynamic output size

`compress` returns the actual compressed byte count via `outputs: {dst_size: int}`.
The Python caller reads this and slices the destination buffer to the actual
size before passing to `decompress`.
