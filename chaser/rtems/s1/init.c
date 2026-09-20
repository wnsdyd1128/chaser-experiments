#include <rtems.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

/** @brief Initialize data outside the analyzed region. @return None. */
void s1_prepare(void);
/** @brief Provide the generated load-count checksum. @return Expected sum. */
uint32_t s1_expected(void);
/** @brief Read initialized data without a global sink. @return Accumulated sum. */
uint32_t chaser_s1(void);

/** @brief Check the linked workload once; this does not measure cache outcomes.
 * @param arg Unused RTEMS argument.
 * @return Does not return; exits with the checksum status.
 */
rtems_task Init(rtems_task_argument arg)
{
    (void)arg;
    s1_prepare();
    uint32_t actual = chaser_s1();
    uint32_t expected = s1_expected();
    printf("S1 checksum=%" PRIu32 " expected=%" PRIu32 " %s\n",
           actual, expected, actual == expected ? "PASS" : "FAIL");
    exit(actual == expected ? 0 : 1);
}

#define CONFIGURE_APPLICATION_NEEDS_CLOCK_DRIVER
#define CONFIGURE_APPLICATION_NEEDS_SIMPLE_CONSOLE_DRIVER
#define CONFIGURE_MAXIMUM_TASKS 4
#define CONFIGURE_MAXIMUM_PROCESSORS 4
#define CONFIGURE_SCHEDULER_EDF_SMP
#define CONFIGURE_INIT_TASK_STACK_SIZE 16384
#define CONFIGURE_INIT_TASK_ATTRIBUTES RTEMS_FLOATING_POINT
#define CONFIGURE_ENABLE_FLOATING_POINT
#define CONFIGURE_RTEMS_INIT_TASKS_TABLE
#define CONFIGURE_INIT
#include <rtems/confdefs.h>
