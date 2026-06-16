/* c2py_runtime.c - nimpy-style CPython API loader
 *
 * Uses dlopen(NULL, ...) + dlsym() to resolve all CPython C API
 * function pointers at module load time. This eliminates the need
 * to link against -lpython, allowing one .so to work across
 * Python 2.7 through 3.14.
 *
 * Compile: gcc -c c2py_runtime.c -o c2py_runtime.o
 * Link:    gcc -shared ... c2py_runtime.o -ldl -o module.so
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <sys/auxv.h>
#include "c2py_runtime.h"

/* Global API table */
c2py_api_t C2PY = {0};
static volatile int _c2py_runtime_initialized = 0;

/* ---- CPU feature flags (populated by _c2py_probe_cpu_features) ---- */

#ifdef __x86_64__
int c2py_amd64_mmx = 0;
int c2py_amd64_sse = 0;
int c2py_amd64_sse2 = 0;
int c2py_amd64_sse3 = 0;
int c2py_amd64_ssse3 = 0;
int c2py_amd64_sse4_1 = 0;
int c2py_amd64_sse4_2 = 0;
int c2py_amd64_avx = 0;
int c2py_amd64_avx2 = 0;
int c2py_amd64_fma = 0;
int c2py_amd64_avx512f = 0;
int c2py_amd64_avx512bw = 0;
int c2py_amd64_avx512dq = 0;
int c2py_amd64_avx512vl = 0;
int c2py_amd64_bmi1 = 0;
int c2py_amd64_bmi2 = 0;
int c2py_amd64_popcnt = 0;
int c2py_amd64_lzcnt = 0;
#endif

#if defined(__aarch64__) || defined(__arm64__)
int c2py_arm64_fp = 0;
int c2py_arm64_asimd = 0;
int c2py_arm64_aes = 0;
int c2py_arm64_pmull = 0;
int c2py_arm64_sha1 = 0;
int c2py_arm64_sha2 = 0;
int c2py_arm64_crc32 = 0;
int c2py_arm64_sve = 0;
int c2py_arm64_sve2 = 0;
#endif

#if defined(__powerpc64__) || defined(__powerpc__)
int c2py_ppc64_altivec = 0;
int c2py_ppc64_vsx = 0;
int c2py_ppc64_power8 = 0;
int c2py_ppc64_power9 = 0;
#endif

static int _resolve(void **ptr, const char *name)
{
    *ptr = dlsym(C2PY.dl_handle, name);
    if (*ptr == NULL) {
        /* Some symbols may legitimately not exist on old Python versions.
         * We only warn for critical ones. */
        return -1;
    }
    return 0;
}

#define RESOLVE(ptr, name) _resolve((void**)&(ptr), name)
#define RESOLVE_REQ(ptr, name) do { \
    if (_resolve((void**)&(ptr), name) != 0) { \
        fprintf(stderr, "c2py_runtime: FATAL - missing symbol: %s\n", name); \
        return -1; \
    } \
} while(0)

/* Python 2.7 module init helper */
static PyObject*
_init_module_2_7(const char *name, PyMethodDef *methods)
{
    void *dl = C2PY.dl_handle;

    /* Try Py_InitModule4 first (Python 2.7 preferred) */
    typedef PyObject* (*init4_fn)(const char*, PyMethodDef*, const char*,
                                   PyObject*, int);
    init4_fn fn4 = (init4_fn)dlsym(dl, "Py_InitModule4_64");
    if (fn4 == NULL) fn4 = (init4_fn)dlsym(dl, "Py_InitModule4");
    if (fn4 != NULL) {
        return fn4(name, methods, NULL, NULL, 1013 /* PYTHON_API_VERSION */);
    }

    /* Fallback: Py_InitModule3 */
    typedef PyObject* (*init3_fn)(const char*, PyMethodDef*, const char*);
    init3_fn fn3 = (init3_fn)dlsym(dl, "Py_InitModule3");
    if (fn3 != NULL) {
        return fn3(name, methods, NULL);
    }

    fprintf(stderr, "c2py_runtime: could not find module init function\n");
    return NULL;
}


/* ---- CPU feature probing ---- */

static void _c2py_probe_cpu_features(void)
{
#ifdef __x86_64__
    unsigned int eax1, ebx1, ecx1, edx1;
    unsigned int eax7, ebx7, ecx7, edx7;
    unsigned int eax81, ebx81, ecx81, edx81;

    /* Determine max standard leaf */
    __asm__ __volatile__("cpuid"
        : "=a"(eax1) : "a"(0) : "ebx", "ecx", "edx");
    unsigned int max_std = eax1;

    /* Leaf 1: baseline features */
    if (max_std >= 1) {
        __asm__ __volatile__("cpuid"
            : "=a"(eax1), "=b"(ebx1), "=c"(ecx1), "=d"(edx1)
            : "a"(1) : );
        c2py_amd64_mmx    = (edx1 >> 23) & 1;
        c2py_amd64_sse    = (edx1 >> 25) & 1;
        c2py_amd64_sse2   = (edx1 >> 26) & 1;
        c2py_amd64_sse3   = (ecx1 >>  0) & 1;
        c2py_amd64_ssse3  = (ecx1 >>  9) & 1;
        c2py_amd64_sse4_1 = (ecx1 >> 19) & 1;
        c2py_amd64_sse4_2 = (ecx1 >> 20) & 1;
        c2py_amd64_avx    = (ecx1 >> 28) & 1;
        c2py_amd64_fma    = (ecx1 >> 12) & 1;
        c2py_amd64_popcnt = (ecx1 >> 23) & 1;
    }

    /* Leaf 7, subleaf 0: extended features */
    if (max_std >= 7) {
        __asm__ __volatile__("cpuid"
            : "=a"(eax7), "=b"(ebx7), "=c"(ecx7), "=d"(edx7)
            : "a"(7), "c"(0));
        c2py_amd64_bmi1    = (ebx7 >>  3) & 1;
        c2py_amd64_avx2    = (ebx7 >>  5) & 1;
        c2py_amd64_bmi2    = (ebx7 >>  8) & 1;
        c2py_amd64_avx512f = (ebx7 >> 16) & 1;
        c2py_amd64_avx512dq = (ebx7 >> 17) & 1;
        c2py_amd64_avx512bw = (ebx7 >> 30) & 1;
        c2py_amd64_avx512vl = (ebx7 >> 31) & 1;
    }

    /* Leaf 0x80000001: extended feature bits (LZCNT) */
    /* Check extended leaf max first */
    __asm__ __volatile__("cpuid"
        : "=a"(eax81) : "a"(0x80000000) : "ebx", "ecx", "edx");
    if (eax81 >= 0x80000001) {
        __asm__ __volatile__("cpuid"
            : "=a"(eax81), "=b"(ebx81), "=c"(ecx81), "=d"(edx81)
            : "a"(0x80000001));
        c2py_amd64_lzcnt = (ecx81 >> 5) & 1;
    }
#endif

#if defined(__aarch64__) || defined(__arm64__)
    {
        unsigned long hwcap = getauxval(AT_HWCAP);
        unsigned long hwcap2 = getauxval(AT_HWCAP2);

        /* ARM64 HWCAP bits (stable kernel ABI) */
        c2py_arm64_fp    = (hwcap >> 0) & 1;
        c2py_arm64_asimd = (hwcap >> 1) & 1;
        c2py_arm64_aes   = (hwcap >> 3) & 1;
        c2py_arm64_pmull = (hwcap >> 4) & 1;
        c2py_arm64_sha1  = (hwcap >> 5) & 1;
        c2py_arm64_sha2  = (hwcap >> 6) & 1;
        c2py_arm64_crc32 = (hwcap >> 7) & 1;
        c2py_arm64_sve   = (hwcap >> 22) & 1;
        c2py_arm64_sve2  = (hwcap2 >> 1) & 1;
    }
#endif

#if defined(__powerpc64__) || defined(__powerpc__)
    {
        unsigned long hwcap = getauxval(AT_HWCAP);
        unsigned long hwcap2 = getauxval(AT_HWCAP2);

        c2py_ppc64_altivec = (hwcap >> 28) & 1;        /* PPC_FEATURE_HAS_ALTIVEC = 0x10000000 */
        c2py_ppc64_vsx     = (hwcap >>  7) & 1;         /* PPC_FEATURE_HAS_VSX     = 0x00000080 */
        c2py_ppc64_power8  = (hwcap2 >> 31) & 1;        /* PPC_FEATURE2_ARCH_2_07  = 0x80000000 */
        c2py_ppc64_power9  = (hwcap2 >> 23) & 1;        /* PPC_FEATURE2_ARCH_3_00  = 0x00800000 */
    }
#endif
}


int c2py_runtime_init(void)
{
    if (_c2py_runtime_initialized) {
        return 0; /* Already initialized */
    }

    /* CPU feature probing runs first -- does not depend on Python */
    _c2py_probe_cpu_features();

    C2PY.dl_handle = dlopen(NULL, RTLD_LAZY | RTLD_GLOBAL);
    if (C2PY.dl_handle == NULL) {
        fprintf(stderr, "c2py_runtime: dlopen(NULL) failed: %s\n", dlerror());
        fprintf(stderr, "c2py_runtime: interpreter may be statically linked "
                "(requires --enable-shared or export-dynamic).\n");
        return -1;
    }

    void *dl = C2PY.dl_handle;

    /* --- Detect Python version --- */
    {
        typedef const char* (*ver_fn)(void);
        ver_fn getver = (ver_fn)dlsym(dl, "Py_GetVersion");
        if (getver) {
            const char *v = getver();
            if (v) sscanf(v, "%d.%d", &C2PY.version_major, &C2PY.version_minor);
        }
        if (C2PY.version_major == 0) {
            /* Fallback: check for Py3-only symbol */
            if (dlsym(dl, "PyModule_Create2")) {
                C2PY.version_major = 3;
            } else {
                C2PY.version_major = 2;
            }
            C2PY.version_minor = 0;
        }
    }

    /* --- Detect free-threaded build ---
     * The version string on free-threaded builds contains "free-threading".
     * We also verify with Py_IncRef existence (free-threaded builds must
     * export Py_IncRef for atomic refcount operations).
     */
    {
        typedef const char* (*ver_fn)(void);
        ver_fn getver = (ver_fn)dlsym(dl, "Py_GetVersion");
        const char *vstr = getver ? getver() : "";
        C2PY.is_free_threaded = (vstr && strstr(vstr, "free-threading") != NULL);
    }

    /* --- Set ABI layout --- */
    if (C2PY.is_free_threaded) {
        /* Free-threaded PyObject layout (32 bytes LP64):
         *   ob_tid:0 ob_flags:8 ob_mutex:10 ob_gc_bits:11
         *   ob_ref_local:12 ob_ref_shared:16 ob_type:24 */
        C2PY.pyobject_size = 32;
        C2PY.ob_refcnt_offset = 16;  /* ob_ref_shared */
    } else {
        /* Standard GIL-enabled PyObject layout (16 bytes LP64):
         *   ob_refcnt:0 ob_type:8 */
        C2PY.pyobject_size = 16;
        C2PY.ob_refcnt_offset = 0;   /* ob_refcnt */
    }
    C2PY.pyobject_size_ft = 32;

    /* pymoduledef_max_size: pad generously for both layouts */
    {
        Py_ssize_t sz_gil = sizeof(PyModuleDef);
        Py_ssize_t sz_ft  = sizeof(PyModuleDef_FT);
        C2PY.pymoduledef_max_size = (sz_gil > sz_ft) ? sz_gil : sz_ft;
    }

    /* --- Buffer protocol (required) --- */
    RESOLVE_REQ(C2PY.GetBuffer, "PyObject_GetBuffer");
    RESOLVE_REQ(C2PY.ReleaseBuffer, "PyBuffer_Release");

    /* --- Old buffer protocol (Python 2.x only) --- */
    C2PY.AsReadBuffer = (int (*)(PyObject*, const void**, Py_ssize_t*))
        dlsym(dl, "PyObject_AsReadBuffer");
    C2PY.AsWriteBuffer = (int (*)(PyObject*, void**, Py_ssize_t*))
        dlsym(dl, "PyObject_AsWriteBuffer");
    C2PY.Err_Clear = (void (*)(void))dlsym(dl, "PyErr_Clear");
    RESOLVE_REQ(C2PY.Err_Clear, "PyErr_Clear");
    C2PY.buffer_api_is_pep3118 = (C2PY.version_major >= 3);

    /* --- Buffer struct size ---
     * CPython 2.x has Py_buffer.smalltable[2] (96 bytes LP64).
     * CPython 3.x dropped smalltable; Debian/Ubuntu builds from 3.6+
     * all have sizeof(Py_buffer)==80 (internal at offset 72).
     * Use 80 for all 3.x, 96 for 2.x, to match observed ABI.
     */
    C2PY.pybuffer_size = (C2PY.version_major >= 3)
        ? C2PY_PYBUFFER_SZ_POST312 : C2PY_PYBUFFER_SZ_PRE312;

    /* --- Fastcall support (METH_FASTCALL stable ABI since 3.12) --- */
    C2PY.use_fastcall = (C2PY.version_major >= 3 && C2PY.version_minor >= 12);

    /* --- Argument parsing (required) --- */
    RESOLVE_REQ(C2PY.ParseTuple, "PyArg_ParseTuple");
    RESOLVE(C2PY.ParseTupleAndKeywords, "PyArg_ParseTupleAndKeywords");

    /* --- Error detection for fastcall scalar conversion --- */
    RESOLVE_REQ(C2PY.Err_Occurred, "PyErr_Occurred");

    /* --- Value construction (required) --- */
    RESOLVE_REQ(C2PY.Long_FromLong, "PyLong_FromLong");
    RESOLVE(C2PY.Long_FromLongLong, "PyLong_FromLongLong");
    RESOLVE_REQ(C2PY.Float_FromDouble, "PyFloat_FromDouble");

    /* --- Tuple construction (required) --- */
    RESOLVE_REQ(C2PY.Tuple_New, "PyTuple_New");
    RESOLVE_REQ(C2PY.Tuple_SetItem, "PyTuple_SetItem");

    /* --- Scalar conversion --- */
    RESOLVE_REQ(C2PY.Long_AsLong, "PyLong_AsLong");
    RESOLVE_REQ(C2PY.Float_AsDouble, "PyFloat_AsDouble");

    /* --- Exception handling (required) --- */
    RESOLVE_REQ(C2PY.exc_TypeError, "PyExc_TypeError");
    RESOLVE_REQ(C2PY.exc_ValueError, "PyExc_ValueError");
    RESOLVE_REQ(C2PY.exc_RuntimeError, "PyExc_RuntimeError");
    RESOLVE_REQ(C2PY.exc_MemoryError, "PyExc_MemoryError");
    RESOLVE_REQ(C2PY.Err_SetString, "PyErr_SetString");
    RESOLVE_REQ(C2PY.Err_Format, "PyErr_Format");

    /* One dereference is always needed to reach the real PyObject*:
     * - Pre-3.12: PyExc_* are PyObject* globals (heap type pointers).
     *   dlsym gives &PyExc_ValueError (a PyObject**). Deref -> PyObject*.
     * - 3.12+: PyExc_* are static PyObjects with shared-refcount
     *   indirection.  dlsym gives &_PyExc_ValueError.  First 8 bytes
     *   point to the shared-refcount struct (the real PyObject*).
     *   Deref -> PyObject*.
     *
     * In both layouts a single dereference yields the PyObject* that
     * PyErr_SetString expects. */
    C2PY.exc_TypeError = *(void **)C2PY.exc_TypeError;
    C2PY.exc_ValueError = *(void **)C2PY.exc_ValueError;
    C2PY.exc_RuntimeError = *(void **)C2PY.exc_RuntimeError;
    C2PY.exc_MemoryError = *(void **)C2PY.exc_MemoryError;

    /* --- Module creation --- */
    {
        void *mc = dlsym(dl, "PyModule_Create2");
        C2PY.Module_Create2 = (PyObject* (*)(PyModuleDef*, int))mc;
    }
    C2PY.InitModule_2_7 = _init_module_2_7;

    /* --- Reference counting ---
     * Py_IncRef / Py_DecRef are stable-ABI functions added in Python 3.12.
     * On older interpreters these symbols may not be exported; fall back
     * through _Py_IncRef (internal name on some builds) to manual
     * increment of the ob_refcnt field (always the first member of
     * PyObject, matching our struct definition in c2py_runtime.h).
     *
     * On free-threaded builds, manual refcounting is UNSAFE (ob_ref_shared
     * requires atomic operations).  Py_IncRef/Py_DecRef MUST be resolved
     * or we fail init. */
    {
        if (_resolve((void**)&C2PY.IncRef, "Py_IncRef") != 0)
            _resolve((void**)&C2PY.IncRef, "_Py_IncRef");
        if (_resolve((void**)&C2PY.DecRef, "Py_DecRef") != 0)
            _resolve((void**)&C2PY.DecRef, "_Py_DecRef");

        if (C2PY.is_free_threaded) {
            if (C2PY.IncRef == NULL || C2PY.DecRef == NULL) {
                fprintf(stderr, "c2py_runtime: FATAL - free-threaded build "
                        "requires Py_IncRef / Py_DecRef symbols\n");
                return -1;
            }
        } else {
            if (C2PY.IncRef == NULL)
                C2PY.IncRef = _c2py_inc_ref_manual;
            if (C2PY.DecRef == NULL)
                C2PY.DecRef = _c2py_dec_ref_manual;
        }
    }

    /* --- Object attribute access --- */
    RESOLVE_REQ(C2PY.SetAttrString, "PyObject_SetAttrString");

    /* --- Pointer-to-int --- */
    RESOLVE_REQ(C2PY.Long_FromVoidPtr, "PyLong_FromVoidPtr");

    /* --- GIL management --- */
    RESOLVE_REQ(C2PY.SaveThread, "PyEval_SaveThread");
    RESOLVE_REQ(C2PY.RestoreThread, "PyEval_RestoreThread");

    /* --- None singleton ---
     * _Py_NoneStruct is a static PyObject; dlsym returns &_Py_NoneStruct,
     * which is the same as Py_None (the macro: (&_Py_NoneStruct)).
     * Py_None is immortal so INCREF/DECREF is unnecessary but harmless.
     */
    {
        void *none = dlsym(dl, "_Py_NoneStruct");
        if (none == NULL) {
            /* On some platforms Py_None is a pointer variable pointing
             * to the struct. Try loading it and dereferencing. */
            void **pnone = (void**)dlsym(dl, "Py_None");
            if (pnone) none = *pnone;
        }
        C2PY.none_obj = (PyObject*)none;
        if (C2PY.none_obj == NULL) {
            fprintf(stderr, "c2py_runtime: could not resolve Py_None\n");
            return -1;
        }
    }

    _c2py_runtime_initialized = 1;
    return 0;
}
