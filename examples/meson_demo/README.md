# Meson Demo

## Interface

```yaml
module: _arraysum
source: [arraysum.c]

functions:
  - py_sig: "array_sum(a: buffer, b: buffer, result: buffer) -> int"
    doc: "Element-wise addition of two double arrays: out[i] = a[i] + b[i]"
    checks:
      - "a.format == 'd'"
      - "b.format == 'd'"
      - "result.format == 'd'"
      - "a.n == b.n"
      - "a.n == result.n"
    c_overloads:
      - sig: "array_sum(const double *a, const double *b, double *result, int n) -> int"
        map: {a: "a.ptr", b: "b.ptr", result: "result.ptr", n: "a.n"}```

## C Source

```c
/* arraysum.c - element-wise addition of double arrays */
extern int array_sum(const double *a, const double *b, double *result, int n);

int array_sum(const double *a, const double *b, double *result, int n) {
    int i;
    for (i = 0; i < n; i++) {
        result[i] = a[i] + b[i];
    }
    return n;
}```

## Build

```bash
$ c2py23 build arraysum.c2py
```

