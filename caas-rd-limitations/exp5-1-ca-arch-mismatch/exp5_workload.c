/**
 * @file exp5_workload.c
 * @brief Job bodies of the exp5 task set: four victims and four polluters.
 *
 * Every job is the exp3 cyclic sweep with its stride left free. Holding the
 * address count fixed holds CA = 1 / distinct fixed, while the stride decides
 * how many cache lines those addresses occupy. A victim therefore keeps one CA
 * across cases whose cached footprint differs by the stride ratio, which is the
 * whole point of the experiment: CA counts addresses, the cache counts lines.
 *
 * The sweep is a pure read. A store would add an RD = 0 point to the histogram
 * and a write-through transaction per iteration, neither of which the cost axis
 * here is asking about.
 */

#include "exp5_workload.h"

#include <string.h>

static volatile uint8_t victim_data[EXP5_VICTIMS][EXP5_VICTIM_BYTES]
    __attribute__((aligned(4096)));
static volatile uint8_t polluter_data[EXP5_POLLUTERS][EXP5_POLLUTER_BYTES]
    __attribute__((aligned(4096)));

/**
 * @brief Touch `distinct` addresses `stride` bytes apart, `sweeps` times.
 *
 * @param[in] buf      Task-private buffer of at least distinct * stride bytes.
 * @param[in] distinct Addresses touched per sweep (> 0).
 * @param[in] stride   Bytes between consecutive addresses (> 0).
 * @param[in] sweeps   Repetitions of the cycle (>= 2, so a reuse exists).
 *
 * @note buf is volatile so the reads survive optimization; the access pattern
 *       is the measured quantity.
 */
static void sweep(volatile uint8_t *buf, long distinct, long stride, long sweeps)
{
    const long bytes = distinct * stride;

    for (long s = 0; s < sweeps; s++) {
        for (long i = 0; i < bytes; i += stride) {
            (void)buf[i];
        }
    }
}

void exp5_victim_job(int index)
{
    sweep(victim_data[index], EXP5_VICTIM_DISTINCT, EXP5_VICTIM_STRIDE,
          EXP5_VICTIM_SWEEPS);
}

void exp5_polluter_job(int index)
{
    sweep(polluter_data[index], EXP5_POLLUTER_DISTINCT, EXP5_POLLUTER_STRIDE,
          EXP5_POLLUTER_SWEEPS);
}

/**
 * @brief Zero every task buffer, so each measured case starts from one state.
 *
 * Called between cases rather than between jobs: within a case the cache state
 * left by the previous job is exactly what the measurement is about.
 */
void exp5_reset_buffers(void)
{
    memset((void *)victim_data, 0, sizeof(victim_data));
    memset((void *)polluter_data, 0, sizeof(polluter_data));
}
