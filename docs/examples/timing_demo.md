# Performance Timing

Demonstrates c2py23's built-in performance timing instrumentation.
Two overloads (double and float) show per-variant timing breakdown.

## Interface

```yaml
--8<-- "examples/timing_demo/wsum.c2py"
```

## C Source

```c
--8<-- "examples/timing_demo/wsum.c"
```

## Jupyter Notebook

The interactive notebook `examples/timing_demo/timing_demo.ipynb` demonstrates:

- Reading timing data with `c2py23.perf.read_perf()`
- Per-function vs per-overload timing breakdown
- Comparing c2py23 timing with `%%time` cell magic
- Switching tick source: wall-clock (default) vs CPU cycle counter
- Dynamically enabling/disabling timing per function

## Build & Run

```bash
pip install -e .                    # from repo root
cd examples/timing_demo
c2py23 wsum.c2py -o wsummod_wrapper.c
python -c "
import ctypes
import timing_demomod as tmod

data = (ctypes.c_double * 5)(1.0, 2.0, 3.0, 4.0, 5.0)
r = tmod.wsum(data, 2.0)
print('Sum:', r)
from c2py23.perf import read_perf
print('Timing:', read_perf(tmod.wsum))
"
```

## How It Works

`timing: true` enables per-function performance counters.  Two `c2py_perf_t`
structs are emitted per function: one for the wrapper overhead and one for
each overload's C code.  Ticks are recorded without any Python-side
interaction -- the wrapper reads the cycle counter or `clock_gettime`
before and after the C call.

The tick source defaults to nanosecond-resolution wall-clock.  Switch to
CPU cycle counter for higher precision:

```python
mymod._c2py_set_tick_source("cycle")
```

Fall back to wall-clock:

```python
mymod._c2py_set_tick_source("clock")
```

When timing is disabled (`set_enabled(func, 0)`), the tick counters are
bypassed entirely -- zero overhead.
