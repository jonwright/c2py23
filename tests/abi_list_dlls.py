"""List loaded shared libraries / DLLs in the current Python process.

Works on Linux (via /proc/self/maps) and Windows (via EnumProcessModules).
Used by CI ABI diagnostic to confirm which CPython runtime is active.
"""

from __future__ import print_function

import os
import sys


def _linux_list_libs():
    """Parse /proc/self/maps to find loaded .so files. Deduplicate."""
    seen = set()
    if not os.path.exists("/proc/self/maps"):
        return ["ERROR: /proc/self/maps not found"]

    libs = []
    with open("/proc/self/maps", "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 6:
                path = parts[5]
                if (".so" in path or "libpython" in path.lower()) and path not in seen:
                    seen.add(path)
                    libs.append(path)
    # Also try ldd on the python binary
    import subprocess

    try:
        out = subprocess.check_output(["ldd", sys.executable], stderr=subprocess.STDOUT).decode(
            "utf-8", errors="replace"
        )
        for line in out.split("\n"):
            lib = line.strip().split()[0] if line.strip() else ""
            if lib and ("python" in lib.lower() or ".so" in lib) and lib not in seen:
                seen.add(lib)
                libs.append(lib)
    except Exception:
        pass
    return sorted(libs)


def _windows_list_dlls():
    """Use EnumProcessModules from psapi.dll to list loaded DLLs."""
    import ctypes
    from ctypes import wintypes

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
    except Exception as e:
        return ["ERROR loading psapi: %s" % e]

    psapi.EnumProcessModules.argtypes = [
        wintypes.HANDLE,
        wintypes.HMODULE * 4096,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    psapi.EnumProcessModules.restype = wintypes.BOOL

    psapi.GetModuleBaseNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.HMODULE,
        ctypes.c_wchar_p,
        wintypes.DWORD,
    ]
    psapi.GetModuleBaseNameW.restype = wintypes.DWORD

    hProcess = kernel32.GetCurrentProcess()
    modules = (wintypes.HMODULE * 4096)()
    cbNeeded = wintypes.DWORD()

    if not psapi.EnumProcessModules(hProcess, modules, ctypes.sizeof(modules), ctypes.byref(cbNeeded)):
        return ["ERROR: EnumProcessModules failed, err=%d" % ctypes.get_last_error()]

    count = cbNeeded.value // ctypes.sizeof(wintypes.HMODULE)
    names = []
    for i in range(count):
        name = ctypes.create_unicode_buffer(260)
        if psapi.GetModuleBaseNameW(hProcess, modules[i], name, 260):
            names.append(name.value)
    return sorted(names)


def main():
    print("=== loaded libraries ===")
    print("Python: %s" % sys.executable)
    print("platform: %s" % sys.platform)

    if sys.platform == "win32":
        libs = _windows_list_dlls()
    else:
        libs = _linux_list_libs()

    print("count: %d" % len(libs))
    for lib in libs:
        print("  %s" % lib)


if __name__ == "__main__":
    main()
