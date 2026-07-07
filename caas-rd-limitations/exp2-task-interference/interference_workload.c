#include <inttypes.h>
#include <rtems.h>
#include <stdio.h>

#include "exp2_workload.h"

#define TASK_STACK_SIZE 4096
#define TASK_PRIORITY 10
#define TASK_PRIORITY_HIGH 5
#define TASK_PRIORITY_LOW 20
#define EXP2_JOBS 4
#ifndef EXP2_TASK_PERIOD_TICKS
#define EXP2_TASK_PERIOD_TICKS 100
#endif
#define TASK_PERIOD_TICKS EXP2_TASK_PERIOD_TICKS
#define TASK_PERIOD_NS ((uint64_t)TASK_PERIOD_TICKS * 1000ULL * 1000ULL)
#define CPU_UNPINNED (-1)

#define SET_AFFINITY(task_id, cpu)                               \
    do {                                                         \
        cpu_set_t cpuset;                                        \
        CPU_ZERO(&cpuset);                                       \
        CPU_SET((cpu), &cpuset);                                 \
        rtems_task_set_affinity((task_id), sizeof(cpuset), &cpuset); \
    } while (0)

typedef struct {
    exp2_job_fn_t job;
    int task_idx;
    rtems_id done_sem;
    uint64_t sum_ns;
    uint64_t avg_ns;
    uint64_t max_ns;
    int misses;
} exp2_arg_t;

static exp2_arg_t args[EXP2_MAX_TASKS];

static exp2_job_fn_t standalone_jobs[EXP2_MAX_TASKS] = {
    exp2_standalone_a, exp2_standalone_b, exp2_standalone_c, exp2_standalone_d,
    exp2_standalone_e, exp2_standalone_f, exp2_standalone_g, exp2_standalone_h,
    exp2_standalone_i, exp2_standalone_j, exp2_standalone_k, exp2_standalone_l,
    exp2_standalone_m, exp2_standalone_n, exp2_standalone_o, exp2_standalone_p,
};

static exp2_reset_fn_t standalone_resets[EXP2_MAX_TASKS] = {
    exp2_reset_standalone_a, exp2_reset_standalone_b,
    exp2_reset_standalone_c, exp2_reset_standalone_d,
    exp2_reset_standalone_e, exp2_reset_standalone_f,
    exp2_reset_standalone_g, exp2_reset_standalone_h,
    exp2_reset_standalone_i, exp2_reset_standalone_j,
    exp2_reset_standalone_k, exp2_reset_standalone_l,
    exp2_reset_standalone_m, exp2_reset_standalone_n,
    exp2_reset_standalone_o, exp2_reset_standalone_p,
};

static rtems_task_priority task_priority(int task_idx)
{
    if (EXP2_INTERFERENCE_TYPE == EXP2_TYPE_B_PREEMPTIVE) {
        return task_idx < EXP2_B_VICTIMS ? TASK_PRIORITY_LOW : TASK_PRIORITY_HIGH;
    }
    return TASK_PRIORITY;
}

static rtems_task worker_task(rtems_task_argument arg)
{
    exp2_arg_t *task_arg = (exp2_arg_t *)(uintptr_t)arg;
    rtems_id period_id;

    rtems_status_code sc = rtems_rate_monotonic_create(
        rtems_build_name('P', '2', '0', (char)('0' + task_arg->task_idx)),
        &period_id);
    if (sc != RTEMS_SUCCESSFUL) {
        task_arg->misses = -1;
        rtems_semaphore_release(task_arg->done_sem);
        rtems_task_exit();
    }

    for (int job = 0; job < EXP2_JOBS; job++) {
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

    task_arg->avg_ns = task_arg->sum_ns / EXP2_JOBS;
    rtems_rate_monotonic_delete(period_id);
    rtems_semaphore_release(task_arg->done_sem);
    rtems_task_exit();
}

static void print_task_result(const char *case_name, const exp2_arg_t *arg)
{
    printf("RESULT,experiment=exp2,case=%s,task=%d,metric=avg_ns,value=%" PRIu64 "\n",
           case_name, arg->task_idx, arg->avg_ns);
    printf("RESULT,experiment=exp2,case=%s,task=%d,metric=max_ns,value=%" PRIu64 "\n",
           case_name, arg->task_idx, arg->max_ns);
    printf("RESULT,experiment=exp2,case=%s,task=%d,metric=period_ns,value=%" PRIu64 "\n",
           case_name, arg->task_idx, TASK_PERIOD_NS);
    printf("RESULT,experiment=exp2,case=%s,task=%d,metric=misses,value=%d\n",
           case_name, arg->task_idx, arg->misses);
    printf("RESULT,experiment=exp2,case=%s,task=%d,metric=utilization_ppm,value=%" PRIu64 "\n",
           case_name, arg->task_idx, (arg->avg_ns * 1000000ULL) / TASK_PERIOD_NS);
}

static void run_single(const char *case_name, int task_idx,
                       exp2_reset_fn_t reset, exp2_job_fn_t job)
{
    rtems_id sem_id;
    rtems_id task_id;

    reset();
    rtems_semaphore_create(rtems_build_name('D', 'S', '2', '0'), 0,
                           RTEMS_COUNTING_SEMAPHORE, 0, &sem_id);

    args[task_idx] = (exp2_arg_t){job, task_idx, sem_id, 0, 0, 0, 0};
    rtems_task_create(rtems_build_name('I', 'S', '2', (char)('0' + task_idx)),
                      task_priority(task_idx), TASK_STACK_SIZE, RTEMS_DEFAULT_MODES,
                      RTEMS_DEFAULT_ATTRIBUTES, &task_id);
    SET_AFFINITY(task_id, 0);

    uint64_t start_ns = rtems_clock_get_uptime_nanoseconds();
    rtems_task_start(task_id, worker_task,
                     (rtems_task_argument)(uintptr_t)&args[task_idx]);
    rtems_semaphore_obtain(sem_id, RTEMS_WAIT, RTEMS_NO_TIMEOUT);
    uint64_t end_ns = rtems_clock_get_uptime_nanoseconds();

    printf("RESULT,experiment=exp2,case=%s,metric=elapsed_ns,value=%" PRIu64 "\n",
           case_name, end_ns - start_ns);
    print_task_result(case_name, &args[task_idx]);

    rtems_task_delete(task_id);
    rtems_semaphore_delete(sem_id);
}

static void maybe_set_affinity(rtems_id task_id, int cpu)
{
    if (cpu >= 0) {
        SET_AFFINITY(task_id, cpu);
    }
}

static void print_status_error(const char *case_name, int task_idx,
                               const char *op, rtems_status_code sc)
{
    printf("RESULT,experiment=exp2,case=%s,task=%d,metric=%s_status,value=%d\n",
           case_name, task_idx, op, (int)sc);
}

static int should_start_as_victim(int idx)
{
    return EXP2_INTERFERENCE_TYPE == EXP2_TYPE_B_PREEMPTIVE &&
           idx < EXP2_B_VICTIMS;
}

static void start_group_task(const char *case_name, int idx,
                             rtems_id task_ids[EXP2_MAX_TASKS])
{
    if (task_ids[idx] == RTEMS_ID_NONE) {
        return;
    }
    rtems_status_code sc = rtems_task_start(
        task_ids[idx], worker_task, (rtems_task_argument)(uintptr_t)&args[idx]);
    if (sc != RTEMS_SUCCESSFUL) {
        print_status_error(case_name, idx, "start", sc);
    }
}

static void fill_type_b_partitioned_cpus(int cpus[EXP2_MAX_TASKS])
{
    const int theta_ppm = 2000;
    int residual[4] = {1000000, 1000000, 1000000, 1000000};
    int used[EXP2_MAX_TASKS] = {0};
    for (int rank = 0; rank < EXP2_ACTIVE_TASKS; rank++) {
        int pick = -1;
        int best_u = -1;
        for (int idx = 0; idx < EXP2_ACTIVE_TASKS; idx++) {
            int u = idx < EXP2_B_VICTIMS ? 25576 : 295174;
            if (!used[idx] && u > best_u) { pick = idx; best_u = u; }
        }
        used[pick] = 1;
        int ca = pick < EXP2_B_VICTIMS ? 7812 : 977;
        int first = ca <= theta_ppm ? 3 : 0;
        int last = ca <= theta_ppm ? 3 : 2;
        int core = first;
        for (int candidate = first + 1; candidate <= last; candidate++) {
            if (residual[candidate] > residual[core]) { core = candidate; }
        }
        cpus[pick] = core;
        residual[core] -= best_u;
    }
}
static void run_group(const char *case_name, const int cpus[EXP2_MAX_TASKS])
{
    rtems_id sem_id;
    rtems_id task_ids[EXP2_MAX_TASKS];
    int created_count = 0;

    for (int idx = 0; idx < EXP2_ACTIVE_TASKS; idx++) {
        standalone_resets[idx]();
    }
    rtems_semaphore_create(rtems_build_name('D', 'N', '2', '0'), 0,
                           RTEMS_COUNTING_SEMAPHORE, 0, &sem_id);

    for (int idx = 0; idx < EXP2_ACTIVE_TASKS; idx++) {
        args[idx] = (exp2_arg_t){standalone_jobs[idx], idx, sem_id, 0, 0, 0, 0};
        rtems_status_code sc = rtems_task_create(
            rtems_build_name('I', 'G', '2', (char)('0' + idx)),
            task_priority(idx),
            TASK_STACK_SIZE, RTEMS_DEFAULT_MODES, RTEMS_DEFAULT_ATTRIBUTES,
            &task_ids[idx]);
        if (sc != RTEMS_SUCCESSFUL) {
            print_status_error(case_name, idx, "create", sc);
            task_ids[idx] = RTEMS_ID_NONE;
            continue;
        }
        created_count++;
        maybe_set_affinity(task_ids[idx], cpus[idx]);
    }

    uint64_t start_ns = rtems_clock_get_uptime_nanoseconds();
    if (EXP2_INTERFERENCE_TYPE == EXP2_TYPE_B_PREEMPTIVE) {
        for (int idx = 0; idx < EXP2_ACTIVE_TASKS; idx++) {
            if (should_start_as_victim(idx)) {
                start_group_task(case_name, idx, task_ids);
            }
        }
        rtems_task_wake_after(1);
        for (int idx = 0; idx < EXP2_ACTIVE_TASKS; idx++) {
            if (!should_start_as_victim(idx)) {
                start_group_task(case_name, idx, task_ids);
            }
        }
    } else {
        for (int idx = 0; idx < EXP2_ACTIVE_TASKS; idx++) {
            start_group_task(case_name, idx, task_ids);
        }
    }
    for (int idx = 0; idx < created_count; idx++) {
        rtems_semaphore_obtain(sem_id, RTEMS_WAIT, RTEMS_NO_TIMEOUT);
    }
    uint64_t end_ns = rtems_clock_get_uptime_nanoseconds();

    printf("RESULT,experiment=exp2,case=%s,metric=elapsed_ns,value=%" PRIu64 "\n",
           case_name, end_ns - start_ns);
    for (int idx = 0; idx < EXP2_ACTIVE_TASKS; idx++) {
        print_task_result(case_name, &args[idx]);
    }

    for (int idx = 0; idx < EXP2_ACTIVE_TASKS; idx++) {
        rtems_task_delete(task_ids[idx]);
    }
    rtems_semaphore_delete(sem_id);
}

void run_exp2_task_interference(void)
{
    const int global_cpus[EXP2_MAX_TASKS] = {
        CPU_UNPINNED, CPU_UNPINNED, CPU_UNPINNED, CPU_UNPINNED,
        CPU_UNPINNED, CPU_UNPINNED, CPU_UNPINNED, CPU_UNPINNED,
        CPU_UNPINNED, CPU_UNPINNED, CPU_UNPINNED, CPU_UNPINNED,
        CPU_UNPINNED, CPU_UNPINNED, CPU_UNPINNED, CPU_UNPINNED};
    const int partitioned_cpus[EXP2_MAX_TASKS] = {
        0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3};
    int type_b_partitioned_cpus[EXP2_MAX_TASKS] = {0};

    for (int idx = 0; idx < EXP2_ACTIVE_TASKS; idx++) {
        run_single("ALONE", idx, standalone_resets[idx], standalone_jobs[idx]);
    }
    run_group("GLOBAL", global_cpus);
    if (EXP2_INTERFERENCE_TYPE == EXP2_TYPE_B_PREEMPTIVE) {
        fill_type_b_partitioned_cpus(type_b_partitioned_cpus);
        run_group("PARTITIONED", type_b_partitioned_cpus);
        return;
    }
    run_group("PARTITIONED", partitioned_cpus);
}
