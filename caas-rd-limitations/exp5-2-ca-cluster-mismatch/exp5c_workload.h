#ifndef EXP5C_WORKLOAD_H
#define EXP5C_WORKLOAD_H

#include <stdint.h>

/**
 * @file exp5c_workload.h
 * @brief Parameters of the exp5-2 task set, one compile-time case per binary.
 *
 * Same cyclic sweep as exp3 and exp5-1, so CA = 1 / distinct exactly and the
 * stride is free to move the cached footprint without moving CA. Victims here
 * alternate a heavy and a light job, in opposite phases, so that pinning two of
 * them to one core lands both heavy jobs in the same release. Nothing in
 * `{CA, U}` reports that phase: U is the average over the run and is equal for
 * all four victims by construction.
 */

/** Victims are the deadline-critical tasks; polluters keep the cores they run
 *  on free of any victim's lines. */
#define EXP5C_VICTIMS 4
#define EXP5C_POLLUTERS 4
#define EXP5C_ACTIVE_TASKS (EXP5C_VICTIMS + EXP5C_POLLUTERS)
#define EXP5C_MAX_TASKS 8

/** Victim access pattern. The default is the 4 KB spread case; the packed case
 *  overrides the stride alone, which divides the footprint by 32 and leaves CA
 *  untouched. Four victims at 128 lines fill exactly one L1, so a cluster of
 *  two cores can hold every victim's footprint on both of its caches. */
#ifndef EXP5C_VICTIM_DISTINCT
#define EXP5C_VICTIM_DISTINCT 128
#endif
#ifndef EXP5C_VICTIM_STRIDE
#define EXP5C_VICTIM_STRIDE 32
#endif

/** Sweeps of the heavy and the light job. A victim runs one of each per two
 *  releases; which one comes first is its phase. The ratio is what makes a
 *  pinned pair of in-phase victims expensive: their heavy jobs serialise on
 *  the one core they share, while a cluster can put them on two. */
#ifndef EXP5C_HEAVY_SWEEPS
#define EXP5C_HEAVY_SWEEPS 8
#endif
#ifndef EXP5C_LIGHT_SWEEPS
#define EXP5C_LIGHT_SWEEPS 1
#endif

/** Polluter access pattern, fixed at 32 KB: twice the GR740 L1. */
#ifndef EXP5C_POLLUTER_DISTINCT
#define EXP5C_POLLUTER_DISTINCT 1024
#endif
#define EXP5C_POLLUTER_STRIDE 32
#ifndef EXP5C_POLLUTER_SWEEPS
#define EXP5C_POLLUTER_SWEEPS 2
#endif

#define EXP5C_VICTIM_BYTES (EXP5C_VICTIM_DISTINCT * EXP5C_VICTIM_STRIDE)
#define EXP5C_POLLUTER_BYTES (EXP5C_POLLUTER_DISTINCT * EXP5C_POLLUTER_STRIDE)

/** Measured releases per task. */
#ifndef EXP5C_JOBS
#define EXP5C_JOBS 128
#endif

/** Victim period in 1 ms ticks. The polluter period is a multiple of it, so
 *  under EDF the victims carry the earlier deadline and preempt a polluter
 *  rather than queueing behind it. */
#ifndef EXP5C_VICTIM_PERIOD_TICKS
#define EXP5C_VICTIM_PERIOD_TICKS 1
#endif
#ifndef EXP5C_POLLUTER_PERIOD_TICKS
#define EXP5C_POLLUTER_PERIOD_TICKS 4
#endif

/** Cores of the GR740. */
#define EXP5C_CORES 4

/** Scheduler instance names of the clustered build. Cluster A owns cores 0, 1
 *  and 2 and holds the victims; cluster B owns core 3 and holds the polluters,
 *  so no victim ever runs on a core a polluter has touched. Only used where
 *  <rtems.h> is in scope. */
#define EXP5C_SCHED_A rtems_build_name('E', 'D', 'F', 'A')
#define EXP5C_SCHED_B rtems_build_name('E', 'D', 'F', 'B')

/** Case label carried on every RESULT line. */
#ifndef EXP5C_CASE_NAME
#define EXP5C_CASE_NAME "CV128"
#endif

/**
 * @brief Run victim `index`'s job for release `job`.
 *
 * @param[in] index Victim index (0 <= index < EXP5C_VICTIMS).
 * @param[in] job   Release counter; its parity and the victim's phase decide
 *                  whether this release is the heavy or the light job.
 */
void exp5c_victim_job(int index, int job);

/**
 * @brief Sweep polluter `index`'s 32 KB buffer twice.
 *
 * @param[in] index Polluter index (0 <= index < EXP5C_POLLUTERS).
 */
void exp5c_polluter_job(int index);

void exp5c_reset_buffers(void);

#endif
