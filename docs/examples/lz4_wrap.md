# LZ4 Compression Wrapping

Wraps the [LZ4](https://github.com/lz4/lz4) compression library using c2py23.
Demonstrates uint8 buffer handling with dynamic output size (compress returns
the compressed byte count).

## Interface

```yaml
--8<-- "examples/lz4_wrap/lz4.c2py"
```

## C Source

```c
--8<-- "examples/lz4_wrap/lz4_thin.c"
```

## Build & Run

```bash
git submodule update --init lz4
cd examples/lz4_wrap
pip install -e ../..
bash build.sh
python example.py
```

## Output

```
$ python example.py
Compressed 1400 -> 29 bytes
Decompressed: 1400 bytes, match=True
```

### Key Design Decisions

- Buffers use `format == 'B'` (uint8) matching LZ4's `char*` convention
- Thin wrapper (`lz4_thin.c`) casts `uint8_t*` to `char*` and back
- `compress` returns the compressed byte count via `outputs:`
- Caller allocates the destination buffer and slices it to the actual compressed size
