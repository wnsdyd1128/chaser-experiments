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
#ifdef CHASER_SUSPENDS
/* Self-suspending jobs (task fields suspend_ticks or suspend_points): the job's segments
 * separated by rtems_task_wake_after, all inside the measured bracket. suspends[i] counts task
 * i's sleeps; the flattened tables (workload.c) hold the segment run after each sleep, the
 * checksum expected from the segment before it, and every job's ticks per sleep (point-major).
 * The job reports its last segment's checksum; a wrong earlier checksum is reported as a
 * checksum error. Defined only when some task suspends, so other builds are unchanged. */
static const unsigned suspends[TASK_COUNT] = CHASER_SUSPENDS;
extern uint32_t (*const workload_resume_jobs[])(void);
extern const uint32_t workload_suspend_expected[];
extern const uint32_t workload_suspend_ticks[];
#endif
#ifdef CHASER_OFFSETS
/* Release offsets (task field offset_ticks): a task with an offset arms at t0 with an empty
 * phase period of offsets[i] ticks, so its first job is released at t0 + offset and every later
 * job a period after the previous one. While it waits it is inside a period, so EDF gives it a
 * deadline instead of the background priority of a task without one. Defined only when some
 * task has an offset, so other builds are unchanged. */
static const unsigned offsets[TASK_COUNT] = CHASER_OFFSETS;
#define ARMS_AT_T0(i, j) ((j) == 0 && !offsets[i])
#define PHASE_NS(i) ((uint64_t)offsets[i] * TICK_NS)
#else
#define ARMS_AT_T0(i, j) ((j) == 0)
#define PHASE_NS(i) 0
#endif
/* Restore the original numbering: require() records __LINE__, so builds without suspension
 * or offsets keep the same code as before. */
#line 17
static rtems_id coordinator, start_barrier, tasks[TASK_COUNT];
static uint64_t t0_ns;
static uint32_t t0_tick;
static struct {
    unsigned domain_mask, affinity_mask, scheduler_ok, count;
    uint32_t arm_before_tick, arm_after_tick;
} placement[TASK_COUNT];
typedef struct {
    uint64_t cpu, wall;
    unsigned state, postponed;
} public_status;
static struct {
    uint64_t start, completion, status_before_end, status_after_start;
    unsigned start_core, end_core, checksum, status;
    public_status before, after;
    period_probe diagnostic_before, diagnostic_after;
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
    if (ARCHITECTURE == 3) return cores[i] < 2 ? cores[i] : 2;
    return cores[i];
}

static int active(unsigned i)
{
    return chaser_mode == 0 || chaser_mode == i + 1;
}

static uint64_t nanoseconds(const struct timespec *time)
{
    return (uint64_t)time->tv_sec * 1000000000ULL + time->tv_nsec;
}

static void read_status(rtems_id id, public_status *out)
{
    rtems_rate_monotonic_period_status status;
    require(rtems_rate_monotonic_get_status(id, &status));
    out->cpu = nanoseconds(&status.executed_since_last_period);
    out->wall = nanoseconds(&status.since_last_period);
    out->state = status.state;
    out->postponed = status.postponed_jobs_count;
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
#ifdef CHASER_SUSPENDS
    /* Task i's offsets in the flattened tables, outside every measured job. */
    unsigned segment_base = 0, ticks_base = 0;
    for (unsigned k = 0; k < i; ++k) {
        segment_base += suspends[k];
        ticks_base += suspends[k] * job_counts[k];
    }
#endif
#line 93
    for (unsigned j = 0; j < job_counts[i]; ++j) {
#ifdef CHASER_OFFSETS
        if (j == 0 && offsets[i]) {
            placement[i].arm_before_tick = rtems_clock_get_ticks_since_boot();
            require(rtems_rate_monotonic_period(period, offsets[i]));
            placement[i].arm_after_tick = rtems_clock_get_ticks_since_boot();
            require(rtems_event_send(coordinator, 1U << i));
            require(rtems_barrier_wait(start_barrier, RTEMS_NO_TIMEOUT));
        }
#endif
#line 94
        if (ARMS_AT_T0(i, j)) placement[i].arm_before_tick = rtems_clock_get_ticks_since_boot();
        jobs[i][j].status = rtems_rate_monotonic_period(period, periods[i]);
        if (ARMS_AT_T0(i, j)) {
            placement[i].arm_after_tick = rtems_clock_get_ticks_since_boot();
            /* Every worker arms at t0, then blocks so other nonperiodic
             * workers on the same core can arm before EDF workload begins. */
            require(rtems_event_send(coordinator, 1U << i));
            require(rtems_barrier_wait(start_barrier, RTEMS_NO_TIMEOUT));
        }
#ifdef CHASER_WORKLOAD_LIFECYCLE
        if (!chaser_empty) workload_reset(i);
#endif
        if (chaser_trace) probe_period(period, &jobs[i][j].diagnostic_before);
        jobs[i][j].start_core = rtems_scheduler_get_processor();
        jobs[i][j].start = rtems_clock_get_uptime_nanoseconds();
        read_status(period, &jobs[i][j].before);
        jobs[i][j].status_before_end = rtems_clock_get_uptime_nanoseconds();
        jobs[i][j].checksum = job();
#ifdef CHASER_SUSPENDS
        if (!chaser_empty && suspends[i]) {
            unsigned wrong = 0;
            for (unsigned p = 0; p < suspends[i]; ++p) {
                unsigned ticks = workload_suspend_ticks[ticks_base + p * job_counts[i] + j];
                wrong |= jobs[i][j].checksum != workload_suspend_expected[segment_base + p];
                if (ticks) require(rtems_task_wake_after(ticks));
                jobs[i][j].checksum = workload_resume_jobs[segment_base + p]();
            }
            if (wrong) jobs[i][j].checksum = ~workload_expected[i];
        }
#endif
#line 112
        jobs[i][j].status_after_start = rtems_clock_get_uptime_nanoseconds();
        read_status(period, &jobs[i][j].after);
        jobs[i][j].completion = rtems_clock_get_uptime_nanoseconds();
        jobs[i][j].end_core = rtems_scheduler_get_processor();
        if (chaser_trace) probe_period(period, &jobs[i][j].diagnostic_after);
#ifdef CHASER_WORKLOAD_LIFECYCLE
        if (!chaser_empty) jobs[i][j].checksum = workload_checksum(i);
#endif
        placement[i].count++;
#ifdef CHASER_CONTINUE_AFTER_MISS
        /* Soft-deadline run: a late completion, a postponed release (RTEMS_TIMEOUT) and an
         * expired period are recorded and the worker goes on; a wrong checksum or another
         * period status still stops it, keeping that final record. */
        if ((jobs[i][j].status != RTEMS_SUCCESSFUL && jobs[i][j].status != RTEMS_TIMEOUT)
                || jobs[i][j].checksum != (chaser_empty ? 0 : workload_expected[i]))
            break;
#else
#line 121
        /* Preserve the offending final record, including a final-job miss. */
        if (jobs[i][j].status != RTEMS_SUCCESSFUL
                || jobs[i][j].after.state != RATE_MONOTONIC_ACTIVE
                || jobs[i][j].after.postponed
                || jobs[i][j].completion > t0_ns + PHASE_NS(i) + (uint64_t)(j + 1) * periods[i] * TICK_NS
                || jobs[i][j].checksum != (chaser_empty ? 0 : workload_expected[i]))
            break;
#endif
#line 128
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
    printf("PERIODIC {\"kind\":\"run\",\"plan_hash\":\"%s\",\"contract_id\":\"%s\",\"cpus\":4,"
           "\"mode\":%u,\"trace\":%u,\"empty\":%u,\"t0_ns\":%" PRIu64 ",\"t0_tick\":%u,"
           "\"tick_ns\":%" PRIu64 "}\n", CHASER_PLAN_HASH, CHASER_CONTRACT_ID, (unsigned)chaser_mode,
           (unsigned)chaser_trace, (unsigned)chaser_empty, t0_ns, (unsigned)t0_tick, (uint64_t)TICK_NS);
    for (unsigned i = 0; i < TASK_COUNT; ++i) {
        if (!active(i)) continue;
        printf("PERIODIC {\"kind\":\"task\",\"task\":%u,\"thread\":%u,"
               "\"domain_mask\":%u,\"affinity_mask\":%u,\"scheduler_ok\":%u,"
               "\"arm_before_tick\":%u,\"arm_after_tick\":%u}\n",
               i, (unsigned)tasks[i], placement[i].domain_mask,
               placement[i].affinity_mask, placement[i].scheduler_ok,
               (unsigned)placement[i].arm_before_tick, (unsigned)placement[i].arm_after_tick);
        for (unsigned j = 0; j < placement[i].count; ++j) {
            printf("PERIODIC {\"kind\":\"job\",\"task\":%u,\"job\":%u,"
                   "\"release_ns\":%" PRIu64 ",\"start_ns\":%" PRIu64
                   ",\"completion_ns\":%" PRIu64 ",\"cpu_before_ns\":%" PRIu64
                   ",\"cpu_after_ns\":%" PRIu64 ",\"wall_before_ns\":%" PRIu64
                   ",\"wall_after_ns\":%" PRIu64 ",\"status_before_end_ns\":%" PRIu64
                   ",\"status_after_start_ns\":%" PRIu64 ",\"state_before\":%u,\"state_after\":%u,"
                   "\"postponed_before\":%u,\"postponed_after\":%u,\"period_status\":%u,"
                   "\"start_core\":%u,\"end_core\":%u,\"checksum\":%u",
                   i, j, t0_ns + PHASE_NS(i) + (uint64_t)j * periods[i] * TICK_NS,
                   jobs[i][j].start, jobs[i][j].completion,
                   jobs[i][j].before.cpu, jobs[i][j].after.cpu,
                   jobs[i][j].before.wall, jobs[i][j].after.wall,
                   jobs[i][j].status_before_end, jobs[i][j].status_after_start,
                   jobs[i][j].before.state, jobs[i][j].after.state,
                   jobs[i][j].before.postponed, jobs[i][j].after.postponed,
                   jobs[i][j].status, jobs[i][j].start_core, jobs[i][j].end_core,
                   jobs[i][j].checksum);
            if (chaser_trace) {
                const period_probe *before = &jobs[i][j].diagnostic_before;
                const period_probe *after = &jobs[i][j].diagnostic_after;
                printf(",\"epoch_before_ns\":%" PRIu64 ",\"epoch_after_ns\":%" PRIu64
                       ",\"timer_before\":%" PRIu64 ",\"timer_after\":%" PRIu64
                       ",\"edf_before\":%" PRIu64 ",\"edf_after\":%" PRIu64,
                       before->epoch_ns, after->epoch_ns, before->timer, after->timer,
                       before->edf, after->edf);
            }
            puts("}");
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
     * BSP. Arm tick brackets and public status elapsed-time bounds check phase;
     * exact watchdog/EDF deadlines are available only in diagnostic mode. */
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
