#include <stdint.h>
/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "us": "us",
                        "value": "value"
                    },
                    "sig": "sleep_fill_f32(float *arr, intptr_t n, float value, int us)",
                    "when": "arr.format == 'f'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "us": "us",
                        "value": "value"
                    },
                    "sig": "sleep_fill_f64(double *arr, intptr_t n, double value, int us)",
                    "when": "arr.format == 'd'"
                }
            ],
            "default_raise": "TypeError: expected float or double buffer",
            "gil_release": true,
            "py_sig": "sleep_fill(arr: buffer, value: float, us: int) -> void"
        },
        {
            "c_overloads": [
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "us": "us",
                        "value": "value"
                    },
                    "sig": "sleep_fill_f32(float *arr, intptr_t n, float value, int us)",
                    "when": "arr.format == 'f'"
                },
                {
                    "map": {
                        "arr": "arr.ptr",
                        "n": "arr.n",
                        "us": "us",
                        "value": "value"
                    },
                    "sig": "sleep_fill_f64(double *arr, intptr_t n, double value, int us)",
                    "when": "arr.format == 'd'"
                }
            ],
            "default_raise": "TypeError: expected float or double buffer",
            "py_sig": "sleep_fill_no_gil(arr: buffer, value: float, us: int) -> void"
        }
    ],
    "module": "gilmod",
    "source": [
        "sleep_fill.c"
    ]
}
C2PY_END */

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

static void c2py_sleep_us(int us)
{
#ifdef _WIN32
    Sleep((us + 999) / 1000);
#else
    usleep(us);
#endif
}

void sleep_fill_f32(float *arr, intptr_t n, float value, int us)
{
    c2py_sleep_us(us);
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void sleep_fill_f64(double *arr, intptr_t n, double value, int us)
{
    c2py_sleep_us(us);
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}
