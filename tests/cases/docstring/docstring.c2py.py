# Python dict format equivalent of docstring.c2py
{
    "module": "docmod",
    "source": ["docstring.c"],
    "functions": [
        {
            "py_sig": "inc(x: int) -> int",
            "doc": "Increment x by 1 and return the result",
            "c_overloads": [
                {
                    "sig": "add_one(int x) -> int",
                    "map": {
                        "x": "x",
                    },
                },
            ],
        },
    ],
}
