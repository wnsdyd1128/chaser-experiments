#ifndef EXP5C_PLACEMENT_H
#define EXP5C_PLACEMENT_H

#include <rtems.h>
#include <stddef.h>
#include <stdint.h>

#include "exp5c_workload.h"

/**
 * @file exp5c_placement.h
 * @brief The placements exp5-2 compares, and how a task is put in one.
 *
 * A placement is named and carries one processor mask per task. The flat build
 * realises it as a one-to-one affinity; the clustered build ignores the masks
 * and moves the task to the scheduler instance that owns its cluster, because
 * the EDF SMP scheduler accepts only one-to-one or full affinity sets.
 */
typedef struct {
    const char *name;
    uint32_t mask[EXP5C_MAX_TASKS];
} exp5c_placement_t;

/**
 * @brief Placements measured by this build.
 *
 * @param[out] count Number of placements returned (non-null).
 * @return Placement array, owned by the module and valid for the run.
 */
const exp5c_placement_t *exp5c_placements(size_t *count);

/**
 * @brief Put one task where the placement under test wants it.
 *
 * @param[in] task_id   Dormant task to place.
 * @param[in] task_idx  Index of the task in the set (0 <= idx < active tasks).
 * @param[in] placement Placement under test (non-null).
 * @param[in] priority  Priority to keep when the task changes scheduler.
 *
 * @note A failure is reported as a SETUP RESULT line rather than aborting, so
 *       a run that could not be placed is visible in the log instead of
 *       silently measuring something else.
 */
void exp5c_place_task(rtems_id task_id, int task_idx,
                      const exp5c_placement_t *placement,
                      rtems_task_priority priority);

#endif
