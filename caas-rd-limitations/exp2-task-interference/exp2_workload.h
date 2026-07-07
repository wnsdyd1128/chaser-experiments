#ifndef EXP2_WORKLOAD_H
#define EXP2_WORKLOAD_H

#include <stdint.h>

#define EXP2_MAX_TASKS 16

#ifndef EXP2_ACTIVE_TASKS
#define EXP2_ACTIVE_TASKS 8
#endif

#define EXP2_L1_LINE_SIZE 32

#define EXP2_TYPE_A_SHARED_LLC 1
#define EXP2_TYPE_B_PREEMPTIVE 2
#define EXP2_TYPE_C_SELF_CONFLICT 3

#ifndef EXP2_INTERFERENCE_TYPE
#define EXP2_INTERFERENCE_TYPE EXP2_TYPE_A_SHARED_LLC
#endif

#ifndef EXP2_SWEEPS
#define EXP2_SWEEPS 24576
#endif

#ifndef EXP2_HOT_LINES
#define EXP2_HOT_LINES 8
#endif

#ifndef EXP2_B_VICTIMS
#define EXP2_B_VICTIMS 3
#endif

#ifndef EXP2_B_VICTIM_LINES
#define EXP2_B_VICTIM_LINES 128
#endif

#ifndef EXP2_B_POLLUTER_LINES
#define EXP2_B_POLLUTER_LINES 1024
#endif

#if EXP2_INTERFERENCE_TYPE == EXP2_TYPE_B_PREEMPTIVE
#define EXP2_ACCESS_STRIDE EXP2_L1_LINE_SIZE
#define EXP2_DEFAULT_LINES EXP2_B_POLLUTER_LINES
#else
#define EXP2_ACCESS_STRIDE (4 * 1024)
#define EXP2_DEFAULT_LINES EXP2_HOT_LINES
#endif

#define EXP2_CONFLICT_STRIDE (4 * 1024)
#define EXP2_CONFLICT_SIZE (EXP2_CONFLICT_STRIDE * EXP2_DEFAULT_LINES)
#define EXP2_WS_PRESSURE (EXP2_ACCESS_STRIDE * EXP2_DEFAULT_LINES)

typedef void (*exp2_job_fn_t)(void);
typedef void (*exp2_reset_fn_t)(void);

void exp2_standalone_a(void);
void exp2_standalone_b(void);
void exp2_standalone_c(void);
void exp2_standalone_d(void);
void exp2_standalone_e(void);
void exp2_standalone_f(void);
void exp2_standalone_g(void);
void exp2_standalone_h(void);
void exp2_standalone_i(void);
void exp2_standalone_j(void);
void exp2_standalone_k(void);
void exp2_standalone_l(void);
void exp2_standalone_m(void);
void exp2_standalone_n(void);
void exp2_standalone_o(void);
void exp2_standalone_p(void);

void exp2_reset_standalone_a(void);
void exp2_reset_standalone_b(void);
void exp2_reset_standalone_c(void);
void exp2_reset_standalone_d(void);
void exp2_reset_standalone_e(void);
void exp2_reset_standalone_f(void);
void exp2_reset_standalone_g(void);
void exp2_reset_standalone_h(void);
void exp2_reset_standalone_i(void);
void exp2_reset_standalone_j(void);
void exp2_reset_standalone_k(void);
void exp2_reset_standalone_l(void);
void exp2_reset_standalone_m(void);
void exp2_reset_standalone_n(void);
void exp2_reset_standalone_o(void);
void exp2_reset_standalone_p(void);

#endif
