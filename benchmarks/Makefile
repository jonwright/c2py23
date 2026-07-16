# benchmarks/Makefile -- build gold-standard wrappers and c2py23 wrappers
# All benchmarks are single-threaded; use taskset -c 0 to pin to one core.

PYTHON ?= python3
PYTHON_CONFIG ?= $(PYTHON)-config
CC ?= gcc
CFLAGS ?= -O2 -fPIC -Wall -Werror
CPY_CFLAGS = $(CFLAGS) $(shell $(PYTHON_CONFIG) --includes)
CPY_LDFLAGS = $(shell $(PYTHON_CONFIG) --ldflags) -shared

NUMPY_INCLUDES := $(shell $(PYTHON) -c "import numpy; print(numpy.get_include())" 2>/dev/null)

C2PY = $(PYTHON) -m c2py23.cli

SRCDIR = src
BUILDDIR = build
BUILDDIR_PH = build_ph

all: gold_noargs gold_vnorm gold_numpy_vnorm gold_getitem c2py_noargs c2py_vnorm c2py_vnorm_bare c2py_getitem \
    c2py_vnorm_ndarray c2py_vnorm_buffer c2py_vnorm_dlpack

$(BUILDDIR):
	mkdir -p $(BUILDDIR)

# ---- Gold standard: handwritten CPython extensions ----

$(BUILDDIR)/gold_noargs.so: $(SRCDIR)/gold_noargs.c | $(BUILDDIR)
	$(CC) $(CPY_CFLAGS) $(CPY_LDFLAGS) -o $@ $<

$(BUILDDIR)/gold_vnorm.so: $(SRCDIR)/gold_vnorm.c | $(BUILDDIR)
	$(CC) $(CPY_CFLAGS) $(CPY_LDFLAGS) -o $@ $< -lm

$(BUILDDIR)/gold_numpy_vnorm.so: $(SRCDIR)/gold_numpy_vnorm.c | $(BUILDDIR)
	$(CC) $(CPY_CFLAGS) -I$(NUMPY_INCLUDES) $(CPY_LDFLAGS) -o $@ $< -lm

$(BUILDDIR)/gold_getitem.so: $(SRCDIR)/gold_getitem.c | $(BUILDDIR)
	$(CC) $(CPY_CFLAGS) $(CPY_LDFLAGS) -o $@ $< -lm

gold_noargs: $(BUILDDIR)/gold_noargs.so
gold_vnorm:  $(BUILDDIR)/gold_vnorm.so
gold_numpy_vnorm: $(BUILDDIR)/gold_numpy_vnorm.so
gold_getitem: $(BUILDDIR)/gold_getitem.so

# ---- c2py23 wrappers ----

$(BUILDDIR)/c2py_noargs.so: $(SRCDIR)/c2py_noargs.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR)
	$(C2PY) build $(SRCDIR)/c2py_noargs.c2py
	mv $(SRCDIR)/c2py_noargs.so $(BUILDDIR)/
	rm -f $(SRCDIR)/c2py_noargs_wrapper.c

$(BUILDDIR)/c2py_vnorm.so: $(SRCDIR)/c2py_vnorm.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR)
	$(C2PY) build $(SRCDIR)/c2py_vnorm.c2py
	mv $(SRCDIR)/c2py_vnorm.so $(BUILDDIR)/
	rm -f $(SRCDIR)/c2py_vnorm_wrapper.c

$(BUILDDIR)/c2py_vnorm_bare.so: $(SRCDIR)/c2py_vnorm_bare.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR)
	$(C2PY) build $(SRCDIR)/c2py_vnorm_bare.c2py
	mv $(SRCDIR)/c2py_vnorm_bare.so $(BUILDDIR)/
	rm -f $(SRCDIR)/c2py_vnorm_bare_wrapper.c

$(BUILDDIR)/c2py_getitem.so: $(SRCDIR)/c2py_getitem.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR)
	$(C2PY) build $(SRCDIR)/c2py_getitem.c2py
	mv $(SRCDIR)/c2py_getitem.so $(BUILDDIR)/
	rm -f $(SRCDIR)/c2py_getitem_wrapper.c

$(BUILDDIR)/c2py_vnorm_ndarray.so: $(SRCDIR)/c2py_vnorm_ndarray.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR)
	$(C2PY) build $(SRCDIR)/c2py_vnorm_ndarray.c2py
	mv $(SRCDIR)/c2py_vnorm_ndarray.so $(BUILDDIR)/
	rm -f $(SRCDIR)/c2py_vnorm_ndarray_wrapper.c

$(BUILDDIR)/c2py_vnorm_buffer.so: $(SRCDIR)/c2py_vnorm_buffer.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR)
	$(C2PY) build $(SRCDIR)/c2py_vnorm_buffer.c2py
	mv $(SRCDIR)/c2py_vnorm_buffer.so $(BUILDDIR)/
	rm -f $(SRCDIR)/c2py_vnorm_buffer_wrapper.c

$(BUILDDIR)/c2py_vnorm_dlpack.so: $(SRCDIR)/c2py_vnorm_dlpack.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR)
	$(C2PY) build $(SRCDIR)/c2py_vnorm_dlpack.c2py
	mv $(SRCDIR)/c2py_vnorm_dlpack.so $(BUILDDIR)/
	rm -f $(SRCDIR)/c2py_vnorm_dlpack_wrapper.c

c2py_noargs: $(BUILDDIR)/c2py_noargs.so
c2py_vnorm:  $(BUILDDIR)/c2py_vnorm.so
c2py_vnorm_bare: $(BUILDDIR)/c2py_vnorm_bare.so
c2py_getitem: $(BUILDDIR)/c2py_getitem.so
c2py_vnorm_ndarray: $(BUILDDIR)/c2py_vnorm_ndarray.so
c2py_vnorm_buffer: $(BUILDDIR)/c2py_vnorm_buffer.so
c2py_vnorm_dlpack: $(BUILDDIR)/c2py_vnorm_dlpack.so

# ---- c2py23 pythonh wrappers (direct #include Python.h, no dlsym) ----

$(BUILDDIR_PH):
	mkdir -p $(BUILDDIR_PH)

$(BUILDDIR_PH)/c2py_noargs.so: $(SRCDIR)/c2py_noargs.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR_PH)
	$(C2PY) build --pythonh $(SRCDIR)/c2py_noargs.c2py
	mv $(SRCDIR)/c2py_noargs.*.so $(BUILDDIR_PH)/c2py_noargs.so
	rm -f $(SRCDIR)/c2py_noargs_wrapper.c

$(BUILDDIR_PH)/c2py_vnorm.so: $(SRCDIR)/c2py_vnorm.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR_PH)
	$(C2PY) build --pythonh $(SRCDIR)/c2py_vnorm.c2py
	mv $(SRCDIR)/c2py_vnorm.*.so $(BUILDDIR_PH)/c2py_vnorm.so
	rm -f $(SRCDIR)/c2py_vnorm_wrapper.c

$(BUILDDIR_PH)/c2py_vnorm_bare.so: $(SRCDIR)/c2py_vnorm_bare.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR_PH)
	$(C2PY) build --pythonh $(SRCDIR)/c2py_vnorm_bare.c2py
	mv $(SRCDIR)/c2py_vnorm_bare.*.so $(BUILDDIR_PH)/c2py_vnorm_bare.so
	rm -f $(SRCDIR)/c2py_vnorm_bare_wrapper.c

$(BUILDDIR_PH)/c2py_getitem.so: $(SRCDIR)/c2py_getitem.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR_PH)
	$(C2PY) build --pythonh $(SRCDIR)/c2py_getitem.c2py
	mv $(SRCDIR)/c2py_getitem.*.so $(BUILDDIR_PH)/c2py_getitem.so
	rm -f $(SRCDIR)/c2py_getitem_wrapper.c

$(BUILDDIR_PH)/c2py_vnorm_ndarray.so: $(SRCDIR)/c2py_vnorm_ndarray.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR_PH)
	$(C2PY) build --pythonh $(SRCDIR)/c2py_vnorm_ndarray.c2py
	mv $(SRCDIR)/c2py_vnorm_ndarray.*.so $(BUILDDIR_PH)/c2py_vnorm_ndarray.so
	rm -f $(SRCDIR)/c2py_vnorm_ndarray_wrapper.c

$(BUILDDIR_PH)/c2py_vnorm_buffer.so: $(SRCDIR)/c2py_vnorm_buffer.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR_PH)
	$(C2PY) build --pythonh $(SRCDIR)/c2py_vnorm_buffer.c2py
	mv $(SRCDIR)/c2py_vnorm_buffer.*.so $(BUILDDIR_PH)/c2py_vnorm_buffer.so
	rm -f $(SRCDIR)/c2py_vnorm_buffer_wrapper.c

$(BUILDDIR_PH)/c2py_vnorm_dlpack.so: $(SRCDIR)/c2py_vnorm_dlpack.c2py $(SRCDIR)/tiny_kernel.c $(SRCDIR)/tiny_kernel.h | $(BUILDDIR_PH)
	$(C2PY) build --pythonh $(SRCDIR)/c2py_vnorm_dlpack.c2py
	mv $(SRCDIR)/c2py_vnorm_dlpack.*.so $(BUILDDIR_PH)/c2py_vnorm_dlpack.so
	rm -f $(SRCDIR)/c2py_vnorm_dlpack_wrapper.c

c2py_noargs_ph: $(BUILDDIR_PH)/c2py_noargs.so
c2py_vnorm_ph:  $(BUILDDIR_PH)/c2py_vnorm.so
c2py_vnorm_bare_ph: $(BUILDDIR_PH)/c2py_vnorm_bare.so
c2py_getitem_ph: $(BUILDDIR_PH)/c2py_getitem.so
c2py_vnorm_ndarray_ph: $(BUILDDIR_PH)/c2py_vnorm_ndarray.so
c2py_vnorm_buffer_ph: $(BUILDDIR_PH)/c2py_vnorm_buffer.so
c2py_vnorm_dlpack_ph: $(BUILDDIR_PH)/c2py_vnorm_dlpack.so

# ---- Clean ----

clean:
	rm -rf $(BUILDDIR) $(BUILDDIR_PH)
	rm -f $(SRCDIR)/c2py_noargs*.so $(SRCDIR)/c2py_noargs_wrapper.c
	rm -f $(SRCDIR)/c2py_vnorm*.so $(SRCDIR)/c2py_vnorm_wrapper.c
	rm -f $(SRCDIR)/c2py_vnorm_bare*.so $(SRCDIR)/c2py_vnorm_bare_wrapper.c
	rm -f $(SRCDIR)/c2py_vnorm_ndarray*.so $(SRCDIR)/c2py_vnorm_ndarray_wrapper.c
	rm -f $(SRCDIR)/c2py_vnorm_buffer*.so $(SRCDIR)/c2py_vnorm_buffer_wrapper.c
	rm -f $(SRCDIR)/c2py_vnorm_dlpack*.so $(SRCDIR)/c2py_vnorm_dlpack_wrapper.c
	rm -f $(SRCDIR)/c2py_getitem*.so $(SRCDIR)/c2py_getitem_wrapper.c

# ---- Run benchmarks (single-threaded via taskset) ----

bench: all c2py_noargs_ph c2py_vnorm_ph c2py_vnorm_bare_ph c2py_getitem_ph \
    c2py_vnorm_ndarray_ph c2py_vnorm_buffer_ph c2py_vnorm_dlpack_ph
	taskset -c 0 $(PYTHON) -m pytest test_noargs_overhead.py test_vnorm_overhead.py test_getitem_overhead.py -v -s

bench-getitem: gold_getitem c2py_getitem
	taskset -c 0 $(PYTHON) -m pytest test_getitem_overhead.py -v -s

bench-noargs: gold_noargs c2py_noargs
	taskset -c 0 $(PYTHON) -m pytest test_noargs_overhead.py -v -s

bench-vnorm: gold_vnorm gold_numpy_vnorm c2py_vnorm c2py_vnorm_bare
	taskset -c 0 $(PYTHON) -m pytest test_vnorm_overhead.py -v -s

# ---- Gather results for mkdocs ----

results:
	@echo "<!-- Auto-generated by 'make results' -->" > $(SRCDIR)/benchmark_results.md
	@echo "" >> $(SRCDIR)/benchmark_results.md
	@echo "# Benchmark Results" >> $(SRCDIR)/benchmark_results.md
	@echo "" >> $(SRCDIR)/benchmark_results.md
	@echo '```' >> $(SRCDIR)/benchmark_results.md
	@$(MAKE) bench 2>&1 | tee -a $(SRCDIR)/benchmark_results.md
	@echo '```' >> $(SRCDIR)/benchmark_results.md

.PHONY: all clean bench bench-noargs bench-vnorm results \
        gold_noargs gold_vnorm gold_numpy_vnorm \
        c2py_noargs c2py_vnorm c2py_vnorm_bare \
        c2py_vnorm_ndarray c2py_vnorm_buffer c2py_vnorm_dlpack
