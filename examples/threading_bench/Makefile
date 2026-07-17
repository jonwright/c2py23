CC       = gcc
CFLAGS   = -O3 -Wall -Werror
OMPFLAGS = -fopenmp

.PHONY: all clean

all:
	c2py23 mc_pi.c2py -o mcpimod_wrapper.c
	CC=$(CC) LIBS="-ldl -lm" python -c "
from setuptools import setup, Extension
from c2py23.build import DlsymCmdclass
setup(name='mcpimod',
    ext_modules=[Extension('mcpimod',
        ['mcpimod_wrapper.c', 'mc_pi.c',
         'c2py23/runtime/c2py_runtime.c'],
        include_dirs=['.', 'c2py23/runtime'])],
    cmdclass=DlsymCmdclass,
    script_args=['build_ext'])
"

omp:
	c2py23 mc_pi.c2py -o mcpimod_wrapper.c
	CC=$(CC) CFLAGS="$(CFLAGS) $(OMPFLAGS)" LIBS="-ldl -lm" python -c "
from setuptools import setup, Extension
from c2py23.build import DlsymCmdclass
setup(name='mcpimod',
    ext_modules=[Extension('mcpimod',
        ['mcpimod_wrapper.c', 'mc_pi.c',
         'c2py23/runtime/c2py_runtime.c'],
        include_dirs=['.', 'c2py23/runtime'])],
    cmdclass=DlsymCmdclass,
    script_args=['build_ext'])
"

clean:
	rm -f mcpimod.so mcpimod_wrapper.c
