#ifndef CHASER_PERIODIC_PROBE_H
#define CHASER_PERIODIC_PROBE_H

#include <rtems.h>

/** @brief Kernel period identity, sampled under its lock. */
typedef struct {
    uint64_t epoch_ns, timer, edf;
    unsigned state, postponed;
} period_probe;

/** @brief Read the installed RTEMS period epoch and EDF priority node.
 * @param id Live period owned by the caller.
 * @param out Non-null caller-owned result.
 * @return None; aborts if the period no longer exists.
 */
void probe_period(rtems_id id, period_probe *out);

/** @brief Install the dispatch recorder before diagnostic workers start.
 * @return Public extension creation status; caller must check success.
 */
rtems_status_code probe_start(void);

/** @brief Remove the recorder after all workers reach the cleanup barrier.
 * @return Public extension deletion status; caller must check success.
 */
rtems_status_code probe_stop(void);

/** @brief Emit buffered dispatch evidence after all workers finish.
 * @return None.
 */
void probe_print(void);

extern volatile uint32_t chaser_trace;
#endif
