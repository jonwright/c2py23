#include <stdint.h>

/* C2PY_BEGIN
{
    "functions": [
        {
            "c_overloads": [
                {
                    "map": {
                        "offset": "offset",
                        "ptr": "ptr",
                        "value": "value"
                    },
                    "sig": "int address_store(void *ptr, int value, int offset)"
                }
            ],
            "py_sig": "address_store(ptr: int, value: int, offset: int) -> int"
        }
    ],
    "module": "addressmod",
    "source": [
        "address.c"
    ]
}
C2PY_END */

int address_store(void *ptr, int value, int offset) {
    if (!ptr) return -1;
    int *p = (int *)ptr;
    p[offset] = value;
    return 0;
}
