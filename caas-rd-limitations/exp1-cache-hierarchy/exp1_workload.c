#include "exp1_workload.h"

#include <string.h>

#if defined(__clang__)
#define YARD_ANALYZE \
    __attribute__((annotate("ape.analyze"))) \
    __attribute__((annotate("yard.analyze")))
#else
#define YARD_ANALYZE
#endif

static volatile uint8_t buf_l1_fit[EXP1_WS_L1_FIT] __attribute__((aligned(4096)));
static volatile uint8_t buf_l1_exceed[EXP1_WS_L1_EXCEED]
    __attribute__((aligned(4096)));
static volatile uint8_t buf_l2_fit[EXP1_WS_L2_FIT] __attribute__((aligned(4096)));
static volatile uint8_t buf_l2_pressure[EXP1_WS_L2_PRESSURE]
    __attribute__((aligned(4096)));

YARD_ANALYZE
void exp1_l1_fit(void)
{
    for (int sweep = 0; sweep < EXP1_SWEEPS; sweep++) {
        for (int i = 0; i < EXP1_WS_L1_FIT; i += EXP1_L1_LINE_SIZE) {
            buf_l1_fit[i] = (uint8_t)(buf_l1_fit[i] + 1);
        }
    }
}

YARD_ANALYZE
void exp1_l1_exceed(void)
{
    for (int sweep = 0; sweep < EXP1_SWEEPS; sweep++) {
        for (int i = 0; i < EXP1_WS_L1_EXCEED; i += EXP1_L1_LINE_SIZE) {
            buf_l1_exceed[i] = (uint8_t)(buf_l1_exceed[i] + 1);
        }
    }
}

YARD_ANALYZE
void exp1_l2_fit(void)
{
    for (int sweep = 0; sweep < EXP1_SWEEPS; sweep++) {
        for (int i = 0; i < EXP1_WS_L2_FIT; i += EXP1_L1_LINE_SIZE) {
            buf_l2_fit[i] = (uint8_t)(buf_l2_fit[i] + 1);
        }
    }
}

YARD_ANALYZE
void exp1_l2_pressure(void)
{
    for (int sweep = 0; sweep < EXP1_SWEEPS; sweep++) {
        for (int i = 0; i < EXP1_WS_L2_PRESSURE; i += EXP1_L1_LINE_SIZE) {
            buf_l2_pressure[i] = (uint8_t)(buf_l2_pressure[i] + 1);
        }
    }
}

void exp1_reset_l1_fit(void)
{
    memset((void *)buf_l1_fit, 0, sizeof(buf_l1_fit));
}

void exp1_reset_l1_exceed(void)
{
    memset((void *)buf_l1_exceed, 0, sizeof(buf_l1_exceed));
}

void exp1_reset_l2_fit(void)
{
    memset((void *)buf_l2_fit, 0, sizeof(buf_l2_fit));
}

void exp1_reset_l2_pressure(void)
{
    memset((void *)buf_l2_pressure, 0, sizeof(buf_l2_pressure));
}
