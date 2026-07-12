"""Print names of all loaded DLLs containing 'python' in the name.
Used to diagnose which CPython DLLs are available for c2py_runtime
on free-threaded Windows builds.
"""
from __future__ import print_function

import ctypes
import ctypes.wintypes

kernel32 = ctypes.windll.kernel32
psapi = ctypes.WinDLL('psapi.dll')

hProcess = kernel32.GetCurrentProcess()
modules = (ctypes.wintypes.HMODULE * 1024)()
cbNeeded = ctypes.wintypes.DWORD()

if psapi.EnumProcessModules(hProcess, modules,
                            ctypes.sizeof(modules),
                            ctypes.byref(cbNeeded)):
    count = cbNeeded.value // ctypes.sizeof(ctypes.wintypes.HMODULE)
    print("Loaded modules (%d):" % count)
    for i in range(count):
        name = ctypes.create_unicode_buffer(260)
        psapi.GetModuleBaseNameW(hProcess, modules[i], name, 260)
        name_lower = name.value.lower()
        if 'python' in name_lower or 'vcruntime' in name_lower:
            print("  %s" % name.value)
