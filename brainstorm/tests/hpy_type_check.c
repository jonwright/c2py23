/* hpy_type_check.c -- HPy type detection test for GraalPy/PyPy/CPython.
 *
 * Build: see Makefile (defines HPY_ABI_CPYTHON)
 */
#include "hpy.h"
#include <string.h>

HPyDef_METH(is_ndarray, "is_ndarray", HPyFunc_O)
static HPy is_ndarray_impl(HPyContext *ctx, HPy self, HPy arg)
{
    HPy h_type, h_name;
    long result = 0;

    h_type = HPy_Type(ctx, arg);
    if (HPy_IsNull(h_type))
        return HPyLong_FromLong(ctx, -1);

    h_name = HPy_GetAttr_s(ctx, h_type, "__name__");
    if (!HPy_IsNull(h_name)) {
        HPy_ssize_t size;
        const char *name = HPyUnicode_AsUTF8AndSize(ctx, h_name, &size);
        if (name && size == 7 && memcmp(name, "ndarray", 7) == 0)
            result = 1;
        HPy_Close(ctx, h_name);
    }
    HPy_Close(ctx, h_type);
    return HPyLong_FromLong(ctx, result);
}

HPyDef_METH(has_dlpack, "has_dlpack", HPyFunc_O)
static HPy has_dlpack_impl(HPyContext *ctx, HPy self, HPy arg)
{
    HPy method = HPy_GetAttr_s(ctx, arg, "__dlpack__");
    long result = HPy_IsNull(method) ? 0 : 1;
    if (!HPy_IsNull(method))
        HPy_Close(ctx, method);
    return HPyLong_FromLong(ctx, result);
}

static HPyDef *module_defines[] = {
    &is_ndarray,
    &has_dlpack,
    NULL
};

static HPyModuleDef moduledef = {
    .doc = "HPy type tests",
    .size = 0,
    .defines = module_defines,
};

HPy_MODINIT(hpy_type_check, moduledef)
