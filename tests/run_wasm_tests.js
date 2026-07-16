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

async function load_module(name) {
    const wasmPath = WASM_DIR + '/' + name + '.wasm';
    const pyPath = '/tmp/' + name + PYODIDE_SUFFIX;
    const wasm = fs.readFileSync(wasmPath);
    py.FS.writeFile(pyPath, wasm);
    await py.runPythonAsync('import importlib.machinery as _m; import importlib.util as _u; ' +
        '_l=_m.ExtensionFileLoader("' + name + '","' + pyPath + '");' +
        '_s=_u.spec_from_file_location("' + name + '","' + pyPath + '",loader=_l);' +
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
data = (ctypes.c_double * 5)(1,2,3,4,5)
r = optmod.process(data)
assert r == 1, str(r)
r2 = optmod.process(data, 2)
assert r2 == 2, str(r2)
r3 = optmod.process(data, 3, 1)
assert r3 == 3, str(r3)
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
data = (ctypes.c_double * 3)(1,2,3)
r = timedmod.wsum(data, 2.0)
assert abs(r - 12) < 0.001, str(r)
# timing attributes exist
assert hasattr(timedmod, '_c2py_perf_data')
`);
    ok('timing', 'weighted sum + perf attr');
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
buf = (ctypes.c_uint32 * 1)(123)
ptr = ctypes.addressof(buf)
r = addressmod.address_store(ptr, 99, 0)
assert r == 99, str(r)
`);
    ok('address', 'raw pointer pass-through');
}

async function test_array_sig() {
    await load_module('array_sig');
    await py_exec(`
import arraymod, ctypes
import sys

# sum_rows: (N,3) double
data = (ctypes.c_double * 6)(1,2,3,4,5,6)
if hasattr(ctypes, 'memoryview'):
    mv = memoryview(data).cast('d', (2, 3))
    r = arraymod.sum_rows(mv)
    assert abs(r - 21) < 0.001, 'sum_rows: ' + str(r)
else:
    r = arraymod.sum_rows(data)
    assert abs(r - 21) < 0.001, 'sum_rows: ' + str(r)

# sum_33: 3x3 double
data33 = (ctypes.c_double * 9)(1,1,1, 2,2,2, 3,3,3)
r2 = arraymod.sum_33(data33)
assert abs(r2 - 18) < 0.001, 'sum_33: ' + str(r2)

# sum_1d_fixed: 5 doubles
data5 = (ctypes.c_double * 5)(1,2,3,4,5)
r3 = arraymod.sum_1d_fixed(data5)
assert abs(r3 - 15) < 0.001, 'sum_1d_fixed: ' + str(r3)
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

// ---- Main runner ----

async function main() {
    console.log('Loading Pyodide...');
    py = await loadPyodide();
    console.log('Pyodide loaded.\n');

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
    ];

    for (const [name, fn] of tests) {
        console.log(name + '...');
        try {
            await fn();
        } catch (e) {
            const msg = e.message ? e.message.split('\n')[0] : String(e);
            fail(name, msg);
        }
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
