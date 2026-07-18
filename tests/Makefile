# tests/Makefile -- build c2py23 dlsym test modules (POSIX make)
#
# Usage:
#   make -f tests/Makefile all             # build all test modules (Linux/macOS)
#   make -f tests/Makefile all EXT=.pyd     # build on Windows
#   make -f tests/Makefile clean
#
# Environment: CC CFLAGS LDFLAGS LIBS EXT

CC       ?= gcc
CFLAGS   ?= -O2 -Wall -fPIC
LDFLAGS  ?=
LIBS     ?= -ldl -lm
EXT      ?= .so

RUNTIME_SRC  := c2py23/runtime/c2py_runtime.c
RUNTIME_INC  := c2py23/runtime
RUNTIME_HDRS := c2py23/runtime/c2py_runtime.h \
                c2py23/runtime/c2py_dlsym.h \
                c2py23/runtime/c2py_pythonh.h

# ---- generated per-module rules ----
include tests/test_makefile_deps.mk

# ---- examples with non-standard source structures ----
examples/kissfft_wrap/kissfftmod$(EXT): examples/kissfft_wrap/kissfftmod_wrapper.c \
		examples/kissfft_wrap/kissfft_thin.c $(RUNTIME_SRC) \
		examples/kissfft/kiss_fft.c examples/kissfft/kiss_fftr.c
	$(CC) $(CFLAGS) -shared -I$(RUNTIME_INC) -Iexamples/kissfft_wrap -Iexamples/kissfft \
		examples/kissfft_wrap/kissfftmod_wrapper.c \
		examples/kissfft_wrap/kissfft_thin.c \
		examples/kissfft/kiss_fft.c \
		examples/kissfft/kiss_fftr.c \
		$(RUNTIME_SRC) \
		-o $@ $(LDFLAGS) $(LIBS) -lm

examples/kissfft_wrap/kissfftmod_wrapper.c: examples/kissfft_wrap/kissfft.c2py $(RUNTIME_HDRS)
	python3 -m c2py23 examples/kissfft_wrap/kissfft.c2py -o $@

examples/lz4_wrap/lz4mod$(EXT): examples/lz4_wrap/lz4mod_wrapper.c \
		examples/lz4_wrap/lz4_thin.c $(RUNTIME_SRC) \
		examples/lz4/lib/lz4.c
	$(CC) $(CFLAGS) -shared -I$(RUNTIME_INC) -Iexamples/lz4_wrap -Iexamples/lz4/lib \
		examples/lz4_wrap/lz4mod_wrapper.c \
		examples/lz4_wrap/lz4_thin.c \
		examples/lz4/lib/lz4.c \
		$(RUNTIME_SRC) \
		-o $@ $(LDFLAGS) $(LIBS)

examples/lz4_wrap/lz4mod_wrapper.c: examples/lz4_wrap/lz4.c2py $(RUNTIME_HDRS)
	python3 -m c2py23 examples/lz4_wrap/lz4.c2py -o $@

# ---- aggregate targets ----
MODULES := \
	tests/cases/fill/fillmod$(EXT) \
	tests/cases/arraysum/arraysum$(EXT) \
	tests/cases/scalar_output/statmod$(EXT) \
	tests/cases/constants/constmod$(EXT) \
	tests/cases/address/addressmod$(EXT) \
	tests/cases/transform/xfrm$(EXT) \
	tests/cases/gil_release/gilmod$(EXT) \
	tests/cases/types/typesmod$(EXT) \
	tests/cases/typedispatch/dispatchmod$(EXT) \
	tests/cases/optional/optmod$(EXT) \
	tests/cases/timing/timedmod$(EXT) \
	tests/cases/template/summod$(EXT) \
	tests/cases/docstring/docmod$(EXT) \
	tests/cases/dot/dotmod$(EXT) \
	tests/cases/array_sig/arraymod$(EXT) \
	tests/cases/freethreading/freethreadmod$(EXT) \
	tests/cases/simd_dispatch/simd_fillmod$(EXT) \
	examples/kissfft_wrap/kissfftmod$(EXT) \
	examples/lz4_wrap/lz4mod$(EXT)

.PHONY: all clean

all: $(MODULES)
	@echo "[make] dlsym build complete"

clean:
	rm -f $(MODULES)
	@echo "[make] cleaned"
