#ifndef TINY_KERNEL_H
#define TINY_KERNEL_H

void vnorm(const double vec[restrict][3], double mods[restrict], ptrdiff_t n);

void noop(void);

double get_item(const double arr[], int i);

#endif
