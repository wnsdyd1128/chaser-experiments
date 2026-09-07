/**
 * @file mean_rd_workload.c
 * @brief Time-domain test of CA's dependence on the reuse histogram's mean.
 *
 * CA = 1 / (1 + mean RD), so it sees the reuse histogram only through its
 * weighted mean and is blind to its shape. Two workloads are built to have the
 * same mean RD by construction and opposite L1 behaviour:
 *
 *   A (repeats = 1)  every reuse sits at RD = distinct - 1, past L1
 *   B (repeats = k)  (k-1)/k of the reuses sit at RD = 0 and hit L1, the rest
 *                    at RD = distinct - 1
 *
 * One parameterised sweep serves both, so the two differ only in `repeats` and
 * run the same instruction sequence around the same load. Cost is not measured
 * here; the driver reports elapsed time and the analysis side divides it out.
 */

#include <inttypes.h>
#include <rtems.h>
#include <stdio.h>

/** Bytes between consecutive touched addresses, equal to the GR740 line size
 *  so that each distinct address occupies a cache line of its own. */
#define EXP4_STRIDE 32

/** Loads per case, held constant so the 1/cycles cold-miss share stays
 *  comparable between cases. */
#define EXP4_ACCESSES (1L << 23)

/** Measured repetitions of the job body per case. */
#define EXP4_JOBS 3

/** Largest case, 1 MB. Every case uses the leading bytes of this buffer. */
#define EXP4_MAX_DISTINCT 32768

static volatile uint8_t buf[EXP4_MAX_DISTINCT * EXP4_STRIDE]
    __attribute__((aligned(4096)));

/** One measured case: `distinct` addresses, each read 2^shift times in a row. */
typedef struct {
    long distinct;
    long shift;
} exp4_case_t;

/**
 * Cases, in pairs of workload A (repeats = 1) and B (repeats = 3).
 *
 * The first three of each pair fit in L1 and take no memory stall, so they fit
 * that workload's non-memory floor; the fourth is the case under test. A and B
 * run different instruction mixes, so each needs its own floor.
 *
 * D = 965 with k = 1 and D = 2895 with k = 3 both give a mean RD of exactly 964
 * at these access counts, so the two carry identical CA while only B's reuses
 * are L1-local. k is kept small so that the longest reuse distance stays near
 * the L1 line count and the two are legible on one axis; a larger k would widen
 * the cost gap but push the L1 boundary into the corner of any plot of them.
 * Overridable at compile time to re-run one case alone on a freshly booted
 * machine.
 */
#ifndef EXP4_CASES
#define EXP4_CASES \
    {128, 1}, {256, 1}, {384, 1}, {965, 1}, \
    {128, 3}, {256, 3}, {384, 3}, {2895, 3}
#endif

static const exp4_case_t exp4_cases[] = {EXP4_CASES};

/**
 * @brief Read `distinct` addresses one stride apart, 2^shift times each,
 *        cycling `cycles` times.
 *
 * The loop is flat and the address is derived by shifting the load counter, so
 * every load carries the same instructions whatever `shift` is. That is what
 * lets the two workloads be compared on their raw measured times: a nested
 * repeat loop would amortise the address arithmetic over 2^shift loads and
 * give the two different non-memory costs.
 *
 * @param[in] distinct Distinct addresses per cycle (0 < distinct <=
 *                     EXP4_MAX_DISTINCT).
 * @param[in] shift    log2 of the back-to-back reads of each address, which
 *                     sets the share of RD = 0 reuses (>= 0).
 * @param[in] cycles   Times the whole cycle repeats (> 0).
 *
 * @note buf is volatile so the reads survive optimization; the access pattern
 *       is the entire point of the workload. Reads only, so the histogram has
 *       no store-induced RD = 0 point beyond the ones `shift` creates.
 */
static void sweep(long distinct, long shift, long cycles)
{
    const long loads = distinct << shift;

    for (long c = 0; c < cycles; c++) {
        for (long j = 0; j < loads; j++) {
            (void)buf[(j >> shift) * EXP4_STRIDE];
        }
    }
}

/**
 * @brief Measure one case and print its RESULT lines.
 *
 * Only measured quantities are printed. With D = distinct, k = repeats,
 * C = cycles, J = EXP4_JOBS and T_j the elapsed time of job j:
 *
 *     amortized time per load = (sum_j T_j) / (J * D * k * C)
 *     mean RD                 = (D - 1) * (C - 1) / (k * C - 1)
 *
 * The mean RD is exact for finite C: the first cycle contributes no reuse, so
 * the asymptotic (D - 1) / k understates it. Both are derived at analysis time
 * so each keeps a single definition.
 *
 * @param[in] item Case to run.
 * @pre item.distinct > 0 and <= EXP4_MAX_DISTINCT; item.repeats > 0.
 */
static void run_case(exp4_case_t item)
{
    const long repeats = 1L << item.shift;
    const long cycles = EXP4_ACCESSES / (item.distinct * repeats);
    const long accesses = item.distinct * repeats * cycles;
    uint64_t sum_ns = 0;
    uint64_t max_ns = 0;

    for (int job = 0; job < EXP4_JOBS; job++) {
        uint64_t start_ns = rtems_clock_get_uptime_nanoseconds();
        sweep(item.distinct, item.shift, cycles);
        uint64_t elapsed_ns = rtems_clock_get_uptime_nanoseconds() - start_ns;

        sum_ns += elapsed_ns;
        if (elapsed_ns > max_ns) {
            max_ns = elapsed_ns;
        }
    }

#define EXP4_CASE_FMT "RESULT,experiment=exp4,case=K%ldD%ld,metric="
    /* repeats, not shift, so the analysis side reads the same field as before */
    printf(EXP4_CASE_FMT "distinct,value=%ld\n",
           repeats, item.distinct, item.distinct);
    printf(EXP4_CASE_FMT "repeats,value=%ld\n",
           repeats, item.distinct, repeats);
    printf(EXP4_CASE_FMT "working_set_bytes,value=%ld\n",
           repeats, item.distinct, item.distinct * EXP4_STRIDE);
    printf(EXP4_CASE_FMT "cycles,value=%ld\n",
           repeats, item.distinct, cycles);
    printf(EXP4_CASE_FMT "accesses,value=%ld\n",
           repeats, item.distinct, accesses);
    printf(EXP4_CASE_FMT "avg_ns,value=%" PRIu64 "\n",
           repeats, item.distinct, sum_ns / EXP4_JOBS);
    printf(EXP4_CASE_FMT "max_ns,value=%" PRIu64 "\n",
           repeats, item.distinct, max_ns);
#undef EXP4_CASE_FMT
}

/**
 * @brief Run every case in exp4_cases and report each.
 *
 * Runs on the Init task with the other cores idle, so the measurement carries
 * no co-scheduling or shared-cache interference.
 */
void run_exp4_ca_mean_rd(void)
{
    const size_t cases = sizeof(exp4_cases) / sizeof(exp4_cases[0]);

    for (size_t i = 0; i < cases; i++) {
        run_case(exp4_cases[i]);
    }
}
