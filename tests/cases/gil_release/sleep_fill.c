#include <stdint.h>
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
