CC       ?= gcc
CFLAGS   ?= -O3 -Wall -Werror
OMPFLAGS ?= -fopenmp
LIBS     ?= -ldl -lm

RUNTIME_SRC := ../../c2py23/runtime/c2py_runtime.c
RUNTIME_INC := ../../c2py23/runtime

.PHONY: all omp clean

mcpimod_wrapper.c: mc_pi.c2py $(wildcard $(RUNTIME_INC)/*.h)
	python3 -m c2py23 mc_pi.c2py -o $@

mcpimod.so: mcpimod_wrapper.c mc_pi.c $(RUNTIME_SRC)
	$(CC) $(CFLAGS) -shared -I$(RUNTIME_INC) -I. \
		$(filter %.c,$^) \
		-o $@ $(LDFLAGS) $(LIBS)

all: mcpimod.so

omp: CFLAGS += $(OMPFLAGS)
omp: mcpimod.so

clean:
	rm -f mcpimod.so mcpimod_wrapper.c
