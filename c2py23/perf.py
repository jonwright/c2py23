"""c2py23 performance data decoder.

Reads c2py_perf_t structs exposed as raw pointers on modules built with
`timing: true` in their .c2py file.

Usage:
    from c2py23.perf import read_perf

    import my_timed_module
    stats = read_perf(my_timed_module._perf_myfunc)
    print(stats)

    # With C2PY_USE_CYCLE_COUNTER, provide the frequency for correct ns:
    stats = read_perf(my_timed_module._perf_myfunc,
                      freq_hz=my_timed_module._c2py_tick_frequency())
"""
from __future__ import print_function

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
        ("variant",    ctypes.c_int),
        ("group_idx",  ctypes.c_int),
        ("variant_name", ctypes.c_void_p),
    ]


def _to_ns(ticks, freq_hz):
    """Convert tick count to nanoseconds, guarding against freq_hz == 0."""
    if freq_hz == 0 or freq_hz is None:
        return ticks
    return ticks * 1000000000 // freq_hz


def read_perf(ptr_int, freq_hz=None):
    """Decode a c2py_perf_t from the raw pointer (as Python int).

    Parameters
    ----------
    ptr_int : int
        Raw pointer to the c2py_perf_t struct (e.g. module._perf_myfunc).
    freq_hz : int or None, optional
        Tick source frequency in Hz.  When None or 0, the raw tick values
        are returned under the _ns keys (correct for the default
        clock_gettime source which returns nanoseconds).  When provided
        and != 1e9, the values are converted and the raw tick values are
        additionally returned under _cycles keys.

    Returns
    -------
    dict with keys:
        call_count, t_enter, t_pre_c, t_post_c, t_exit,
        c_dur_ns, wrap_dur_ns,
        c_min_ns, c_max_ns, c_mean_ns,
        wrap_min_ns, wrap_max_ns, wrap_mean_ns.
      Additional keys when freq_hz is provided and != 1e9:
        c_dur_cycles, wrap_dur_cycles,
        c_min_cycles, c_max_cycles, c_mean_cycles,
        wrap_min_cycles, wrap_max_cycles, wrap_mean_cycles.
    """
    if ptr_int == 0:
        return {"call_count": 0}
    p = _c2py_perf_t.from_address(ptr_int)
    n = p.call_count
    vname = ""
    if p.variant_name:
        try:
            vname = ctypes.c_char_p(p.variant_name).value
            if vname is None:
                vname = ""
            elif isinstance(vname, bytes):
                vname = vname.decode('ascii', errors='replace')
        except Exception:
            vname = ""

    c_dur = p.t_post_c - p.t_pre_c
    wrap_dur = (p.t_pre_c - p.t_enter) + (p.t_exit - p.t_post_c) \
               if p.t_enter or p.t_exit else 0

    result = {
        "call_count": n,
        "t_enter":    p.t_enter,
        "t_pre_c":    p.t_pre_c,
        "t_post_c":   p.t_post_c,
        "t_exit":     p.t_exit,
        "c_dur_ns":   _to_ns(c_dur, freq_hz),
        "wrap_dur_ns": _to_ns(wrap_dur, freq_hz),
        "c_min_ns":   _to_ns(p.t_c_min, freq_hz),
        "c_max_ns":   _to_ns(p.t_c_max, freq_hz),
        "c_mean_ns":  _to_ns(p.t_c_total / float(n), freq_hz) if n else 0,
        "wrap_min_ns":  _to_ns(p.t_wrap_min, freq_hz),
        "wrap_max_ns":  _to_ns(p.t_wrap_max, freq_hz),
        "wrap_mean_ns": _to_ns(p.t_wrap_total / float(n), freq_hz) if n else 0,
        "variant":    p.variant,
        "group_idx":  p.group_idx,
        "variant_name": vname,
    }

    if freq_hz is not None and freq_hz != 0 and freq_hz != 1000000000:
        result["c_dur_cycles"]   = c_dur
        result["wrap_dur_cycles"] = wrap_dur
        result["c_min_cycles"]   = p.t_c_min
        result["c_max_cycles"]   = p.t_c_max
        result["c_mean_cycles"]  = p.t_c_total / float(n) if n else 0
        result["wrap_min_cycles"]  = p.t_wrap_min
        result["wrap_max_cycles"]  = p.t_wrap_max
        result["wrap_mean_cycles"] = p.t_wrap_total / float(n) if n else 0

    return result


def reset_perf(ptr_int):
    """Zero a c2py_perf_t struct, resetting all counters.

    Call this between benchmark batches to get clean per-batch stats
    without needing to toggle timing on/off.

    Parameters
    ----------
    ptr_int : int
        Raw pointer to the c2py_perf_t struct (e.g. module._perf_myfunc).
    """
    if ptr_int == 0:
        return
    ctypes.memset(ptr_int, 0, ctypes.sizeof(_c2py_perf_t))
    # Restore sentinel values for min tracking
    p = _c2py_perf_t.from_address(ptr_int)
    p.variant = -1
    p.group_idx = -1
    p.t_c_min = 2**64 - 1
    p.t_wrap_min = 2**64 - 1


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
