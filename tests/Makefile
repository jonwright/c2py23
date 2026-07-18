# tests/Makefile -- build c2py23 dlsym test modules (GNU make)
#
# Usage:
#   make -f tests/Makefile all             # build all test modules (Linux/macOS)
#   make -f tests/Makefile all EXT=.pyd     # build on Windows
#   make -f tests/Makefile clean
#
# Environment: CC CFLAGS LDFLAGS LIBS EXT MSVC

CC       ?= gcc
CFLAGS   ?= -O2 -Wall
LDFLAGS  ?=

# Single-header mode: USE_SINGLE_HEADER=1 uses c2py.h (stb-style blob)
# instead of c2py_runtime.c.  Wrappers are generated with --emit-header.
# No -I flag or runtime .c to compile.
ifdef USE_SINGLE_HEADER
RUNTIME_SRC  :=
RUNTIME_INC  :=
RUNTIME_HDRS := c2py23/runtime/c2py.h
C2PY_FLAGS   := --emit-header
else
RUNTIME_SRC  := c2py23/runtime/c2py_runtime.c
RUNTIME_INC  := c2py23/runtime
RUNTIME_HDRS := c2py23/runtime/c2py_runtime.h \
                c2py23/runtime/c2py_dlsym.h \
                c2py23/runtime/c2py_pythonh.h
endif

# Auto-detect MSVC from CC or env var
ifneq ($(or $(MSVC),$(findstring cl,$(CC))),)
  EXT      ?= .pyd
  LIBS     ?=
else
  EXT      ?= .so
  LIBS     ?= -ldl -lm
endif

# ---- generated per-module rules ----
include tests/test_makefile_deps.mk

# ---- examples with non-standard source structures ----
examples/kissfft_wrap/kissfftmod_wrapper.c: examples/kissfft_wrap/kissfft.c2py $(RUNTIME_HDRS)
	python3 -m c2py23 examples/kissfft_wrap/kissfft.c2py -o $@

examples/lz4_wrap/lz4mod_wrapper.c: examples/lz4_wrap/lz4.c2py $(RUNTIME_HDRS)
	python3 -m c2py23 examples/lz4_wrap/lz4.c2py -o $@

KISSFFT_SRC := examples/kissfft_wrap/kissfftmod_wrapper.c \
              examples/kissfft_wrap/kissfft_thin.c \
              examples/kissfft/kiss_fft.c \
              examples/kissfft/kiss_fftr.c \
              $(RUNTIME_SRC)

LZ4_SRC := examples/lz4_wrap/lz4mod_wrapper.c \
          examples/lz4_wrap/lz4_thin.c \
          examples/lz4/lib/lz4.c \
          $(RUNTIME_SRC)

ifndef MSVC
examples/kissfft_wrap/kissfftmod$(EXT): $(KISSFFT_SRC)
	$(CC) $(CFLAGS) -fPIC -shared -I$(RUNTIME_INC) -Iexamples/kissfft_wrap -Iexamples/kissfft \
		$(KISSFFT_SRC) -o $@ $(LDFLAGS) $(LIBS) -lm

examples/lz4_wrap/lz4mod$(EXT): $(LZ4_SRC)
	$(CC) $(CFLAGS) -fPIC -shared -I$(RUNTIME_INC) -Iexamples/lz4_wrap -Iexamples/lz4/lib \
		$(LZ4_SRC) -o $@ $(LDFLAGS) $(LIBS)
endif

ifdef MSVC
examples/kissfft_wrap/kissfftmod$(EXT): $(KISSFFT_SRC)
	$(CC) $(CFLAGS) /LD /I$(RUNTIME_INC) /Iexamples/kissfft_wrap /Iexamples/kissfft \
		$(KISSFFT_SRC) /link /OUT:$@ $(LDFLAGS)

examples/lz4_wrap/lz4mod$(EXT): $(LZ4_SRC)
	$(CC) $(CFLAGS) /LD /I$(RUNTIME_INC) /Iexamples/lz4_wrap /Iexamples/lz4/lib \
		$(LZ4_SRC) /link /OUT:$@ $(LDFLAGS)
endif

# ---- benchmark modules (share tiny_kernel.c, output to benchmarks/build/) ----
# Only built on Unix (pattern rules; skipped on MSVC for simplicity)
BENCH_SRC := benchmarks/src/tiny_kernel.c
BENCH_DIR := benchmarks/build
BENCH_MODS := c2py_vnorm c2py_vnorm_bare c2py_vnorm_ndarray \
              c2py_vnorm_buffer c2py_vnorm_dlpack c2py_getitem c2py_noargs

$(BENCH_DIR):
	mkdir -p $(BENCH_DIR)

benchmarks/src/%_wrapper.c: benchmarks/src/%.c2py $(RUNTIME_HDRS)
	python3 -m c2py23 $< -o $@

ifndef MSVC
$(BENCH_DIR)/%$(EXT): benchmarks/src/%_wrapper.c $(BENCH_SRC) $(RUNTIME_SRC) | $(BENCH_DIR)
	$(CC) $(CFLAGS) -fPIC -shared -I$(RUNTIME_INC) -Ibenchmarks/src \
		$^ -o $@ $(LDFLAGS) $(LIBS) -lm

BENCH_TARGETS := $(addprefix $(BENCH_DIR)/,$(addsuffix $(EXT),$(BENCH_MODS)))
else
BENCH_TARGETS :=
endif

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
	examples/lz4_wrap/lz4mod$(EXT) \
	$(BENCH_TARGETS)

.PHONY: all clean

all: $(MODULES)
	@echo "[make] dlsym build complete"

clean:
	rm -f $(MODULES)
	@echo "[make] cleaned"
