"""CPU feature flags: agree with /proc/cpuinfo and respect implications.

Uses the simd_fillmod test module, which exports the c2py_amd64_* globals.
Linux x86_64 only; skipped elsewhere.
"""

from __future__ import print_function

import ctypes
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# c2py name -> /proc/cpuinfo name where they differ
CPUINFO = {
    "avx512vnni": "avx512_vnni",
    "avx512bitalg": "avx512_bitalg",
    "avx512vpopcntdq": "avx512_vpopcntdq",
    "avx512vbmi2": "avx512_vbmi2",
    "lzcnt": "abm",
    "sse3": "pni",
}
FLAGS = (
    "sse2 sse3 ssse3 sse4_1 sse4_2 avx avx2 fma f16c avx_vnni "
    "avx512f avx512cd avx512dq avx512bw avx512vl avx512ifma avx512vbmi "
    "avx512vbmi2 avx512vnni avx512bitalg avx512vpopcntdq aes pclmulqdq "
    "sha_ni gfni vaes vpclmulqdq adx movbe bmi1 bmi2 popcnt lzcnt"
).split()
# feature -> features it builds on
IMPLIES = {
    "avx2": "avx", "fma": "avx", "f16c": "avx", "avx_vnni": "avx",
    "vaes": "avx", "vpclmulqdq": "avx", "avx512f": "avx2",
    "avx512cd": "avx512f", "avx512dq": "avx512f", "avx512bw": "avx512f",
    "avx512vl": "avx512f", "avx512ifma": "avx512f", "avx512vnni": "avx512f",
    "avx512vpopcntdq": "avx512f", "avx512vbmi": "avx512bw",
    "avx512vbmi2": "avx512bw", "avx512bitalg": "avx512bw",
}


def _cpuinfo_flags():
    with open("/proc/cpuinfo") as f:
        for line in f:
            if line.startswith("flags"):
                return set(line.split(":", 1)[1].split())
    return None


def _read_flags():
    sys.path.insert(0, os.path.join(HERE, "cases", "simd_dispatch"))
    import simd_fillmod

    lib = ctypes.CDLL(simd_fillmod.__file__)
    return dict((n, ctypes.c_int.in_dll(lib, "c2py_amd64_" + n).value) for n in FLAGS)


def test_cpu_features():
    if platform.machine() not in ("x86_64", "AMD64") or not sys.platform.startswith("linux"):
        print("SKIP: cpu_features (needs Linux x86_64)")
        return
    cpu = _cpuinfo_flags()
    if cpu is None:
        print("SKIP: cpu_features (no /proc/cpuinfo flags)")
        return
    got = _read_flags()
    for name in FLAGS:
        expect = int(CPUINFO.get(name, name) in cpu)
        assert got[name] == expect, "%s: c2py=%d cpuinfo=%d" % (name, got[name], expect)
    for name, base in IMPLIES.items():
        assert not got[name] or got[base], "%s set without %s" % (name, base)
    print("PASS: cpu_features")


if __name__ == "__main__":
    test_cpu_features()
