#include <stdint.h>
#include <unistd.h>

void sleep_fill_f32(float *arr, int n, float value, int us)
{
    usleep(us);
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}

void sleep_fill_f64(double *arr, int n, double value, int us)
{
    usleep(us);
    int i;
    for (i = 0; i < n; i++) arr[i] = value;
}
