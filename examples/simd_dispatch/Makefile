# Makefile -- multi-flag SIMD compilation + c2py23 wrapping
#
# Compiles poly_kernel.c three times with different -m flags,
# producing ISA-specific object files.  c2py23 links them into
# the final .so and wraps them with CPU-feature dispatch.
#
# Usage:
#   make              build polysimd.so
#   make test         build and run test_polysimd.py
#   make clean        remove generated files

CC     ?= gcc
C2PY   ?= c2py23
CFLAGS := -O3 -Wall -Werror -fPIC -ffast-math

.PHONY: all test clean

all: polysimd.so

# --- Multi-flag compilation ---
# Each variant compiled from the SAME source with different -m flags
# and -DKERNEL_FN that renames the function.

poly_f32_avx512.o: poly_kernel.c
	$(CC) -c $(CFLAGS) -mavx512f -DKERNEL_FN=poly_f32_avx512 $< -o $@

poly_f32_avx2.o: poly_kernel.c
	$(CC) -c $(CFLAGS) -mavx2 -DKERNEL_FN=poly_f32_avx2 $< -o $@

poly_f32_scalar.o: poly_kernel.c
	$(CC) -c $(CFLAGS) -DKERNEL_FN=poly_f32_scalar $< -o $@

# --- c2py23 wrap ---
polysimd.so: polysimd.c2py poly_f32_avx512.o poly_f32_avx2.o poly_f32_scalar.o
	$(C2PY) build polysimd.c2py -o polysimd.so

test: polysimd.so
	python3 test_polysimd.py

clean:
	rm -f poly_f32_avx512.o poly_f32_avx2.o poly_f32_scalar.o
	rm -f polysimd_wrapper.c polysimd.so
