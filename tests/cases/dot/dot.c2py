# Python dict format equivalent of dot.c2py
{
    "module": "dotmod",
    "source": ["dot.c"],
    "functions": [
        {
            "py_sig": "dot(a: buffer, b: buffer) -> float",
            "checks": [
                "a.format == b.format",
                "a.n == b.n",
            ],
            "c_overloads": [
                {
                    "sig": "dot_f(const float *a, const float *b, intptr_t n) -> float",
                    "map": {
                        "a": "a.ptr",
                        "b": "b.ptr",
                        "n": "a.n",
                    },
                    "when": "a.format == 'f'",
                },
                {
                    "sig": "dot_d(const double *a, const double *b, intptr_t n) -> double",
                    "map": {
                        "a": "a.ptr",
                        "b": "b.ptr",
                        "n": "a.n",
                    },
                    "when": "a.format == 'd'",
                },
            ],
            "default_raise": "TypeError: expected float or double buffer",
        },
    ],
}
