"""c2py23 performance data decoder.

Reads c2py_perf_t structs exposed as raw pointers on modules built with
`timing: true` in their .c2py file.

Usage:
    from c2py23.perf import read_perf

    import my_timed_module
    stats = read_perf(my_timed_module._perf_myfunc)
    print(stats)
"""

import ctypes


class _c2py_perf_t(ctypes.Structure):
    _fields_ = [
        ("call_count", ctypes.c_uint64),
        ("t_enter",    ctypes.c_uint64),
        ("t_pre_c",    ctypes.c_uint64),
        ("t_post_c",   ctypes.c_uint64),
        ("t_exit",     ctypes.c_uint64),
        ("t_c_min",    ctypes.c_uint64),
        ("t_c_max",    ctypes.c_uint64),
        ("t_c_total",  ctypes.c_uint64),
        ("t_wrap_min", ctypes.c_uint64),
        ("t_wrap_max", ctypes.c_uint64),
        ("t_wrap_total", ctypes.c_uint64),
    ]


def read_perf(ptr_int):
    """Decode a c2py_perf_t from the raw pointer (as Python int).

    Returns a dict with:
        call_count, t_enter, t_pre_c, t_post_c, t_exit,
        c_dur_ns, wrap_dur_ns,
        c_min_ns, c_max_ns, c_mean_ns,
        wrap_min_ns, wrap_max_ns, wrap_mean_ns.

    All time values are in nanoseconds.
    """
    if ptr_int == 0:
        return {"call_count": 0}
    p = _c2py_perf_t.from_address(ptr_int)
    n = p.call_count
    return {
        "call_count": n,
        "t_enter":    p.t_enter,
        "t_pre_c":    p.t_pre_c,
        "t_post_c":   p.t_post_c,
        "t_exit":     p.t_exit,
        "c_dur_ns":   p.t_post_c - p.t_pre_c,
        "wrap_dur_ns": (p.t_pre_c - p.t_enter) + (p.t_exit - p.t_post_c)
                       if p.t_enter or p.t_exit else 0,
        "c_min_ns":   p.t_c_min,
        "c_max_ns":   p.t_c_max,
        "c_mean_ns":  p.t_c_total / n if n else 0,
        "wrap_min_ns":  p.t_wrap_min,
        "wrap_max_ns":  p.t_wrap_max,
        "wrap_mean_ns": p.t_wrap_total / n if n else 0,
    }


def read_enabled(enabled_ptr_int):
    """Read the _c2py_timing_enabled flag."""
    if enabled_ptr_int == 0:
        return 0
    return ctypes.c_int.from_address(enabled_ptr_int).value


def set_enabled(enabled_ptr_int, value):
    """Set the _c2py_timing_enabled flag (0 or 1)."""
    if enabled_ptr_int == 0:
        return
    ctypes.c_int.from_address(enabled_ptr_int).value = value
