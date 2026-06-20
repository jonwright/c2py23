"""arraysum - meson build demo (c2py23 + c2py_loader).
"""
from __future__ import print_function

import os as _os

from c2py23.c2py_loader import load_native

_mod = load_native(_os.path.dirname(_os.path.abspath(__file__)), '_arraysum')

for _k, _v in _mod.__dict__.items():
    if _k.startswith('__') and _k.endswith('__'):
        continue
    globals()[_k] = _v
