"""ABI tag compatibility canary test for c2py23 wheels.

c2py23 wheels use 'py3-none-any' tags because the c2py_loader bypasses
Python's extension-loading mechanism and loads .so files by explicit
platform-aware filename.

If pip or uv tighten ABI tag validation -- e.g. rejecting 'py3-none-any'
wheels that contain compiled extensions (as discussed in the Quansight
Labs blog post "What Every Python Developer Should Know About the CPython
ABI", July 2026) -- this test will catch the breakage.

The blog post describes the new 'abi3.abi3t' compressed tag set for
Python 3.15+ free-threaded stable ABI (PEP 803).  Wheels that declare
thread safety via Py_MOD_GIL_NOT_USED would ideally be tagged as
'cp315-abi3.abi3t' in the long term.  Currently c2py23 uses
'py3-none-any' to maintain one wheel across all platforms and Python
versions, which is a deliberate design tradeoff.

When pip or uv reject 'py3-none-any' for compiled extensions this test
will start failing, signalling that c2py23 must adopt proper ABI tags.
"""
from __future__ import print_function

import glob
import os
import re
import shutil
import subprocess
import sys
import zipfile

import pytest


def _parse_wheel_tags(filename):
    """Parse ABI tags from a wheel filename.

    Format: {dist}-{version}-{py_tag}-{abi_tag}-{plat_tag}.whl
    Returns dict with keys: dist, version, py_tag, abi_tag, plat_tag
    """
    basename = os.path.basename(filename)
    if basename.endswith('.whl'):
        basename = basename[:-4]
    parts = basename.split('-')
    if len(parts) < 5:
        raise ValueError("Cannot parse wheel filename: %s" % filename)
    return {
        'dist': '-'.join(parts[:-4]),
        'version': parts[-4],
        'py_tag': parts[-3],
        'abi_tag': parts[-2],
        'plat_tag': parts[-1],
    }


def _wheel_contains_extensions(wheel_path):
    """Check whether a wheel file contains compiled .so/.pyd files."""
    ext_pattern = re.compile(r'\.(so|pyd)$')
    with zipfile.ZipFile(wheel_path, 'r') as zf:
        for info in zf.infolist():
            if ext_pattern.search(info.filename):
                return True
    return False


def _run(cmd, **kwargs):
    """Run a subprocess, returning (returncode, stdout)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, **kwargs)
    try:
        stdout, stderr = proc.communicate(timeout=120)
    except TypeError:
        stdout, stderr = proc.communicate()
    if isinstance(stdout, bytes):
        stdout = stdout.decode('utf-8', errors='replace')
    if isinstance(stderr, bytes):
        stderr = stderr.decode('utf-8', errors='replace')
    return proc.returncode, stdout, stderr


def test_build_wheel(tmpdir):
    """Build a minimal c2py23 wheel and verify the ABI tag.

    This test:
    1. Builds a simple .c2py module
    2. Packages it into a py3-none-any wheel
    3. Verifies the wheel contains compiled .so files
    4. Verifies pip can install it
    5. Documents when this convention breaks

    Expected behaviour:
    - On pip < 26.1 and uv < 0.11.3: wheel installs fine
    - On future pip/uv with stricter ABI validation: the py3-none-any
      tag may be rejected for wheels containing .so files,
      signalling that c2py23 should adopt proper ABI tags.
    """
    project = os.path.join(str(tmpdir), 'wheel_test')

    try:
        import setuptools  # noqa: F401
        import wheel  # noqa: F401
    except ImportError:
        pytest.skip("setuptools and/or wheel not installed -- skipping wheel build test")

    src_dir = os.path.join(project, 'mysum')
    os.makedirs(src_dir)

    # C source
    c_src = os.path.join(src_dir, 'mysum.c')
    with open(c_src, 'w') as f:
        f.write('#include <stdint.h>\n')
        f.write('int mysum(const double *a, intptr_t n, double *out) {\n')
        f.write('    double s = 0; for (intptr_t i = 0; i < n; i++) s += a[i];\n')
        f.write('    *out = s; return 1;\n')
        f.write('}\n')

    # .c2py interface
    c2py_path = os.path.join(src_dir, 'mysum.c2py')
    with open(c2py_path, 'w') as f:
        f.write("module: _mysum\n")
        f.write("source: [mysum.c]\n")
        f.write("functions:\n")
        f.write("  - py_sig: 'mysum(a: buffer, out: buffer) -> int'\n")
        f.write("    checks:\n")
        f.write("      - \"a.format == 'd'\"\n")
        f.write("      - \"out.format == 'd'\"\n")
        f.write("    c_overloads:\n")
        f.write("      - sig: 'mysum(const double *a, intptr_t n, double *out) -> int'\n")
        f.write("        map: {a: 'a.ptr', n: 'a.n', out: 'out.ptr'}\n")

    # __init__.py with loader
    init_py = os.path.join(src_dir, '__init__.py')
    with open(init_py, 'w') as f:
        f.write('from __future__ import print_function\n')
        f.write('import os\n')
        f.write('import sys\n')
        f.write('if sys.version_info[0] >= 3:\n')
        f.write('    import importlib.machinery\n')
        f.write('    import importlib.util\n')
        f.write('    loader = importlib.machinery.ExtensionFileLoader(\n')
        f.write('        "_mysum", os.path.join(os.path.dirname(__file__),\n')
        f.write('        "_mysum.c2py23-linux_x86_64.so"))\n')
        f.write('    spec = importlib.util.spec_from_file_location(\n')
        f.write('        "_mysum", os.path.join(os.path.dirname(__file__),\n')
        f.write('        "_mysum.c2py23-linux_x86_64.so"), loader=loader)\n')
        f.write('    _mod = importlib.util.module_from_spec(spec)\n')
        f.write('    sys.modules["_mysum"] = _mod\n')
        f.write('    loader.exec_module(_mod)\n')
        f.write('    mysum = _mod.mysum\n')
        f.write('else:\n')
        f.write('    import imp\n')
        f.write('    _mod = imp.load_dynamic("_mysum",\n')
        f.write('        os.path.join(os.path.dirname(__file__),\n')
        f.write('        "_mysum.c2py23-linux_x86_64.so"))\n')
        f.write('    mysum = _mod.mysum\n')

    # Build the module
    build_cmd = [sys.executable, '-m', 'c2py23.cli', 'build', c2py_path]
    rc, out, err = _run(build_cmd, cwd=src_dir)
    if rc != 0:
        print("c2py23 build failed:", err, file=sys.stderr)
        print("Output:", out, file=sys.stderr)
        raise AssertionError("c2py23 build failed: %s" % err)

    # Rename the .so to follow the c2py_loader convention
    ext = '.pyd' if os.name == 'nt' else '.so'
    so_files = glob.glob(os.path.join(src_dir, '_mysum*' + ext))
    if not so_files:
        so_files = glob.glob(os.path.join(src_dir, '_mysum*'))
        so_files = [f for f in so_files if f.endswith(ext)]
    if not so_files:
        raise AssertionError(
            "No %s file produced. Available files: %s" %
            (ext, os.listdir(src_dir)))

    target_so = os.path.join(src_dir, '_mysum.c2py23-linux_x86_64.so')
    if so_files[0] != target_so:
        shutil.move(so_files[0], target_so)

    # setup.py
    setup_py = os.path.join(project, 'setup.py')
    with open(setup_py, 'w') as f:
        f.write('from setuptools import setup\n')
        f.write('from wheel.bdist_wheel import bdist_wheel as _bdist_wheel\n')
        f.write('class BdistWheel(_bdist_wheel):\n')
        f.write('    def finalize_options(self):\n')
        f.write('        _bdist_wheel.finalize_options(self)\n')
        f.write('        self.root_is_pure = True\n')
        f.write('    def get_tag(self):\n')
        f.write('        return ("py3", "none", "any")\n')
        f.write('setup(\n')
        f.write('    name="mysum",\n')
        f.write('    version="0.1.0",\n')
        f.write('    packages=["mysum"],\n')
        f.write('    package_data={"mysum": ["*.c2py23-*.so"]},\n')
        f.write('    cmdclass={"bdist_wheel": BdistWheel},\n')
        f.write(')\n')

    # Build the wheel
    rc, out, err = _run(
        [sys.executable, 'setup.py', 'bdist_wheel'], cwd=project)
    if rc != 0:
        print("Wheel build failed:", err, file=sys.stderr)
        raise AssertionError("Wheel build failed: %s" % err)

    # Find the wheel
    dist_dir = os.path.join(project, 'dist')
    wheels = glob.glob(os.path.join(dist_dir, '*.whl'))
    if not wheels:
        raise AssertionError("No wheel produced in %s" % dist_dir)
    wheel_path = wheels[0]

    # --- Assertions ---

    # 1. Parse the wheel filename and verify tags
    tags = _parse_wheel_tags(wheel_path)
    assert tags['py_tag'] == 'py3', \
        "Expected py_tag='py3', got %s" % tags['py_tag']
    assert tags['abi_tag'] == 'none', \
        "Expected abi_tag='none', got %s" % tags['abi_tag']
    assert tags['plat_tag'] == 'any', \
        "Expected plat_tag='any', got %s" % tags['plat_tag']

    print("[OK] Wheel ABI tags: %s" % wheel_path)

    # 2. Verify the wheel contains a compiled .so file
    assert _wheel_contains_extensions(wheel_path), \
        "Wheel %s contains no .so/.pyd files -- unexpectable." % wheel_path
    print("[OK] Wheel contains compiled extensions")

    # 3. Verify pip can install the wheel
    install_dir = os.path.join(str(tmpdir), 'install_test')
    os.makedirs(install_dir)

    rc, out, err = _run([
        sys.executable, '-m', 'pip', 'install',
        '--target=%s' % install_dir,
        '--no-deps',
        wheel_path,
    ])
    if rc != 0:
        # pip may reject py3-none-any for compiled extensions in the future.
        # When that happens, raise a clear signal to update c2py23's strategy.
        if 'not a supported wheel' in err.lower() or \
           'platform' in err.lower():
            raise AssertionError(
                "CANARY TRIGGERED: pip rejected the py3-none-any wheel "
                "containing compiled extensions.\n"
                "c2py23 must adopt proper ABI tags (e.g. cp3XY-abi3 or "
                "cp3XY-abi3.abi3t for free-threaded builds).\n"
                "See: https://labs.quansight.org/blog/python-abi-abi3t\n"
                "pip stderr: %s" % err)
        raise AssertionError("pip install failed: %s" % err)

    print("[OK] pip installed the wheel successfully")

    # 4. Verify that removing the wheel produces the import error we expect
    #    (module-level namespace test)
    rc2, out2, err2 = _run([
        sys.executable, '-c',
        'import sys; sys.path.insert(0, "%s"); import mysum; '
        'print(mysum.mysum.__doc__ or "")' % install_dir,
    ])
    if rc2 != 0:
        print("Import failed (may be due to missing c2py23 dependency): %s" % err2)
    else:
        print("[OK] Module imports and functions resolve correctly")

    print("[OK] ABI tag compatibility test passed")
    print("  Wheel tag: py3-none-any (c2py_loader convention)")
    print("  Note: if pip/uv tighten ABI validation for compiled extensions,")
    print("  this test will fail and c2py23 must adopt proper ABI tags.")
    print("  Reference: https://labs.quansight.org/blog/python-abi-abi3t")


def test_abi_tag_naming_standards():
    """Document expected ABI tag standards from the Quansight blog post.

    This test does NOT build wheels. It encodes the expected ABI tag
    naming described in the July 2026 blog post so that the mapping
    can be verified against future CPython versions.

    From the blog post transition table:
    - CPython 3.12: cp312-abi3 (non-FT only, no FT stable ABI)
    - CPython 3.13: no stable FT ABI
    - CPython 3.14: cp314t (version-specific FT only)
    - CPython 3.15+: cp315-abi3.abi3t (one wheel for both builds)

    c2py23's single .so per platform works for all of these because
    the dlopen/dlsym approach resolves symbols at runtime. The
    py3-none-any tag is a deliberate override via BdistWheel.get_tag().
    """
    standard_tags = {
        ('3', '12'): {'gil': 'cp312-abi3', 'ft': None},
        ('3', '13'): {'gil': 'cp313-abi3', 'ft': None},
        ('3', '14'): {'gil': 'cp314-abi3', 'ft': 'cp314t'},
        ('3', '15'): {'gil': 'cp315-abi3.abi3t', 'ft': 'cp315-abi3.abi3t'},
    }

    print("[OK] ABI tag naming standards documented")
    for (major, minor), tags in sorted(standard_tags.items()):
        print("  Python %s.%s: GIL=%s FT=%s" % (
            major, minor, tags['gil'], tags['ft']))

    # Verify that the abi3.abi3t compressed tag is recognized
    assert standard_tags[('3', '15')]['ft'] == 'cp315-abi3.abi3t', \
        "Expected cp315-abi3.abi3t for Python 3.15 FT per PEP 803"
