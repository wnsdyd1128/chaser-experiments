#include <rtems.h>
#include <stdio.h>

#include "exp5c_workload.h"

#define MICROSECONDS_PER_TICK 1000
#define TASK_STACK_SIZE 8192

void run_exp5c_cluster_mismatch(void);

rtems_task Init(rtems_task_argument arg)
{
    (void)arg;

    printf("\n=== EXP5-2: clustered is the ground truth, case %s ===\n",
           EXP5C_CASE_NAME);
    run_exp5c_cluster_mismatch();
    printf("=== EXP5-2: complete ===\n");
}

#define CONFIGURE_APPLICATION_NEEDS_CLOCK_DRIVER
#define CONFIGURE_APPLICATION_NEEDS_SIMPLE_CONSOLE_DRIVER

#define CONFIGURE_MAXIMUM_TASKS 16
#define CONFIGURE_MAXIMUM_SEMAPHORES 8
#define CONFIGURE_MAXIMUM_PERIODS 16
#define CONFIGURE_MAXIMUM_PROCESSORS 4

#define CONFIGURE_INIT_TASK_ATTRIBUTES RTEMS_FLOATING_POINT
#define CONFIGURE_ENABLE_FLOATING_POINT

#define CONFIGURE_RTEMS_INIT_TASKS_TABLE
#define CONFIGURE_INIT_TASK_STACK_SIZE TASK_STACK_SIZE

#define CONFIGURE_MICROSECONDS_PER_TICK MICROSECONDS_PER_TICK
#define CONFIGURE_MAXIMUM_PRIORITY 255

/* Clustered scheduling needs one scheduler instance per cluster, and a
 * processor belongs to exactly one instance for the life of the system. That
 * is why the clustered placement is a separate binary rather than another case
 * inside the flat one: affinity masks cannot express it, because the EDF SMP
 * scheduler accepts only one-to-one or full affinity sets. */
#define CONFIGURE_SCHEDULER_EDF_SMP

#if defined(EXP5C_CLUSTERED)
#include <rtems/scheduler.h>

RTEMS_SCHEDULER_EDF_SMP(cluster_a);
RTEMS_SCHEDULER_EDF_SMP(cluster_b);

#define CONFIGURE_SCHEDULER_TABLE_ENTRIES \
    RTEMS_SCHEDULER_TABLE_EDF_SMP(cluster_a, EXP5C_SCHED_A), \
    RTEMS_SCHEDULER_TABLE_EDF_SMP(cluster_b, EXP5C_SCHED_B)

#define CONFIGURE_SCHEDULER_ASSIGNMENTS \
    RTEMS_SCHEDULER_ASSIGN(0, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY), \
    RTEMS_SCHEDULER_ASSIGN(0, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY), \
    RTEMS_SCHEDULER_ASSIGN(0, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY), \
    RTEMS_SCHEDULER_ASSIGN(1, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY)
#endif

#define CONFIGURE_INIT
#include <rtems/confdefs.h>
