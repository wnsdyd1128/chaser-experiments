/**
 * @file arch_comparison.c
 * @brief Measures one exp5 case under ALONE, GLOBAL and PARTITIONED.
 *
 * Every task is periodic and every job body is timed with
 * rtems_clock_get_uptime_nanoseconds() around the call, so the reported time is
 * the job's own execution on the GR740 as laysim runs it.
 *
 * All eight tasks share one priority and one period, so a released task never
 * preempts a running one: EDF breaks the deadline tie in favour of the running
 * job. The measured window therefore holds execution only, never a co-runner's
 * stolen time, and the sole difference between GLOBAL and PARTITIONED is which
 * task last owned the private cache of the core the job runs on.
 */

#include <inttypes.h>
#include <rtems.h>
#include <stdio.h>

#include "exp5_workload.h"

#define TASK_STACK_SIZE 4096
#define TASK_PRIORITY 10
#define TASK_PERIOD_NS ((uint64_t)EXP5_TASK_PERIOD_TICKS * 1000ULL * 1000ULL)
#define CPU_UNPINNED (-1)

#define SET_AFFINITY(task_id, cpu)                                   \
    do {                                                             \
        cpu_set_t cpuset;                                            \
        CPU_ZERO(&cpuset);                                           \
        CPU_SET((cpu), &cpuset);                                     \
        rtems_task_set_affinity((task_id), sizeof(cpuset), &cpuset); \
    } while (0)

typedef struct {
    int task_idx;
    rtems_id done_sem;
    uint64_t sum_ns;
    uint64_t avg_ns;
    uint64_t max_ns;
    uint64_t min_ns;
    uint32_t cpu_mask;
    int misses;
} exp5_arg_t;

static exp5_arg_t args[EXP5_MAX_TASKS];

/** @return "victim" for the first EXP5_VICTIMS tasks, "polluter" otherwise. */
static const char *role_of(int task_idx)
{
    return task_idx < EXP5_VICTIMS ? "victim" : "polluter";
}

/** @brief Run one job of the task at `task_idx`, whatever its role. */
static void run_job(int task_idx)
{
    if (task_idx < EXP5_VICTIMS) {
        exp5_victim_job(task_idx);
    } else {
        exp5_polluter_job(task_idx - EXP5_VICTIMS);
    }
}

/**
 * @brief Core this task gets under the cache-affinity-aware placement.
 *
 * Victims share the first half of the cores and polluters the second half, so
 * a victim never follows a polluter on a core whatever the task counts are.
 */
static int partitioned_cpu(int task_idx)
{
    const int half = EXP5_CORES / 2;

    return task_idx < EXP5_VICTIMS
               ? task_idx % half
               : half + (task_idx - EXP5_VICTIMS) % half;
}

static rtems_task worker_task(rtems_task_argument arg)
{
    exp5_arg_t *task_arg = (exp5_arg_t *)(uintptr_t)arg;
    rtems_id period_id;

    rtems_status_code sc = rtems_rate_monotonic_create(
        rtems_build_name('P', '5', '0', (char)('a' + task_arg->task_idx)),
        &period_id);
    if (sc != RTEMS_SUCCESSFUL) {
        task_arg->misses = -1;
        rtems_semaphore_release(task_arg->done_sem);
        rtems_task_exit();
    }

    for (int job = 0; job < EXP5_JOBS; job++) {
        if (rtems_rate_monotonic_period(period_id, EXP5_TASK_PERIOD_TICKS) ==
            RTEMS_TIMEOUT) {
            task_arg->misses++;
        }

        uint64_t start_ns = rtems_clock_get_uptime_nanoseconds();
        run_job(task_arg->task_idx);
        uint64_t elapsed_ns = rtems_clock_get_uptime_nanoseconds() - start_ns;

        task_arg->cpu_mask |= 1U << rtems_scheduler_get_processor();
        task_arg->sum_ns += elapsed_ns;
        if (elapsed_ns > task_arg->max_ns) {
            task_arg->max_ns = elapsed_ns;
        }
        if (elapsed_ns < task_arg->min_ns) {
            task_arg->min_ns = elapsed_ns;
        }
    }

    task_arg->avg_ns = task_arg->sum_ns / EXP5_JOBS;
    rtems_rate_monotonic_delete(period_id);
    rtems_semaphore_release(task_arg->done_sem);
    rtems_task_exit();
}

static void print_metric(const char *case_name, const exp5_arg_t *arg,
                         const char *metric, uint64_t value)
{
    printf("RESULT,experiment=exp5,config=%s,case=%s,task=%d,role=%s,"
           "metric=%s,value=%" PRIu64 "\n",
           EXP5_CASE_NAME, case_name, arg->task_idx, role_of(arg->task_idx),
           metric, value);
}

/**
 * @brief Report one task's measured job times and the cores it ran on.
 *
 * cpu_mask is the set of processors that executed a job of this task. Under
 * PARTITIONED it must hold the single pinned core; under GLOBAL it shows what
 * the SMP scheduler actually did, which is what makes the placement claim
 * checkable rather than assumed.
 */
static void print_task_result(const char *case_name, const exp5_arg_t *arg)
{
    print_metric(case_name, arg, "avg_ns", arg->avg_ns);
    print_metric(case_name, arg, "max_ns", arg->max_ns);
    print_metric(case_name, arg, "min_ns", arg->min_ns);
    print_metric(case_name, arg, "period_ns", TASK_PERIOD_NS);
    print_metric(case_name, arg, "misses", (uint64_t)arg->misses);
    print_metric(case_name, arg, "cpu_mask", arg->cpu_mask);
    print_metric(case_name, arg, "utilization_ppm",
                 (arg->avg_ns * 1000000ULL) / TASK_PERIOD_NS);
}

static void init_arg(int idx, rtems_id sem_id)
{
    args[idx] = (exp5_arg_t){idx, sem_id, 0, 0, 0, UINT64_MAX, 0, 0};
}

/**
 * @brief Run one task on core 0 with the other seven absent.
 *
 * This is the standalone measurement the CAAS feature vector is built from:
 * avg_ns divided by the period is U, and CA comes from the access pattern.
 */
static void run_single(const char *case_name, int idx)
{
    rtems_id sem_id;
    rtems_id task_id;

    exp5_reset_buffers();
    rtems_semaphore_create(rtems_build_name('D', 'S', '5', '0'), 0,
                           RTEMS_COUNTING_SEMAPHORE, 0, &sem_id);
    init_arg(idx, sem_id);

    rtems_task_create(rtems_build_name('S', '5', '0', (char)('a' + idx)),
                      TASK_PRIORITY, TASK_STACK_SIZE, RTEMS_DEFAULT_MODES,
                      RTEMS_DEFAULT_ATTRIBUTES, &task_id);
    SET_AFFINITY(task_id, 0);
    rtems_task_start(task_id, worker_task,
                     (rtems_task_argument)(uintptr_t)&args[idx]);
    rtems_semaphore_obtain(sem_id, RTEMS_WAIT, RTEMS_NO_TIMEOUT);

    print_task_result(case_name, &args[idx]);
    rtems_task_delete(task_id);
    rtems_semaphore_delete(sem_id);
}

/**
 * @brief Run the whole task set under one placement.
 *
 * @param[in] case_name Label for the RESULT lines.
 * @param[in] cpus      Per-task core, or CPU_UNPINNED to leave the task to the
 *                      SMP scheduler.
 */
static void run_group(const char *case_name, const int cpus[EXP5_MAX_TASKS])
{
    rtems_id sem_id;
    rtems_id task_ids[EXP5_MAX_TASKS];

    exp5_reset_buffers();
    rtems_semaphore_create(rtems_build_name('D', 'G', '5', '0'), 0,
                           RTEMS_COUNTING_SEMAPHORE, 0, &sem_id);

    for (int idx = 0; idx < EXP5_ACTIVE_TASKS; idx++) {
        init_arg(idx, sem_id);
        rtems_task_create(rtems_build_name('G', '5', '0', (char)('a' + idx)),
                          TASK_PRIORITY, TASK_STACK_SIZE, RTEMS_DEFAULT_MODES,
                          RTEMS_DEFAULT_ATTRIBUTES, &task_ids[idx]);
        if (cpus[idx] >= 0) {
            SET_AFFINITY(task_ids[idx], cpus[idx]);
        }
    }

    for (int idx = 0; idx < EXP5_ACTIVE_TASKS; idx++) {
        rtems_task_start(task_ids[idx], worker_task,
                         (rtems_task_argument)(uintptr_t)&args[idx]);
    }
    for (int idx = 0; idx < EXP5_ACTIVE_TASKS; idx++) {
        rtems_semaphore_obtain(sem_id, RTEMS_WAIT, RTEMS_NO_TIMEOUT);
    }

    for (int idx = 0; idx < EXP5_ACTIVE_TASKS; idx++) {
        print_task_result(case_name, &args[idx]);
        rtems_task_delete(task_ids[idx]);
    }
    rtems_semaphore_delete(sem_id);
}

static void print_setup(const char *metric, long value)
{
    printf("RESULT,experiment=exp5,config=%s,case=SETUP,metric=%s,value=%ld\n",
           EXP5_CASE_NAME, metric, value);
}

/**
 * @brief Report the compile-time shape of this case, then measure it.
 *
 * PARTITIONED is the cache-affinity-aware placement: victims share cores 0 and
 * 1 with each other, polluters share cores 2 and 3, so no victim ever follows a
 * polluter on a core. GLOBAL sets no affinity at all.
 */
void run_exp5_arch_mismatch(void)
{
    int global_cpus[EXP5_MAX_TASKS];
    int partitioned_cpus[EXP5_MAX_TASKS];

    for (int idx = 0; idx < EXP5_ACTIVE_TASKS; idx++) {
        global_cpus[idx] = CPU_UNPINNED;
        partitioned_cpus[idx] = partitioned_cpu(idx);
    }

    print_setup("victim_distinct", EXP5_VICTIM_DISTINCT);
    print_setup("victim_stride", EXP5_VICTIM_STRIDE);
    print_setup("victim_bytes", EXP5_VICTIM_BYTES);
    print_setup("victim_sweeps", EXP5_VICTIM_SWEEPS);
    print_setup("polluter_distinct", EXP5_POLLUTER_DISTINCT);
    print_setup("polluter_stride", EXP5_POLLUTER_STRIDE);
    print_setup("polluter_bytes", EXP5_POLLUTER_BYTES);
    print_setup("polluter_sweeps", EXP5_POLLUTER_SWEEPS);
    print_setup("jobs", EXP5_JOBS);
    print_setup("victims", EXP5_VICTIMS);
    print_setup("polluters", EXP5_POLLUTERS);

    for (int idx = 0; idx < EXP5_ACTIVE_TASKS; idx++) {
        run_single("ALONE", idx);
    }
    run_group("GLOBAL", global_cpus);
    run_group("PARTITIONED", partitioned_cpus);
}
