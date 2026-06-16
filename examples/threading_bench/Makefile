CC       = gcc
CFLAGS   = -O3 -Wall -Werror
OMPFLAGS = -fopenmp

.PHONY: all clean serial omp

all: serial

serial:
	c2py23 build mc_pi.c2py

omp:
	CFLAGS="$(OMPFLAGS)" c2py23 build mc_pi.c2py

clean:
	rm -f mcpimod.so mcpimod_wrapper.c
