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
#include <assert.h>
#include <stdio.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#elif defined(__linux__)
#include <dlfcn.h>
#include <sys/auxv.h> /* Linux: getauxval for CPU feature detection on ARM64/POWER */
#include <pthread.h>
#else
#include <dlfcn.h>
#include <pthread.h>
#endif

#include "c2py_runtime.h"

#ifdef _MSC_VER
#include <intrin.h>
#endif

/* Cross-platform symbol resolution */
#ifdef _WIN32
#define C2PY_RESOLVE(handle, name) GetProcAddress((HMODULE)(handle), (name))
#else
#define C2PY_RESOLVE(handle, name) dlsym((handle), (name))
#endif

/* Global API table */
c2py_api_t C2PY = {0};
static volatile int _c2py_runtime_initialized = 0;
static int _c2py_init_result = 0;

#ifndef _WIN32
static pthread_once_t _c2py_init_once = PTHREAD_ONCE_INIT;
#else
static CRITICAL_SECTION _c2py_init_cs;
static BOOL _c2py_init_cs_ready = FALSE;
#endif

/* ---- CPU feature flags (populated by _c2py_probe_cpu_features) ----
 * Always defined (unconditionally) so that a .c2py file can include
 * any mix of arch headers without link errors.  On non-matching
 * architectures the values remain 0. */

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

int c2py_arm64_fp = 0;
int c2py_arm64_asimd = 0;
int c2py_arm64_aes = 0;
int c2py_arm64_pmull = 0;
int c2py_arm64_sha1 = 0;
int c2py_arm64_sha2 = 0;
int c2py_arm64_crc32 = 0;
int c2py_arm64_sve = 0;
int c2py_arm64_sve2 = 0;

int c2py_ppc64_altivec = 0;
int c2py_ppc64_vsx = 0;
int c2py_ppc64_power8 = 0;
int c2py_ppc64_power9 = 0;

/* Tick source: 0 = wall clock (default), 1 = CPU cycle counter */
int _c2py_use_cycle_counter = 0;

/* Detected cycle counter frequency, or 0 if unknown (probed at init).
 * When _c2py_use_cycle_counter is toggled, the active frequency is
 * copied to c2py_tick_frequency_hz. */
uint64_t c2py_cycle_counter_frequency_hz = 0;

/* Active tick source frequency in Hz, declared extern in c2py_runtime.h. */
uint64_t c2py_tick_frequency_hz = 0;

/* On Windows GetProcAddress returns a function-pointer type;
 * casting it to void* and back is inherent to the nimpy trick. */
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable:4152)
#endif
static int _resolve(void **ptr, const char *name)
{
    *ptr = C2PY_RESOLVE(C2PY.dl_handle, name);
    if (*ptr == NULL) {
        /* Some symbols may legitimately not exist on old Python versions.
         * We only warn for critical ones. */
        return -1;
    }
    return 0;
}
#ifdef _MSC_VER
#pragma warning(pop)
#endif

#define RESOLVE(ptr, name) _resolve((void**)&(ptr), name)
#define RESOLVE_REQ(ptr, name) do { \
    if (_resolve((void**)&(ptr), name) != 0) { \
        fprintf(stderr, "c2py_runtime: FATAL - missing symbol: %s\n", name); \
        return; \
    } \
} while(0)

/* Python 2.7 module init helper */
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable:4152)
#endif
static PyObject*
_init_module_2_7(const char *name, PyMethodDef *methods)
{
    void *dl = C2PY.dl_handle;

    /* Try Py_InitModule4 first (Python 2.7 preferred) */
    typedef PyObject* (*init4_fn)(const char*, PyMethodDef*, const char*,
                                   PyObject*, int);
    init4_fn fn4 = (init4_fn)C2PY_RESOLVE(dl, "Py_InitModule4_64");
    if (fn4 == NULL) fn4 = (init4_fn)C2PY_RESOLVE(dl, "Py_InitModule4");
    if (fn4 != NULL) {
        return fn4(name, methods, NULL, NULL, 1013 /* PYTHON_API_VERSION */);
    }

    /* Fallback: Py_InitModule3 */
    typedef PyObject* (*init3_fn)(const char*, PyMethodDef*, const char*);
    init3_fn fn3 = (init3_fn)C2PY_RESOLVE(dl, "Py_InitModule3");
    if (fn3 != NULL) {
        return fn3(name, methods, NULL);
    }

    fprintf(stderr, "c2py_runtime: could not find module init function\n");
    return NULL;
}
#ifdef _MSC_VER
#pragma warning(pop)
#endif


/* ---- CPU feature probing ---- */

static void _c2py_probe_cpu_features(void)
{
#ifdef __x86_64__
    unsigned int eax1, ebx1, ecx1, edx1;
    unsigned int eax7, ebx7, ecx7, edx7;
    unsigned int eax81, ebx81, ecx81, edx81;
    unsigned int max_std;

#if defined(_MSC_VER)
    {
        int info[4];
        __cpuidex(info, 0, 0);
        max_std = (unsigned int)info[0];

        if (max_std >= 1) {
            __cpuidex(info, 1, 0);
            eax1 = (unsigned int)info[0];
            ebx1 = (unsigned int)info[1];
            ecx1 = (unsigned int)info[2];
            edx1 = (unsigned int)info[3];
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
        if (max_std >= 7) {
            __cpuidex(info, 7, 0);
            ebx7 = (unsigned int)info[1];
            ecx7 = (unsigned int)info[2];
            edx7 = (unsigned int)info[3];
            c2py_amd64_bmi1    = (ebx7 >>  3) & 1;
            c2py_amd64_avx2    = (ebx7 >>  5) & 1;
            c2py_amd64_bmi2    = (ebx7 >>  8) & 1;
            c2py_amd64_avx512f = (ebx7 >> 16) & 1;
            c2py_amd64_avx512dq = (ebx7 >> 17) & 1;
            c2py_amd64_avx512bw = (ebx7 >> 30) & 1;
            c2py_amd64_avx512vl = (ebx7 >> 31) & 1;
        }
        __cpuidex(info, 0x80000000, 0);
        if ((unsigned int)info[0] >= 0x80000001) {
            __cpuidex(info, 0x80000001, 0);
            ecx81 = (unsigned int)info[2];
            c2py_amd64_lzcnt = (ecx81 >> 5) & 1;
        }
    }
#else
    /* Determine max standard leaf */
    __asm__ __volatile__("cpuid"
        : "=a"(eax1) : "a"(0) : "ebx", "ecx", "edx");
    max_std = eax1;

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
#endif /* _MSC_VER */
#endif

#if (defined(__aarch64__) || defined(__arm64__)) && !defined(_WIN32)
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

#if (defined(__powerpc64__) || defined(__powerpc__)) && !defined(_WIN32)
    {
        unsigned long hwcap = getauxval(AT_HWCAP);
        unsigned long hwcap2 = getauxval(AT_HWCAP2);

        c2py_ppc64_altivec = (hwcap >> 28) & 1;        /* PPC_FEATURE_HAS_ALTIVEC = 0x10000000 */
        c2py_ppc64_vsx     = (hwcap >>  7) & 1;         /* PPC_FEATURE_HAS_VSX     = 0x00000080 */
        c2py_ppc64_power8  = (hwcap2 >> 31) & 1;        /* PPC_FEATURE2_ARCH_2_07  = 0x80000000 */
        c2py_ppc64_power9  = (hwcap2 >> 23) & 1;        /* PPC_FEATURE2_ARCH_3_00  = 0x00800000 */
    }
#endif

/* ---- Tick source frequency detection ---- */

    /* Default: wall clock returns nanoseconds, frequency is 1e9 Hz.
     * Cycle counter frequency is probed separately below and stored
     * in c2py_cycle_counter_frequency_hz; it is only used when the
     * caller toggles _c2py_use_cycle_counter to 1. */
    c2py_tick_frequency_hz = 1000000000ULL;

    /* Always attempt to detect CPU cycle counter frequency.
     * On platforms without a readable cycle counter this remains 0. */
#if defined(__x86_64__) || defined(__i386__)
    {
#if defined(_MSC_VER)
        int info[4];
        int got_freq = 0;
        __cpuidex(info, 0, 0);
        if ((unsigned int)info[0] >= 0x15) {
            __cpuidex(info, 0x15, 0);
            unsigned int eax = (unsigned int)info[0];
            unsigned int ebx = (unsigned int)info[1];
            unsigned int ecx = (unsigned int)info[2];
            if (ebx != 0 && eax != 0 && ecx != 0) {
                c2py_cycle_counter_frequency_hz =
                    (uint64_t)ecx * (uint64_t)ebx / (uint64_t)eax;
                got_freq = 1;
            }
        }
        if (!got_freq) {
            LARGE_INTEGER qpf;
            if (QueryPerformanceFrequency(&qpf) && qpf.QuadPart > 0) {
                c2py_cycle_counter_frequency_hz = (uint64_t)qpf.QuadPart;
            }
        }
#else
        unsigned int eax, ebx, ecx, edx;
        unsigned int max_std;
        int got_freq = 0;
        __asm__ __volatile__("cpuid" : "=a"(max_std) : "a"(0) : "ebx", "ecx", "edx");
        if (max_std >= 0x15) {
            __asm__ __volatile__("cpuid"
                : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
                : "a"(0x15));
            if (ebx != 0 && eax != 0 && ecx != 0) {
                c2py_cycle_counter_frequency_hz =
                    (uint64_t)ecx * (uint64_t)ebx / (uint64_t)eax;
                got_freq = 1;
            }
        }
        if (!got_freq) {
            FILE *f = fopen("/proc/cpuinfo", "r");
            if (f) {
                char line[256];
                while (fgets(line, sizeof(line), f)) {
                    double mhz;
                    if (sscanf(line, "cpu MHz : %lf", &mhz) == 1) {
                        c2py_cycle_counter_frequency_hz =
                            (uint64_t)(mhz * 1000000.0 + 0.5);
                        break;
                    }
                }
                fclose(f);
            }
        }
#endif /* _MSC_VER */
    }
#elif (defined(__aarch64__) || defined(__arm64__)) && !defined(_MSC_VER)
    {
        uint64_t freq;
        __asm__ __volatile__("mrs %0, CNTFRQ_EL0" : "=r"(freq));
        if (freq != 0) {
            c2py_cycle_counter_frequency_hz = freq;
        }
    }
#elif defined(__powerpc64__) || defined(__powerpc__)
    {
#ifdef _WIN32
        c2py_cycle_counter_frequency_hz = 0;
#else
        FILE *f = fopen("/proc/device-tree/cpus/timebase-frequency", "r");
        if (f) {
            unsigned char buf[8] = {0};
            size_t r = fread(buf, 1, 8, f);
            fclose(f);
            if (r == 4) {
                c2py_cycle_counter_frequency_hz =
                    ((uint64_t)buf[0] << 24) |
                    ((uint64_t)buf[1] << 16) |
                    ((uint64_t)buf[2] << 8)  |
                     (uint64_t)buf[3];
            } else if (r >= 8) {
                c2py_cycle_counter_frequency_hz =
                    ((uint64_t)buf[0] << 56) |
                    ((uint64_t)buf[1] << 48) |
                    ((uint64_t)buf[2] << 40) |
                    ((uint64_t)buf[3] << 32) |
                    ((uint64_t)buf[4] << 24) |
                    ((uint64_t)buf[5] << 16) |
                    ((uint64_t)buf[6] << 8)  |
                     (uint64_t)buf[7];
            }
        }
#endif /* _WIN32 */
    }
#endif
    /* If detection failed, c2py_cycle_counter_frequency_hz remains 0. */
}


#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable:4152)  /* GetProcAddress fn/data ptr cast */
#endif
static void _c2py_runtime_init_once(void)
{
    _c2py_init_result = -1;  /* assume failure until full success */

    /* CPU feature probing runs first -- does not depend on Python */
    _c2py_probe_cpu_features();

    /* --- Reject 32-bit builds --- */
    if (sizeof(void*) != 8) {
        fprintf(stderr, "c2py_runtime: 32-bit platforms are not supported. "
                "Detected %d-bit pointer width. "
                "c2py23 targets LP64 (64-bit) only; "
                "32-bit Py_buffer layout is unverified.\n",
                (int)(sizeof(void*) * 8));
        return;
    }

#ifdef _WIN32
    /* On Windows, python3.dll is the stable-ABI forwarder DLL (PEP 384).
     * It is loaded as a dependency of python3XX.dll, which in turn
     * loads this extension module.  python3.dll exports the limited
     * API which covers all symbols c2py23 needs.
     * Fall back to enumerating known versioned DLL names for Python
     * installations that do not ship python3.dll (e.g. Python 2.7). */
    {
        /* Prefer versioned DLLs: python3.dll is the stable-ABI
         * forwarder which may not export all symbols (e.g. Python 3.9
         * does not export PyObject_GetBuffer from python3.dll). */
        static const char *candidates[] = {
            "python315.dll", "python314.dll", "python313.dll",
            "python312.dll", "python311.dll", "python310.dll",
            "python39.dll", "python38.dll", "python37.dll",
            "python36.dll", "python27.dll",
            "python3.dll",
            NULL
        };
        int i;
        for (i = 0; candidates[i]; i++) {
            C2PY.dl_handle = (void*)GetModuleHandleA(candidates[i]);
            if (C2PY.dl_handle) break;
        }
        if (C2PY.dl_handle == NULL) {
            fprintf(stderr, "c2py_runtime: GetModuleHandle failed "
                    "(python3.dll not found). "
                    "GetLastError=%lu\n", GetLastError());
            fprintf(stderr, "c2py_runtime: interpreter may be statically "
                    "linked or embedded in an unusual host.\n");
            return;
        }
    }
#else
    C2PY.dl_handle = dlopen(NULL, RTLD_LAZY | RTLD_GLOBAL);
    if (C2PY.dl_handle == NULL) {
        fprintf(stderr, "c2py_runtime: dlopen(NULL) failed: %s\n", dlerror());
        fprintf(stderr, "c2py_runtime: interpreter may be statically linked "
                "(requires --enable-shared or export-dynamic).\n");
        return;
    }
#endif

    void *dl = C2PY.dl_handle;

    /* --- Detect Python version --- */
    {
        typedef const char* (*ver_fn)(void);
        ver_fn getver = (ver_fn)C2PY_RESOLVE(dl, "Py_GetVersion");
        if (getver) {
            const char *v = getver();
#ifdef _MSC_VER
            if (v) sscanf_s(v, "%d.%d", &C2PY.version_major, &C2PY.version_minor);
#else
            if (v) sscanf(v, "%d.%d", &C2PY.version_major, &C2PY.version_minor);
#endif
        }
        if (C2PY.version_major == 0) {
            /* Fallback: check for Py3-only symbol */
            if (C2PY_RESOLVE(dl, "PyModule_Create2")) {
                C2PY.version_major = 3;
            } else {
                C2PY.version_major = 2;
            }
            C2PY.version_minor = 0;
        }
    }

    /* --- Reject unsupported Python versions --- */
#ifdef _WIN32
    if (C2PY.version_major >= 3 && C2PY.version_minor > 14) {
        fprintf(stderr,
                "c2py_runtime: Python %d.%d on Windows is not yet supported.\n"
                "Supported versions: 2.7, 3.6-3.14.\n"
                "To add Windows support for a new Python version, audit the CPython\n"
                "headers for ABI changes and update checks in c2py_runtime.c.\n",
                C2PY.version_major, C2PY.version_minor);
        return;
    }
#else
    if (C2PY.version_major >= 3 && C2PY.version_minor > 15) {
        fprintf(stderr,
                "c2py_runtime: Python %d.%d is not supported.\n"
                "Supported versions: 2.7, 3.6-3.15.\n"
                "To add support for a new Python version, audit the CPython\n"
                "headers for ABI changes and update checks in c2py_runtime.c.\n",
                C2PY.version_major, C2PY.version_minor);
        return;
    }
#endif

    /* --- Detect free-threaded build ---
     *
     * Detection priority (first successful method wins):
     * 0. C2PY_FORCE_FT environment variable (1 = force FT, 0 = force standard).
     * 1. Py_GetVersion() string contains "free-threading" (CPython 3.13+).
     * 2. _Py_IsGILEnabled exists and returns 0 (CPython 3.13+ FT builds).
     *    This is an exported function: int _Py_IsGILEnabled(void).
     * 3. Py_GIL_DISABLED config var... but we cannot easily query that
     *    without #include <Python.h> or cpython/initconfig.h.
     *    On the rare builds where neither 1 nor 2 works, the user should
     *    set C2PY_FORCE_FT=1 environment variable at load time.
     */
    {
        int found_ft = 0;

        /* Method 0: environment variable override */
        const char *force_ft = getenv("C2PY_FORCE_FT");
        if (force_ft != NULL) {
            if (force_ft[0] == '1') {
                found_ft = 1;
            }
            C2PY.is_free_threaded = found_ft;
            goto ft_detection_done;
        }

        /* Method 1: version string */
        typedef const char* (*ver_fn)(void);
        ver_fn getver = (ver_fn)C2PY_RESOLVE(dl, "Py_GetVersion");
        const char *vstr = getver ? getver() : "";
        if (vstr && strstr(vstr, "free-threading") != NULL)
            found_ft = 1;

        /* Method 2: _Py_IsGILEnabled (CPython 3.13+) */
        if (!found_ft) {
            typedef int (*gil_check_fn)(void);
            gil_check_fn gilchk = (gil_check_fn)C2PY_RESOLVE(dl, "_Py_IsGILEnabled");
            if (gilchk && gilchk() == 0)
                found_ft = 1;
        }

        C2PY.is_free_threaded = found_ft;
    }
    ft_detection_done:
        /* Nothing to do here; detection logic uses goto to skip above when C2PY_FORCE_FT is set */

    /* --- Set ABI layout (provisional; runtime probe refines below) --- */
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

    /* Sanity-check detected layout consistency */
    assert(C2PY.pyobject_size > 0);
    assert(C2PY.ob_refcnt_offset >= 0);

    assert(C2PY.ob_refcnt_offset + (Py_ssize_t)sizeof(Py_ssize_t) <= C2PY.pyobject_size);

    /* pymoduledef_max_size: pad generously for both layouts */
    {
        Py_ssize_t sz_gil = sizeof(PyModuleDef);
        Py_ssize_t sz_ft  = sizeof(PyModuleDef_FT);
        C2PY.pymoduledef_max_size = (sz_gil > sz_ft) ? sz_gil : sz_ft;
    }

    /* --- Buffer protocol (required) --- */
    RESOLVE_REQ(C2PY.GetBuffer, "PyObject_GetBuffer");
    RESOLVE_REQ(C2PY.ReleaseBuffer, "PyBuffer_Release");
    if (C2PY.GetBuffer == NULL || C2PY.ReleaseBuffer == NULL) return;

    /* --- Old buffer protocol (Python 2.x only) --- */
    C2PY.AsReadBuffer = (int (*)(PyObject*, const void**, Py_ssize_t*))
        C2PY_RESOLVE(dl, "PyObject_AsReadBuffer");
    C2PY.AsWriteBuffer = (int (*)(PyObject*, void**, Py_ssize_t*))
        C2PY_RESOLVE(dl, "PyObject_AsWriteBuffer");
    C2PY.Err_Clear = (void (*)(void))C2PY_RESOLVE(dl, "PyErr_Clear");
    RESOLVE_REQ(C2PY.Err_Clear, "PyErr_Clear");
    if (C2PY.Err_Clear == NULL) return;
    C2PY.buffer_api_is_pep3118 = (C2PY.version_major >= 3);

    /* --- Buffer struct size (default) ---
     * Runtime probe below will refine this.  Safe default: 80 for 3.x, 96 for 2.x.
     * On Debian/Ubuntu this is always correct (all 3.6+ builds dropped smalltable).
     * Upstream CPython 3.0-3.11 may need 96; the probe catches that case.
     */
    C2PY.pybuffer_size = (C2PY.version_major >= 3)
        ? C2PY_PYBUFFER_SZ_POST312 : C2PY_PYBUFFER_SZ_PRE312;

    /* --- Fastcall support (METH_FASTCALL stable ABI since 3.12) --- */
    C2PY.use_fastcall = (C2PY.version_major >= 3 && C2PY.version_minor >= 12);

    /* --- Argument parsing (required) --- */
    RESOLVE_REQ(C2PY.ParseTuple, "PyArg_ParseTuple");
    RESOLVE(C2PY.ParseTupleAndKeywords, "PyArg_ParseTupleAndKeywords");
    if (C2PY.ParseTuple == NULL) return;

    /* --- Error detection for fastcall scalar conversion --- */
    RESOLVE_REQ(C2PY.Err_Occurred, "PyErr_Occurred");
    if (C2PY.Err_Occurred == NULL) return;

    /* --- Value construction (required) --- */
    RESOLVE_REQ(C2PY.Long_FromLong, "PyLong_FromLong");
    RESOLVE_REQ(C2PY.Long_FromLongLong, "PyLong_FromLongLong");
    RESOLVE_REQ(C2PY.Long_FromUnsignedLongLong, "PyLong_FromUnsignedLongLong");
    RESOLVE_REQ(C2PY.Float_FromDouble, "PyFloat_FromDouble");
    if (C2PY.Long_FromLong == NULL || C2PY.Float_FromDouble == NULL) return;

    /* --- Runtime PyObject layout probe ---
     * Create a temporary PyLong and check where ob_type lives.
     * GIL layout (16 bytes): ob_refcnt:0  ob_type:8
     * FT  layout (32 bytes): ob_tid:0 ... ob_type:24
     * On GIL, offset 8 is a heap type pointer (high address).
     * On FT,  offset 8 is ob_flags/mutex/gc_bits (small values).
     * This verifies/overrides the version-based FT detection above.
     */
    {
        PyObject *tmp = C2PY.Long_FromLong(1);
        if (tmp) {
            void *p8 = *(void**)((char*)tmp + 8);
            /* A valid CPython type pointer is always a heap/data address
             * well above 0x100000. ob_flags/mutex/gc_bits are small ints. */
            if (p8 != NULL && (uintptr_t)p8 >= 0x100000) {
                /* offset 8 is a pointer -> GIL layout confirmed */
            } else {
                /* offset 8 is not a pointer -> FT layout */
                C2PY.is_free_threaded = 1;
                C2PY.pyobject_size = 32;
                C2PY.ob_refcnt_offset = 16;
            }
            /* DecRef: use direct dlsym (C2PY.DecRef not resolved yet) */
            {
                typedef void (*dref_fn)(PyObject*);
                dref_fn dref = (dref_fn)C2PY_RESOLVE(dl, "Py_DecRef");
                if (!dref) dref = (dref_fn)C2PY_RESOLVE(dl, "_Py_DecRef");
                if (dref) dref(tmp);
            }
        }
    }

    /* --- Tuple construction (required) --- */
    RESOLVE_REQ(C2PY.Tuple_New, "PyTuple_New");
    RESOLVE_REQ(C2PY.Tuple_SetItem, "PyTuple_SetItem");
    if (C2PY.Tuple_New == NULL || C2PY.Tuple_SetItem == NULL) return;

    /* --- String construction (optional, needed for _variants_*) --- */
    RESOLVE(C2PY.Unicode_FromString, "PyUnicode_FromString");
    RESOLVE(C2PY.String_FromString, "PyString_FromString");

    /* --- Scalar conversion --- */
    RESOLVE_REQ(C2PY.Long_AsLong, "PyLong_AsLong");
    RESOLVE_REQ(C2PY.Long_AsLongLong, "PyLong_AsLongLong");
    RESOLVE_REQ(C2PY.Float_AsDouble, "PyFloat_AsDouble");
    if (C2PY.Long_AsLong == NULL || C2PY.Long_AsLongLong == NULL ||
        C2PY.Float_AsDouble == NULL) return;

    /* --- Exception handling (required) --- */
    RESOLVE_REQ(C2PY.exc_TypeError, "PyExc_TypeError");
    RESOLVE_REQ(C2PY.exc_ValueError, "PyExc_ValueError");
    RESOLVE_REQ(C2PY.exc_RuntimeError, "PyExc_RuntimeError");
    RESOLVE_REQ(C2PY.exc_MemoryError, "PyExc_MemoryError");
    RESOLVE_REQ(C2PY.Err_SetString, "PyErr_SetString");
    RESOLVE_REQ(C2PY.Err_Format, "PyErr_Format");
    if (C2PY.exc_TypeError   == NULL || C2PY.exc_ValueError  == NULL ||
        C2PY.exc_RuntimeError == NULL || C2PY.exc_MemoryError == NULL ||
        C2PY.Err_SetString    == NULL || C2PY.Err_Format      == NULL) return;

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
        void *mc = C2PY_RESOLVE(dl, "PyModule_Create2");
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
                return;
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
    if (C2PY.SetAttrString == NULL) return;
    RESOLVE_REQ(C2PY.GetAttrString, "PyObject_GetAttrString");
    if (C2PY.GetAttrString == NULL) return;

    /* --- Pointer-to-int --- */
    RESOLVE_REQ(C2PY.Long_FromVoidPtr, "PyLong_FromVoidPtr");
    if (C2PY.Long_FromVoidPtr == NULL) return;

    /* --- GIL management --- */
    RESOLVE_REQ(C2PY.SaveThread, "PyEval_SaveThread");
    RESOLVE_REQ(C2PY.RestoreThread, "PyEval_RestoreThread");
    if (C2PY.SaveThread == NULL || C2PY.RestoreThread == NULL) return;
    /* PyUnstable_Module_SetGIL: only exported on --disable-gil builds (3.13+) */
    RESOLVE(C2PY.Unstable_Module_SetGIL, "PyUnstable_Module_SetGIL");

    /* --- None singleton ---
     * _Py_NoneStruct is a static PyObject; dlsym returns &_Py_NoneStruct,
     * which is the same as Py_None (the macro: (&_Py_NoneStruct)).
     * Py_None is immortal so INCREF/DECREF is unnecessary but harmless.
     */
    {
        void *none = C2PY_RESOLVE(dl, "_Py_NoneStruct");
        if (none == NULL) {
            /* On some platforms Py_None is a pointer variable pointing
             * to the struct. Try loading it and dereferencing. */
            void **pnone = (void**)C2PY_RESOLVE(dl, "Py_None");
            if (pnone) none = *pnone;
        }
        C2PY.none_obj = (PyObject*)none;
        if (C2PY.none_obj == NULL) {
            fprintf(stderr, "c2py_runtime: could not resolve Py_None\n");
            return;
        }
    }

    /* --- Runtime Py_buffer size probe ---
     * PyBuffer_FillInfo sets view->internal = NULL. For a bytes object,
     * this writes to offset 72 (80-byte layout) or 88 (96-byte layout).
     * We probe with a sentinel to determine the real sizeof(Py_buffer).
     * This is needed for non-Debian CPython 3.0-3.11 which still have
     * smalltable[2] (96 bytes LP64); Debian/Ubuntu backported the removal.
     */
    {
        unsigned char probe[96];
        Py_buffer *pb = (Py_buffer*)probe;
        typedef PyObject* (*bytes_fn)(const char*, Py_ssize_t);
        bytes_fn mkbytes = (bytes_fn)C2PY_RESOLVE(dl, "PyBytes_FromStringAndSize");
        if (!mkbytes)
            mkbytes = (bytes_fn)C2PY_RESOLVE(dl, "PyString_FromStringAndSize");
        PyObject *by = mkbytes ? mkbytes("x", 1) : NULL;
        if (by) {
            memset(probe, 0xAA, sizeof(probe));
            if (C2PY.GetBuffer(by, pb, PyBUF_STRIDES | PyBUF_FORMAT) == 0) {
                /* internal=NULL at offset 72 (80-byte layout, LP64) or
                 * offset 88 (96-byte layout, LP64).  The offset 72 is
                 * LP64-specific; on ILP32 the correct offset would be 40.
                 * The 32-bit rejection above ensures we never reach here
                 * on platforms where this offset would be wrong.
                 * See also: c2py_runtime.h C2PY_PYBUFFER_SZ_* definitions. */
#ifdef __LP64__
                if (*((char*)pb + 72) == 0)
                    C2PY.pybuffer_size = C2PY_PYBUFFER_SZ_POST312;
                else
                    C2PY.pybuffer_size = C2PY_PYBUFFER_SZ_PRE312;
#else
                /* 32-bit not supported; previous check rejects it */
                C2PY.pybuffer_size = C2PY_PYBUFFER_SZ_PRE312;
#endif
                C2PY.ReleaseBuffer(pb);
            }
            C2PY.DecRef(by);
        }
    }

    _c2py_init_result = 0;
    _c2py_runtime_initialized = 1;
}
#ifdef _MSC_VER
#pragma warning(pop)
#endif

int c2py_runtime_init(void)
{
#ifndef _WIN32
    pthread_once(&_c2py_init_once, _c2py_runtime_init_once);
    return _c2py_init_result;
#else
    if (!_c2py_runtime_initialized) {
        if (!_c2py_init_cs_ready) {
            InitializeCriticalSection(&_c2py_init_cs);
            _c2py_init_cs_ready = TRUE;
        }
        EnterCriticalSection(&_c2py_init_cs);
        if (!_c2py_runtime_initialized) {
            _c2py_runtime_init_once();
        }
        LeaveCriticalSection(&_c2py_init_cs);
    }
    return _c2py_init_result;
#endif
}
