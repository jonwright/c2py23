"""Print all loaded DLL names in the current process.
Runs on Windows only. Uses EnumProcessModules from psapi.dll.
"""
from __future__ import print_function
import sys
import ctypes
from ctypes import wintypes

print("=== DLL dump start ===", flush=True)
print("Python:", sys.executable, flush=True)

try:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
except Exception as e:
    print("ERROR loading DLLs:", e, flush=True)
    sys.exit(1)

# EnumProcessModules requires psapi.dll
psapi.EnumProcessModules.argtypes = [
    wintypes.HANDLE,
    wintypes.HMODULE * 1024,
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
modules = (wintypes.HMODULE * 1024)()
cbNeeded = wintypes.DWORD()

if psapi.EnumProcessModules(hProcess, modules,
                            ctypes.sizeof(modules),
                            ctypes.byref(cbNeeded)):
    count = cbNeeded.value // ctypes.sizeof(wintypes.HMODULE)
    print("Loaded modules: %d" % count, flush=True)
    for i in range(count):
        name = ctypes.create_unicode_buffer(260)
        if psapi.GetModuleBaseNameW(hProcess, modules[i], name, 260):
            print("  %s" % name.value, flush=True)
else:
    err = ctypes.get_last_error()
    print("EnumProcessModules failed, error=%d" % err, flush=True)

print("=== DLL dump end ===", flush=True)
