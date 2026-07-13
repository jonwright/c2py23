# KISS FFT Wrapping

Wraps the [KISS FFT](https://github.com/mborgerding/kissfft) library using c2py23.
Demonstrates complex-number handling via interleaved float32 buffers
(c2py23 has no native complex type).

--8<-- "examples/kissfft_wrap/README.md"

## How It Works

### Complex numbers as float pairs

c2py23 has no complex type.  The thin wrapper casts `float*` buffers to
`kiss_fft_cpx*` (a struct of two floats).  Python callers create interleaved
float arrays -- `[re0, im0, re1, im1, ...]`.

### Buffer sizing

The real FFT takes N real floats. Its output is N/2+1 complex bins stored
as (N/2+1)*2 = N+2 floats.  The check `spec.n >= data.n + 2` enforces this.

The complex FFT takes N complex numbers = N*2 floats.  The check
`fin.n % 2 == 0` ensures an even number of floats (complete pairs).

### Map expressions

The C function receives `n` (number of complex elements), but the buffer
has `N*2` floats.  The map `n: "fin.n / 2"` bridges this.
