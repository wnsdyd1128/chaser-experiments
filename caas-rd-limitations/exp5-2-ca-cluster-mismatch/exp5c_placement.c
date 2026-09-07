/**
 * @file exp5c_placement.c
 * @brief Placement table of exp5-2 and the two ways of realising a placement.
 *
 * All placements but GLOBAL give the victims cores 0 to 2 and the polluters
 * core 3, so they differ in how freely a victim moves inside those cores and
 * in nothing else. PARTITIONED and PARTITIONED_ALT differ only in which two
 * victims share a core: the first pairs them in index order, which puts two
 * in-phase victims together, the second pairs them across phases.
 */

#include "exp5c_placement.h"

#include <stdio.h>

const exp5c_placement_t *exp5c_placements(size_t *count)
{
#if defined(EXP5C_CLUSTERED)
    static const exp5c_placement_t placements[] = {
        {"CLUSTERED", {0}},
    };
#else
    static const exp5c_placement_t placements[] = {
        {"GLOBAL", {0xF, 0xF, 0xF, 0xF, 0xF, 0xF, 0xF, 0xF}},
        {"PARTITIONED", {0x1, 0x1, 0x2, 0x4, 0x8, 0x8, 0x8, 0x8}},
        {"PARTITIONED_ALT", {0x1, 0x4, 0x1, 0x2, 0x8, 0x8, 0x8, 0x8}},
    };
#endif

    *count = sizeof(placements) / sizeof(placements[0]);
    return placements;
}

static void report_failure(const char *metric, rtems_status_code sc)
{
    printf("RESULT,experiment=exp5c,config=%s,case=SETUP,metric=%s,value=%d\n",
           EXP5C_CASE_NAME, metric, (int)sc);
}

#if !defined(EXP5C_CLUSTERED)
static void set_affinity_mask(rtems_id task_id, uint32_t mask)
{
    cpu_set_t cpuset;

    CPU_ZERO(&cpuset);
    for (int cpu = 0; cpu < EXP5C_CORES; cpu++) {
        if ((mask & (1u << cpu)) != 0) {
            CPU_SET(cpu, &cpuset);
        }
    }

    rtems_status_code sc = rtems_task_set_affinity(task_id, sizeof(cpuset),
                                                   &cpuset);
    if (sc != RTEMS_SUCCESSFUL) {
        report_failure("affinity_status", sc);
    }
}
#endif

void exp5c_place_task(rtems_id task_id, int task_idx,
                      const exp5c_placement_t *placement,
                      rtems_task_priority priority)
{
#if defined(EXP5C_CLUSTERED)
    rtems_id scheduler_id;
    rtems_name name = task_idx < EXP5C_VICTIMS ? EXP5C_SCHED_A : EXP5C_SCHED_B;

    rtems_status_code sc = rtems_scheduler_ident(name, &scheduler_id);
    if (sc == RTEMS_SUCCESSFUL) {
        sc = rtems_task_set_scheduler(task_id, scheduler_id, priority);
    }
    if (sc != RTEMS_SUCCESSFUL) {
        report_failure("cluster_status", sc);
    }
    (void)placement;
#else
    (void)priority;
    set_affinity_mask(task_id, placement->mask[task_idx]);
#endif
}
