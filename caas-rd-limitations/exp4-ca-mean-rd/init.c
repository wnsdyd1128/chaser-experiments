#include <rtems.h>
#include <stdio.h>

#define MICROSECONDS_PER_TICK 1000
#define TASK_STACK_SIZE 4096

void run_exp4_ca_mean_rd(void);

rtems_task Init(rtems_task_argument arg)
{
    (void)arg;

    printf("\n=== EXP4: CA mean-RD limitation, time domain ===\n");
    run_exp4_ca_mean_rd();
    printf("=== EXP4: complete ===\n");
}

#define CONFIGURE_APPLICATION_NEEDS_CLOCK_DRIVER
#define CONFIGURE_APPLICATION_NEEDS_SIMPLE_CONSOLE_DRIVER

#define CONFIGURE_MAXIMUM_TASKS 4
#define CONFIGURE_MAXIMUM_PROCESSORS 4

#define CONFIGURE_INIT_TASK_ATTRIBUTES RTEMS_FLOATING_POINT
#define CONFIGURE_ENABLE_FLOATING_POINT

#define CONFIGURE_RTEMS_INIT_TASKS_TABLE
#define CONFIGURE_INIT_TASK_STACK_SIZE TASK_STACK_SIZE

#define CONFIGURE_MICROSECONDS_PER_TICK MICROSECONDS_PER_TICK
#define CONFIGURE_SCHEDULER_EDF_SMP
#define CONFIGURE_MAXIMUM_PRIORITY 255

#define CONFIGURE_INIT
#include <rtems/confdefs.h>
