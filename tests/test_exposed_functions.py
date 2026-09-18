"""Every Python function exposed by a generated c2py23 module must be
invocable without crashing, and each _variants_<name>() introspection
function must return the full, non-empty list of variant names.

Background: _variants_<name>() builds its result tuple with
PyBytes_FromStringAndSize, which resolves to NULL on Python 2.7 in dlsym
mode unless the runtime falls back to PyString_FromStringAndSize.  Before
that fallback was added, calling any _variants_<name>() segfaulted on
Python 2.7.  These tests call every exposed callable with no arguments on
every built module, so a NULL function pointer anywhere in the exposed API
kills the pytest process (signal 11) and fails CI instead of passing
silently.

Python 2.7 compatible.  Does not depend on numpy.
"""

from __future__ import print_function

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "cases")

IS_PY3 = sys.version_info[0] >= 3


def _case_modules():
    """Yield (directory, module_name) for each built test-case extension."""
    for pattern in ("*.so", "*.pyd"):
        for so in sorted(glob.glob(os.path.join(CASES, "*", pattern))):
            name = os.path.splitext(os.path.basename(so))[0]
            yield os.path.dirname(so), name


def _names(seq):
    """Normalise variant names to native str on both Python 2 and 3."""
    if IS_PY3:
        return [x.decode("ascii") if isinstance(x, bytes) else x for x in seq]
    return list(seq)


def test_variants_function_returns_backend_names():
    """The variants module's _variants_proc() must return both variant names.

    This is the exact path that segfaulted on Python 2.7 before the
    PyString_FromStringAndSize fallback was added to the runtime.
    """
    sys.path.insert(0, os.path.join(CASES, "variants"))
    import varcmod

    names = _names(varcmod._variants_proc())
    assert names == ["proc_a", "proc_b"], (
        "expected the two variant names, got %s" % (names,)
    )


def test_every_exposed_function_is_callable_without_crashing():
    """Call every zero-arg-callable exposed function on every built module.

    Functions that need arguments raise TypeError, which is expected and
    skipped.  A segfault (NULL function pointer) destroys the whole pytest
    process, so this single test guards the entire exposed API surface of
    every generated module.  Each _variants_<name>() must also actually
    return a non-empty sequence, not just fail to crash.
    """
    seen = 0
    exercised = 0
    for d, name in _case_modules():
        sys.path.insert(0, d)
        try:
            module = __import__(name)
        except ImportError:
            continue
        for attr in sorted(dir(module)):
            if attr.startswith("__"):
                continue
            obj = getattr(module, attr)
            if not callable(obj):
                continue
            seen += 1
            try:
                result = obj()
            except TypeError:
                # requires arguments -- not a zero-arg entry point
                continue
            except Exception as e:
                raise AssertionError(
                    "%s.%s() raised %s: %s" % (name, attr, type(e).__name__, e)
                )
            if attr.startswith("_variants_"):
                assert isinstance(result, (tuple, list)) and len(result) > 0, (
                    "%s.%s() must return a non-empty tuple/list, got %r"
                    % (name, attr, result)
                )
            exercised += 1
    assert seen > 0, "no exposed callables were found across test modules"
    assert exercised > 0, "no zero-arg-callable exposed function was exercised"
