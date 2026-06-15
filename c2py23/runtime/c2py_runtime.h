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
#include <time.h>

#ifdef __cplusplus
extern "C" {
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

/* PyObject - we only store/compare pointers; the layout here is for
 * PyModuleDef_Base embedding and sizeof checks only. */
typedef struct _c2py_object {
    Py_ssize_t ob_refcnt;
    void *ob_type;
} PyObject;

/* Shorthand for embedding PyObject at the head of a struct */
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

/* PyMethodDef: stable layout since 1.0 */
typedef struct {
    const char *ml_name;
    PyCFunction ml_meth;
    int ml_flags;
    const char *ml_doc;
} PyMethodDef;

/* PyModuleDef_Base: stable core layout since Python 3.0 */
typedef struct PyModuleDef_Base {
    PyObject ob_base;
    PyObject *(*m_init)(void);
    Py_ssize_t m_index;
    PyObject *m_copy;
} PyModuleDef_Base;

/* PyModuleDef for Python 3.x  (core fields ABI-stable across 3.x) */
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

/* ------------------------------------------------------------------ */
/* Function pointer table - populated by c2py_runtime_init()          */
/* ------------------------------------------------------------------ */

typedef struct {
    void *dl_handle;
    int version_major;
    int version_minor;

    int use_fastcall;               /* 1 = use METH_FASTCALL wrappers (Python >= 3.12) */
    Py_ssize_t pybuffer_size;      /* actual sizeof(Py_buffer) for this Python version */

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
    PyObject* (*Float_FromDouble)(double);

    /* Tuple construction */
    PyObject* (*Tuple_New)(Py_ssize_t);
    int (*Tuple_SetItem)(PyObject*, Py_ssize_t, PyObject*);

    /* Scalar conversion from objects */
    long (*Long_AsLong)(PyObject*);
    double (*Float_AsDouble)(PyObject*);

    /* Exception objects (pointers to the actual exception types) */
    void *exc_TypeError;
    void *exc_ValueError;
    void *exc_RuntimeError;
    void *exc_MemoryError;
    void (*Err_SetString)(PyObject*, const char*);
    PyObject* (*Err_Occurred)(void);

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

} c2py_api_t;

/* The global API table */
extern c2py_api_t C2PY;

/* ------------------------------------------------------------------ */
/* Convenience macros                                                 */
/* ------------------------------------------------------------------ */

#define PyObject_GetBuffer(o, b, f)    C2PY.GetBuffer((PyObject*)(o), (b), (f))
#define PyBuffer_Release(b)            C2PY.ReleaseBuffer(b)
#define PyArg_ParseTuple(a, f, ...)    C2PY.ParseTuple((PyObject*)(a), (f), ##__VA_ARGS__)
#define PyArg_ParseTupleAndKeywords(a, k, f, kw, ...) \
    C2PY.ParseTupleAndKeywords((PyObject*)(a), (PyObject*)(k), (f), (char**)(kw), ##__VA_ARGS__)
#define PyLong_FromLong(v)             C2PY.Long_FromLong(v)
#define PyLong_FromLongLong(v)         C2PY.Long_FromLongLong(v)
#define PyFloat_FromDouble(v)          C2PY.Float_FromDouble(v)
#define PyLong_AsLong(o)               C2PY.Long_AsLong((PyObject*)(o))
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

/* Manual refcount increment - our PyObject has ob_refcnt first.
 * Safe on CPython 2.7 through 3.11 where refcount is a simple
 * Py_ssize_t; on 3.12+ the real Py_IncRef symbol is used instead. */
static inline void _c2py_inc_ref_manual(PyObject *op)
{
    ++op->ob_refcnt;
}

static inline void _c2py_dec_ref_manual(PyObject *op)
{
    --op->ob_refcnt;
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
} c2py_perf_t;

/* Returns monotonic time in cycles or nanoseconds depending on arch.
 * The unit is consistent within a single run; differential timing
 * (t_post - t_pre) uses the same source and gives valid deltas.
 * On x86_64/ARM64: uses CPU cycle counter for lower overhead.
 * On others: clock_gettime(CLOCK_MONOTONIC) fallback.
 */
#if defined(__x86_64__) || defined(__i386__)
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
#else
static inline uint64_t c2py_ticks(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}
#endif

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
/* Init function                                                      */
/* ------------------------------------------------------------------ */

int c2py_runtime_init(void);

#ifdef __cplusplus
}
#endif

#endif /* C2PY_RUNTIME_H */
