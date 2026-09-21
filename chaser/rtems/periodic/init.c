#include <rtems.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include "config.h"
#include "workload.h"
#include "probe.h"

#define ARM RTEMS_EVENT_0
#define TICK_NS 1000000ULL

volatile uint32_t chaser_mode = 0x434d4f44;
volatile uint32_t chaser_empty = 0x43454d50;
static const unsigned periods[TASK_COUNT] = CHASER_PERIODS;
static const unsigned job_counts[TASK_COUNT] = CHASER_JOB_COUNTS;
static const unsigned cores[TASK_COUNT] = CHASER_CORES;
static rtems_id coordinator, start_barrier, tasks[TASK_COUNT];
static uint64_t t0_ns;
static uint32_t t0_tick;
static struct {
    unsigned domain_mask, affinity_mask, scheduler_ok, count;
} placement[TASK_COUNT];
static struct {
    uint64_t start, completion, cpu_before, cpu_after;
    unsigned start_core, end_core, checksum, status;
    period_probe before, after;
} jobs[TASK_COUNT][MAX_JOBS];

static void require_at(rtems_status_code status, unsigned line)
{
    if (status != RTEMS_SUCCESSFUL) {
        printf("PERIODIC {\"kind\":\"error\",\"status\":%u,\"line\":%u}\n",
               (unsigned)status, line);
        exit(1);
    }
}
#define require(status) require_at(status, __LINE__)

static unsigned mask(const cpu_set_t *set)
{
    unsigned bits = 0;
    for (unsigned c = 0; c < 4; ++c)
        if (CPU_ISSET(c, set)) bits |= 1U << c;
    return bits;
}

static unsigned scheduler_index(unsigned i)
{
    if (chaser_mode || ARCHITECTURE == 0) return 0;
    if (ARCHITECTURE == 1) return cores[i] != 0;
    return cores[i];
}

static int active(unsigned i)
{
    return chaser_mode == 0 || chaser_mode == i + 1;
}

static uint64_t cpu_time(rtems_id id)
{
    rtems_rate_monotonic_period_status status;
    require(rtems_rate_monotonic_get_status(id, &status));
    return (uint64_t)status.executed_since_last_period.tv_sec * 1000000000ULL
        + status.executed_since_last_period.tv_nsec;
}

static uint32_t empty_job(void) { return 0; }

static rtems_task worker(rtems_task_argument argument)
{
    unsigned i = (unsigned)argument;
    uint32_t (*job)(void) = chaser_empty ? empty_job : workload_jobs[i];
    rtems_id period;
    rtems_event_set received;
    require(rtems_rate_monotonic_create(rtems_build_name('P', 'E', 'R', i), &period));
    require(rtems_event_send(coordinator, 1U << i));
    require(rtems_event_receive(ARM, RTEMS_EVENT_ALL | RTEMS_WAIT,
                                RTEMS_NO_TIMEOUT, &received));
    for (unsigned j = 0; j < job_counts[i]; ++j) {
        jobs[i][j].status = rtems_rate_monotonic_period(period, periods[i]);
        if (j == 0) {
            /* Every worker arms at t0, then blocks so other nonperiodic
             * workers on the same core can arm before EDF workload begins. */
            require(rtems_event_send(coordinator, 1U << i));
            require(rtems_barrier_wait(start_barrier, RTEMS_NO_TIMEOUT));
        }
        probe_period(period, &jobs[i][j].before);
        jobs[i][j].start_core = rtems_scheduler_get_processor();
        jobs[i][j].start = rtems_clock_get_uptime_nanoseconds();
        jobs[i][j].cpu_before = cpu_time(period);
        jobs[i][j].checksum = job();
        jobs[i][j].cpu_after = cpu_time(period);
        jobs[i][j].completion = rtems_clock_get_uptime_nanoseconds();
        jobs[i][j].end_core = rtems_scheduler_get_processor();
        probe_period(period, &jobs[i][j].after);
        placement[i].count++;
        /* Preserve the offending final record, including a final-job miss. */
        if (jobs[i][j].status != RTEMS_SUCCESSFUL
                || jobs[i][j].after.state != RATE_MONOTONIC_ACTIVE
                || jobs[i][j].after.postponed
                || jobs[i][j].completion > t0_ns + (uint64_t)(j + 1) * periods[i] * TICK_NS
                || jobs[i][j].checksum != (chaser_empty ? 0 : workload_expected[i]))
            break;
    }
    /* Keep object-allocator lock contention and teardown dispatches outside
     * every worker's measurement interval, not only this worker's last job. */
    require(rtems_rate_monotonic_cancel(period));
    require(rtems_event_send(coordinator, 1U << i));
    require(rtems_barrier_wait(start_barrier, RTEMS_NO_TIMEOUT));
    require(rtems_rate_monotonic_delete(period));
    require(rtems_event_send(coordinator, 1U << i));
    rtems_task_exit();
}

static void print_results(void)
{
    printf("PERIODIC {\"kind\":\"run\",\"plan_hash\":\"%s\",\"cpus\":4,"
           "\"mode\":%u,\"trace\":%u,\"empty\":%u,\"t0_ns\":%" PRIu64 ",\"t0_tick\":%u,"
           "\"tick_ns\":%" PRIu64 "}\n", CHASER_PLAN_HASH, (unsigned)chaser_mode,
           (unsigned)chaser_trace, (unsigned)chaser_empty, t0_ns, (unsigned)t0_tick, (uint64_t)TICK_NS);
    for (unsigned i = 0; i < TASK_COUNT; ++i) {
        if (!active(i)) continue;
        printf("PERIODIC {\"kind\":\"task\",\"task\":%u,\"thread\":%u,"
               "\"domain_mask\":%u,\"affinity_mask\":%u,\"scheduler_ok\":%u}\n",
               i, (unsigned)tasks[i], placement[i].domain_mask,
               placement[i].affinity_mask, placement[i].scheduler_ok);
        for (unsigned j = 0; j < placement[i].count; ++j) {
            printf("PERIODIC {\"kind\":\"job\",\"task\":%u,\"job\":%u,"
                   "\"release_ns\":%" PRIu64 ",\"start_ns\":%" PRIu64
                   ",\"completion_ns\":%" PRIu64 ",\"cpu_before_ns\":%" PRIu64
                   ",\"cpu_after_ns\":%" PRIu64 ",\"epoch_before_ns\":%" PRIu64
                   ",\"epoch_after_ns\":%" PRIu64 ",\"timer_before\":%" PRIu64
                   ",\"timer_after\":%" PRIu64 ",\"edf_before\":%" PRIu64
                   ",\"edf_after\":%" PRIu64 ",\"state_before\":%u,\"state_after\":%u,"
                   "\"postponed_before\":%u,\"postponed_after\":%u,\"period_status\":%u,"
                   "\"start_core\":%u,\"end_core\":%u,\"checksum\":%u}\n",
                   i, j, t0_ns + (uint64_t)j * periods[i] * TICK_NS,
                   jobs[i][j].start, jobs[i][j].completion,
                   jobs[i][j].cpu_before, jobs[i][j].cpu_after,
                   jobs[i][j].before.epoch_ns, jobs[i][j].after.epoch_ns,
                   jobs[i][j].before.timer, jobs[i][j].after.timer,
                   jobs[i][j].before.edf, jobs[i][j].after.edf,
                   jobs[i][j].before.state, jobs[i][j].after.state,
                   jobs[i][j].before.postponed, jobs[i][j].after.postponed,
                   jobs[i][j].status, jobs[i][j].start_core, jobs[i][j].end_core,
                   jobs[i][j].checksum);
        }
    }
    probe_print();
    puts("PERIODIC {\"kind\":\"end\",\"complete\":1}");
}

/** @brief Run a finite periodic taskset with explicit scheduler domains.
 * @param argument Unused RTEMS initialization argument.
 * @return Does not return; raw results are printed before simulator exit.
 */
rtems_task Init(rtems_task_argument argument)
{
    (void)argument;
    if (chaser_mode > TASK_COUNT || chaser_trace > 1 || chaser_empty > 1
            || (chaser_mode && ARCHITECTURE != 2)
            || rtems_scheduler_get_processor_maximum() != 4) {
        puts("PERIODIC {\"kind\":\"error\",\"reason\":\"boot_mode\"}");
        exit(1);
    }
    coordinator = rtems_task_self();
    if (chaser_trace) require(probe_start());
    cpu_set_t requested;
    CPU_ZERO(&requested);
    CPU_SET(0, &requested);
    require(rtems_task_set_affinity(coordinator, sizeof(requested), &requested));
    workload_prepare();
    require(rtems_barrier_create(rtems_build_name('B','O','O','T'),
                                 RTEMS_BARRIER_AUTOMATIC_RELEASE,
                                 chaser_mode ? 2 : TASK_COUNT + 1, &start_barrier));
    rtems_event_set all = 0, received;
    for (unsigned i = 0; i < TASK_COUNT; ++i) {
        if (!active(i)) continue;
        rtems_id scheduler, actual;
        cpu_set_t set;
        require(rtems_scheduler_ident(rtems_build_name('E', 'D', 'F',
                                      '0' + scheduler_index(i)), &scheduler));
        require(rtems_task_create(rtems_build_name('J', 'O', 'B', i), 2, 16384,
                                  RTEMS_DEFAULT_MODES, RTEMS_FLOATING_POINT, &tasks[i]));
        require(rtems_task_set_scheduler(tasks[i], scheduler, 2));
        CPU_ZERO(&requested);
        for (unsigned c = 0; c < 4; ++c) CPU_SET(c, &requested);
        require(rtems_task_set_affinity(tasks[i], sizeof(requested), &requested));
        require(rtems_task_get_scheduler(tasks[i], &actual));
        placement[i].scheduler_ok = actual == scheduler;
        require(rtems_scheduler_get_processor_set(scheduler, sizeof(set), &set));
        placement[i].domain_mask = mask(&set);
        require(rtems_task_get_affinity(tasks[i], sizeof(set), &set));
        placement[i].affinity_mask = mask(&set);
        require(rtems_task_start(tasks[i], worker, i));
        all |= 1U << i;
    }
    require(rtems_event_receive(all, RTEMS_EVENT_ALL | RTEMS_WAIT, RTEMS_NO_TIMEOUT, &received));
    /* A fixed future tick is the nominal epoch. Uptime starts at zero on this
     * BSP; raw kernel epochs verify tick phase instead of assuming dispatch
     * time equals release time. */
    t0_tick = rtems_clock_get_ticks_since_boot() + 20;
    t0_ns = (uint64_t)t0_tick * TICK_NS;
    require(rtems_task_wake_after(t0_tick - rtems_clock_get_ticks_since_boot()));
    for (unsigned i = 0; i < TASK_COUNT; ++i)
        if (active(i)) require(rtems_event_send(tasks[i], ARM));
    require(rtems_event_receive(all, RTEMS_EVENT_ALL | RTEMS_WAIT, RTEMS_NO_TIMEOUT, &received));
    require(rtems_barrier_wait(start_barrier, RTEMS_NO_TIMEOUT));
    require(rtems_event_receive(all, RTEMS_EVENT_ALL | RTEMS_WAIT, RTEMS_NO_TIMEOUT, &received));
    if (chaser_trace) require(probe_stop());
    require(rtems_barrier_wait(start_barrier, RTEMS_NO_TIMEOUT));
    require(rtems_event_receive(all, RTEMS_EVENT_ALL | RTEMS_WAIT, RTEMS_NO_TIMEOUT, &received));
    print_results();
    exit(0);
}

#define CONFIGURE_APPLICATION_NEEDS_CLOCK_DRIVER
#define CONFIGURE_APPLICATION_NEEDS_SIMPLE_CONSOLE_DRIVER
#define CONFIGURE_MAXIMUM_TASKS (TASK_COUNT + 1)
#define CONFIGURE_MAXIMUM_PERIODS TASK_COUNT
#define CONFIGURE_MAXIMUM_BARRIERS 1
#define CONFIGURE_MAXIMUM_PROCESSORS 4
#define CONFIGURE_SCHEDULER_EDF_SMP
#define CONFIGURE_MICROSECONDS_PER_TICK 1000
#define CONFIGURE_MINIMUM_TASK_STACK_SIZE 16384
#define CONFIGURE_INIT_TASK_STACK_SIZE 16384
#define CONFIGURE_INIT_TASK_ATTRIBUTES RTEMS_FLOATING_POINT
#define CONFIGURE_ENABLE_FLOATING_POINT
#define CONFIGURE_MAXIMUM_USER_EXTENSIONS 1
#include <rtems/scheduler.h>
#include "topology.h"
#define CONFIGURE_RTEMS_INIT_TASKS_TABLE
#define CONFIGURE_INIT
#include <rtems/confdefs.h>
