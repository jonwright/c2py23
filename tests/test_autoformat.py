"""Element type and alignment checks derived from the C signature
(review findings B1 and B9).

Builds on tests/cases/autoformat (autoformatmod), whose .c2py has no
format checks at all: every <buf>.ptr passed as a typed C pointer gets a
derived element-type check from the pointee type.  The call that used to
corrupt the heap runs in a subprocess so a regression fails the test, not
pytest.

Python 2.7 - 3.15 compatible.
"""

from __future__ import print_function

import array
import ctypes
import os
import subprocess
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)
_CASE = os.path.join(_HERE, "cases", "autoformat")
sys.path.insert(0, _CASE)
sys.path.insert(0, _PROJECT)
sys.path.insert(0, _HERE)

import autoformatmod as m  # noqa: E402
from _extload import extload_prelude  # noqa: E402
from c2py23.parser import from_c2py_dict  # noqa: E402
from c2py23.generator import generate  # noqa: E402

_LONG_SIZE = ctypes.sizeof(ctypes.c_long)


def _value_error(fn, a):
    try:
        fn(a)
    except ValueError as e:
        return str(e)
    raise AssertionError("%s(%s) did not raise ValueError" % (fn.__name__, getattr(a, "dtype", type(a))))


# --- B1: sumd(const double *) with no checks ------------------------------


def test_sum_f64_rejects_other_types_with_value_error():
    for dt in ("f4", "u1", "i8", "q"):
        msg = _value_error(m.sum_f64, np.zeros(4, dtype=dt))
        assert "sum_f64: arg 'a' check failed: a.format == 'd'" in msg, msg
    assert m.sum_f64(np.arange(4, dtype="f8")) == 6.0


def test_message_reports_format_and_itemsize():
    msg = _value_error(m.sum_f64, np.zeros(3, dtype=np.uint8))
    assert "got format='B', itemsize=1" in msg, msg


def test_message_says_how_to_fix_element_type():
    msg = _value_error(m.sum_f64, np.zeros(3, dtype="f4"))
    assert "the C parameter is double *: pass a buffer of that element type" in msg, msg
    assert "check_format: False" in msg, msg
    # int32_t and int share one derived check: both are named.
    msg = _value_error(m.sum_i32, np.zeros(3, dtype="f8"))
    assert "the C parameter is int32_t or int *" in msg, msg


def test_noncontiguous_message_names_arg_and_fix():
    msg = _value_error(m.sum_f64, np.zeros(8)[::2])
    assert msg.startswith("sum_f64: arg 'a': buffer not contiguous"), msg
    assert "numpy.ascontiguousarray" in msg, msg


_FILL_SNIPPET = (
    extload_prelude()
    + """
import sys
import numpy as np
m = c2py_load("autoformatmod", %r)
a = np.zeros(1000, np.uint8)
try:
    m.filld(a, 1.0)
except ValueError:
    sys.exit(0)
sys.exit(3)
"""
)


def test_uint8_fill_raises_not_crash():
    """Review finding B1 (archive/2026-11_review.md): filld(uint8[1000]) wrote 8000 bytes and killed the process."""
    p = subprocess.Popen([sys.executable, "-c", _FILL_SNIPPET % (_CASE,)])
    assert p.wait() == 0
    a = np.zeros(5)
    m.filld(a, 2.5)
    assert list(a) == [2.5] * 5


# --- one case per row of the pointee table -------------------------------


def _row(fn, accept, reject):
    for dt in accept:
        a = np.arange(5, dtype=dt) if np.dtype(dt).kind != "b" else np.ones(5, dtype=dt)
        assert fn(a) == float(a.astype("f8").sum()), (fn.__name__, dt)
    for dt in reject:
        _value_error(fn, np.zeros(3, dtype=dt))


def test_row_double():
    _row(m.sum_f64, ["f8"], ["f4", "i8", "u8"])


def test_row_float():
    _row(m.sum_f32, ["f4"], ["f8", "i4", "u4"])


def test_row_int8():
    _row(m.sum_i8, ["i1"], ["u1", "?", "i2"])


def test_row_uint8():
    _row(m.sum_u8, ["u1"], ["i1", "?", "u2"])


def test_row_char_accepts_any_one_byte_type():
    _row(m.sum_char, ["i1", "u1", "?"], ["i2", "u2", "f4"])
    c = (ctypes.c_char * 3)(b"a", b"b", b"c")
    assert m.sum_char(c) == float(ord("a") + ord("b") + ord("c"))


def test_row_int16():
    _row(m.sum_i16, ["i2"], ["u2", "f2", "i4"])


def test_row_uint16():
    _row(m.sum_u16, ["u2"], ["i2", "f2", "u4"])


def test_row_int32_and_int():
    """'i', plus 'l' only where sizeof(long) == 4."""
    l_ok = ["l"] if _LONG_SIZE == 4 else []
    l_bad = [] if _LONG_SIZE == 4 else ["l"]
    for fn in (m.sum_i32, m.sum_int):
        _row(fn, ["i"] + l_ok, ["I", "f4", "q", "h"] + l_bad)


def test_row_uint32():
    l_ok = ["L"] if _LONG_SIZE == 4 else []
    l_bad = [] if _LONG_SIZE == 4 else ["L"]
    _row(m.sum_u32, ["I"] + l_ok, ["i", "f4", "Q"] + l_bad)


def test_row_int64():
    """'q', plus 'l' only where sizeof(long) == 8."""
    l_ok = ["l"] if _LONG_SIZE == 8 else []
    l_bad = [] if _LONG_SIZE == 8 else ["l"]
    _row(m.sum_i64, ["q"] + l_ok, ["Q", "f8", "i"] + l_bad)


def test_row_uint64():
    l_ok = ["L"] if _LONG_SIZE == 8 else []
    l_bad = [] if _LONG_SIZE == 8 else ["L"]
    _row(m.sum_u64, ["Q"] + l_ok, ["q", "f8", "I"] + l_bad)


def test_ctypes_arrays():
    """ctypes exports '<d', '<l', ... (native order, accepted)."""
    assert m.sum_f64((ctypes.c_double * 3)(1, 2, 3)) == 6.0
    assert m.sum_i32((ctypes.c_int32 * 3)(1, 2, 3)) == 6.0
    assert m.sum_i64((ctypes.c_int64 * 3)(1, 2, 3)) == 6.0
    _value_error(m.sum_i64, (ctypes.c_int32 * 3)(1, 2, 3))


def test_array_array():
    """On Python 2.7 array.array has only the old buffer API: format NULL,
    itemsize 1, which is 'B' (bytes) -- so it is uint8/char, never double."""
    a = array.array("d", [1.0, 2.0])
    if sys.version_info[0] >= 3:
        assert m.sum_f64(a) == 3.0
    else:
        _value_error(m.sum_f64, a)
    assert m.sum_u8(array.array("B", [1, 2, 3])) == 6.0


def test_void_pointer_has_no_check():
    assert m.count_bytes(np.zeros(3, dtype="f4")) == 12
    assert m.count_bytes(np.zeros(5, dtype="u1")) == 5


# --- overloads without when: are selected by the derived terms ----------


def test_overloads_dispatch_on_pointee_type():
    a = np.ones(3, dtype="f4")
    assert m.scale(a, 2.0) == 32
    assert list(a) == [2.0] * 3
    b = np.ones(3, dtype="f8")
    assert m.scale(b, 3.0) == 64
    assert list(b) == [3.0] * 3
    bad = np.ones(3, dtype="i4")
    msg = _value_error(lambda x: m.scale(x, 1.0), bad)
    assert "scale: no overload matches" in msg, msg
    expected = "(got 'a' format=%r itemsize=%d ndim=%d)" % (memoryview(bad).format, bad.itemsize, bad.ndim)
    assert expected in msg, msg


# --- opt-outs ------------------------------------------------------------


def test_check_format_false_restores_old_behaviour():
    raw = np.array([1.5, 2.5]).view(np.uint8)  # aligned for double
    assert m.sum_raw(raw) == 4.0
    assert m.sum_raw(np.array([1.0, 2.0])) == 3.0


# --- B9: alignment -------------------------------------------------------


def test_unaligned_buffer_raises():
    a = np.frombuffer(bytearray(33), dtype="f8", offset=1)
    assert a.ctypes.data % 8 != 0
    msg = _value_error(m.sum_f64, a)
    assert msg.startswith("sum_f64: arg 'a': buffer not aligned for the C parameter type double *"), msg
    assert "(alignment 8, address % 8 == 1)" in msg, msg
    assert "aligned copy" in msg and "check_alignment: False" in msg, msg


def test_check_alignment_false_accepts_unaligned():
    buf = bytearray(33)
    buf[1:9] = np.array([4.5]).tobytes()
    a = np.frombuffer(buf, dtype="f8", offset=1)
    assert m.sum_unaligned(a) == 4.5


def test_empty_unaligned_buffer_is_accepted():
    a = np.frombuffer(bytearray(9), dtype="f8", offset=1, count=0)
    assert m.sum_f64(a) == 0.0


def _unaligned_u64():
    buf = bytearray(33)
    buf[1:5] = b"\x01\x02\x03\x04"
    a = np.frombuffer(buf, dtype="u8", offset=1)
    assert a.ctypes.data % 8 != 0
    return a


def test_unaligned_u64_to_char_pointer_is_accepted():
    # The alignment needed is that of the C parameter (char: none), not
    # of the buffer's element type.
    assert m.sum_chars(_unaligned_u64()) == 10


def test_unaligned_u64_to_void_pointer_is_accepted():
    assert m.count_bytes(_unaligned_u64()) == 32


def test_unaligned_u64_to_uint64_pointer_raises():
    msg = _value_error(m.sum_u64, _unaligned_u64())
    assert "buffer not aligned for the C parameter type uint64_t *" in msg, msg


def test_unaligned_bytes_reinterpreted_as_double_raise():
    # check_format: False lets bytes through as double *, but the pointer
    # still has to be aligned for double.
    raw = np.frombuffer(bytearray(17), dtype=np.uint8, offset=1)
    assert raw.ctypes.data % 8 != 0
    msg = _value_error(m.sum_raw, raw)
    assert "buffer not aligned for the C parameter type double *" in msg, msg


# --- generator-level rules (no build) ------------------------------------


def _spec(func):
    return {"module": "gmod", "source": ["gmod.c"], "functions": [func]}


def _simple(checks=None, when=None, **kw):
    ol = {"sig": "void k(const double *a, intptr_t n)", "map": {"a": "a.ptr", "n": "a.n"}}
    if when is not None:
        ol["when"] = when
    f = {"py_sig": "k(a: buffer) -> void", "c_overloads": [ol]}
    if checks is not None:
        f["checks"] = checks
    if when is not None:
        f["default_raise"] = "ValueError: nope"
    f.update(kw)
    return generate(from_c2py_dict(_spec(f)))


def test_user_constraint_suppresses_derived_check():
    for checks, when in (
        (["a.format == 'd'"], None),
        (["a.itemsize == 8"], None),
        (None, "a.format == 'd'"),
    ):
        code = _simple(checks=checks, when=when)
        assert "derived check" not in code
        assert code.count("c2py_format_type(info_a->format)") <= 1


def test_derived_check_and_opt_outs_in_generated_code():
    code = _simple()
    assert "/* derived check: a.format == 'd' */" in code
    assert 'c2py_check_alignment(info_a, sizeof(double), "double", ' in code
    assert "derived check" not in _simple(check_format=False)
    assert "c2py_check_alignment" not in _simple(check_alignment=False)


def _group(sig_b):
    f = {
        "py_sig": "g(a: buffer) -> void",
        "c_overloads": [
            {
                "map": {"a": "a.ptr", "n": "a.n"},
                "group": "grp",
                "variants": [
                    {"sig": "void ga(const double *a, intptr_t n)"},
                    {"sig": sig_b, "default": False},
                ],
            }
        ],
    }
    return generate(from_c2py_dict(_spec(f)))


def test_group_variants_agreeing_get_group_term():
    code = _group("void gb(const double *a, intptr_t n)")
    assert "if (((c2py_format_type(info_a->format) == 'd')))" in code
    assert "g: no overload matches: 'a' needs (a.format == 'd')" in code


def _cli(tmpdir, text):
    path = os.path.join(tmpdir, "w.c2py")
    with open(path, "w") as f:
        f.write(text)
    out = os.path.join(tmpdir, "w_wrapper.c")
    env = dict(os.environ)
    env["PYTHONPATH"] = _PROJECT + os.pathsep + env.get("PYTHONPATH", "")
    p = subprocess.Popen(
        [sys.executable, "-m", "c2py23", path, "-o", out],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    _, err = p.communicate()
    assert p.returncode == 0, err
    with open(out) as f:
        return f.read(), err.decode("ascii", "replace")


def test_unknown_pointee_warns_and_gets_no_check():
    """size_t (and intptr_t, ptrdiff_t, _Bool) are not in the table.  The
    .c2py C-signature grammar has no struct or typedef pointers, so these
    are the only unknown pointee types that can reach the generator."""
    tmpdir = tempfile.mkdtemp()
    code, err = _cli(
        tmpdir,
        '{"module": "w", "functions": [{"py_sig": "count(a: buffer) -> void", '
        '"c_overloads": [{"sig": "void count_sz(const size_t *a, intptr_t n)", '
        '"map": {"a": "a.ptr", "n": "a.n"}}]}]}\n',
    )
    assert "warning" in err and "count" in err and "'a'" in err and "size_t" in err, err
    assert "derived check" not in code


def test_group_variants_disagreeing_warn():
    tmpdir = tempfile.mkdtemp()
    code, err = _cli(
        tmpdir,
        '{"module": "w", "functions": [{"py_sig": "g(a: buffer) -> void", '
        '"c_overloads": [{"map": {"a": "a.ptr", "n": "a.n"}, "group": "grp", "variants": ['
        '{"sig": "void ga(const double *a, intptr_t n)"}, '
        '{"sig": "void gb(const float *a, intptr_t n)", "default": False}]}]}]}\n',
    )
    assert "warning" in err and "grp" in err, err
    assert "c2py_format_type" not in code
