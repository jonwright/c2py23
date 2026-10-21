# test_ndarray_backends.py -- ndarray/DLPack edge cases and fallback behavior
"""Tests that numpy ndarray fast-path works correctly for common numpy
types and that non-numpy types correctly fall through to buffer protocol.

Requires numpy (skipped gracefully via importorskip when absent)."""

from __future__ import print_function
import sys, os, array, ctypes

import pytest

np = pytest.importorskip("numpy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "benchmarks", "build"))

# These are built by the benchmark Makefile (called from run_tests.sh)
# Each module uses a specific acquisition backend.
_can_import = True
try:
    import c2py_vnorm  # default [ndarray, buffer]
    import c2py_vnorm_bare  # default [ndarray, buffer], no checks
    import c2py_vnorm_ndarray  # acquire: [ndarray]
    import c2py_vnorm_buffer  # acquire: [buffer]
    import c2py_vnorm_dlpack  # acquire: [dlpack]
    import c2py_getitem  # default [ndarray, buffer]
except ImportError:
    _can_import = False

needs_modules = pytest.mark.skipif(not _can_import, reason="benchmark modules not built")


def make_vec(n=2):
    return np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype="f8")[:n]


def make_mods(n=2):
    return np.zeros(n, dtype="f8")


@needs_modules
class TestNdarrayFastPath:
    """Verify the ndarray struct-cast path handles common numpy objects."""

    def test_basic_ndarray(self):
        """Plain numpy.ndarray should use the fast path."""
        c2py_vnorm.vnorm(make_vec(), make_mods())

    def test_f_contiguous(self):
        """F-contiguous arrays have same ob_type, get ndarray fast path,
        but the slow_axis == 0 check in _impl correctly rejects them."""
        arr = np.asfortranarray(np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype="f8"))
        mods = np.zeros(3, dtype="f8")
        with pytest.raises(ValueError, match="slow_axis"):
            c2py_vnorm_bare.vnorm(arr, mods)

    def test_1d_reshape(self):
        """reshaped 1D arrays are still ndarray type."""
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype="f8").reshape(2, 3)
        c2py_vnorm_bare.vnorm(arr, make_mods())

    def test_ndarray_subclass(self):
        """Subclasses have a different ob_type, so they fall through
        to the buffer protocol -- still work correctly."""
        arr = make_vec().view(type("MyArray", (np.ndarray,), {}))
        mods = make_mods().view(type("MyMods", (np.ndarray,), {}))
        c2py_vnorm.vnorm(arr, mods)

    def test_masked_array(self):
        """np.ma.MaskedArray has a different ob_type, falls to buffer."""
        arr = np.ma.array(make_vec())
        mods = np.ma.array(make_mods())
        c2py_vnorm.vnorm(arr, mods)

    def test_read_only_rejected(self):
        """Writable request on read-only ndarray: ValueError mentioning
        read-only, from the fast path's flags check or (PyPy) from
        numpy's PEP 3118 export -- the same on every build."""
        mods_ro = make_mods()
        mods_ro.setflags(write=False)
        with pytest.raises(ValueError) as e:
            c2py_vnorm.vnorm(make_vec(), mods_ro)
        assert "read-only" in str(e.value), e.value

    def test_dtype_rejected(self):
        """float32 numpy arrays are rejected by the format check."""
        arr = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype="f4")
        mods = np.zeros(2, dtype="f4")
        with pytest.raises(ValueError, match="format"):
            c2py_vnorm.vnorm(arr, mods)

    def test_memoryview_fallback(self):
        """memoryview of a numpy array has a different ob_type;
        falls to buffer protocol."""
        mv = memoryview(make_vec())
        mods = make_mods()
        c2py_vnorm.vnorm(mv, mods)

    def test_array_module(self):
        """array.array has ob_type != numpy.ndarray, falls to buffer.

        On 2.7 array.array has only the old buffer API: untyped bytes
        (format 'B'), which a format == 'd' check must reject."""
        a = array.array("d", [1.0, 2.0, 3.0, 4.0, 5.0])
        if sys.version_info[0] >= 3:
            assert c2py_getitem.getitem(a, 2) == 3.0
        else:
            with pytest.raises(ValueError):
                c2py_getitem.getitem(a, 2)


@needs_modules
class TestBackendSpecific:
    """Verify each acquisition backend works in isolation."""

    def test_ndarray_only(self):
        """ndarray-only backend handles numpy arrays (GIL and free-threaded)."""
        mods = make_mods()
        c2py_vnorm_ndarray.vnorm(make_vec(), mods)
        assert np.allclose(mods, np.linalg.norm(make_vec(), axis=1))

    def test_ndarray_first_probe_threads(self):
        """Threads meeting the first ndarray at once all get correct data.

        The fast path probes numpy's layout on first use and publishes it
        to every thread; on free-threaded Python the probes really run
        concurrently.  A fresh interpreter makes this the first ndarray
        seen; an Event releases all threads together."""
        import subprocess

        script = r"""
from __future__ import print_function
import sys, threading
sys.path.insert(0, sys.argv[1])
import numpy as np
import c2py_vnorm_ndarray as m

N_THREADS, N_CALLS = 8, 200
go = threading.Event()
errors = []

def work(k):
    vec = np.arange(3.0 * (k + 1)).reshape(-1, 3) + k
    want = np.sqrt((vec * vec).sum(axis=1))
    go.wait()
    for _ in range(N_CALLS):
        mods = np.zeros(vec.shape[0])
        m.vnorm(vec, mods)
        if not np.array_equal(mods, want):
            errors.append((k, mods, want))
            return

threads = [threading.Thread(target=work, args=(k,)) for k in range(N_THREADS)]
for t in threads:
    t.start()
go.set()
for t in threads:
    t.join()
print("ERRORS", len(errors))
sys.exit(1 if errors else 0)
"""
        build = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "benchmarks", "build")
        for _ in range(5):
            p = subprocess.Popen(
                [sys.executable, "-c", script, build], stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            out = p.communicate()[0].decode("ascii", "replace")
            assert p.returncode == 0, out
            assert "ERRORS 0" in out, out

    def test_buffer_only(self):
        """buffer-only backend handles numpy arrays via PEP 3118."""
        c2py_vnorm_buffer.vnorm(make_vec(), make_mods())

    def test_buffer_array_module(self):
        """buffer-only backend handles array.array."""
        # getitem buffer-only is tested indirectly via alternating test;
        # vnorm with array.array isn't possible (shape mismatch).
        # Just verify import works.
        assert c2py_vnorm_buffer is not None

    def test_dlpack(self):
        """DLPACK backend: verify basic import and function signature.

        Writability is covered by TestDLPackValidation: a DLPack 1.0
        capsule carries a read-only flag, which is honoured; a legacy
        capsule carries none and is never written through.
        """
        import c2py_vnorm_dlpack as m

        assert hasattr(m, "vnorm")
        # verify it can compute with a 2D input (as the interface requires);
        # the writable output needs a DLPack 1.0 (versioned) capsule
        vec = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float64)
        mods = np.zeros(2, dtype=np.float64)
        if _numpy_dlpack_versioned():
            m.vnorm(vec, mods)
            assert np.isclose(mods[0], np.sqrt(1 + 4 + 9), atol=0.01)
        else:
            with pytest.raises(TypeError):
                m.vnorm(vec, mods)

    def test_ndarray_and_buffer_same_result(self):
        """ndarray and buffer backends produce the same result."""
        vec, mods_a = make_vec(), make_mods()
        mods_b = make_mods()
        c2py_vnorm_ndarray.vnorm(vec, mods_a)
        c2py_vnorm_buffer.vnorm(vec, mods_b)
        assert np.allclose(mods_a, mods_b)


@needs_modules
class TestDlpackFallback:
    """Non-dlpack objects pass through silently to next backend."""

    def test_array_array_no_dlpack(self):
        """array.array does not have __dlpack__, dlpack backend
        fails silently, buffer fallback succeeds (3.x; on 2.7 the old
        buffer API gives untyped bytes, rejected by format == 'd')."""
        a = array.array("d", [1.0, 2.0, 3.0, 4.0, 5.0])
        if sys.version_info[0] >= 3:
            assert c2py_getitem.getitem(a, 2) == 3.0
        else:
            with pytest.raises(ValueError):
                c2py_getitem.getitem(a, 2)


def _other_byteorder():
    """'>' on a little-endian host, '<' on a big-endian host --
    i.e. always the non-native PEP 3118 prefix character."""
    return ">" if sys.byteorder == "little" else "<"


@needs_modules
class TestByteOrderRejection:
    """c2py23 only supports native-byte-order buffers (see AGENTS.md).  A
    buffer with an explicit non-native PEP 3118 prefix must raise instead
    of being silently read with the wrong byte order."""

    def test_buffer_backend_rejects_non_native(self):
        """acquire: [buffer] -- format string carries the explicit
        prefix, checked directly by c2py_format_is_native()."""
        swapped = _other_byteorder() + "f8"
        vec = make_vec().astype(swapped)
        mods = make_mods().astype(swapped)
        with pytest.raises(ValueError):
            c2py_vnorm_buffer.vnorm(vec, mods)

    def test_ndarray_backend_rejects_non_native(self):
        """acquire: [ndarray] only -- the fast path itself detects the
        non-native PyArray_Descr.byteorder and refuses to use it; with
        no other backend configured, acquisition fails outright."""
        swapped = _other_byteorder() + "f8"
        vec = make_vec().astype(swapped)
        mods = make_mods().astype(swapped)
        with pytest.raises(Exception):
            c2py_vnorm_ndarray.vnorm(vec, mods)

    def test_default_backend_falls_through_and_rejects(self):
        """Default acquire: [ndarray, buffer] -- ndarray fast path
        declines (non-native byteorder), falls through to the buffer
        protocol backend, which then correctly rejects it too."""
        swapped = _other_byteorder() + "f8"
        vec = make_vec().astype(swapped)
        mods = make_mods().astype(swapped)
        with pytest.raises(ValueError):
            c2py_vnorm.vnorm(vec, mods)

    def test_native_byteorder_still_works(self):
        """Sanity check: explicit native-order dtype (e.g. '<f8' on a
        little-endian host) is accepted exactly like a bare 'f8'."""
        native = "<" if sys.byteorder == "little" else ">"
        vec = make_vec().astype(native + "f8")
        mods = make_mods().astype(native + "f8")
        c2py_vnorm.vnorm(vec, mods)
        assert np.allclose(mods, np.linalg.norm(vec, axis=1))


@needs_modules
class TestSizeOneDims:
    """numpy leaves the stride of a length-1 axis raw (a[None, :] has
    strides (0, 8)) and only normalises it in its PEP 3118 export.  The
    contiguity check must ignore it, so every backend accepts the array."""

    def _vec(self):
        v = np.array([1.0, 2.0, 3.0])[None, :]
        assert v.strides[0] == 0, v.strides
        return v

    def test_ndarray_backend(self):
        mods = np.zeros(1)
        c2py_vnorm_ndarray.vnorm(self._vec(), mods)
        assert np.allclose(mods, [np.sqrt(14.0)])

    def test_default_backend(self):
        mods = np.zeros(1)
        c2py_vnorm.vnorm(self._vec(), mods)
        assert np.allclose(mods, [np.sqrt(14.0)])

    def test_buffer_backend(self):
        mods = np.zeros(1)
        c2py_vnorm_buffer.vnorm(self._vec(), mods)
        assert np.allclose(mods, [np.sqrt(14.0)])


@needs_modules
class TestUnknownItemsize:
    """The ndarray fast path gave every type char it did not list (float16
    'e', complex 'D', datetime, ...) itemsize 1, so a contiguous array was
    rejected as "not contiguous".  It must decline instead, so the buffer
    backend reports the real format."""

    def test_float16_reports_format(self):
        vec = make_vec().astype("f2")
        with pytest.raises(ValueError) as e:
            c2py_vnorm.vnorm(vec, make_mods())
        msg = str(e.value)
        assert "format" in msg and "contiguous" not in msg, msg

    def test_datetime_rejected(self):
        """numpy datetimes are rejected, never as "not contiguous".  On 3.x
        numpy refuses the PEP 3118 export ("cannot include dtype 'M'");
        on 2.7 the old buffer API exports raw bytes and vec.ndim == 2
        rejects them."""
        vec = np.zeros((2, 3), dtype="M8[s]")
        with pytest.raises(ValueError) as e:
            c2py_vnorm.vnorm(vec, make_mods())
        msg = str(e.value)
        assert "contiguous" not in msg, msg


class _LegacyDLPack(object):
    """A producer that predates DLPack 1.0: __dlpack__ takes no keywords."""

    def __init__(self, a):
        self.a = a

    def __dlpack__(self):
        return self.a.__dlpack__()


class _RawDLPack(object):
    """A producer handing out a hand-built (possibly malformed) capsule."""

    def __init__(self, ndim, shape=None, byte_offset=0, data=None):
        import ctypes

        class DLTensor(ctypes.Structure):
            _fields_ = [
                ("data", ctypes.c_void_p),
                ("device_type", ctypes.c_int32),
                ("device_id", ctypes.c_int32),
                ("ndim", ctypes.c_int32),
                ("code", ctypes.c_uint8),
                ("bits", ctypes.c_uint8),
                ("lanes", ctypes.c_uint16),
                ("shape", ctypes.POINTER(ctypes.c_int64)),
                ("strides", ctypes.POINTER(ctypes.c_int64)),
                ("byte_offset", ctypes.c_int64),
            ]

        class DLManagedTensor(ctypes.Structure):
            _fields_ = [("dl_tensor", DLTensor), ("manager_ctx", ctypes.c_void_p), ("deleter", ctypes.c_void_p)]

        self.store = (ctypes.c_double * 8)()
        self.shape = (ctypes.c_int64 * 4)(*(shape or [1, 1, 1, 1]))
        m = DLManagedTensor()
        m.dl_tensor.data = ctypes.addressof(self.store) if data is None else data
        m.dl_tensor.device_type = 1
        m.dl_tensor.ndim = ndim
        m.dl_tensor.code, m.dl_tensor.bits, m.dl_tensor.lanes = 2, 64, 1
        if shape is not None:
            m.dl_tensor.shape = ctypes.cast(self.shape, ctypes.POINTER(ctypes.c_int64))
        m.dl_tensor.byte_offset = byte_offset
        self.m = m
        new = ctypes.pythonapi.PyCapsule_New
        new.restype = ctypes.py_object
        new.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
        self._new = new

    def __dlpack__(self, **kw):
        import ctypes

        return self._new(ctypes.addressof(self.m), b"dltensor", None)


def _numpy_dlpack_versioned():
    """True if numpy exports DLPack 1.0 capsules (numpy >= 2.1).

    False for legacy-only DLPack (numpy 1.22 - 2.0) and for no DLPack at
    all (numpy < 1.22: no __dlpack__, so the DLPack backend declines and
    a DLPack-only module reports "all backends exhausted")."""
    try:
        np.zeros(1).__dlpack__(max_version=(1, 0))
        return True
    except (TypeError, AttributeError):
        return False


@needs_modules
class TestDLPackValidation:
    """DLPack is foreign data: honour the read-only flag of a versioned
    capsule, never write through a legacy one, and reject malformed
    tensors before reading them.

    numpy < 2.1 exports only legacy capsules (and refuses read-only arrays
    altogether), and numpy < 1.22 has no DLPack at all, so a DLPack-only
    module cannot write to their arrays: the cases with a numpy output
    expect "all backends exhausted" there.  The hand-built capsules need
    no numpy DLPack and run everywhere."""

    def test_read_only_input(self):
        """Versioned: a read-only input is accepted.  Legacy numpy refuses
        the export, and a DLPack-only module has no other backend."""
        vec = make_vec()
        vec.flags.writeable = False
        mods = make_mods()
        if _numpy_dlpack_versioned():
            c2py_vnorm_dlpack.vnorm(vec, mods)
            assert np.allclose(mods, np.linalg.norm(vec, axis=1))
        else:
            with pytest.raises(TypeError) as e:
                c2py_vnorm_dlpack.vnorm(vec, mods)
            assert "all backends exhausted" in str(e.value), e.value

    def test_read_only_output_rejected(self):
        """Versioned: the read-only flag raises ValueError, and that reason
        reaches the caller (the backend loop used to replace it with "all
        backends exhausted").  Legacy numpy refuses the export instead."""
        mods = make_mods()
        mods.flags.writeable = False
        if _numpy_dlpack_versioned():
            with pytest.raises(ValueError) as e:
                c2py_vnorm_dlpack.vnorm(make_vec(), mods)
            assert "read-only" in str(e.value), e.value
        else:
            with pytest.raises(TypeError) as e:
                c2py_vnorm_dlpack.vnorm(make_vec(), mods)
            assert "all backends exhausted" in str(e.value), e.value

    def test_legacy_producer_input_ok(self):
        """A legacy capsule is fine as an input (the numpy output needs a
        versioned capsule, which numpy < 2.1 cannot make)."""
        mods = make_mods()
        if _numpy_dlpack_versioned():
            c2py_vnorm_dlpack.vnorm(_LegacyDLPack(make_vec()), mods)
            assert np.allclose(mods, np.linalg.norm(make_vec(), axis=1))
        else:
            with pytest.raises(TypeError) as e:
                c2py_vnorm_dlpack.vnorm(_LegacyDLPack(make_vec()), mods)
            assert "all backends exhausted" in str(e.value), e.value

    def test_legacy_producer_never_written(self):
        """A legacy capsule cannot say whether writes are allowed: decline
        (as np.from_dlpack makes it read-only)."""
        with pytest.raises(TypeError) as e:
            c2py_vnorm_dlpack.vnorm(make_vec(), _LegacyDLPack(make_mods()))
        assert "all backends exhausted" in str(e.value), e.value

    def test_null_shape_rejected(self):
        with pytest.raises(ValueError) as e:
            c2py_vnorm_dlpack.vnorm(_RawDLPack(ndim=2), make_mods())
        assert "shape is NULL" in str(e.value), e.value

    def test_negative_ndim_rejected(self):
        with pytest.raises(ValueError) as e:
            c2py_vnorm_dlpack.vnorm(_RawDLPack(ndim=-1), make_mods())
        assert "ndim out of range" in str(e.value), e.value

    def test_negative_byte_offset_rejected(self):
        with pytest.raises(ValueError) as e:
            c2py_vnorm_dlpack.vnorm(_RawDLPack(ndim=2, shape=[2, 3], byte_offset=-8), make_mods())
        assert "offset" in str(e.value), e.value

    def test_null_data_rejected(self):
        with pytest.raises(ValueError) as e:
            c2py_vnorm_dlpack.vnorm(_RawDLPack(ndim=2, shape=[2, 3], data=0), make_mods())
        assert "NULL data" in str(e.value), e.value

    def test_well_formed_raw_capsule_works(self):
        """Control: the same hand-built capsule, well formed, is accepted
        as an input (the numpy output needs a versioned capsule)."""
        raw = _RawDLPack(ndim=2, shape=[2, 3])
        for i, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]):
            raw.store[i] = v
        mods = make_mods()
        if _numpy_dlpack_versioned():
            c2py_vnorm_dlpack.vnorm(raw, mods)
            assert np.allclose(mods, np.linalg.norm(make_vec(), axis=1))
        else:
            with pytest.raises(TypeError):
                c2py_vnorm_dlpack.vnorm(raw, mods)

    def test_versioned_output_written(self):
        """A writable numpy output goes through a versioned capsule; numpy
        < 2.1 has only legacy capsules, which are declined."""
        mods = make_mods()
        if _numpy_dlpack_versioned():
            c2py_vnorm_dlpack.vnorm(make_vec(), mods)
            assert np.allclose(mods, np.linalg.norm(make_vec(), axis=1))
        else:
            with pytest.raises(TypeError) as e:
                c2py_vnorm_dlpack.vnorm(make_vec(), mods)
            assert "all backends exhausted" in str(e.value), e.value


@needs_modules
class TestComplexRejection:
    """Complex types are intentionally unsupported (docs/design.md #53).
    numpy exports complex128 as PEP 3118 "Zd"; a last-character format
    match accepted it as 'd' and read half the data.  Every backend must
    reject it; callers pass interleaved pairs via .view(np.float64)."""

    def _vec(self):
        return make_vec().astype("c16")

    def test_buffer_backend_rejects_complex(self):
        with pytest.raises(ValueError):
            c2py_vnorm_buffer.vnorm(self._vec(), make_mods())

    def test_ndarray_backend_rejects_complex(self):
        with pytest.raises(Exception):
            c2py_vnorm_ndarray.vnorm(self._vec(), make_mods())

    def test_default_backend_rejects_complex(self):
        with pytest.raises(ValueError):
            c2py_vnorm.vnorm(self._vec(), make_mods())

    def test_struct_and_repeat_formats_rejected(self):
        """A structured dtype of two doubles exports "T{d:a:d:b:}"-style
        formats; it must not match 'd' either."""
        rec = np.zeros((2, 3), dtype=[("re", "f8"), ("im", "f8")])
        with pytest.raises(ValueError):
            c2py_vnorm_buffer.vnorm(rec, make_mods())


def test_dlpack_abi():
    """Verify DLPack struct layouts match expectations (compile-time)."""
    import subprocess
    import os

    script_dir = os.path.dirname(__file__)
    src = os.path.join(script_dir, "check_dlpack_abi.c")
    if not os.path.exists(src):
        pytest.skip("check_dlpack_abi.c not found")
    out = "/tmp/check_dlpack_abi_test"
    devnull = open(os.devnull, "w")
    result = subprocess.call(
        ["gcc", "-std=c99", "-Wall", src, "-o", out],
        stdout=devnull,
        stderr=devnull,
    )
    devnull.close()
    if result != 0:
        pytest.skip("cannot compile check_dlpack_abi.c")
    proc = subprocess.Popen([out], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, _ = proc.communicate()
    stdout_str = stdout.decode() if isinstance(stdout, bytes) else stdout
    assert "DLPACK_ABI_OK 1" in stdout_str, "DLPack ABI check failed"


def test_numpy_abi():
    """Verify NumPy ndarray struct layouts match the runtime's offsets.

    Built from sysconfig (python-config is often absent, e.g. in CI), so
    it runs wherever there is a C compiler and the Python headers --
    including free-threaded builds, whose larger object header moves the
    descriptor and tp_name offsets."""
    import subprocess
    import sysconfig
    import tempfile
    import shutil

    if sys.platform == "win32":
        pytest.skip("check_numpy_abi.c embeds Python via gcc; Windows CI has MSVC only")
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_numpy_abi.c")
    # INCLUDEPY: distro-patched interpreters (Debian/Ubuntu 2.7) report a
    # wrong get_paths()["include"] (/usr/local/...); INCLUDEPY is where
    # Python.h really is.
    include = sysconfig.get_config_var("INCLUDEPY") or sysconfig.get_paths()["include"]
    libdir = sysconfig.get_config_var("LIBDIR") or ""
    ldlib = sysconfig.get_config_var("LDLIBRARY") or ""
    if sysconfig.get_config_var("PYTHONFRAMEWORK") and ".framework" in ldlib:
        # macOS framework build: LDLIBRARY is Python.framework/Versions/X.Y/Python.
        # Link that file itself: "-framework Python" takes Versions/Current,
        # which is some other Python when several are installed (CI runners).
        link = [os.path.join(sysconfig.get_config_var("PYTHONFRAMEWORKPREFIX"), ldlib)]
    else:
        # libpython3.14t.so / libpython3.12.a / libpython3.12.dylib -> -lpython3.14t
        libname = ldlib[3:].split(".so")[0].split(".a")[0].split(".dylib")[0]
        link = ["-L" + libdir, "-Wl,-rpath," + libdir, "-l" + libname]
    extra = (sysconfig.get_config_var("LIBS") or "").split() + (sysconfig.get_config_var("SYSLIBS") or "").split()
    tmp = tempfile.mkdtemp()
    try:
        exe = os.path.join(tmp, "check_numpy_abi")
        cmd = [os.environ.get("CC", "gcc"), src, "-I" + include, "-I" + np.get_include(), "-o", exe] + link + extra
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.communicate()[0].decode("ascii", "replace")
        assert p.returncode == 0, "cannot compile check_numpy_abi.c:\n%s\n%s" % (" ".join(cmd), out)
        # The embedded interpreter must be this one: same prefix (an
        # interpreter outside the default prefix cannot find its stdlib
        # otherwise) and same path (numpy may be in the user site).
        env = dict(os.environ)
        env["PYTHONHOME"] = os.pathsep.join([sys.prefix, sys.exec_prefix])
        env["PYTHONPATH"] = os.pathsep.join(q for q in sys.path if q)
        p = subprocess.Popen([exe], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        out = p.communicate()[0].decode("ascii", "replace")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # The probe must have embedded this very interpreter (not another
    # libpython found by the linker); say so plainly if not.
    want = "PYVER " + sys.version.split()[0]
    assert want in out, "probe embedded a different Python (want %r):\n%s" % (want, out)
    assert "NUMPY_ABI_OK 1" in out, "NumPy ABI check failed:\n" + out
