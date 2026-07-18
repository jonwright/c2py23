# Python dict format equivalent of mc_pi.c2py
{
    "module": "mcpimod",
    "source": ["mc_pi.c"],
    "free_threading": True,
    "functions": [
        {
            "py_sig": "mc_pi(n: int, seed: int = 0) -> int",
            "doc": "Monte Carlo Pi estimation (serial, GIL released).",
            "gil_release": True,
            "c_overloads": [
                {
                    "sig": "mc_pi_serial(int n, int seed) -> int",
                    "map": {
                        "n": "n",
                        "seed": "seed",
                    },
                },
            ],
        },
    ],
}
