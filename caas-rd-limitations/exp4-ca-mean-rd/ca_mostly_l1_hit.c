#include "yard_analyze.h"

#define L1_HIT_ACCESSES 48
#define TAIL_EVENTS 16
#define TAIL_GAP_LINES 4096
#define LINE_FLOATS 8  /* 32 B cache line / 4 B float */

volatile float target[LINE_FLOATS];
volatile float gap[TAIL_EVENTS][TAIL_GAP_LINES][LINE_FLOATS];

/*
 * Mostly L1-hit case.
 *
 * Most target reuses are immediate RD=0 reuses.  A small tail is separated by
 * TAIL_GAP_LINES distinct cache lines.  The weighted mean RD is intentionally
 * close to ca_all_l1_miss.c, but the target object's L1 behavior is much more
 * cache-friendly.
 */
YARD_ANALYZE
void ca_mostly_l1_hit(void)
{
  for (int r = 0; r < L1_HIT_ACCESSES; r++)
  {
    target[0];
  }

  for (int t = 0; t < TAIL_EVENTS; t++)
  {
    for (int i = 0; i < TAIL_GAP_LINES; i++)
    {
      gap[t][i][0];
    }
    target[0];
  }
}

int main(void)
{
  ca_mostly_l1_hit();
  return 0;
}
