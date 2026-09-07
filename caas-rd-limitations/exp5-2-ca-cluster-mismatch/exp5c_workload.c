/**
 * @file exp5c_workload.c
 * @brief Job bodies of the exp5-2 task set: phased victims and polluters.
 *
 * The sweep is the exp3 cycle with a free stride, so CA = 1 / distinct holds
 * whatever the stride is, while the stride alone decides how many cache lines
 * a victim occupies. Victims alternate a heavy and a light job; victims 0 and 1
 * carry phase 0 and victims 2 and 3 carry phase 1, so at every release exactly
 * two victims run heavy. Averaged over the run all four are identical, which is
 * all that U reports.
 */

#include "exp5c_workload.h"

#include <string.h>

static volatile uint8_t victim_data[EXP5C_VICTIMS][EXP5C_VICTIM_BYTES]
    __attribute__((aligned(4096)));
static volatile uint8_t polluter_data[EXP5C_POLLUTERS][EXP5C_POLLUTER_BYTES]
    __attribute__((aligned(4096)));

/**
 * @brief Touch `distinct` addresses `stride` bytes apart, `sweeps` times.
 *
 * @param[in] buf      Task-private buffer of at least distinct * stride bytes.
 * @param[in] distinct Addresses touched per sweep (> 0).
 * @param[in] stride   Bytes between consecutive addresses (> 0).
 * @param[in] sweeps   Repetitions of the cycle (>= 2, so a reuse exists).
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

/** @return Phase of a victim: 0 for the first half, 1 for the second. */
static int victim_phase(int index)
{
    return index < EXP5C_VICTIMS / 2 ? 0 : 1;
}

void exp5c_victim_job(int index, int job)
{
    const long sweeps = (job % 2) == victim_phase(index)
                            ? EXP5C_HEAVY_SWEEPS
                            : EXP5C_LIGHT_SWEEPS;

    sweep(victim_data[index], EXP5C_VICTIM_DISTINCT, EXP5C_VICTIM_STRIDE,
          sweeps);
}

void exp5c_polluter_job(int index)
{
    sweep(polluter_data[index], EXP5C_POLLUTER_DISTINCT, EXP5C_POLLUTER_STRIDE,
          EXP5C_POLLUTER_SWEEPS);
}

/**
 * @brief Zero every task buffer, so each measured case starts from one state.
 */
void exp5c_reset_buffers(void)
{
    memset((void *)victim_data, 0, sizeof(victim_data));
    memset((void *)polluter_data, 0, sizeof(polluter_data));
}
