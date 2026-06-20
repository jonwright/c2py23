"""Module lifecycle stress tests: re-import cycles, concurrent imports, subinterpreters.

These require built .so files (from run_tests.sh or manual c2py23 build).
"""
from __future__ import print_function

import sys
import os
import gc
import ctypes
import threading
import warnings

warnings.filterwarnings("ignore", message=".*API version mismatch.*")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CASES_DIR = os.path.join(SCRIPT_DIR, 'cases')


def _setup_mod_path(name):
    sys.path.insert(0, os.path.join(_CASES_DIR, name))


def _teardown_mod_path(name):
    p = os.path.join(_CASES_DIR, name)
    while p in sys.path:
        sys.path.remove(p)


def _reimport(name):
    """Delete, gc, and re-import a module. Returns the re-imported module."""
    if name in sys.modules:
        del sys.modules[name]
    gc.collect()
    gc.collect()
    mod = __import__(name)
    return mod


# ---- Task R: re-import cycle tests ----

def test_reimport_arraysum():
    """Import -> delete -> gc -> re-import x 10 cycles with call between each."""
    mod_name = 'arraysum'
    _setup_mod_path(mod_name)
    try:
        mod = __import__(mod_name)
        a = (ctypes.c_double * 4)(1, 2, 3, 4)
        b = (ctypes.c_double * 4)(5, 6, 7, 8)
        c = (ctypes.c_double * 4)(0, 0, 0, 0)

        for i in range(10):
            # Call before reimport
            result = mod.array_sum(a, b, c)
            assert result == 4, "arraysum result mismatch at cycle %d" % i

            # Re-import cycle
            mod = _reimport(mod_name)

        # Final call
        result = mod.array_sum(a, b, c)
        assert result == 4, "arraysum result mismatch after reimport"
        print("PASS: reimport_arraysum")
    finally:
        _teardown_mod_path(mod_name)


def test_reimport_fill():
    """Re-import a module with type dispatch (when: conditions)."""
    mod_name = 'fillmod'
    _setup_mod_path('fill')
    try:
        mod = __import__(mod_name)
        arr = (ctypes.c_float * 6)(0, 0, 0, 0, 0, 0)

        for i in range(10):
            mod.fill(arr, 42.0)
            for j in range(6):
                assert arr[j] == 42.0, "fill value mismatch at cycle %d" % i

            mod = _reimport(mod_name)

        print("PASS: reimport_fill")
    finally:
        _teardown_mod_path('fill')


def test_reimport_scalar_output():
    """Re-import a module with output scalars (outputs: syntax)."""
    mod_name = 'statmod'
    _setup_mod_path('scalar_output')
    try:
        mod = __import__(mod_name)
        data = (ctypes.c_double * 5)(3.0, 1.0, 4.0, 1.0, 5.0)

        for i in range(10):
            result = mod.stats(data)
            assert len(result) == 2, "Expected 2-element tuple, got %s" % str(result)

            mod = _reimport(mod_name)

        result = mod.stats(data)
        assert len(result) == 2
        print("PASS: reimport_scalar_output")
    finally:
        _teardown_mod_path('scalar_output')


# ---- Task S: concurrent import tests ----

def test_concurrent_import_arraysum():
    """Multiple threads importing the same module simultaneously."""
    mod_name = 'arraysum'
    _setup_mod_path(mod_name)
    try:
        n_threads = 10
        results = {}
        errors = {}
        lock = threading.Lock()

        def worker(tid):
            try:
                mod = __import__(mod_name)
                a = (ctypes.c_double * 2)(1, 2)
                b = (ctypes.c_double * 2)(3, 4)
                c = (ctypes.c_double * 2)(0, 0)
                r = mod.array_sum(a, b, c)
                with lock:
                    results[tid] = r
            except Exception as e:
                with lock:
                    errors[tid] = str(e)

        # Import first to trigger runtime init, then delete for concurrent reimport
        mod = __import__(mod_name)
        del sys.modules[mod_name]
        gc.collect()

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, "Concurrent import errors: %s" % errors
        for tid, r in results.items():
            assert r == 2, "Thread %d got wrong result %d" % (tid, r)

        print("PASS: concurrent_import_arraysum")
    finally:
        _teardown_mod_path(mod_name)


def test_concurrent_import_fill():
    """Concurrent import of a type-dispatch module from multiple threads."""
    mod_name = 'fillmod'
    _setup_mod_path('fill')
    try:
        n_threads = 10
        results = {}
        errors = {}
        lock = threading.Lock()

        def worker(tid):
            try:
                mod = __import__(mod_name)
                arr = (ctypes.c_float * 3)(0, 0, 0)
                mod.fill(arr, 99.0)
                with lock:
                    results[tid] = list(arr)
            except Exception as e:
                with lock:
                    errors[tid] = str(e)

        # Pre-import + delete for concurrent stress
        mod = __import__(mod_name)
        del sys.modules[mod_name]
        gc.collect()

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, "Concurrent fill import errors: %s" % errors
        for tid, vals in results.items():
            for v in vals:
                assert v == 99.0, "Thread %d got wrong fill value" % tid

        print("PASS: concurrent_import_fill")
    finally:
        _teardown_mod_path('fill')


# ---- Task Q: subinterpreter test (Python 3.12+) ----

def test_subinterpreter_basic():
    """Verify that c2py23 modules report subinterpreter incompatibility (3.12+).

    Known limitation: the nimpy-style extension loading bypasses normal
    extension module mechanics (no Py_mod_multiple_interpreters slot),
    so c2py23 .so files cannot be imported in subinterpreters.

    This test documents the current behavior and will need updating
    if subinterpreter support is added in the future.
    """
    if sys.version_info < (3, 12):
        print("SKIP: subinterpreter_basic (requires Python 3.12+)")
        return

    try:
        import _xxsubinterpreters as _interpreters
    except ImportError:
        print("SKIP: subinterpreter_basic (_xxsubinterpreters not available)")
        return

    mod_name = 'arraysum'
    _setup_mod_path(mod_name)
    try:
        interpid = _interpreters.create()
        code = """
import sys
sys.path.insert(0, %r)
try:
    import arraysum
except ImportError as e:
    assert "does not support loading in subinterpreters" in str(e), (
        "Expected subinterpreter ImportError, got: %%s" %% e)
else:
    raise AssertionError("Expected ImportError for subinterpreter import")
""" % os.path.join(_CASES_DIR, mod_name)
        _interpreters.run_string(interpid, code)
        _interpreters.destroy(interpid)
        print("PASS: subinterpreter_basic")
    finally:
        _teardown_mod_path(mod_name)


def test_subinterpreter_multiple():
    """Multiple subinterpreters: each one should reject c2py23 import."""
    if sys.version_info < (3, 12):
        print("SKIP: subinterpreter_multiple (requires Python 3.12+)")
        return

    try:
        import _xxsubinterpreters as _interpreters
    except ImportError:
        print("SKIP: subinterpreter_multiple (_xxsubinterpreters not available)")
        return

    mod_name = 'arraysum'
    _setup_mod_path(mod_name)
    try:
        for _ in range(5):
            interpid = _interpreters.create()
            code = """
import sys
sys.path.insert(0, %r)
try:
    import arraysum
except ImportError as e:
    assert "does not support loading in subinterpreters" in str(e)
else:
    raise AssertionError("Expected ImportError for subinterpreter import")
""" % os.path.join(_CASES_DIR, mod_name)
            _interpreters.run_string(interpid, code)
            _interpreters.destroy(interpid)
        print("PASS: subinterpreter_multiple")
    finally:
        _teardown_mod_path(mod_name)


# ---- Task P: exception path stress tests ----

def test_exception_partial_buffer():
    """When acquisition of buffer 2/3 fails, verify buffer 1 is released."""
    sys.path.insert(0, os.path.join(_CASES_DIR, 'arraysum'))
    try:
        import arraysum
        a = (ctypes.c_double * 4)(1, 2, 3, 4)
        b = (ctypes.c_double * 4)(5, 6, 7, 8)
        c = (ctypes.c_float * 4)(0, 0, 0, 0)  # wrong format for c

        for i in range(100):
            try:
                arraysum.array_sum(a, b, c)
                assert False, "Should have raised ValueError"
            except ValueError:
                pass
        print("PASS: exception_partial_buffer")
    finally:
        sys.path.remove(os.path.join(_CASES_DIR, 'arraysum'))


def test_exception_overload_failure():
    """No overload matches -> default_raise or generic error."""
    sys.path.insert(0, os.path.join(_CASES_DIR, 'transform'))
    try:
        import xfrm
        # Pass 1D arrays to a function that only has 2D shape dispatch (N,3) or (3,N)
        arr = (ctypes.c_double * 6)(1, 2, 3, 4, 5, 6)
        out = (ctypes.c_double * 6)(0, 0, 0, 0, 0, 0)

        for i in range(100):
            try:
                xfrm.transform(arr, out)
                assert False, "Should have raised (no shape match for 1D)"
            except ValueError:
                pass
        print("PASS: exception_overload_failure")
    finally:
        sys.path.remove(os.path.join(_CASES_DIR, 'transform'))


def test_exception_alias_detection():
    """Writable buffer alias detection must be stable over repeated calls."""
    sys.path.insert(0, os.path.join(_CASES_DIR, 'arraysum'))
    try:
        import arraysum as m
        a = (ctypes.c_double * 4)(1, 2, 3, 4)

        for i in range(100):
            try:
                m.array_sum(a, a, a)  # all three buffers alias
                assert False, "Should have raised ValueError (alias)"
            except ValueError:
                pass
        print("PASS: exception_alias_detection")
    finally:
        sys.path.remove(os.path.join(_CASES_DIR, 'arraysum'))


# ---- Runner ----

if __name__ == '__main__':
    results = []
    for name in sorted(globals()):
        if name.startswith('test_'):
            try:
                globals()[name]()
                results.append(('PASS', name))
            except Exception as e:
                results.append(('FAIL', name + ': ' + str(e)))
                import traceback
                traceback.print_exc()

    passed = sum(1 for r, _ in results if r == 'PASS')
    total = len(results)
    print('\nResults: %d/%d passed' % (passed, total))
    sys.exit(0 if passed == total else 1)
