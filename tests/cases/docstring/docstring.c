
/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "x": "x"
                    },
                    "sig": "add_one(int x) -> int"
                }
            ],
            "doc": "Increment x by 1 and return the result",
            "py_sig": "inc(x: int) -> int"
        }
    ],
    "module": "docmod",
    "source": [
        "docstring.c"
    ]
}
C2PY_END */

int add_one(int x)
{
    return x + 1;
}
