# Timing Demo

## Interface

```python
# Python dict format equivalent of wsum.c2py
{
    "module": "timing_demomod",
    "source": ["wsum.c"],
    "timing": True,
    "functions": [
        {
            "py_sig": "wsum(data: buffer, weight: float) -> float",
            "doc": "Weighted sum with automatic dispatch. Supports double and float buffers.",
            "c_overloads": [
                {
                    "sig": "weighted_sum_double(const double *data, intptr_t n, float weight) -> double",
                    "map": {
                        "data": "data.ptr",
                        "n": "data.n",
                        "weight": "weight",
                    },
                    "when": "data.format == 'd'",
                    "name": "double",
                },
                {
                    "sig": "weighted_sum_float(const float *data, intptr_t n, float weight) -> double",
                    "map": {
                        "data": "data.ptr",
                        "n": "data.n",
                        "weight": "weight",
                    },
                    "when": "data.format == 'f'",
                    "name": "float",
                },
            ],
            "default_raise": "TypeError: expected float or double buffer",
        },
    ],
}
```

## C Source

```c
#include <stdint.h>

double weighted_sum_double(const double *data, intptr_t n, float weight) {
    double total = 0.0;
    intptr_t i;
    for (i = 0; i < n; i++) {
        total += data[i] * (double)weight;
    }
    return total;
}

double weighted_sum_float(const float *data, intptr_t n, float weight) {
    double total = 0.0;
    intptr_t i;
    for (i = 0; i < n; i++) {
        total += (double)data[i] * (double)weight;
    }
    return total;
}
```

## Build

```bash
$ c2py23 wsum.c2py -o timing_demomod_wrapper.c
```


Compile:

```bash
$ cc -shared -fPIC c2py23/runtime/c2py_runtime.c timing_demomod_wrapper.c wsum.c -I c2py23/runtime -o timing_demomod.so -ldl -lm
```

See [docs/building](building) for cmake, meson, and setuptools options.

