#ifndef EXP1_WORKLOAD_H
#define EXP1_WORKLOAD_H

#include <stdint.h>

#define EXP1_L1_LINE_SIZE 32
#define EXP1_SWEEPS 256
#define EXP1_WS_L1_FIT (8 * 1024)
#define EXP1_WS_L1_EXCEED (24 * 1024)
#define EXP1_WS_L2_FIT (512 * 1024)
#define EXP1_WS_L2_PRESSURE (1536 * 1024)

typedef void (*exp1_job_fn_t)(void);
typedef void (*exp1_reset_fn_t)(void);

void exp1_l1_fit(void);
void exp1_l1_exceed(void);
void exp1_l2_fit(void);
void exp1_l2_pressure(void);

void exp1_reset_l1_fit(void);
void exp1_reset_l1_exceed(void);
void exp1_reset_l2_fit(void);
void exp1_reset_l2_pressure(void);

#endif
