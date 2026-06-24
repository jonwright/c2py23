"""c2py23 performance data decoder.

Reads c2py_perf_t data via module-level C accessor functions -- no ctypes
required.  Modules built with `timing: true` expose `_c2py_perf_read`,
`_c2py_perf_meta`, `_c2py_perf_reset` and pointer attributes on the module
so that `read_perf()` can locate the right perf counter from the wrapper
function object alone.

Usage::

    from c2py23.perf import read_perf, reset_perf

    import my_timed_module
    stats = read_perf(my_timed_module.wsum)
    print(stats)

    # With C2PY_USE_CYCLE_COUNTER, provide the frequency:
    stats = read_perf(my_timed_module.wsum,
                      freq_hz=my_timed_module._c2py_tick_frequency())

    # Read the currently-selected variant's timing:
    stats = read_perf(my_timed_module.poly, variant=True)

    # Reset counters between benchmark batches:
    reset_perf(my_timed_module.wsum)
"""
from __future__ import print_function

import array
import sys


# ---- Layout constants for the uint64 buffer ----
_I_CALL_COUNT    = 0
_I_T_ENTER       = 1
_I_T_PRE_C       = 2
_I_T_POST_C      = 3
_I_T_EXIT        = 4
_I_T_C_MIN       = 5
_I_T_C_MAX       = 6
_I_T_C_TOTAL     = 7
_I_T_WRAP_MIN    = 8
_I_T_WRAP_MAX    = 9
_I_T_WRAP_TOTAL  = 10
_N_FIELDS        = 11


def _get_mod(func):
    """Return the module that owns *func*.

    On Python 3.x, C function objects expose ``func.__self__`` directly.
    On Python 2.7, ``PyCFunction`` has no ``__self__``, so we fall back
    to ``func.__module__`` and look it up in ``sys.modules``.
    """
    mod = getattr(func, '__self__', None)
    if mod is not None:
        return mod
    modname = getattr(func, '__module__', None)
    if modname:
        return sys.modules[modname]
    return None


def _make_perf_buf():
    """Return a writable buffer with room for _N_FIELDS uint64 values.

    On Python 3.3+ we use ``array.array('Q')`` which supports direct
    indexing and 8-byte elements.  On Python 2.7 the ``'Q'`` typecode
    is unavailable; we use ``bytearray`` instead and decode elements
    via ``struct.unpack_from``.
    """
    if hasattr(array, 'typecodes') and 'Q' in array.typecodes:
        return array.array('Q', [0] * _N_FIELDS)
    return bytearray(_N_FIELDS * 8)


def _read_buf(buf, idx):
    """Read the uint64 value at position *idx* from a perf buffer."""
    if isinstance(buf, array.array):
        return buf[idx]
    import struct
    return struct.unpack_from('<Q', str(buf), idx * 8)[0]


def _to_ns(ticks, freq_hz):
    """Convert tick count to nanoseconds, guarding against freq_hz == 0."""
    if freq_hz == 0 or freq_hz is None:
        return ticks
    return ticks * 1000000000 // freq_hz


def _get_perf_ptr(func, variant=None):
    """Resolve the raw perf-struct pointer for *func*.

    Parameters
    ----------
    func : callable
        A wrapper function on a timing-enabled module (e.g. ``mod.wsum``).
    variant : None, True, or str, optional
        - None       -> wrapper overhead counter (``_c2py_perf_ptr_*``)
        - True       -> currently-selected variant (``_c2py_active_ptr_*``)
        - str        -> named overload (``_c2py_ol_ptr_funcname__name``)

    Returns
    -------
    int
        Raw pointer value (Python int).
    """
    name = func.__name__
    mod = _get_mod(func)

    if variant is True:
        attr = '_c2py_active_ptr_' + name
        if hasattr(mod, attr):
            return getattr(mod, attr)
        return getattr(mod, '_c2py_perf_ptr_' + name)

    if isinstance(variant, str):
        attr = '_c2py_ol_ptr_{0}__{1}'.format(name, variant)
        return getattr(mod, attr)

    return getattr(mod, '_c2py_perf_ptr_' + name)


def read_perf(func, freq_hz=None, variant=None):
    """Decode a c2py_perf_t counter.

    Parameters
    ----------
    func : callable
        Wrapper function on a timing-enabled module (e.g. ``mod.wsum``).
        The module is found via ``func.__self__`` and the counter pointer
        is looked up by ``func.__name__`` on the module.
    freq_hz : int or None, optional
        Tick source frequency in Hz.  When None or 0, the raw tick values
        are returned under the ``_ns`` keys (correct for the default
        ``clock_gettime`` source which returns nanoseconds).  When provided
        and not equal to 1e9, the values are converted and the raw tick
        values are additionally returned under ``_cycles`` keys.
    variant : None, True, or str, optional
        Which perf counter to read:

        - ``None`` (default) -- wrapper-overhead counter
        - ``True`` -- the currently-selected variant (functions with
          variant groups only; falls back to wrapper overhead otherwise)
        - ``str`` -- a named overload, e.g. ``"weighted_sum"`` for the
          counter ``_c2py_ol_ptr_wsum__weighted_sum``

    Returns
    -------
    dict with keys:
        call_count, t_enter, t_pre_c, t_post_c, t_exit,
        c_dur_ns, wrap_dur_ns,
        c_min_ns, c_max_ns, c_mean_ns,
        wrap_min_ns, wrap_max_ns, wrap_mean_ns,
        variant, group_idx, variant_name.
      Additional keys when freq_hz is provided and != 1e9:
        c_dur_cycles, wrap_dur_cycles,
        c_min_cycles, c_max_cycles, c_mean_cycles,
        wrap_min_cycles, wrap_max_cycles, wrap_mean_cycles.
    """
    ptr = _get_perf_ptr(func, variant)
    if ptr == 0:
        return {"call_count": 0}

    mod = _get_mod(func)

    buf = _make_perf_buf()
    mod._c2py_perf_read(ptr, buf)
    variant_val, group_idx, vname = mod._c2py_perf_meta(ptr)

    n = _read_buf(buf, _I_CALL_COUNT)
    t_enter   = _read_buf(buf, _I_T_ENTER)
    t_pre_c   = _read_buf(buf, _I_T_PRE_C)
    t_post_c  = _read_buf(buf, _I_T_POST_C)
    t_exit    = _read_buf(buf, _I_T_EXIT)
    t_c_min   = _read_buf(buf, _I_T_C_MIN)
    t_c_max   = _read_buf(buf, _I_T_C_MAX)
    t_c_total = _read_buf(buf, _I_T_C_TOTAL)
    t_w_min   = _read_buf(buf, _I_T_WRAP_MIN)
    t_w_max   = _read_buf(buf, _I_T_WRAP_MAX)
    t_w_total = _read_buf(buf, _I_T_WRAP_TOTAL)

    c_dur = t_post_c - t_pre_c
    wrap_dur = (t_pre_c - t_enter) + (t_exit - t_post_c) \
               if t_enter or t_exit else 0

    result = {
        "call_count": n,
        "t_enter":    t_enter,
        "t_pre_c":    t_pre_c,
        "t_post_c":   t_post_c,
        "t_exit":     t_exit,
        "c_dur_ns":   _to_ns(c_dur, freq_hz),
        "wrap_dur_ns": _to_ns(wrap_dur, freq_hz),
        "c_min_ns":   _to_ns(t_c_min, freq_hz),
        "c_max_ns":   _to_ns(t_c_max, freq_hz),
        "c_mean_ns":  _to_ns(t_c_total / float(n), freq_hz) if n else 0,
        "wrap_min_ns":  _to_ns(t_w_min, freq_hz),
        "wrap_max_ns":  _to_ns(t_w_max, freq_hz),
        "wrap_mean_ns": _to_ns(t_w_total / float(n), freq_hz) if n else 0,
        "variant":    variant_val,
        "group_idx":  group_idx,
        "variant_name": vname,
    }

    if freq_hz is not None and freq_hz != 0 and freq_hz != 1000000000:
        result["c_dur_cycles"]   = c_dur
        result["wrap_dur_cycles"] = wrap_dur
        result["c_min_cycles"]   = t_c_min
        result["c_max_cycles"]   = t_c_max
        result["c_mean_cycles"]  = t_c_total / float(n) if n else 0
        result["wrap_min_cycles"]  = t_w_min
        result["wrap_max_cycles"]  = t_w_max
        result["wrap_mean_cycles"] = t_w_total / float(n) if n else 0

    return result


def reset_perf(func, variant=None):
    """Reset a c2py_perf_t counter to its initial state.

    Parameters
    ----------
    func : callable
        Wrapper function on a timing-enabled module (e.g. ``mod.wsum``).
    variant : None, True, or str, optional
        Selects which counter to reset.  See :func:`read_perf`.
    """
    ptr = _get_perf_ptr(func, variant)
    if ptr == 0:
        return
    mod = _get_mod(func)
    mod._c2py_perf_reset(ptr)


def read_enabled(func):
    """Return 1 if per-call timing is enabled, 0 otherwise.

    Parameters
    ----------
    func : callable
        Any wrapper function from a timing-enabled module.  The module
        is found via ``func.__self__`` (Python 3) or ``func.__module__``
        (Python 2.7).
    """
    mod = _get_mod(func)
    return mod._c2py_perf_get_enabled()


def set_enabled(func, value):
    """Enable (value=1) or disable (value=0) per-call timing.

    Parameters
    ----------
    func : callable
        See :func:`get_enabled`.
    value : int
        1 to enable, 0 to disable.
    """
    mod = _get_mod(func)
    mod._c2py_perf_set_enabled(int(value))
