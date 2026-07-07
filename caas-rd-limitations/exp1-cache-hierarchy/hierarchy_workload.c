#include <inttypes.h>
#include <rtems.h>
#include <stdio.h>

#include "exp1_workload.h"

#define EXP1_JOBS 3
#define TASK_PRIORITY 10
#define TASK_STACK_SIZE 8192
#define TASK_PERIOD_TICKS 2000
#define TASK_PERIOD_NS ((uint64_t)TASK_PERIOD_TICKS * 1000ULL * 1000ULL)

typedef struct {
    exp1_job_fn_t job;
    rtems_id done_sem;
    uint64_t sum_ns;
    uint64_t avg_ns;
    uint64_t max_ns;
    int misses;
} exp1_arg_t;

static exp1_arg_t exp1_arg;

static rtems_task worker_task(rtems_task_argument arg)
{
    exp1_arg_t *task_arg = (exp1_arg_t *)(uintptr_t)arg;
    rtems_id period_id;

    rtems_rate_monotonic_create(rtems_build_name('P', '1', '0', '0'),
                                &period_id);

    for (int job = 0; job < EXP1_JOBS; job++) {
        if (rtems_rate_monotonic_period(period_id, TASK_PERIOD_TICKS) ==
            RTEMS_TIMEOUT) {
            task_arg->misses++;
        }

        uint64_t start_ns = rtems_clock_get_uptime_nanoseconds();
        task_arg->job();
        uint64_t end_ns = rtems_clock_get_uptime_nanoseconds();
        uint64_t elapsed_ns = end_ns - start_ns;

        task_arg->sum_ns += elapsed_ns;
        if (elapsed_ns > task_arg->max_ns) {
            task_arg->max_ns = elapsed_ns;
        }
    }

    task_arg->avg_ns = task_arg->sum_ns / EXP1_JOBS;
    rtems_rate_monotonic_delete(period_id);
    rtems_semaphore_release(task_arg->done_sem);
    rtems_task_exit();
}

static void run_case(const char *case_name, int size, exp1_reset_fn_t reset,
                     exp1_job_fn_t job)
{
    rtems_id sem_id;
    rtems_id task_id;

    reset();
    rtems_semaphore_create(rtems_build_name('D', 'N', '1', '0'), 0,
                           RTEMS_COUNTING_SEMAPHORE, 0, &sem_id);
    exp1_arg = (exp1_arg_t){job, sem_id, 0, 0, 0, 0};

    uint64_t start_ns = rtems_clock_get_uptime_nanoseconds();
    rtems_task_create(rtems_build_name('W', 'K', '1', '0'), TASK_PRIORITY,
                      TASK_STACK_SIZE, RTEMS_DEFAULT_MODES,
                      RTEMS_DEFAULT_ATTRIBUTES, &task_id);
    rtems_task_start(task_id, worker_task,
                     (rtems_task_argument)(uintptr_t)&exp1_arg);
    rtems_semaphore_obtain(sem_id, RTEMS_WAIT, RTEMS_NO_TIMEOUT);
    uint64_t end_ns = rtems_clock_get_uptime_nanoseconds();
    uint64_t elapsed_ns = end_ns - start_ns;

    printf("RESULT,experiment=exp1,case=%s,metric=working_set_bytes,value=%d\n",
           case_name, size);
    printf("RESULT,experiment=exp1,case=%s,metric=elapsed_ns,value=%" PRIu64 "\n",
           case_name, elapsed_ns);
    printf("RESULT,experiment=exp1,case=%s,metric=avg_ns,value=%" PRIu64 "\n",
           case_name, exp1_arg.avg_ns);
    printf("RESULT,experiment=exp1,case=%s,metric=max_ns,value=%" PRIu64 "\n",
           case_name, exp1_arg.max_ns);
    printf("RESULT,experiment=exp1,case=%s,metric=period_ns,value=%" PRIu64 "\n",
           case_name, TASK_PERIOD_NS);
    printf("RESULT,experiment=exp1,case=%s,metric=misses,value=%d\n",
           case_name, exp1_arg.misses);
    printf("RESULT,experiment=exp1,case=%s,metric=utilization_ppm,value=%" PRIu64 "\n",
           case_name, (exp1_arg.avg_ns * 1000000ULL) / TASK_PERIOD_NS);

    rtems_task_delete(task_id);
    rtems_semaphore_delete(sem_id);
}

void run_exp1_cache_hierarchy(void)
{
    run_case("L1_FIT", EXP1_WS_L1_FIT, exp1_reset_l1_fit, exp1_l1_fit);
    run_case("L1_EXCEED", EXP1_WS_L1_EXCEED, exp1_reset_l1_exceed,
             exp1_l1_exceed);
    run_case("L2_FIT", EXP1_WS_L2_FIT, exp1_reset_l2_fit, exp1_l2_fit);
    run_case("L2_PRESSURE", EXP1_WS_L2_PRESSURE, exp1_reset_l2_pressure,
             exp1_l2_pressure);
}
