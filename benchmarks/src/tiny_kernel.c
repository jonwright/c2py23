#include <math.h>
#include <stddef.h>
#include "tiny_kernel.h"

void vnorm(const double vec[restrict][3], double mods[restrict], ptrdiff_t n)
{
    ptrdiff_t i;
    for (i = 0; i < n; i++) {
        mods[i] = sqrt(vec[i][0] * vec[i][0] +
                       vec[i][1] * vec[i][1] +
                       vec[i][2] * vec[i][2]);
    }
}

void noop(void)
{
    /* intentionally empty */
}

double get_item(const double arr[], int i)
{
    return arr[i];
}
