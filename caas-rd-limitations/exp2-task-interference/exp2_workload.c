#include "exp2_workload.h"

#include <string.h>

#if defined(__clang__)
#define YARD_ANALYZE \
    __attribute__((annotate("ape.analyze"))) \
    __attribute__((annotate("yard.analyze")))
#else
#define YARD_ANALYZE
#endif

static volatile uint8_t task_data[EXP2_MAX_TASKS][EXP2_WS_PRESSURE]
    __attribute__((aligned(4096)));
static volatile uint8_t task_shadow[EXP2_MAX_TASKS][EXP2_WS_PRESSURE]
    __attribute__((aligned(4096)));

#define DEFINE_STANDALONE_TASK(index, name)                         \
    YARD_ANALYZE                                                    \
    void name(void)                                                 \
    {                                                               \
        const int limit =                                           \
            (EXP2_INTERFERENCE_TYPE == EXP2_TYPE_B_PREEMPTIVE &&    \
             (index) < EXP2_B_VICTIMS)                              \
                ? (EXP2_B_VICTIM_LINES * EXP2_ACCESS_STRIDE)        \
                : EXP2_WS_PRESSURE;                                 \
        for (int sweep_idx = 0; sweep_idx < EXP2_SWEEPS; sweep_idx++) { \
            for (int i = 0; i < limit; i += EXP2_ACCESS_STRIDE) {   \
                task_data[index][i] = (uint8_t)(task_data[index][i] + 1); \
                if (EXP2_INTERFERENCE_TYPE == EXP2_TYPE_C_SELF_CONFLICT) { \
                    task_shadow[index][i] =                         \
                        (uint8_t)(task_shadow[index][i] + task_data[index][i]); \
                }                                                   \
            }                                                       \
        }                                                           \
    }

DEFINE_STANDALONE_TASK(0, exp2_standalone_a)
DEFINE_STANDALONE_TASK(1, exp2_standalone_b)
DEFINE_STANDALONE_TASK(2, exp2_standalone_c)
DEFINE_STANDALONE_TASK(3, exp2_standalone_d)
DEFINE_STANDALONE_TASK(4, exp2_standalone_e)
DEFINE_STANDALONE_TASK(5, exp2_standalone_f)
DEFINE_STANDALONE_TASK(6, exp2_standalone_g)
DEFINE_STANDALONE_TASK(7, exp2_standalone_h)
DEFINE_STANDALONE_TASK(8, exp2_standalone_i)
DEFINE_STANDALONE_TASK(9, exp2_standalone_j)
DEFINE_STANDALONE_TASK(10, exp2_standalone_k)
DEFINE_STANDALONE_TASK(11, exp2_standalone_l)
DEFINE_STANDALONE_TASK(12, exp2_standalone_m)
DEFINE_STANDALONE_TASK(13, exp2_standalone_n)
DEFINE_STANDALONE_TASK(14, exp2_standalone_o)
DEFINE_STANDALONE_TASK(15, exp2_standalone_p)

#define DEFINE_RESET_TASK(index, name)                             \
    void name(void)                                                \
    {                                                              \
        memset((void *)task_data[index], 0, sizeof(task_data[index])); \
        memset((void *)task_shadow[index], 0, sizeof(task_shadow[index])); \
    }

DEFINE_RESET_TASK(0, exp2_reset_standalone_a)
DEFINE_RESET_TASK(1, exp2_reset_standalone_b)
DEFINE_RESET_TASK(2, exp2_reset_standalone_c)
DEFINE_RESET_TASK(3, exp2_reset_standalone_d)
DEFINE_RESET_TASK(4, exp2_reset_standalone_e)
DEFINE_RESET_TASK(5, exp2_reset_standalone_f)
DEFINE_RESET_TASK(6, exp2_reset_standalone_g)
DEFINE_RESET_TASK(7, exp2_reset_standalone_h)
DEFINE_RESET_TASK(8, exp2_reset_standalone_i)
DEFINE_RESET_TASK(9, exp2_reset_standalone_j)
DEFINE_RESET_TASK(10, exp2_reset_standalone_k)
DEFINE_RESET_TASK(11, exp2_reset_standalone_l)
DEFINE_RESET_TASK(12, exp2_reset_standalone_m)
DEFINE_RESET_TASK(13, exp2_reset_standalone_n)
DEFINE_RESET_TASK(14, exp2_reset_standalone_o)
DEFINE_RESET_TASK(15, exp2_reset_standalone_p)
