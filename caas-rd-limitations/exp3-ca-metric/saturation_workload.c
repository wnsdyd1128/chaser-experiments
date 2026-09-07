/**
 * @file saturation_workload.c
 * @brief Time-domain measurement of the exp3 cyclic sweep on the GR740.
 *
 * Mirrors the access pattern of ca_sweep.c, which is measured externally under
 * cachegrind, so that the same working sets can be compared on a miss-rate axis
 * and on a nanosecond axis. The reuse histogram collapses to the single point
 * RD = distinct - 1, so CA is exactly 1 / distinct and is derived at analysis
 * time rather than computed here.
 *
 * Unlike exp1, no rate-monotonic period wraps the job body. exp3 is a single
 * task with no deadline claim, so a period would contribute nothing to the
 * measurement while dominating simulation time.
 */

#include <inttypes.h>
#include <rtems.h>
#include <stdio.h>

/** Bytes between consecutive touched addresses. Must match CA_SWEEP_STRIDE in
 *  ca_sweep.c so both measurement paths see the same access pattern. */
#define EXP3_STRIDE 32

/** Total accesses per case, held constant across working sets so the 1/sweeps
 *  cold-miss share stays comparable. Matches ACCESSES in
 *  tools/run_cachegrind_sweep.sh. */
#define EXP3_ACCESSES (1L << 23)

/** Measured repetitions of the job body per case. */
#define EXP3_JOBS 3

/** Largest case. Every smaller case uses the leading bytes of the same buffer,
 *  which is how ca_sweep.c sizes its allocation per case. */
#define EXP3_MAX_DISTINCT 1048576

static volatile uint8_t buf[EXP3_MAX_DISTINCT * EXP3_STRIDE]
    __attribute__((aligned(4096)));

/** Working sets swept, 4 KB to 32 MB. Must match DISTINCT_LIST in
 *  tools/run_cachegrind_sweep.sh so the two axes line up case by case.
 *
 *  Overridable at compile time, as DISTINCT_LIST is on the cachegrind path, so
 *  that a case can be re-run alone on a freshly booted machine to check it
 *  against its value from the batched sweep. */
#ifndef EXP3_DISTINCT_LIST
#define EXP3_DISTINCT_LIST \
    128, 256, 384, 512, 768, 1024, 2048, 8192, \
    16384, 49152, 65536, 98304, 131072, 262144, 524288, 1048576
#endif

static const long exp3_distinct_list[] = {EXP3_DISTINCT_LIST};

/**
 * @brief Touch `distinct` addresses one stride apart, `sweeps` times.
 *
 * @param[in] distinct Number of distinct addresses per sweep
 *                     (0 < distinct <= EXP3_MAX_DISTINCT).
 * @param[in] sweeps   Number of times the cycle repeats (> 0).
 *
 * @note buf is volatile so the read survives optimization; the access
 *       pattern is the entire point of the workload. The touch is a plain
 *       read: a store would add a write-through transaction per iteration
 *       that costs instructions but no memory stall, and it would put an
 *       RD = 0 point in the histogram that CA does not need.
 */
static void sweep(long distinct, long sweeps)
{
    const long bytes = distinct * EXP3_STRIDE;

    for (long s = 0; s < sweeps; s++) {
        for (long i = 0; i < bytes; i += EXP3_STRIDE) {
            (void)buf[i];
        }
    }
}

/**
 * @brief Measure one working set and print its RESULT lines.
 *
 * Only measured quantities are printed; the plotted cost is derived from them
 * at analysis time so that it keeps a single definition. With D = distinct,
 * S = sweeps, J = EXP3_JOBS and T_j the elapsed time of job j:
 *
 *     average time per array access = (sum_j T_j) / (J * D * S)
 *
 * avg_ns below carries (sum_j T_j) / J, so the analysis side divides it by
 * `accesses` = D * S alone.
 *
 * T_j spans the sweep() call and nothing else. Inside it are the D * S inner
 * iterations, the S outer iterations, and any interrupt taken in the window;
 * outside it are the printf calls below and everything before run_case, so
 * boot and .bss clearing are not counted. The denominator counts only the
 * buf[] reads, one per inner iteration. The loop's own stack traffic is in the
 * numerator and not in the denominator, which is why the quotient sits an
 * order of magnitude above an L1 hit and must not be read as a memory latency.
 *
 * @param[in] distinct Number of distinct addresses for this case.
 * @pre distinct > 0 and distinct <= EXP3_MAX_DISTINCT.
 */
static void run_case(long distinct)
{
    const long sweeps = EXP3_ACCESSES / distinct;
    const long accesses = distinct * sweeps;
    uint64_t sum_ns = 0;
    uint64_t max_ns = 0;

    for (int job = 0; job < EXP3_JOBS; job++) {
        uint64_t start_ns = rtems_clock_get_uptime_nanoseconds();
        sweep(distinct, sweeps);
        uint64_t elapsed_ns = rtems_clock_get_uptime_nanoseconds() - start_ns;

        sum_ns += elapsed_ns;
        if (elapsed_ns > max_ns) {
            max_ns = elapsed_ns;
        }
    }

    printf("RESULT,experiment=exp3,case=D%ld,metric=distinct,value=%ld\n",
           distinct, distinct);
    printf("RESULT,experiment=exp3,case=D%ld,metric=working_set_bytes,value=%ld\n",
           distinct, distinct * EXP3_STRIDE);
    printf("RESULT,experiment=exp3,case=D%ld,metric=sweeps,value=%ld\n",
           distinct, sweeps);
    printf("RESULT,experiment=exp3,case=D%ld,metric=accesses,value=%ld\n",
           distinct, accesses);
    printf("RESULT,experiment=exp3,case=D%ld,metric=avg_ns,value=%" PRIu64 "\n",
           distinct, sum_ns / EXP3_JOBS);
    printf("RESULT,experiment=exp3,case=D%ld,metric=max_ns,value=%" PRIu64 "\n",
           distinct, max_ns);
}

/**
 * @brief Sweep every working set in exp3_distinct_list and report each.
 *
 * Runs on the Init task with the other three cores idle, so the measurement
 * carries no co-scheduling or shared-cache interference.
 */
void run_exp3_ca_saturation(void)
{
    const size_t cases = sizeof(exp3_distinct_list) / sizeof(exp3_distinct_list[0]);

    for (size_t i = 0; i < cases; i++) {
        run_case(exp3_distinct_list[i]);
    }
}
