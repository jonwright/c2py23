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
	tests/cases/simd_dispatch/simd_fillmod$(EXT)

.PHONY: all clean

all: $(MODULES)
	@echo "[make] dlsym build complete"

clean:
	rm -f $(MODULES)
	@echo "[make] cleaned"
