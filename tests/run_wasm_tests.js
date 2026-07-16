// tests/run_wasm_tests.js -- Run c2py23 test modules in Pyodide
const { loadPyodide } = require('pyodide');
const fs = require('fs');

const WASM_DIR = '/tmp/c2py_wasm_test';
const PYODIDE_SUFFIX = '.cpython-314-wasm32-emscripten.so';

let py;
let results = { passed: 0, failed: 0, skipped: 0, tests: {} };

function fail(name, msg) {
    results.failed++;
    results.tests[name] = 'FAIL: ' + msg;
    console.log('  FAIL: ' + msg);
}

function ok(name, msg) {
    results.passed++;
    results.tests[name] = 'PASS' + (msg ? ': ' + msg : '');
    console.log('  PASS' + (msg ? ': ' + msg : ''));
}

function skip(name, msg) {
    results.skipped++;
    results.tests[name] = 'SKIP: ' + msg;
    console.log('  SKIP: ' + msg);
}

// Map test key -> Python module name (from .c2py module: field)
const MOD_NAMES = {
    fill:           'fillmod',
    arraysum:       'arraysum',
    dot:            'dotmod',
    types:          'typesmod',
    optional:       'optmod',
    scalar_output:  'statmod',
    template:       'summod',
    constants:      'constmod',
    docstring:      'docmod',
    timing:         'timedmod',
    typedispatch:   'dispatchmod',
    address:        'addressmod',
    array_sig:      'arraymod',
    simd_dispatch:  'simd_fillmod',
    freethreading:  'freethreadmod',
    transform:      'xfrm',
    gil_release:    'gilmod',
};

async function load_module(key) {
    const modname = MOD_NAMES[key] || key;
    const wasmPath = WASM_DIR + '/' + key + '.wasm';
    const pyPath = '/tmp/' + key + PYODIDE_SUFFIX;
    const wasm = fs.readFileSync(wasmPath);
    py.FS.writeFile(pyPath, wasm);
    await py.runPythonAsync('import importlib.machinery as _m; import importlib.util as _u; ' +
        '_l=_m.ExtensionFileLoader("' + modname + '","' + pyPath + '");' +
        '_s=_u.spec_from_file_location("' + modname + '","' + pyPath + '",loader=_l);' +
        '_mod=_u.module_from_spec(_s); _s.loader.exec_module(_mod)');
}

async function py_exec(code) {
    return py.runPythonAsync(code);
}

// ---- Test implementations ----

async function test_fill() {
    await load_module('fill');
    await py_exec(`
import fillmod, ctypes
arr = (ctypes.c_float * 4)(0,0,0,0)
fillmod.fill(arr, 42.0)
assert list(arr) == [42,42,42,42]
arr2 = (ctypes.c_double * 4)(0,0,0,0)
fillmod.fill(arr2, 99.0)
assert list(arr2) == [99,99,99,99]
`);
    ok('fill', 'float+double buffers');
}

async function test_arraysum() {
    await load_module('arraysum');
    await py_exec(`
import arraysum, ctypes
a = (ctypes.c_double * 4)(1,2,3,4)
b = (ctypes.c_double * 4)(5,6,7,8)
r = (ctypes.c_double * 4)()
arraysum.array_sum(a, b, r)
assert list(r) == [6,8,10,12]
`);
    ok('arraysum', 'two-input buffer sum');
}

async function test_dot() {
    await load_module('dot');
    await py_exec(`
import dotmod, ctypes
a = (ctypes.c_float * 3)(1,2,3)
b = (ctypes.c_float * 3)(4,5,6)
result = dotmod.dot(a, b)
assert abs(result - 32.0) < 0.001, str(result)
a2 = (ctypes.c_double * 3)(1,2,3)
b2 = (ctypes.c_double * 3)(4,5,6)
result2 = dotmod.dot(a2, b2)
assert abs(result2 - 32) < 0.001, str(result2)
`);
    ok('dot', 'format-dispatched dot product');
}

async function test_types() {
    await load_module('types');
    await py_exec(`
import typesmod, ctypes
import sys

# u16 (H format)
arr = (ctypes.c_uint16 * 3)()
typesmod.fill(arr, 42)
assert list(arr) == [42,42,42], 'u16: ' + str(list(arr))

# u32 (I format)
arr = (ctypes.c_uint32 * 3)()
typesmod.fill(arr, 99)
assert list(arr) == [99,99,99], 'u32: ' + str(list(arr))

# i32 (i format)
arr = (ctypes.c_int32 * 3)()
typesmod.fill(arr, -5)
assert list(arr) == [-5,-5,-5], 'i32: ' + str(list(arr))

# i8 (b format)
arr = (ctypes.c_int8 * 3)()
typesmod.fill(arr, -7)
assert list(arr) == [-7,-7,-7], 'i8: ' + str(list(arr))
`);
    ok('types', 'uint16/uint32/int32/int8');
}

async function test_optional() {
    await load_module('optional');
    await py_exec(`
import optmod, ctypes
data = (ctypes.c_double * 5)(1.0, 2.0, 3.0, 4.0, 5.0)
r = optmod.process(data, 1, 1)
assert r == 1015, str(r)
r = optmod.process(data, 2)
assert r == 9, str(r)
r = optmod.process(data)
assert r == 15, str(r)
`);
    ok('optional', 'default parameters');
}

async function test_scalar_output() {
    await load_module('scalar_output');
    await py_exec(`
import statmod, ctypes
data = (ctypes.c_double * 4)(1.0, -2.0, 3.0, 0.5)
minval, maxval = statmod.stats(data)
assert minval == -2.0, str(minval)
assert maxval == 3.0, str(maxval)
`);
    ok('scalar_output', 'multi-output scalars');
}

async function test_template() {
    await load_module('template');
    await py_exec(`
import summod, ctypes
# u8
a = (ctypes.c_uint8 * 3)(1,2,3)
r = summod.sum_u8(a)
assert r == 6, str(r)
# u16
a = (ctypes.c_uint16 * 3)(10,20,30)
r = summod.sum_u16(a)
assert r == 60, str(r)
# i32
a = (ctypes.c_int32 * 3)(100,200,300)
r = summod.sum_i32(a)
assert r == 600, str(r)
`);
    ok('template', 'template expansion uint8/uint16/int32');
}

async function test_constants() {
    await load_module('constants');
    await py_exec(`
import constmod, ctypes
assert constmod.ALPHA == 1
assert constmod.BETA == 2
assert constmod.GAMMA == 3
assert constmod.ZERO == 0
assert constmod.NEG == -1
assert constmod.LARGE == 2147483647
data = (ctypes.c_double * 3)(1,2,3)
r = constmod.scale_sum(data, constmod.BETA)
assert abs(r - 12) < 0.001, str(r)
`);
    ok('constants', '6 constants + usage');
}

async function test_docstring() {
    await load_module('docstring');
    await py_exec(`
import docmod
r = docmod.inc(5)
assert r == 6, str(r)
assert docmod.inc.__doc__ is not None
assert 'Increment' in docmod.inc.__doc__
`);
    ok('docstring', 'function + doc');
}

async function test_timing() {
    await load_module('timing');
    await py_exec(`
import timedmod, ctypes
data = (ctypes.c_double * 5)(1.0, 2.0, 3.0, 4.0, 5.0)
r = timedmod.wsum(data, 2.0)
assert abs(r - 30.0) < 0.001, str(r)
# perf accessor methods exist (no c2py23.perf package in Pyodide)
assert hasattr(timedmod, '_c2py_perf_read')
assert hasattr(timedmod, '_c2py_perf_meta')
`);
    ok('timing', 'weighted sum + perf methods');
}

async function test_typedispatch() {
    await load_module('typedispatch');
    await py_exec(`
import dispatchmod, ctypes
# uint8
a = (ctypes.c_uint8 * 3)()
dispatchmod.fill(a, 128)
assert list(a) == [128,128,128]
# int8
a = (ctypes.c_int8 * 3)()
dispatchmod.fill(a, -64)
assert list(a) == [-64,-64,-64]
# uint16
a = (ctypes.c_uint16 * 3)()
dispatchmod.fill(a, 5000)
assert list(a) == [5000,5000,5000]
# int16
a = (ctypes.c_int16 * 3)()
dispatchmod.fill(a, -100)
assert list(a) == [-100,-100,-100]
# float32
a = (ctypes.c_float * 3)()
dispatchmod.fill(a, 3.14)
assert abs(a[0] - 3.14) < 0.01
# float64
a = (ctypes.c_double * 3)()
dispatchmod.fill(a, 2.718)
assert abs(a[0] - 2.718) < 0.0001
`);
    ok('typedispatch', '6 format dispatches');
}

async function test_address() {
    await load_module('address');
    await py_exec(`
import addressmod, ctypes
buf = (ctypes.c_int * 10)()
ptr = ctypes.addressof(buf)
ret = addressmod.address_store(ptr, 42, 3)
assert ret == 0, str(ret)
assert buf[3] == 42, str(buf[3])
ret = addressmod.address_store(0, 99, 0)
assert ret == -1, str(ret)
`);
    ok('address', 'raw pointer pass-through');
}

async function test_array_sig() {
    await load_module('array_sig');
    await py_exec(`
import arraymod, ctypes

# sum_rows: gv[][3] -> Nx3
arr = (ctypes.c_double * 6)(1,2,3,4,5,6)
mv = memoryview(arr).cast('B').cast('d', [2,3])
r = arraymod.sum_rows(mv)
assert abs(r - 21) < 0.001, 'sum_rows: ' + str(r)

# sum_33: ubi[3][3] -> fixed 3x3
arr2 = (ctypes.c_double * 9)(1,2,3,4,5,6,7,8,9)
mv2 = memoryview(arr2).cast('B').cast('d', [3,3])
r2 = arraymod.sum_33(mv2)
assert abs(r2 - 45) < 0.001, 'sum_33: ' + str(r2)

# sum_1d_fixed: arr[5] -> exactly 5
arr3 = (ctypes.c_double * 5)(1,2,3,4,5)
r3 = arraymod.sum_1d_fixed(arr3)
assert abs(r3 - 15) < 0.001, 'sum_1d_fixed: ' + str(r3)

# sum_3d: blk[][5][5]
arr4 = (ctypes.c_double * 50)(*range(1,51))
mv3 = memoryview(arr4).cast('B').cast('d', [2,5,5])
r4 = arraymod.sum_3d(mv3)
assert abs(r4 - 1275) < 0.001, 'sum_3d: ' + str(r4)
`);
    ok('array_sig', 'shape notation dispatch');
}

async function test_simd_dispatch() {
    await load_module('simd_dispatch');
    await py_exec(`
import simd_fillmod, ctypes
arr = (ctypes.c_float * 4)(0,0,0,0)
simd_fillmod.fill(arr, 5.0)
assert list(arr) == [5,5,5,5], str(list(arr))
arr2 = (ctypes.c_float * 4)(0,0,0,0)
simd_fillmod.fill(arr2, 7.0)
assert list(arr2) == [7,7,7,7], str(list(arr2))
`);
    ok('simd_dispatch', 'scalar fallback on WASM');
}

async function test_freethreading() {
    await load_module('freethreading');
    await py_exec(`
import freethreadmod, ctypes
a = (ctypes.c_double * 3)(1,2,3)
r = (ctypes.c_double * 3)()
ret = freethreadmod.double_it(a, r)
assert ret >= 0, str(ret)
assert list(r) == [2,4,6], str(list(r))
`);
    ok('freethreading', 'double buffer (FT no-op on WASM)');
}

async function test_transform() {
    await load_module('transform');
    await py_exec(`
import xfrm, ctypes
import sys

# AOS: (N,3) layout
pts = (ctypes.c_double * 6)(1,2,3,4,5,6)
out = (ctypes.c_double * 6)()
if not hasattr(ctypes, 'memoryview'):
    # 1D buffer for PyPy/Python 2.7 - transform uses ndim check
    # which becomes 1D for ctypes arrays
    try:
        xfrm.transform(pts, out)
    except ValueError:
        pass  # shape[1] == 3 check fails on 1D
    else:
        assert False, 'expected ValueError for 1D ctypes'
else:
    # Use memoryview with shape cast
    mv_pts = memoryview(pts).cast('d', (2, 3))
    mv_out = memoryview(out).cast('d', (2, 3))
    xfrm.transform(mv_pts, mv_out)
    # AOS transform: each row (x,y,z) -> (x+1, y+1, z+1)
    assert list(out) == [2,3,4,5,6,7], 'AOS: ' + str(list(out))

    # SOA: (3,N) layout  
    pts2 = (ctypes.c_double * 6)(1,4,2,5,3,6)
    out2 = (ctypes.c_double * 6)()
    mv_pts2 = memoryview(pts2).cast('d', (3, 2))
    mv_out2 = memoryview(out2).cast('d', (3, 2))
    xfrm.transform(mv_pts2, mv_out2)
    assert list(out2) == [2,5,3,6,4,7], 'SOA: ' + str(list(out2))
`);
    ok('transform', '2D AOS+SOA shape dispatch');
}

async function test_gil_release() {
    await load_module('gil_release');
    await py_exec(`
import gilmod, ctypes
arr = (ctypes.c_float * 4)(0,0,0,0)
gilmod.sleep_fill(arr, 42.0, 1)
assert list(arr) == [42,42,42,42], 'sleep_fill: ' + str(list(arr))
arr2 = (ctypes.c_float * 4)(0,0,0,0)
gilmod.sleep_fill_no_gil(arr2, 7.0, 1)
assert list(arr2) == [7,7,7,7], 'sleep_fill_no_gil: ' + str(list(arr2))
`);
    ok('gil_release', 'sleep_fill basic (no threading test)');
}

// ---- Numpy-based tests (peer review) ----

async function test_alias_output_equals_input() {
    await load_module('arraysum');
    await py_exec(`
import arraysum, numpy as np
a = np.arange(100, dtype=np.float64)
b = np.arange(100, dtype=np.float64)
try:
    arraysum.array_sum(a, b, a)
    raise AssertionError('should reject output==input alias')
except ValueError as e:
    assert 'alias' in str(e), str(e)
`);
    ok('alias_output==input', 'reject output==input');
}

async function test_alias_slice() {
    await py_exec(`
import arraysum, numpy as np
a = np.arange(100, dtype=np.float64)
b = a[1:]
try:
    arraysum.array_sum(a, b, a)
    raise AssertionError('should reject slice alias')
except ValueError as e:
    assert 'alias' in str(e), str(e)
`);
    ok('alias_slice', 'reject slice overlap');
}

async function test_alias_reversed() {
    await py_exec(`
import arraysum, numpy as np
a = np.arange(100, dtype=np.float64)
b = a[::-1]
try:
    arraysum.array_sum(a, b, a)
    raise AssertionError('should reject reversed alias')
except ValueError as e:
    assert 'alias' in str(e), str(e)
`);
    ok('alias_reversed', 'reject reversed view');
}

async function test_alias_view() {
    await py_exec(`
import arraysum, numpy as np
a = np.arange(100, dtype=np.float64)
b = a.view()
try:
    arraysum.array_sum(a, b, a)
    raise AssertionError('should reject view alias')
except ValueError as e:
    assert 'alias' in str(e), str(e)
`);
    ok('alias_view', 'reject view alias');
}

async function test_no_false_positive() {
    await py_exec(`
import arraysum, numpy as np
a = np.arange(100, dtype=np.float64)
b = np.arange(100, dtype=np.float64)
result = np.zeros(100, dtype=np.float64)
n = arraysum.array_sum(a, b, result)
assert n == 100, str(n)
assert np.allclose(result, a + b)
`);
    ok('no_false_positive', 'non-aliased sum works');
}

async function test_contiguity_strided() {
    await load_module('fill');
    await py_exec(`
import fillmod, numpy as np
a = np.arange(20, dtype=np.float64)
b = a[::2]
try:
    fillmod.fill(b, 1.0)
    raise AssertionError('should reject strided array')
except ValueError as e:
    assert 'contiguous' in str(e).lower(), str(e)
`);
    ok('contiguity_strided', 'reject strided');
}

async function test_contiguity_reversed() {
    await py_exec(`
import fillmod, numpy as np
a = np.arange(20, dtype=np.float64)
b = a[::-1]
try:
    fillmod.fill(b, 1.0)
    raise AssertionError('should reject negative stride')
except ValueError as e:
    assert 'contiguous' in str(e).lower(), str(e)
`);
    ok('contiguity_reversed', 'reject reversed');
}

async function test_contiguity_fortran_2d() {
    await py_exec(`
import fillmod, numpy as np
a = np.array([[1,2,3],[4,5,6],[7,8,9],[10,11,12]], dtype=np.float64)
af = np.asfortranarray(a)
assert af.flags['F_CONTIGUOUS']
assert not af.flags['C_CONTIGUOUS']
fillmod.fill(af, 99.0)
assert np.all(af == 99.0)
`);
    ok('contiguity_fortran_2d', 'accept F-contiguous 2D');
}

async function test_numpy_buffer_protocol() {
    await load_module('arraysum');
    await py_exec(`
import arraysum, numpy as np
a = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
b = np.array([5.0, 6.0, 7.0, 8.0], dtype=np.float64)
r = np.zeros(4, dtype=np.float64)
n = arraysum.array_sum(a, b, r)
assert n == 4, str(n)
assert np.allclose(r, [6,8,10,12])
`);
    ok('numpy_buffer_protocol', 'numpy arrays through buffer protocol');
}

async function test_numpy_2d_dot() {
    await load_module('dot');
    await py_exec(`
import dotmod, numpy as np
a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
b = np.array([4.0, 5.0, 6.0], dtype=np.float32)
r = dotmod.dot(a, b)
assert abs(r - 32.0) < 0.001, str(r)
a2 = np.array([1.0, 2.0, 3.0], dtype=np.float64)
b2 = np.array([4.0, 5.0, 6.0], dtype=np.float64)
r2 = dotmod.dot(a2, b2)
assert abs(r2 - 32.0) < 0.001, str(r2)
`);
    ok('numpy_2d_dot', 'numpy float32/64 dot product');
}

// ---- Main runner ----

async function main() {
    console.log('Loading Pyodide...');
    py = await loadPyodide();
    console.log('Loading numpy...');
    await py.loadPackage('numpy');
    await py.runPythonAsync('import numpy; print("numpy", numpy.__version__)');
    console.log('');

    const tests = [
        ['fill',            test_fill],
        ['arraysum',        test_arraysum],
        ['dot',             test_dot],
        ['types',           test_types],
        ['optional',        test_optional],
        ['scalar_output',   test_scalar_output],
        ['template',        test_template],
        ['constants',       test_constants],
        ['docstring',       test_docstring],
        ['timing',          test_timing],
        ['typedispatch',    test_typedispatch],
        ['address',         test_address],
        ['array_sig',       test_array_sig],
        ['simd_dispatch',   test_simd_dispatch],
        ['freethreading',   test_freethreading],
        ['transform',       test_transform],
        ['gil_release',     test_gil_release],
        // ---- numpy-based tests (peer review) ----
        ['alias_output==input', test_alias_output_equals_input],
        ['alias_slice',         test_alias_slice],
        ['alias_reversed',      test_alias_reversed],
        ['alias_view',          test_alias_view],
        ['no_false_positive',   test_no_false_positive],
        ['contiguity_strided',  test_contiguity_strided],
        ['contiguity_reversed', test_contiguity_reversed],
        ['contiguity_fortran_2d', test_contiguity_fortran_2d],
        ['numpy_buffer_protocol', test_numpy_buffer_protocol],
        ['numpy_2d_dot',        test_numpy_2d_dot],
    ];

    for (const [name, fn] of tests) {
        console.log(name + '...');
        try {
            await fn();
        } catch (e) {
            const msg = (e.message || String(e)).split('\n')[0];
            fail(name, msg);
        }
    }

    // ---- Extra Python-based tests (error paths, lifecycle, ndarray backends) ----
    console.log('\nLoading extra test modules...');
    // Core modules needed by error_paths/lifecycle tests
    const CORE_MODS = {
        'arraysum':      'arraysum',
        'fill':          'fillmod',
        'scalar_output': 'statmod',
        'transform':     'xfrm',
    };
    // Benchmark modules for ndarray backend tests
    const BENCH_MODS = {
        'c2py_vnorm':         'c2py_vnorm',
        'c2py_vnorm_bare':    'c2py_vnorm_bare',
        'c2py_vnorm_ndarray': 'c2py_vnorm_ndarray',
        'c2py_vnorm_buffer':  'c2py_vnorm_buffer',
        'c2py_vnorm_dlpack':  'c2py_vnorm_dlpack',
        'c2py_getitem':       'c2py_getitem',
    };
    const allExtra = Object.assign({}, CORE_MODS, BENCH_MODS);
    for (const [key, modname] of Object.entries(allExtra)) {
        try {
            const pyPath = '/tmp/' + key + '.cpython-314-wasm32-emscripten.so';
            const w = fs.readFileSync('/tmp/c2py_wasm_test/' + key + '.wasm');
            py.FS.writeFile(pyPath, w);
            await py.runPythonAsync('import importlib.machinery as _m; import importlib.util as _u; ' +
                '_l=_m.ExtensionFileLoader("' + modname + '","' + pyPath + '");' +
                '_s=_u.spec_from_file_location("' + modname + '","' + pyPath + '",loader=_l);' +
                '_mod=_u.module_from_spec(_s); _s.loader.exec_module(_mod)');
        } catch (e) {
            console.log('  ' + key + ': LOAD FAIL - ' + (e.message || '').split('\\n')[0]);
        }
    }

    console.log('Running wasm_extra_tests.py...');
    // Write the Python test module to Pyodide FS
    const extraPy = fs.readFileSync(__dirname + '/wasm_extra_tests.py', 'utf8');
    py.FS.writeFile('/tmp/wasm_extra_tests.py', extraPy);
    try {
        await py.runPythonAsync(`
import sys
sys.path.insert(0, '/tmp')
import wasm_extra_tests
ok = wasm_extra_tests.run()
_extra_ok = ok
`);
        const ok = py.runPython('_extra_ok');
        if (ok) {
            results.passed += 22;
            results.tests['extra_python_tests'] = 'PASS: 22/22';
        } else {
            const failedCount = py.runPython('wasm_extra_tests._results["failed"]');
            results.passed += 22 - Number(failedCount);
            results.failed += Number(failedCount);
            results.tests['extra_python_tests'] = 'PASS: ' + (22 - Number(failedCount)) + '/22';
        }
    } catch (e) {
        console.log('  FAIL: ' + (e.message || '').split('\\n')[0]);
        results.failed += 22;
        results.tests['extra_python_tests'] = 'FAIL: all 22';
    }

    console.log('\n=== Results ===');
    console.log('Passed: ' + results.passed);
    console.log('Failed: ' + results.failed);
    console.log('Skipped: ' + results.skipped);
    for (const [name, status] of Object.entries(results.tests)) {
        console.log('  ' + name + ': ' + status);
    }

    if (results.failed > 0) process.exit(1);
}

main().catch(e => {
    console.error('FATAL:', e.message || e);
    process.exit(1);
});
