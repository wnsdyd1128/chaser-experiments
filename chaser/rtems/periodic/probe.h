#ifndef CHASER_PERIODIC_PROBE_H
#define CHASER_PERIODIC_PROBE_H

#include <rtems.h>
#include <rtems/score/thread.h>

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

/** @brief Record scheduler dispatches only when trace mode is selected.
 * @param executing Outgoing thread, owned by RTEMS.
 * @param heir Incoming thread, owned by RTEMS.
 * @return None. Overflow is retained and fails trace validation.
 */
void probe_switch(Thread_Control *executing, Thread_Control *heir);

/** @brief Emit buffered dispatch evidence after all workers finish.
 * @return None.
 */
void probe_print(void);

extern volatile uint32_t chaser_trace;
#endif
