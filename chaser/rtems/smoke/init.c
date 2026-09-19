#include <rtems.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include "workload.h"
#include "config.h"

#define JOB_COUNT 3
#define START RTEMS_EVENT_0

static const unsigned cores[JOB_COUNT] = CHASER_CORES;
static const char *names[JOB_COUNT] = {"packed", "spread", "conflict"};
static void (*const jobs[JOB_COUNT])(void) = {
    chaser_packed, chaser_spread, chaser_conflict
};
static int (*const checks[JOB_COUNT])(void) = {
    chaser_check_packed, chaser_check_spread, chaser_check_conflict
};
static rtems_id coordinator;
static struct {
    uint64_t start, completion, cpu;
    unsigned start_core, end_core;
    int affinity_ok, check;
} results[JOB_COUNT];

static void require_at(rtems_status_code status, unsigned line)
{
    if (status != RTEMS_SUCCESSFUL) {
        printf("SMOKE_ERROR,status=%u,line=%u\n", (unsigned)status, line);
        exit(1);
    }
}

#define require(status) require_at(status, __LINE__)

static uint64_t cpu_time(rtems_id period)
{
    rtems_rate_monotonic_period_status status;
    require(rtems_rate_monotonic_get_status(period, &status));
    if (status.state != RATE_MONOTONIC_ACTIVE) {
        printf("SMOKE_ERROR,period_state=%u\n", (unsigned)status.state);
        exit(1);
    }
    return (uint64_t)status.executed_since_last_period.tv_sec * 1000000000ULL
        + status.executed_since_last_period.tv_nsec;
}

static rtems_task worker(rtems_task_argument index)
{
    unsigned i = (unsigned)index;
    rtems_id period;
    rtems_event_set received;
    require(rtems_rate_monotonic_create(rtems_build_name('P', 'E', 'R', '0' + i), &period));
    require(rtems_event_send(coordinator, (rtems_event_set)1 << i));
    require(rtems_event_receive(START, RTEMS_EVENT_ALL | RTEMS_WAIT,
                                RTEMS_NO_TIMEOUT, &received));
    /* One long period enables the public per-task CPU accounting API. This is
     * a single-job wiring test, not a periodic scheduling performance dataset. */
    require(rtems_rate_monotonic_period(period, 10 * rtems_clock_get_ticks_per_second()));
    results[i].start_core = rtems_scheduler_get_processor();
    results[i].start = rtems_clock_get_uptime_nanoseconds();
    uint64_t before = cpu_time(period);
    jobs[i]();
    results[i].cpu = cpu_time(period) - before;
    results[i].completion = rtems_clock_get_uptime_nanoseconds();
    results[i].end_core = rtems_scheduler_get_processor();
    results[i].check = checks[i]();
    require(rtems_rate_monotonic_delete(period));
    require(rtems_event_send(coordinator, (rtems_event_set)1 << (i + JOB_COUNT)));
    rtems_task_exit();
}

/** @brief Execute the explicit offline mapping after all workers are ready.
 * @param arg Unused RTEMS init argument.
 * @return Does not return; exits after emitting the complete measurement log.
 */
rtems_task Init(rtems_task_argument arg)
{
    (void)arg;
    coordinator = rtems_task_self();
    rtems_id tasks[JOB_COUNT];
    rtems_event_set received;
    unsigned cpus = rtems_scheduler_get_processor_maximum();
    if (cpus != 4) {
        printf("SMOKE_ERROR,cpus=%u\n", cpus);
        exit(1);
    }
    for (unsigned i = 0; i < JOB_COUNT; ++i) {
        cpu_set_t requested, actual;
        CPU_ZERO(&requested);
        CPU_SET(cores[i], &requested);
        require(rtems_task_create(rtems_build_name('J', 'O', 'B', '0' + i), 2,
                                 16384, RTEMS_DEFAULT_MODES, RTEMS_FLOATING_POINT,
                                 &tasks[i]));
        require(rtems_task_set_affinity(tasks[i], sizeof(requested), &requested));
        CPU_ZERO(&actual);
        require(rtems_task_get_affinity(tasks[i], sizeof(actual), &actual));
        results[i].affinity_ok = CPU_EQUAL(&requested, &actual);
        require(rtems_task_start(tasks[i], worker, i));
    }
    require(rtems_event_receive(0x7, RTEMS_EVENT_ALL | RTEMS_WAIT,
                                RTEMS_NO_TIMEOUT, &received));
    /* Common epoch includes the small sequential event-dispatch skew. Nothing
     * is printed while jobs run; worker timestamps precede checksum/log work. */
    uint64_t release = rtems_clock_get_uptime_nanoseconds();
    for (unsigned i = 0; i < JOB_COUNT; ++i)
        require(rtems_event_send(tasks[i], START));
    require(rtems_event_receive(0x38, RTEMS_EVENT_ALL | RTEMS_WAIT,
                                RTEMS_NO_TIMEOUT, &received));
    printf("SMOKE,version=1,cpus=%u,mapping_hash=%s,release_ns=%" PRIu64 "\n",
           cpus, CHASER_MAPPING_HASH, release);
    int passed = 1;
    for (unsigned i = 0; i < JOB_COUNT; ++i) {
        passed &= results[i].affinity_ok && results[i].check
            && results[i].start_core == cores[i] && results[i].end_core == cores[i];
        printf("JOB,task=%s,core=%u,start_core=%u,end_core=%u,affinity_ok=%d,"
               "cpu_ns=%" PRIu64 ",start_ns=%" PRIu64 ",completion_ns=%" PRIu64
               ",check=%d\n", names[i], cores[i], results[i].start_core,
               results[i].end_core, results[i].affinity_ok, results[i].cpu,
               results[i].start, results[i].completion, results[i].check);
    }
    printf("CHASER SMOKE %s\n", passed ? "PASS" : "FAIL");
    exit(passed ? 0 : 1);
}

#define CONFIGURE_APPLICATION_NEEDS_CLOCK_DRIVER
#define CONFIGURE_APPLICATION_NEEDS_SIMPLE_CONSOLE_DRIVER
#define CONFIGURE_MAXIMUM_TASKS 4
#define CONFIGURE_MAXIMUM_PERIODS 3
#define CONFIGURE_MAXIMUM_PROCESSORS 4
#define CONFIGURE_SCHEDULER_EDF_SMP
#define CONFIGURE_MICROSECONDS_PER_TICK 1000
#define CONFIGURE_MINIMUM_TASK_STACK_SIZE 16384
#define CONFIGURE_INIT_TASK_STACK_SIZE 16384
#define CONFIGURE_INIT_TASK_ATTRIBUTES RTEMS_FLOATING_POINT
#define CONFIGURE_ENABLE_FLOATING_POINT
#define CONFIGURE_RTEMS_INIT_TASKS_TABLE
#define CONFIGURE_INIT
#include <rtems/confdefs.h>
