# Python dict format equivalent of arraysum.c2py
{
    "module": "arraysum",
    "source": ["arraysum.c"],
    "free_threading": True,
    "functions": [
        {
            "py_sig": "array_sum(a: buffer, b: buffer, result: buffer) -> int",
            "checks": [
                "a.format == 'd'",
                "b.format == 'd'",
                "result.format == 'd'",
                "a.n == b.n",
                "a.n == result.n",
            ],
            "c_overloads": [
                {
                    "sig": "array_sum(const double *a, const double *b, double *result, intptr_t n) -> int",
                    "map": {
                        "a": "a.ptr",
                        "b": "b.ptr",
                        "result": "result.ptr",
                        "n": "a.n",
                    },
                },
            ],
        },
    ],
}
