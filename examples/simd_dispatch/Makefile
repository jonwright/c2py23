# Makefile -- SIMD dispatch + c2py_loader wheel convention
#
# Compiles poly_kernel.c three times with different -m flags,
# producing ISA-specific object files.  c2py23 links them into
# the final .so using the c2py_loader naming convention:
#
#   _polysimd.c2py23-linux_x86_64.so
#
# Usage:
#   make              build for host arch
#   make PLATFORM=linux_aarch64 CC=aarch64-linux-gnu-gcc
#   make test         build and run test_polysimd.py
#   make clean        remove generated files

CC     ?= gcc
C2PY   ?= c2py23
CFLAGS := -O3 -Wall -Werror -fPIC -ffast-math

# Platform tag: override for cross-compilation
PLATFORM ?= $(shell python3 -c "import sys,platform; p=sys.platform; m=platform.machine(); print('linux_x86_64' if 'linux' in p and m in ('x86_64','AMD64') else '%s_%s' % ('linux' if 'linux' in p else p, 'x86_64' if m=='AMD64' else m))" 2>/dev/null || echo linux_x86_64)

PKG_DIR  := polysimd
MODULE   := _polysimd
SO_NAME  := $(MODULE).c2py23-$(PLATFORM).so

.PHONY: all test clean

all: $(PKG_DIR)/$(SO_NAME)

# --- Multi-flag compilation ---
# Each variant compiled from the SAME source with different -m flags
# and -DKERNEL_FN that renames the function.

poly_f32_avx512.o: poly_kernel.c
	$(CC) -c $(CFLAGS) -mavx512f -DKERNEL_FN=poly_f32_avx512 $< -o $@

poly_f32_avx2.o: poly_kernel.c
	$(CC) -c $(CFLAGS) -mavx2 -DKERNEL_FN=poly_f32_avx2 $< -o $@

poly_f32_scalar.o: poly_kernel.c
	$(CC) -c $(CFLAGS) -DKERNEL_FN=poly_f32_scalar $< -o $@

# --- c2py23 wrap using loader naming convention ---
$(PKG_DIR)/$(SO_NAME): polysimd.c2py poly_f32_avx512.o poly_f32_avx2.o poly_f32_scalar.o
	mkdir -p $(PKG_DIR)
	$(C2PY) build polysimd.c2py -o $(PKG_DIR)/$(SO_NAME)

test: $(PKG_DIR)/$(SO_NAME)
	PYTHONPATH=. python3 test_polysimd.py

clean:
	rm -f poly_f32_avx512.o poly_f32_avx2.o poly_f32_scalar.o
	rm -f polysimd_wrapper.c $(PKG_DIR)/$(SO_NAME)
	rm -rf dist/ build/ *.egg-info
