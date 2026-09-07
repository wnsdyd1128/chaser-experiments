/**
 * @file mean_rd_sweep.c
 * @brief Host mirror of the exp4 access pattern, measured under cachegrind.
 *
 * The RTEMS build reports time on the GR740; this build reports nothing and is
 * measured from outside, so that the same two access patterns also carry a
 * measured miss rate. It touches `distinct` addresses one cache line apart and
 * reads each of them `repeats` times in a row, repeating that cycle `cycles`
 * times, which is the loop of mean_rd_workload.c with the same address order.
 *
 * The reuse histogram of that pattern is known exactly: distinct*(cycles-1)
 * reuses at RD = distinct - 1 and distinct*cycles*(repeats-1) at RD = 0. The
 * miss rate cachegrind reports is what the cache does with it.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

/** Bytes between consecutive touched addresses. Must match EXP4_STRIDE in
 *  mean_rd_workload.c so that each address occupies a cache line of its own. */
#define MEAN_RD_STRIDE 32

/**
 * @brief Read `distinct` addresses, each `repeats` times in a row, `cycles`
 *        times over.
 *
 * @param[in] buf      Working buffer of at least distinct*MEAN_RD_STRIDE bytes
 *                     (non-null, ownership stays with the caller).
 * @param[in] distinct Addresses touched per cycle (> 0).
 * @param[in] repeats  Consecutive reads of each address (> 0).
 * @param[in] cycles   Times the cycle repeats (> 0).
 *
 * @note Declared volatile so the reads survive optimization; the access
 *       pattern is the entire point of the program.
 */
static void sweep(volatile uint8_t * buf, long distinct, long repeats,
                  long cycles)
{
  for (long c = 0; c < cycles; c++)
  {
    for (long i = 0; i < distinct; i++)
    {
      for (long r = 0; r < repeats; r++)
      {
        (void)buf[(size_t)i * MEAN_RD_STRIDE];
      }
    }
  }
}

int main(int argc, char ** argv)
{
  if (argc != 4)
  {
    fprintf(stderr, "usage: %s <distinct> <repeats> <cycles>\n", argv[0]);
    return 2;
  }

  const long distinct = atol(argv[1]);
  const long repeats = atol(argv[2]);
  const long cycles = atol(argv[3]);
  if (distinct <= 0 || repeats <= 0 || cycles <= 0)
  {
    fprintf(stderr, "distinct, repeats and cycles must all be positive\n");
    return 2;
  }

  const size_t bytes = (size_t)distinct * MEAN_RD_STRIDE;
  volatile uint8_t * buf = calloc(bytes, 1);
  if (buf == NULL)
  {
    fprintf(stderr, "cannot allocate %zu bytes\n", bytes);
    return 1;
  }

  sweep(buf, distinct, repeats, cycles);

  printf("distinct=%ld repeats=%ld cycles=%ld stride=%d "
         "working_set_bytes=%zu accesses=%ld\n",
         distinct, repeats, cycles, MEAN_RD_STRIDE, bytes,
         distinct * repeats * cycles);
  free((void *)buf);
  return 0;
}
