#ifndef TINY_KERNEL_H
#define TINY_KERNEL_H

/* restrict qualified via pointer declarator: MSVC accepts restrict after
 * '*' but not in the '[]' array parameter notation used before. */
void vnorm(const double (*restrict vec)[3], double *restrict mods, ptrdiff_t n);

void noop(void);

double get_item(const double arr[], int i);

#endif
