#include "probe.h"
#include <rtems/rtems/ratemonimpl.h>
#include <rtems/score/timestampimpl.h>
#include <rtems/score/schedulerimpl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

/* The runner selects these initialized words before boot using a simulator
 * batch. They are not BSS, and no executable or workload is patched. */
volatile uint32_t chaser_trace = 0x43545243;

void probe_period(rtems_id id, period_probe *out)
{
    ISR_lock_Context lock;
    Rate_monotonic_Control *period = _Rate_monotonic_Get(id, &lock);
    if (period == NULL)
        abort();
    _Rate_monotonic_Acquire_critical(period, &lock);
    /* Match rtems_clock_get_uptime_nanoseconds(): the internal timecounter
     * starts at SBT_1S, whereas the public API subtracts that offset. */
    Timestamp_Control zero_based = period->time_period_initiated - SBT_1S;
    out->epoch_ns = _Timestamp_Get_as_nanoseconds(&zero_based);
    out->timer = period->Timer.expire;
    out->edf = SCHEDULER_PRIORITY_UNMAP(period->Priority.priority);
    out->state = period->state;
    out->postponed = period->postponed_jobs;
    _Rate_monotonic_Release(period, &lock);
}

#define TRACE_CAPACITY 8192
static struct { uint64_t ns; rtems_id task; } dispatches[4][TRACE_CAPACITY];
static unsigned counts[4];
static rtems_id extension;

static void probe_switch(Thread_Control *executing, Thread_Control *heir)
{
    (void)executing;
    if (chaser_trace != 1)
        return;
    /* Dispatch runs with dispatching disabled: each core owns its buffer. */
    unsigned core = rtems_scheduler_get_processor();
    unsigned n = counts[core]++;
    if (n < TRACE_CAPACITY) {
        dispatches[core][n].ns = rtems_clock_get_uptime_nanoseconds();
        dispatches[core][n].task = heir->Object.id;
    }
}

rtems_status_code probe_start(void)
{
    const rtems_extensions_table callbacks = { .thread_switch = probe_switch };
    return rtems_extension_create(rtems_build_name('T', 'R', 'C', 'E'),
                                  &callbacks, &extension);
}

rtems_status_code probe_stop(void)
{
    return rtems_extension_delete(extension);
}

void probe_print(void)
{
    if (chaser_trace != 1)
        return;
    for (unsigned c = 0; c < 4; ++c) {
        unsigned n = counts[c];
        if (n > TRACE_CAPACITY) {
            puts("PERIODIC {\"kind\":\"error\",\"reason\":\"trace_overflow\"}");
            n = TRACE_CAPACITY;
        }
        for (unsigned i = 0; i < n; ++i)
            printf("PERIODIC {\"kind\":\"switch\",\"core\":%u,\"thread\":%u,"
                   "\"ns\":%" PRIu64 "}\n", c, (unsigned)dispatches[c][i].task,
                   dispatches[c][i].ns);
    }
}
