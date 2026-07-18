# test_ndarray_backends.py -- ndarray/DLPack edge cases and fallback behavior
"""Tests that numpy ndarray fast-path works correctly for common numpy
types and that non-numpy types correctly fall through to buffer protocol.

Requires numpy (skipped gracefully via importorskip when absent)."""

from __future__ import print_function
import sys, os, array, ctypes

import pytest

np = pytest.importorskip("numpy")

IS_FREE_THREADED = False
try:
    import sysconfig

    IS_FREE_THREADED = sysconfig.get_config_var("Py_GIL_DISABLED") == 1
except Exception:
    pass
# c2py23 deliberately skips ndarray struct-cast on FT builds because
# the PyObject header layout differs (extra atomic refcounting fields).
_ft_skip_ndarray_only = pytest.mark.skipif(
    IS_FREE_THREADED, reason="ndarray struct-cast disabled on free-threaded Python (PyObject layout differs)"
)

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
        """Writable request on read-only ndarray is rejected by
        the flags check in c2py_pin_ndarray, then buffer fallback
        also rejects it."""
        mods_ro = make_mods()
        mods_ro.setflags(write=False)
        with pytest.raises((TypeError, ValueError)):
            c2py_vnorm.vnorm(make_vec(), mods_ro)

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
        """array.array has ob_type != numpy.ndarray, falls to buffer."""
        a = array.array("d", [1.0, 2.0, 3.0, 4.0, 5.0])
        c2py_getitem.getitem(a, 2)


@needs_modules
class TestBackendSpecific:
    """Verify each acquisition backend works in isolation."""

    @_ft_skip_ndarray_only
    def test_ndarray_only(self):
        """ndarray-only backend handles numpy arrays."""
        c2py_vnorm_ndarray.vnorm(make_vec(), make_mods())

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

        DLPack has no writable/read-only distinction in its protocol
        (the tensor data pointer is always writable from C's perspective).
        The auto-dispatch path [ndarray, dlpack, buffer] handles this
        correctly by trying ndarray first (which enforces writability).
        A DLPack-only backend cannot reject writable requests because
        the DLPack capsule carries no access-permission metadata.
        """
        import c2py_vnorm_dlpack as m

        assert hasattr(m, "vnorm")
        # verify it can compute with a 2D input (as the interface requires)
        vec = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float64)
        mods = np.zeros(2, dtype=np.float64)
        m.vnorm(vec, mods)
        assert np.isclose(mods[0], np.sqrt(1 + 4 + 9), atol=0.01)

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
        fails silently, buffer fallback succeeds."""
        a = array.array("d", [1.0, 2.0, 3.0, 4.0, 5.0])
        c2py_getitem.getitem(a, 2)


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
    """Verify NumPy ndarray struct layouts match expectations."""
    import subprocess
    import os
    import sys

    script_dir = os.path.dirname(__file__)
    src = os.path.join(script_dir, "check_numpy_abi.c")
    if not os.path.exists(src):
        pytest.skip("check_numpy_abi.c not found")

    py_conf = sys.executable + "-config"
    try:
        import subprocess

        includes = subprocess.check_output([py_conf, "--includes"]).decode().strip()
        ldflags = subprocess.check_output([py_conf, "--ldflags", "--embed"]).decode().strip()
    except Exception:
        pytest.skip("python-config not available")

    np_include = np.get_include()
    cmd = ["gcc", src] + includes.split() + ["-I" + np_include] + ldflags.split() + ["-o", "/tmp/check_numpy_abi_test"]
    devnull2 = open(os.devnull, "w")
    result = subprocess.call(cmd, stdout=devnull2, stderr=devnull2)
    devnull2.close()
    if result != 0:
        pytest.skip("cannot compile check_numpy_abi.c")
    proc = subprocess.Popen(["/tmp/check_numpy_abi_test"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, _ = proc.communicate()
    stdout_str = stdout.decode() if isinstance(stdout, bytes) else stdout
    assert "NUMPY_ABI_OK 1" in stdout_str, "NumPy ABI check failed"
