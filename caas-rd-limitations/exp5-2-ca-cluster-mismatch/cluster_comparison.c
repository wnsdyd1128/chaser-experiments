/**
 * @file cluster_comparison.c
 * @brief Measures one exp5-2 case under four placements plus ALONE.
 *
 * Timing comes from rtems_clock_get_uptime_nanoseconds() taken around the job
 * body and again against the rate-monotonic release instant, so both numbers
 * the comparison needs are measured on the GR740 as laysim runs it:
 *
 *   execution time  = end of job - start of job
 *   response time   = end of job - release of that job
 *
 * Response time is the deciding metric. Execution time cannot see a task
 * queueing behind a co-runner pinned to the same core, and that queueing is
 * exactly what a cluster is able to spread.
 *
 * Placements, all with the same four cores and the same eight tasks:
 *
 *   GLOBAL           no affinity at all
 *   PARTITIONED      one core per task, the two in-phase victims paired
 *   PARTITIONED_ALT  one core per task, the paired victims across phases
 *   CLUSTERED        victims share cores 0-2, polluters own core 3
 *
 * The three placements that pin or cluster give the victims the same three
 * cores and the polluters the same one, so they differ in how the victims may
 * move inside those cores and in nothing else.
 *
 * PARTITIONED and PARTITIONED_ALT differ only in which victims share a core.
 * Both are equally justified by `{CA, U}`, since all four victims report the
 * same CA and the same U; only their phase, which no CAAS feature carries,
 * decides which of the two is the good one.
 */

#include <inttypes.h>
#include <rtems.h>
#include <stdio.h>

#include "exp5c_placement.h"
#include "exp5c_workload.h"

#define TASK_STACK_SIZE 4096
#define TASK_PRIORITY 10

typedef struct {
    int task_idx;
    rtems_id done_sem;
    uint64_t exec_sum_ns;
    uint64_t exec_max_ns;
    uint64_t resp_sum_ns;
    uint64_t resp_max_ns;
    uint32_t cpu_mask;
    int jobs;
    int resp_jobs;
    int misses;
} exp5c_arg_t;

static exp5c_arg_t args[EXP5C_MAX_TASKS];

/** @return Nanoseconds held by a timespec from the period statistics. */
static uint64_t timespec_ns(const struct timespec *value)
{
    return (uint64_t)value->tv_sec * 1000000000ULL + (uint64_t)value->tv_nsec;
}

static int is_victim(int task_idx)
{
    return task_idx < EXP5C_VICTIMS;
}

static const char *role_of(int task_idx)
{
    return is_victim(task_idx) ? "victim" : "polluter";
}

static int period_ticks_of(int task_idx)
{
    return is_victim(task_idx) ? EXP5C_VICTIM_PERIOD_TICKS
                               : EXP5C_POLLUTER_PERIOD_TICKS;
}

/** @return Releases to measure, so every task stops at the same wall time. */
static int jobs_of(int task_idx)
{
    return EXP5C_JOBS * EXP5C_VICTIM_PERIOD_TICKS / period_ticks_of(task_idx);
}

/**
 * @brief Run one task's releases and record execution and response times.
 *
 * The anchor is read immediately before the first rate-monotonic call, which
 * is the call that starts the period, so release k sits at anchor + k * period
 * and needs no further clock reads.
 */
static rtems_task worker_task(rtems_task_argument arg)
{
    exp5c_arg_t *task_arg = (exp5c_arg_t *)(uintptr_t)arg;
    const int idx = task_arg->task_idx;
    const int ticks = period_ticks_of(idx);
    const uint64_t period_ns = (uint64_t)ticks * 1000ULL * 1000ULL;
    rtems_id period_id;

    rtems_status_code sc = rtems_rate_monotonic_create(
        rtems_build_name('P', 'C', '0', (char)('0' + idx)), &period_id);
    if (sc != RTEMS_SUCCESSFUL) {
        task_arg->misses = -1;
        rtems_semaphore_release(task_arg->done_sem);
        rtems_task_exit();
    }

    for (int job = 0; job < task_arg->jobs; job++) {
        if (rtems_rate_monotonic_period(period_id, ticks) == RTEMS_TIMEOUT) {
            task_arg->misses++;
        }

        uint64_t start_ns = rtems_clock_get_uptime_nanoseconds();
        if (is_victim(idx)) {
            exp5c_victim_job(idx, job);
        } else {
            exp5c_polluter_job(idx - EXP5C_VICTIMS);
        }
        uint64_t end_ns = rtems_clock_get_uptime_nanoseconds();

        uint64_t exec_ns = end_ns - start_ns;
        task_arg->cpu_mask |= 1U << rtems_scheduler_get_processor();
        task_arg->exec_sum_ns += exec_ns;
        if (exec_ns > task_arg->exec_max_ns) {
            task_arg->exec_max_ns = exec_ns;
        }

    }

    /* Response time comes from RTEMS itself. Its period statistics measure
     * wall time from the release of a period to the call that closes it, on
     * CLOCK_MONOTONIC, so the release instant never has to be reconstructed
     * from the tick counter, whose rate does not track the uptime clock on
     * this simulator. */
    rtems_rate_monotonic_period_statistics stats;
    if (rtems_rate_monotonic_get_statistics(period_id, &stats) ==
        RTEMS_SUCCESSFUL) {
        task_arg->resp_jobs = (int)stats.count;
        task_arg->resp_sum_ns = timespec_ns(&stats.total_wall_time);
        task_arg->resp_max_ns = timespec_ns(&stats.max_wall_time);
    }
    (void)period_ns;

    rtems_rate_monotonic_delete(period_id);
    rtems_semaphore_release(task_arg->done_sem);
    rtems_task_exit();
}

static void print_metric(const char *case_name, int idx, const char *metric,
                         uint64_t value)
{
    printf("RESULT,experiment=exp5c,config=%s,case=%s,task=%d,role=%s,"
           "metric=%s,value=%" PRIu64 "\n",
           EXP5C_CASE_NAME, case_name, idx, role_of(idx), metric, value);
}

static void print_task_result(const char *case_name, const exp5c_arg_t *arg)
{
    const int idx = arg->task_idx;

    print_metric(case_name, idx, "avg_exec_ns", arg->exec_sum_ns / arg->jobs);
    print_metric(case_name, idx, "max_exec_ns", arg->exec_max_ns);
    print_metric(case_name, idx, "avg_resp_ns",
                 arg->resp_sum_ns / (arg->resp_jobs > 0 ? arg->resp_jobs : 1));
    print_metric(case_name, idx, "max_resp_ns", arg->resp_max_ns);
    print_metric(case_name, idx, "period_ns",
                 (uint64_t)period_ticks_of(idx) * 1000ULL * 1000ULL);
    print_metric(case_name, idx, "jobs", (uint64_t)arg->jobs);
    print_metric(case_name, idx, "misses", (uint64_t)arg->misses);
    print_metric(case_name, idx, "cpu_mask", arg->cpu_mask);
    print_metric(case_name, idx, "resp_jobs", (uint64_t)arg->resp_jobs);
}

static void init_arg(int idx, rtems_id sem_id)
{
    args[idx] = (exp5c_arg_t){idx, sem_id, 0, 0, 0, 0, 0, jobs_of(idx), 0, 0};
}

#if !defined(EXP5C_CLUSTERED)
/** @brief Run one task on core 0 alone, which is where U comes from. */
static void run_single(int idx)
{
    cpu_set_t alone_cpu;
    rtems_id sem_id;
    rtems_id task_id;

    CPU_ZERO(&alone_cpu);
    CPU_SET(0, &alone_cpu);
    exp5c_reset_buffers();
    rtems_semaphore_create(rtems_build_name('D', 'S', 'C', '0'), 0,
                           RTEMS_COUNTING_SEMAPHORE, 0, &sem_id);
    init_arg(idx, sem_id);
    rtems_task_create(rtems_build_name('S', 'C', '0', (char)('0' + idx)),
                      TASK_PRIORITY, TASK_STACK_SIZE, RTEMS_DEFAULT_MODES,
                      RTEMS_DEFAULT_ATTRIBUTES, &task_id);
    rtems_task_set_affinity(task_id, sizeof(cpu_set_t), &alone_cpu);
    rtems_task_start(task_id, worker_task,
                     (rtems_task_argument)(uintptr_t)&args[idx]);
    rtems_semaphore_obtain(sem_id, RTEMS_WAIT, RTEMS_NO_TIMEOUT);

    print_task_result("ALONE", &args[idx]);
    rtems_task_delete(task_id);
    rtems_semaphore_delete(sem_id);
}
#endif

/** @brief Run the whole task set under one placement. */
static void run_placement(const exp5c_placement_t *placement)
{
    rtems_id sem_id;
    rtems_id task_ids[EXP5C_MAX_TASKS];

    exp5c_reset_buffers();
    rtems_semaphore_create(rtems_build_name('D', 'G', 'C', '0'), 0,
                           RTEMS_COUNTING_SEMAPHORE, 0, &sem_id);

    for (int idx = 0; idx < EXP5C_ACTIVE_TASKS; idx++) {
        init_arg(idx, sem_id);
        rtems_task_create(rtems_build_name('G', 'C', '0', (char)('0' + idx)),
                          TASK_PRIORITY, TASK_STACK_SIZE, RTEMS_DEFAULT_MODES,
                          RTEMS_DEFAULT_ATTRIBUTES, &task_ids[idx]);
        exp5c_place_task(task_ids[idx], idx, placement, TASK_PRIORITY);
    }
    for (int idx = 0; idx < EXP5C_ACTIVE_TASKS; idx++) {
        rtems_task_start(task_ids[idx], worker_task,
                         (rtems_task_argument)(uintptr_t)&args[idx]);
    }
    for (int idx = 0; idx < EXP5C_ACTIVE_TASKS; idx++) {
        rtems_semaphore_obtain(sem_id, RTEMS_WAIT, RTEMS_NO_TIMEOUT);
    }

    for (int idx = 0; idx < EXP5C_ACTIVE_TASKS; idx++) {
        print_task_result(placement->name, &args[idx]);
        rtems_task_delete(task_ids[idx]);
    }
    rtems_semaphore_delete(sem_id);
}

static void print_setup(const char *metric, long value)
{
    printf("RESULT,experiment=exp5c,config=%s,case=SETUP,metric=%s,"
           "value=%ld\n", EXP5C_CASE_NAME, metric, value);
}

void run_exp5c_cluster_mismatch(void)
{
    size_t placement_count;
    const exp5c_placement_t *placements = exp5c_placements(&placement_count);

    print_setup("victim_distinct", EXP5C_VICTIM_DISTINCT);
    print_setup("victim_stride", EXP5C_VICTIM_STRIDE);
    print_setup("victim_bytes", EXP5C_VICTIM_BYTES);
    print_setup("heavy_sweeps", EXP5C_HEAVY_SWEEPS);
    print_setup("light_sweeps", EXP5C_LIGHT_SWEEPS);
    print_setup("polluter_distinct", EXP5C_POLLUTER_DISTINCT);
    print_setup("polluter_bytes", EXP5C_POLLUTER_BYTES);
    print_setup("victims", EXP5C_VICTIMS);
    print_setup("polluters", EXP5C_POLLUTERS);
    print_setup("jobs", EXP5C_JOBS);

#if !defined(EXP5C_CLUSTERED)
    /* U comes from the flat build; the clustered build measures placement
     * only, so it does not repeat the standalone runs. */
    for (int idx = 0; idx < EXP5C_ACTIVE_TASKS; idx++) {
        run_single(idx);
    }
#endif
    for (size_t i = 0; i < placement_count; i++) {
        run_placement(&placements[i]);
    }
}
