"""Build and run the Windows C ABI checker (check_abi_win.c).
Prints Python version, struct sizes, offsets, and symbol availability.
"""
from __future__ import print_function

import sys
import os
import subprocess
import sysconfig

HERE = os.path.dirname(os.path.abspath(__file__))
C_SRC = os.path.join(HERE, 'check_abi_win.c')
EXE = os.path.join(HERE, 'check_abi_win.exe')

inc = sysconfig.get_path('include')
lib = sysconfig.get_config_var('LIBDIR') or ''
v = sysconfig.get_config_var('VERSION') or ''
v_short = sysconfig.get_config_var('py_version_short') or ''
vv = v_short or v

print("include: {}".format(inc))
print("lib:     {}".format(lib))
print("version: {}".format(vv))

if not os.path.isfile(C_SRC):
    print("C ABI source missing: {}".format(C_SRC))
    sys.exit(0)

# Try python3.lib, then python313.lib, etc.
python_lib = None
for name in ['python3.lib']:
    if lib:
        candidate = os.path.join(lib, name)
        if os.path.isfile(candidate):
            python_lib = candidate
            break

if not python_lib:
    print("python3.lib not found in {}".format(lib))
    print("(C ABI checker skipped)")
    sys.exit(0)

print("linking: {}".format(python_lib))

cmd = [
    'cl', '/nologo', '/I' + inc,
    C_SRC,
    '/link', '/LIBPATH:' + lib, python_lib,
    '/out:' + EXE
]
print(' '.join(cmd))
ret = subprocess.call(cmd)
if ret != 0:
    print("C ABI checker compilation failed")
    sys.exit(1)

# Run it
ret = subprocess.call([EXE])
sys.exit(ret)
