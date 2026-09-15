#include "workload.h"
#include <stdint.h>

#ifdef __clang__
#define ANALYZE __attribute__((annotate("ape.analyze")))
#else
#define ANALYZE
#endif

static volatile uint8_t packed[8] __attribute__((aligned(4096)));
static volatile uint8_t spread[256] __attribute__((aligned(4096)));
static volatile uint8_t conflict[32768] __attribute__((aligned(4096)));

/* The RTEMS jobs and LLVM analysis compile this same translation unit. */
#define JOB(name, array, stride) \
    ANALYZE void name(void) \
    { \
        for (int sweep = 0; sweep < CHASER_SWEEPS; ++sweep) \
            for (int i = 0; i < CHASER_DISTINCT * (stride); i += (stride)) \
                array[i] = (uint8_t)(array[i] + 1); \
    } \
    int chaser_check_##array(void) \
    { \
        for (int i = 0; i < CHASER_DISTINCT; ++i) \
            if (array[i * (stride)] != (uint8_t)CHASER_SWEEPS) \
                return 0; \
        return 1; \
    }

JOB(chaser_packed, packed, 1)
JOB(chaser_spread, spread, 32)
JOB(chaser_conflict, conflict, 4096)
