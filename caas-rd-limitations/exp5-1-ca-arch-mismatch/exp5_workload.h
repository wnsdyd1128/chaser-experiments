#ifndef EXP5_WORKLOAD_H
#define EXP5_WORKLOAD_H

#include <stdint.h>

/**
 * @file exp5_workload.h
 * @brief Parameters of the exp5 task set, one compile-time case per binary.
 *
 * A task touches EXP5_*_DISTINCT addresses EXP5_*_STRIDE bytes apart and
 * repeats that cycle EXP5_*_SWEEPS times. The reuse histogram of such a cycle
 * collapses to the single point RD = distinct - 1, so CA = 1 / distinct
 * exactly, independent of both the sweep count and the stride. The stride only
 * moves the cache lines the same reuse pattern occupies, which is what lets a
 * case pair keep one CA while changing the cached footprint by 32x.
 */

/** Tasks per role. Four of each fills the four GR740 cores twice over; raising
 *  the counts puts more of each role on every core, which is the second axis
 *  the sweep walks next to the victim footprint. */
#ifndef EXP5_VICTIMS
#define EXP5_VICTIMS 4
#endif
#ifndef EXP5_POLLUTERS
#define EXP5_POLLUTERS 4
#endif
#define EXP5_ACTIVE_TASKS (EXP5_VICTIMS + EXP5_POLLUTERS)
#define EXP5_MAX_TASKS EXP5_ACTIVE_TASKS
#define EXP5_CORES 4

/** Victim access pattern. The default is the L1-resident 8 KB case; the packed
 *  case overrides the stride alone, which divides the footprint by 32 and
 *  leaves CA untouched. */
#ifndef EXP5_VICTIM_DISTINCT
#define EXP5_VICTIM_DISTINCT 256
#endif
#ifndef EXP5_VICTIM_STRIDE
#define EXP5_VICTIM_STRIDE 32
#endif

/** Sweeps per job. Two is the smallest count that still produces a reuse, so
 *  the per-job refill of a cache lost to a co-runner stays the dominant term
 *  rather than being amortised away. */
#ifndef EXP5_VICTIM_SWEEPS
#define EXP5_VICTIM_SWEEPS 2
#endif

/** Polluter access pattern, fixed at 32 KB: twice the GR740 L1, so one job
 *  evicts every line a victim can hold. */
#ifndef EXP5_POLLUTER_DISTINCT
#define EXP5_POLLUTER_DISTINCT 1024
#endif
#ifndef EXP5_POLLUTER_STRIDE
#define EXP5_POLLUTER_STRIDE 32
#endif
#ifndef EXP5_POLLUTER_SWEEPS
#define EXP5_POLLUTER_SWEEPS 2
#endif

#define EXP5_VICTIM_BYTES (EXP5_VICTIM_DISTINCT * EXP5_VICTIM_STRIDE)
#define EXP5_POLLUTER_BYTES (EXP5_POLLUTER_DISTINCT * EXP5_POLLUTER_STRIDE)

/** Measured job repetitions per task. */
#ifndef EXP5_JOBS
#define EXP5_JOBS 128
#endif

/** Rate-monotonic period, in 1 ms ticks. Longer than the sum of the two job
 *  bodies that share a core, so a job is never preempted midway and its
 *  measured window holds execution only. */
#ifndef EXP5_TASK_PERIOD_TICKS
#define EXP5_TASK_PERIOD_TICKS 1
#endif

/** Case label carried on every RESULT line. */
#ifndef EXP5_CASE_NAME
#define EXP5_CASE_NAME "F256"
#endif

/**
 * @brief Sweep victim `index`'s buffer once for one job.
 * @param[in] index Victim index (0 <= index < EXP5_VICTIMS).
 */
void exp5_victim_job(int index);

/**
 * @brief Sweep polluter `index`'s 32 KB buffer for one job.
 * @param[in] index Polluter index (0 <= index < EXP5_POLLUTERS).
 */
void exp5_polluter_job(int index);

void exp5_reset_buffers(void);

#endif
