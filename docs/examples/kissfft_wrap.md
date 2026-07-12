# KISS FFT Wrapping

Wraps the [KISS FFT](https://github.com/mborgerding/kissfft) library using c2py23.
Demonstrates complex-number handling via interleaved float32 buffers
(c2py23 has no native complex type).

## Interface

```yaml
--8<-- "examples/kissfft_wrap/kissfft.c2py"
```

## C Source

```c
--8<-- "examples/kissfft_wrap/kissfft_thin.c"
```

## Build & Run

```bash
git submodule update --init kissfft
cd examples/kissfft_wrap
pip install -e ../..
bash build.sh
python example.py
```

## Output

```
$ python example.py
rfft: spec[0]=0.00 spec[1]=0.00
cfft: fout[0]=0.00 fout[1]=0.00
```

The real FFT takes N real floats and produces (N/2+1)*2 floats (interleaved
real/imag pairs).  The complex FFT takes N*2 float32 (interleaved real/imag)
and produces the same shape.

### Key Design Decisions

- Complex data is **interleaved float pairs**, not a native `complex64` type
- Format check is `'f'` (float32) -- the wrapper casts `float*` to `kiss_fft_cpx*`
- `fin.n % 2 == 0` check ensures even-length buffer (complete real/imag pairs)
- Map passes `n = fin.n / 2` (number of complex elements, not float count)
- Real FFT output sizing: `spec.n >= data.n + 2` (N/2+1 complex bins = N+2 floats)
