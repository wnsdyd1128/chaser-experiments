/**
 * @file ca_sweep.c
 * @brief Cyclic address sweep used to expose the CA metric's blindness to the
 *        cache hierarchy.
 *
 * The sweep touches `distinct` addresses one cache line apart and repeats that
 * cycle `sweeps` times. Because every reuse of an address sees exactly the same
 * set of other addresses in between, the reuse histogram collapses to a single
 * point at RD = distinct - 1. CA is therefore exactly 1 / distinct, which lets
 * the analysis side compute CA without running a reuse-distance analyzer over
 * a multi-million access trace.
 *
 * The binary carries no measurement of its own. Cost is measured externally by
 * running it under cachegrind with the GR740 cache geometry forced on the
 * command line; see tools/run_cachegrind_sweep.sh.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

/** Bytes between consecutive touched addresses. Must match the L1 line size
 *  so that each access occupies a distinct cache line. */
#define CA_SWEEP_STRIDE 32

/**
 * @brief Touch `distinct` addresses in a cycle, `sweeps` times.
 *
 * @param[in,out] buf      Working buffer of at least distinct*CA_SWEEP_STRIDE
 *                         bytes (non-null, ownership stays with the caller).
 * @param[in]     distinct Number of distinct addresses per sweep (> 0).
 * @param[in]     sweeps   Number of times the cycle repeats (> 0).
 *
 * @note Declared volatile so the read survives optimization; the access
 *       pattern is the entire point of the program. The touch is a plain
 *       read, which keeps the histogram to one point and matches the read
 *       miss rates this program is measured by.
 */
static void sweep(volatile uint8_t * buf, long distinct, long sweeps)
{
  const size_t bytes = (size_t)distinct * CA_SWEEP_STRIDE;

  for (long s = 0; s < sweeps; s++)
  {
    for (size_t i = 0; i < bytes; i += CA_SWEEP_STRIDE)
    {
      (void)buf[i];
    }
  }
}

int main(int argc, char ** argv)
{
  if (argc != 3)
  {
    fprintf(stderr, "usage: %s <distinct> <sweeps>\n", argv[0]);
    return 2;
  }

  const long distinct = atol(argv[1]);
  const long sweeps = atol(argv[2]);
  if (distinct <= 0 || sweeps <= 0)
  {
    fprintf(stderr, "distinct and sweeps must both be positive\n");
    return 2;
  }

  const size_t bytes = (size_t)distinct * CA_SWEEP_STRIDE;
  volatile uint8_t * buf = calloc(bytes, 1);
  if (buf == NULL)
  {
    fprintf(stderr, "cannot allocate %zu bytes\n", bytes);
    return 1;
  }

  sweep(buf, distinct, sweeps);

  printf(
    "distinct=%ld stride=%d working_set_bytes=%zu sweeps=%ld accesses=%ld\n",
    distinct, CA_SWEEP_STRIDE, bytes, sweeps, distinct * sweeps);
  free((void *)buf);
  return 0;
}
