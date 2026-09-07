#include <rtems.h>
#include <stdio.h>

#define MICROSECONDS_PER_TICK 1000
#define TASK_STACK_SIZE 4096

void run_exp3_ca_saturation(void);

rtems_task Init(rtems_task_argument arg)
{
    (void)arg;

    printf("\n=== EXP3: CA metric saturation, time domain ===\n");
    run_exp3_ca_saturation();
    printf("=== EXP3: complete ===\n");
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
