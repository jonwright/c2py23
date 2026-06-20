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
if not lib:
    prefix = sysconfig.get_config_var('prefix') or ''
    if prefix:
        lib = os.path.join(prefix, 'libs')
    else:
        lib = os.path.join(os.path.dirname(inc), 'libs')

print("include: {}".format(inc))
print("lib:     {}".format(lib))

if not os.path.isfile(C_SRC):
    print("C ABI source missing: {}".format(C_SRC))
    sys.exit(0)

python_lib = None
for name in ['python3.lib', 'python313.lib', 'python312.lib', 'python311.lib',
             'python310.lib', 'python39.lib', 'python38.lib',
             'python27.lib']:
    candidate = os.path.join(lib, name)
    if os.path.isfile(candidate):
        python_lib = candidate
        break

if not python_lib:
    print("No python .lib found in {}".format(lib))
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
    print("C ABI checker compilation failed -- skipping")
    sys.exit(0)  # not a fatal error for the CI job

proc = subprocess.Popen([EXE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()
stdout = stdout.decode('ascii', errors='replace')
stderr = stderr.decode('ascii', errors='replace')
print(stdout)
if stderr:
    print("STDERR:", stderr, file=sys.stderr)
sys.exit(proc.returncode)
