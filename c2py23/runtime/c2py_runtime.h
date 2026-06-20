/* c2py_runtime.h - nimpy-style CPython API loader
 *
 * This header NEVER includes <Python.h>. All Python API types and functions
 * are resolved at runtime via dlopen(NULL) + dlsym(). This means one .so
 * works on Python 2.7 through 3.14 without any compile-time Python dependency.
 *
 * The technique originates from yglukhov/nimpy (https://github.com/yglukhov/nimpy),
 * a Nim-Python bridge designed for ABI compatibility across Python versions.
 * c2py23 adapts it for C, using only the minimal CPython API surface needed.
 */

#ifndef C2PY_RUNTIME_H
#define C2PY_RUNTIME_H

#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
#include <time.h>
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* MSVC C mode does not recognise the inline keyword (C++ only).
 * __inline is the MSVC equivalent (also recognised by MinGW). */
#ifdef _MSC_VER
#define inline __inline
#endif

/* DLL export attribute for module init functions.
 * On Windows the PyInit_<name> symbol must be in the .pyd export
 * table or Python cannot load the module. */
#ifdef _WIN32
#define C2PY_EXPORT __declspec(dllexport)
#else
#define C2PY_EXPORT
#endif

/* ------------------------------------------------------------------ */
/* Py_ssize_t - must be defined before any struct using it            */
/* ------------------------------------------------------------------ */

#if defined(__LP64__) || defined(_WIN64)
typedef long long Py_ssize_t;
#else
typedef long Py_ssize_t;
#endif

/* sizeof(Py_buffer) differs across CPython versions:
 * < 3.12: includes smalltable[2]  (96 bytes LP64, 52 bytes ILP32)
 * >= 3.12: smalltable removed for PEP 697 stable ABI (80 / 44)
 */
#if defined(__LP64__) || defined(_WIN64)
#define C2PY_PYBUFFER_SZ_PRE312   96
#define C2PY_PYBUFFER_SZ_POST312  80
#else
#define C2PY_PYBUFFER_SZ_PRE312   52
#define C2PY_PYBUFFER_SZ_POST312  44
#endif

/* ------------------------------------------------------------------ */
/* CPython type definitions (stable layouts across versions)          */
/* ------------------------------------------------------------------ */

/* PyObject layout: differs between GIL-enabled and free-threaded builds.
 *
 * GIL-enabled (CPython 2.7 - 3.14 standard): 16 bytes LP64
 *   offset 0: Py_ssize_t ob_refcnt
 *   offset 8: void *ob_type
 *
 * Free-threaded (CPython 3.13t+ --disable-gil): 32 bytes LP64
 *   offset  0: uintptr_t ob_tid
 *   offset  8: uint16_t ob_flags
 *   offset 10: uint8_t  ob_mutex
 *   offset 11: uint8_t  ob_gc_bits
 *   offset 12: uint32_t ob_ref_local
 *   offset 16: Py_ssize_t ob_ref_shared   <-- external refcount
 *   offset 24: void *ob_type
 *
 * We define both layouts.  Generated code uses macros (C2PY_SET_MNAME,
 * C2PY_SET_MDOC, etc.) that work with either layout via C2PY offsets.
 */

/* GIL-enabled PyObject layout (standard CPython) */
typedef struct _c2py_object {
    Py_ssize_t ob_refcnt;
    void *ob_type;
} PyObject;

/* Free-threaded PyObject layout (CPython --disable-gil) */
/* PyMutex: per-object lock, uint8_t with two-bit state (private) */
typedef struct { uint8_t _bits; } PyMutex;

typedef struct _c2py_object_ft {
    uintptr_t ob_tid;
    uint16_t ob_flags;
    PyMutex ob_mutex;
    uint8_t ob_gc_bits;
    uint32_t ob_ref_local;
    Py_ssize_t ob_ref_shared;
    void *ob_type;
} PyObject_FT;

/* Shorthand for embedding PyObject at the head of a struct (GIL layout) */
#define PyObject_HEAD \
    Py_ssize_t ob_refcnt; \
    void *ob_type;

typedef void *(*PyCFunction)(PyObject*, PyObject*);

/* Py_buffer: stable since Python 2.6 (PEP 3118).
 * NOTE: includes smalltable[2] field present in CPython 2.7-3.11.
 * In CPython 3.12+ this was removed (PEP 697 stable ABI);
 * we use C2PY.pybuffer_size (set at init) for correct sizeof.
 */
typedef struct {
    void *buf;
    PyObject *obj;
    Py_ssize_t len;
    Py_ssize_t itemsize;
    int readonly;
    int ndim;
    char *format;
    Py_ssize_t *shape;
    Py_ssize_t *strides;
    Py_ssize_t *suboffsets;
    Py_ssize_t smalltable[2];  /* present on CPython 2.7-3.11 */
    void *internal;
} Py_buffer;

/* PyMethodDef: stable layout across all Python versions */
typedef struct {
    const char *ml_name;
    PyCFunction ml_meth;
    int ml_flags;
    const char *ml_doc;
} PyMethodDef;

/* PyModuleDef_Base: standard GIL-enabled layout (Python 3.0+) */
typedef struct PyModuleDef_Base {
    PyObject ob_base;
    PyObject *(*m_init)(void);
    Py_ssize_t m_index;
    PyObject *m_copy;
} PyModuleDef_Base;

/* PyModuleDef_Base for free-threaded builds (PyObject is 32 bytes) */
typedef struct PyModuleDef_Base_FT {
    PyObject_FT ob_base;
    PyObject *(*m_init)(void);
    Py_ssize_t m_index;
    PyObject *m_copy;
} PyModuleDef_Base_FT;

/* PyModuleDef for Python 3.x standard GIL layout */
typedef struct PyModuleDef {
    PyModuleDef_Base m_base;
    const char *m_name;
    const char *m_doc;
    Py_ssize_t m_size;
    PyMethodDef *m_methods;
    void *m_slots;
    void *m_traverse;
    void *m_clear;
    void *m_free;
} PyModuleDef;

/* PyModuleDef for free-threaded builds (PyModuleDef_Base is 56 bytes) */
typedef struct PyModuleDef_FT {
    PyModuleDef_Base_FT m_base;
    const char *m_name;
    const char *m_doc;
    Py_ssize_t m_size;
    PyMethodDef *m_methods;
    void *m_slots;
    void *m_traverse;
    void *m_clear;
    void *m_free;
} PyModuleDef_FT;

/* PyModuleDef_Slot: free-threading/extension slots (PEP 384, PEP 489) */
typedef struct {
    int slot;
    void *value;
} PyModuleDef_Slot;

/* Py_MOD_GIL_NOT_USED: signal that this module supports free-threading.
 * Value is (void*)1 = Py_MOD_GIL_NOT_USED (stable across CPython 3.13+).
 * The slot NUMBER (Py_mod_gil) changed from 4 (3.13-3.14) to 87 (3.15+).
 * That value is determined at runtime via C2PY.py_mod_gil_slot. */
#define Py_MOD_GIL_NOT_USED  ((void*)1)

/* ------------------------------------------------------------------ */
/* Constants                                                          */
/* ------------------------------------------------------------------ */

/* Py_buffer flags */
#define PyBUF_SIMPLE   0
#define PyBUF_WRITABLE 0x0001
#define PyBUF_FORMAT   0x0004
#define PyBUF_ND       0x0008
#define PyBUF_STRIDES  (0x0010 | PyBUF_ND)
#define PyBUF_INDIRECT (0x0100 | PyBUF_STRIDES)

/* PyMethodDef flags */
#define METH_VARARGS   0x0001
#define METH_KEYWORDS  0x0002
#define METH_NOARGS    0x0004
#define METH_O         0x0008
#define METH_CLASS     0x0010
#define METH_STATIC    0x0020
#define METH_FASTCALL  0x0080

/* Module init macro - initializes the PyModuleDef_Base embedded in PyModuleDef. */
#define PyModuleDef_HEAD_INIT { {1, NULL}, NULL, 0, NULL }

/* Module init macro for free-threaded builds (PyObject is 32 bytes).
 * ob_type = NULL, m_init = NULL, m_index = 0, m_copy = NULL.
 * ob_mutex is zeroed via {0} (PyMutex is struct { uint8_t _bits; }).
 * ob_flags = _Py_STATICALLY_ALLOCATED_FLAG (4), ob_ref_local =
 * _Py_IMMORTAL_REFCNT_LOCAL (UINT32_MAX), ob_ref_shared = 0.
 * These match the actual CPython 3.14t/3.15t PyModuleDef_HEAD_INIT(NULL)
 * expansion.  Earlier versions used 0/0/1 which 3.14t tolerated but 3.15t
 * hard-rejects. */
#define _Py_STATICALLY_ALLOCATED_FLAG (1 << 2)
#define _Py_IMMORTAL_REFCNT_LOCAL     0xFFFFFFFFU
#define PyModuleDef_HEAD_INIT_FT \
    { {0, _Py_STATICALLY_ALLOCATED_FLAG, {0}, 0, \
       _Py_IMMORTAL_REFCNT_LOCAL, 0, NULL}, NULL, 0, NULL}

/* ------------------------------------------------------------------ */
/* Function pointer table - populated by c2py_runtime_init()          */
/* ------------------------------------------------------------------ */

typedef struct {
    void *dl_handle;
    int version_major;
    int version_minor;

    int use_fastcall;               /* 1 = use METH_FASTCALL wrappers (Python >= 3.12) */
    int is_free_threaded;           /* 1 = Python built with --disable-gil */
    Py_ssize_t pybuffer_size;      /* actual sizeof(Py_buffer) for this Python version */
    Py_ssize_t pyobject_size;      /* actual sizeof(PyObject) for this Python version */
    Py_ssize_t pyobject_size_ft;   /* sizeof(PyObject) for free-threaded builds (32 LP64) */
    Py_ssize_t pymoduledef_max_size; /* max(sizeof(PyModuleDef), sizeof(PyModuleDef_FT)) */
    ptrdiff_t ob_refcnt_offset;    /* offset of ob_refcnt (or ob_ref_shared on FT) in PyObject */

    /* Buffer protocol */
    int (*GetBuffer)(PyObject*, Py_buffer*, int);
    void (*ReleaseBuffer)(Py_buffer*);

    /* Old buffer protocol (Python 2.x only, NULL on Python 3) */
    int (*AsReadBuffer)(PyObject*, const void**, Py_ssize_t*);
    int (*AsWriteBuffer)(PyObject*, void**, Py_ssize_t*);
    void (*Err_Clear)(void);
    int buffer_api_is_pep3118;  /* 0 = old API only, 1 = PEP 3118 available */

    /* Argument parsing */
    int (*ParseTuple)(PyObject*, const char*, ...);
    int (*ParseTupleAndKeywords)(PyObject*, PyObject*, const char*, char**, ...);

    /* Value construction */
    PyObject* (*Long_FromLong)(long);
    PyObject* (*Long_FromLongLong)(long long);
    PyObject* (*Long_FromUnsignedLongLong)(unsigned long long);
    PyObject* (*Float_FromDouble)(double);

    /* Tuple construction */
    PyObject* (*Tuple_New)(Py_ssize_t);
    int (*Tuple_SetItem)(PyObject*, Py_ssize_t, PyObject*);

    /* Scalar conversion from objects */
    long (*Long_AsLong)(PyObject*);
    long long (*Long_AsLongLong)(PyObject*);
    double (*Float_AsDouble)(PyObject*);

    /* Exception objects (pointers to the actual exception types) */
    void *exc_TypeError;
    void *exc_ValueError;
    void *exc_RuntimeError;
    void *exc_MemoryError;
    void (*Err_SetString)(PyObject*, const char*);
    PyObject* (*Err_Occurred)(void);
    PyObject* (*Err_Format)(PyObject*, const char*, ...);

    /* None singleton (immortal, INCREF/DECREF unnecessary) */
    PyObject *none_obj;

    /* Module creation */
    PyObject* (*Module_Create2)(PyModuleDef*, int);
    PyObject* (*InitModule_2_7)(const char*, PyMethodDef*);

    /* Reference counting */
    void (*IncRef)(PyObject*);
    void (*DecRef)(PyObject*);

    /* Object attribute access */
    int (*SetAttrString)(PyObject*, const char*, PyObject*);

    /* Pointer-to-int conversion (for exposing perf struct addresses) */
    PyObject* (*Long_FromVoidPtr)(void*);

    /* GIL management */
    void* (*SaveThread)(void);
    void (*RestoreThread)(void*);
    /* Free-threading: set Py_MOD_GIL_NOT_USED on module (optional, may be NULL) */
    void (*Unstable_Module_SetGIL)(PyObject*, void*);

} c2py_api_t;

/* The global API table */
extern c2py_api_t C2PY;

/* ------------------------------------------------------------------ */
/* Convenience macros                                                 */
/* ------------------------------------------------------------------ */

#define PyObject_GetBuffer(o, b, f)    C2PY.GetBuffer((PyObject*)(o), (b), (f))
#define PyBuffer_Release(b)            C2PY.ReleaseBuffer(b)

/* MSVC traditional preprocessor auto-removes the comma before an empty
 * __VA_ARGS__; GCC/Clang require the ## token-paste to do so. */
#ifdef _MSC_VER
#define PyArg_ParseTuple(a, f, ...)    C2PY.ParseTuple((PyObject*)(a), (f), __VA_ARGS__)
#define PyArg_ParseTupleAndKeywords(a, k, f, kw, ...) \
    C2PY.ParseTupleAndKeywords((PyObject*)(a), (PyObject*)(k), (f), (char**)(kw), __VA_ARGS__)
#define PyErr_Format(e, f, ...)        C2PY.Err_Format((PyObject*)(e), (f), __VA_ARGS__)
#else
#define PyArg_ParseTuple(a, f, ...)    C2PY.ParseTuple((PyObject*)(a), (f), ##__VA_ARGS__)
#define PyArg_ParseTupleAndKeywords(a, k, f, kw, ...) \
    C2PY.ParseTupleAndKeywords((PyObject*)(a), (PyObject*)(k), (f), (char**)(kw), ##__VA_ARGS__)
#define PyErr_Format(e, f, ...)        C2PY.Err_Format((PyObject*)(e), (f), ##__VA_ARGS__)
#endif

#define PyLong_FromLong(v)             C2PY.Long_FromLong(v)
#define PyLong_FromLongLong(v)         C2PY.Long_FromLongLong(v)
#define PyLong_FromUnsignedLongLong(v) C2PY.Long_FromUnsignedLongLong(v)
#define PyFloat_FromDouble(v)          C2PY.Float_FromDouble(v)
#define PyLong_AsLong(o)               C2PY.Long_AsLong((PyObject*)(o))
#define PyLong_AsLongLong(o)           C2PY.Long_AsLongLong((PyObject*)(o))
#define PyFloat_AsDouble(o)            C2PY.Float_AsDouble((PyObject*)(o))
#define PyErr_SetString(e, m)          C2PY.Err_SetString((PyObject*)(e), (m))
#define PyErr_Clear()                  C2PY.Err_Clear()
#define PyErr_Occurred()               C2PY.Err_Occurred()
#define Py_RETURN_NONE                 do { C2PY.IncRef(C2PY.none_obj); return C2PY.none_obj; } while(0)
#define Py_INCREF(o)                   C2PY.IncRef((PyObject*)(o))
#define Py_DECREF(o)                   C2PY.DecRef((PyObject*)(o))
#define PyObject_SetAttrString(o, n, v) C2PY.SetAttrString((PyObject*)(o), (n), (PyObject*)(v))
#define PyLong_FromVoidPtr(p)          C2PY.Long_FromVoidPtr((void*)(p))
#define PyTuple_New(s)                 C2PY.Tuple_New(s)
#define PyTuple_SetItem(t, i, o)       C2PY.Tuple_SetItem((PyObject*)(t), (i), (PyObject*)(o))
#define PyEval_SaveThread()            C2PY.SaveThread()
#define PyEval_RestoreThread(s)        C2PY.RestoreThread((void*)(s))

#define PyExc_TypeError                ((PyObject*)C2PY.exc_TypeError)
#define PyExc_ValueError               ((PyObject*)C2PY.exc_ValueError)
#define PyExc_RuntimeError             ((PyObject*)C2PY.exc_RuntimeError)
#define PyExc_MemoryError              ((PyObject*)C2PY.exc_MemoryError)

/* ------------------------------------------------------------------ */
/* Reference counting fallbacks (for CPython < 3.12 where Py_IncRef   */
/* is not an exported symbol)                                         */
/* ------------------------------------------------------------------ */

/* Manual refcount increment - accesses ob_refcnt via the correct offset
 * for the Python build (ob_refcnt on GIL, ob_ref_shared on free-threaded).
 * Safe on GIL-enabled builds where refcount is a simple Py_ssize_t field.
 * On free-threaded builds this fallback is UNSAFE (ob_ref_shared requires
 * atomic operations); always prefer Py_IncRef / Py_DecRef on 3.12+. */
static inline void _c2py_inc_ref_manual(PyObject *op)
{
    Py_ssize_t *refcnt = (Py_ssize_t*)((char*)op + C2PY.ob_refcnt_offset);
    ++(*refcnt);
}

/*
 * _c2py_dec_ref_manual: Fallback dec-ref for pre-3.12 Python where
 * Py_DecRef is not resolvable via dlsym. On those versions CPython uses
 * shared refcounts where zero-is-special does not apply -- refcounts
 * never reach zero through normal INCREF/DECREF alone.
 *
 * WARNING: This is a diagnostic-only fallback. When refcount hits zero
 * it prints a warning but does NOT call tp_dealloc destructor.
 * This is acceptable because the fallback is only active on Python < 3.12
 * where the zero-refcount invariant holds. If porting to a platform where
 * this invariant does not hold, implement proper deallocation.
 */
static inline void _c2py_dec_ref_manual(PyObject *op)
{
    Py_ssize_t *refcnt = (Py_ssize_t*)((char*)op + C2PY.ob_refcnt_offset);
    --(*refcnt);
    if (*refcnt == 0) {
        fprintf(stderr, "c2py_runtime: _c2py_dec_ref_manual reached zero "
                "refcount for %p -- possible leak\n", (void*)op);
    }
}

/* ------------------------------------------------------------------ */
/* Buffer acquisition helper with old-API fallback for Python 2.7     */
/* ------------------------------------------------------------------ */

/* Flags for c2py_acquire_buffer */
#define C2PY_BUF_READ   0
#define C2PY_BUF_WRITE  1

/* Returns 0 on success, -1 on failure (with Python exception set) */
static inline int
c2py_acquire_buffer(PyObject *obj, Py_buffer *buf, int want_writable)
{
    int flags = PyBUF_STRIDES | PyBUF_FORMAT;
    if (want_writable) flags |= PyBUF_WRITABLE;

    memset(buf, 0, C2PY.pybuffer_size);

    if (C2PY.buffer_api_is_pep3118) {
        return PyObject_GetBuffer(obj, buf, flags);
    }

    /* Python 2.7: try PEP 3118 first, fall back to old API */
    if (PyObject_GetBuffer(obj, buf, flags) == 0)
        return 0;

    PyErr_Clear();

    if (want_writable) {
        if (C2PY.AsWriteBuffer &&
            C2PY.AsWriteBuffer(obj, (void**)&buf->buf, &buf->len) == 0) {
            buf->readonly = 0;
        } else {
            return -1;
        }
    } else {
        if (C2PY.AsReadBuffer &&
            C2PY.AsReadBuffer(obj, (const void**)&buf->buf, &buf->len) == 0) {
            buf->readonly = 1;
        } else {
            return -1;
        }
    }

    buf->ndim = 1;
    buf->itemsize = 1;
    buf->format = NULL;
    buf->shape = NULL;
    buf->strides = NULL;
    return 0;
}

/* Release a buffer acquired by c2py_acquire_buffer */
static inline void
c2py_release_buffer(Py_buffer *buf)
{
    if (buf->obj != NULL) {
        PyBuffer_Release(buf);
    }
    /* Old buffer API (PyObject_AsRead/WriteBuffer) needs no release */
}

/* ------------------------------------------------------------------ */
/* Performance timing (optional, enabled via timing: true in .c2py)   */
/* ------------------------------------------------------------------ */

typedef struct {
    uint64_t call_count;

    uint64_t t_enter;          /* last call: wrapper entry */
    uint64_t t_pre_c;          /* last call: just before C code */
    uint64_t t_post_c;         /* last call: just after C returns */
    uint64_t t_exit;           /* last call: before return to Python */

    uint64_t t_c_min;          /* min C-call wall time (ns) */
    uint64_t t_c_max;          /* max C-call wall time (ns) */
    uint64_t t_c_total;        /* accumulated C wall time */

    uint64_t t_wrap_min;       /* min wrapper overhead (ns) */
    uint64_t t_wrap_max;       /* max wrapper overhead (ns) */
    uint64_t t_wrap_total;     /* accumulated wrapper overhead */

    int variant;               /* active variant index (0-based), -1 if unset */
    int group_idx;             /* active outer group index, -1 if flat */
    const char *variant_name;  /* points to static string, NULL if unset */
} c2py_perf_t;

/* Returns monotonic nanoseconds by default via clock_gettime().
 * Define -DC2PY_USE_CYCLE_COUNTER at build time to use the CPU's native
 * cycle counter instead (rdtsc on x86, CNTVCT_EL0 on aarch64, timebase
 * on POWER).  This gives lower overhead but returns platform-dependent
 * cycle counts, not nanoseconds.
 *
 * To convert cycle counter deltas to nanoseconds:
 *
 *     uint64_t delta_ns = c2py_ticks_to_ns(t2 - t1, freq_hz);
 *
 * Obtain the counter frequency (Hz) on your platform:
 *   x86:   CPUID leaf 0x15 (EBX/EAX * ECX), or /proc/cpuinfo "cpu MHz"
 *   ARM64: MRS CNTFRQ_EL0, or /sys/devices/system/cpu/cpu0/regs/identification/processor_frequency
 *   POWER: Read /proc/device-tree/cpus/timebase-frequency
 *
 * All tick calls are guarded by _c2py_do_time so there is zero cost
 * when --timing is not enabled in the .c2py interface.
 */
#if defined(C2PY_USE_CYCLE_COUNTER)
#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_IX86))
static inline uint64_t c2py_ticks(void) {
    return __rdtsc();
}
#elif defined(__x86_64__) || defined(__i386__)
static inline uint64_t c2py_ticks(void) {
    unsigned int lo, hi;
    __asm__ __volatile__("rdtsc" : "=a"(lo), "=d"(hi));
    return ((uint64_t)hi << 32) | lo;
}
#elif defined(__aarch64__)
static inline uint64_t c2py_ticks(void) {
    uint64_t cnt;
    __asm__ __volatile__("mrs %0, CNTVCT_EL0" : "=r"(cnt));
    return cnt;
}
#elif defined(__powerpc64__) || defined(__powerpc__)
static inline uint64_t c2py_ticks(void) {
#if defined(__GNUC__) || defined(__clang__)
    return __builtin_ppc_get_timebase();
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}
#elif defined(_WIN32)
static inline uint64_t c2py_ticks(void) {
    LARGE_INTEGER freq, counter;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&counter);
    return (uint64_t)(counter.QuadPart * 1000000000ULL / freq.QuadPart);
}
#else
/* Unsupported arch: fall back to clock_gettime even with C2PY_USE_CYCLE_COUNTER */
static inline uint64_t c2py_ticks(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}
#endif
#else /* !C2PY_USE_CYCLE_COUNTER */
#ifdef _WIN32
static inline uint64_t c2py_ticks(void) {
    LARGE_INTEGER freq, counter;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&counter);
    return (uint64_t)(counter.QuadPart * 1000000000ULL / freq.QuadPart);
}
#else
static inline uint64_t c2py_ticks(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}
#endif
#endif /* C2PY_USE_CYCLE_COUNTER */

/* Convert cycle counter ticks to nanoseconds given the counter frequency
 * in Hz.  Returns ticks * 1e9 / freq_hz.
 * Safe against freq_hz == 0 (returns 0).  May overflow if ticks exceeds
 * ~1.8e10 (18 seconds at 1 GHz), which is well beyond any per-call timing.
 */
static inline uint64_t c2py_ticks_to_ns(uint64_t ticks, uint64_t freq_hz) {
    if (freq_hz == 0) return 0;
    return ticks * 1000000000ULL / freq_hz;
}

/* Tick source frequency in Hz, detected once at runtime init.
 * Default (clock_gettime): 1,000,000,000 (nanosecond ticks).
 * With C2PY_USE_CYCLE_COUNTER: detected cycle counter frequency,
 * or 0 if the platform cannot be probed.
 */
extern uint64_t c2py_tick_frequency_hz;

/* Returns c2py_tick_frequency_hz. */
static inline uint64_t c2py_tick_frequency(void) {
    return c2py_tick_frequency_hz;
}

/* Update a perf record with one call's tick measurements.
 * t_enter:  wrapper entry
 * t_pre_c:  just before C call
 * t_post_c: just after C returns
 * t_exit:   just before returning to Python
 */
static inline void c2py_perf_record(c2py_perf_t *p,
    uint64_t t_enter, uint64_t t_pre_c, uint64_t t_post_c, uint64_t t_exit)
{
    uint64_t c_dur = t_post_c - t_pre_c;
    uint64_t w_dur = (t_pre_c - t_enter) + (t_exit - t_post_c);

    p->call_count++;
    p->t_enter  = t_enter;
    p->t_pre_c  = t_pre_c;
    p->t_post_c = t_post_c;
    p->t_exit   = t_exit;

    p->t_c_total += c_dur;
    p->t_wrap_total += w_dur;

    if (p->call_count == 1) {
        p->t_c_min = c_dur;
        p->t_c_max = c_dur;
        p->t_wrap_min = w_dur;
        p->t_wrap_max = w_dur;
    } else {
        if (c_dur < p->t_c_min) p->t_c_min = c_dur;
        if (c_dur > p->t_c_max) p->t_c_max = c_dur;
        if (w_dur < p->t_wrap_min) p->t_wrap_min = w_dur;
        if (w_dur > p->t_wrap_max) p->t_wrap_max = w_dur;
    }
}

/* Update a perf record for a single C call (no wrapper overhead).
 * Used for per-overload timing inside _impl functions. */
static inline void c2py_perf_record_call(c2py_perf_t *p,
    uint64_t t_pre, uint64_t t_post)
{
    uint64_t c_dur = t_post - t_pre;

    p->call_count++;
    p->t_pre_c  = t_pre;
    p->t_post_c = t_post;

    p->t_c_total += c_dur;

    if (p->call_count == 1) {
        p->t_c_min = c_dur;
        p->t_c_max = c_dur;
    } else {
        if (c_dur < p->t_c_min) p->t_c_min = c_dur;
        if (c_dur > p->t_c_max) p->t_c_max = c_dur;
    }
}

/* ------------------------------------------------------------------ */
/* CPU feature probing (for user extensibility, callable from         */
/* __attribute__((constructor)) functions)                            */
/* ------------------------------------------------------------------ */

#ifdef __x86_64__
#if defined(_MSC_VER)
#include <intrin.h>
static inline unsigned int c2py_cpuid_reg(int leaf, int subleaf, int reg) {
    int info[4];
    __cpuidex(info, leaf, subleaf);
    switch (reg & 3) {
    case 0: return (unsigned int)info[0];
    case 1: return (unsigned int)info[1];
    case 2: return (unsigned int)info[2];
    default: return (unsigned int)info[3];
    }
}
#else
static inline unsigned int c2py_cpuid_reg(int leaf, int subleaf, int reg) {
    unsigned int eax = 0, ebx = 0, ecx = 0, edx = 0;
    __asm__ __volatile__(
        "cpuid"
        : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
        : "a"(leaf), "c"(subleaf));
    switch (reg & 3) {
    case 0: return eax;
    case 1: return ebx;
    case 2: return ecx;
    default: return edx;
    }
}
#endif

static inline int c2py_cpuid_bit(int leaf, int subleaf, int reg, int bit) {
    return (c2py_cpuid_reg(leaf, subleaf, reg) >> bit) & 1;
}

/* Do NOT call cpu_supports from constructors; it may malloc internally.
 * Use c2py_cpuid_bit() instead for custom feature probes. */
#endif

/* ------------------------------------------------------------------ */
/* Init function                                                      */
/* ------------------------------------------------------------------ */

int c2py_runtime_init(void);

#ifdef __cplusplus
}
#endif

#endif /* C2PY_RUNTIME_H */
