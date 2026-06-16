# Makefile -- multi-flag SIMD compilation + c2py23 wrapping
#
# Compiles saxpy_kernel.c three times with different -m flags,
# producing ISA-specific object files.  c2py23 links them into
# the final .so and wraps them with CPU-feature dispatch.
#
# Usage:
#   make              build saxpy.so
#   make test         build and run test_saxpy.py
#   make clean        remove generated files
#
# Override CC/C2PY if needed:
#   CC=gcc-14 C2PY=c2py23 make

CC     ?= gcc
C2PY   ?= c2py23
CFLAGS := -O3 -Wall -Werror -fPIC

.PHONY: all test clean

all: saxpy.so

# --- Multi-flag compilation ---
# Each variant is compiled from the SAME source with different
# -m flags and a -DKERNEL_FN that renames the function.

saxpy_f32_avx512.o: saxpy_kernel.c
	$(CC) -c $(CFLAGS) -mavx512f -DKERNEL_FN=saxpy_f32_avx512 $< -o $@

saxpy_f32_avx2.o: saxpy_kernel.c
	$(CC) -c $(CFLAGS) -mavx2 -DKERNEL_FN=saxpy_f32_avx2 $< -o $@

saxpy_f32_scalar.o: saxpy_kernel.c
	$(CC) -c $(CFLAGS) -DKERNEL_FN=saxpy_f32_scalar $< -o $@

# --- c2py23 wrap ---
# The .c2py 'source:' lists the .o files; the generator does the rest.

saxpy.so: saxpy.c2py saxpy_f32_avx512.o saxpy_f32_avx2.o saxpy_f32_scalar.o
	$(C2PY) build saxpy.c2py -o saxpy.so

test: saxpy.so
	python3 test_saxpy.py

clean:
	rm -f saxpy_f32_avx512.o saxpy_f32_avx2.o saxpy_f32_scalar.o
	rm -f saxpy_wrapper.c saxpy.so
