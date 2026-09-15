#include <rtems.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include "workload.h"

static void measure(const char *name, void (*job)(void))
{
    uint64_t start = rtems_clock_get_uptime_nanoseconds();
    job();
    uint64_t elapsed = rtems_clock_get_uptime_nanoseconds() - start;
    printf("RESULT,case=%s,elapsed_ns=%" PRIu64 "\n", name, elapsed);
}

/** @brief Run the build-selected job once in the RTEMS init task.
 * @param arg Unused RTEMS argument.
 * @return Does not return; exits with the workload check status.
 */
rtems_task Init(rtems_task_argument arg)
{
    (void)arg;
    printf("CHASER START sweeps=%d distinct=%d cpus=%" PRIu32 "\n",
           CHASER_SWEEPS, CHASER_DISTINCT, rtems_scheduler_get_processor_maximum());
    measure(CHASER_NAME, CHASER_JOB);
    int passed = CHASER_CHECK();
    printf("CHASER %s\n", passed ? "PASS" : "FAIL");
    exit(passed ? 0 : 1);
}

#define CONFIGURE_APPLICATION_NEEDS_CLOCK_DRIVER
#define CONFIGURE_APPLICATION_NEEDS_SIMPLE_CONSOLE_DRIVER
#define CONFIGURE_MAXIMUM_TASKS 4
#define CONFIGURE_MAXIMUM_PROCESSORS 4
#define CONFIGURE_SCHEDULER_EDF_SMP
#define CONFIGURE_MICROSECONDS_PER_TICK 1000
#define CONFIGURE_INIT_TASK_STACK_SIZE 16384
/* The linked newlib printf implementation uses floating-point registers. */
#define CONFIGURE_INIT_TASK_ATTRIBUTES RTEMS_FLOATING_POINT
#define CONFIGURE_ENABLE_FLOATING_POINT
#define CONFIGURE_RTEMS_INIT_TASKS_TABLE
#define CONFIGURE_INIT
#include <rtems/confdefs.h>
