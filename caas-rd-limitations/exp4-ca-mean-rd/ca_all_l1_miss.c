#include "yard_analyze.h"

#define EVENTS 64
#define GAP_LINES 1088
#define LINE_FLOATS 8  /* 32 B cache line / 4 B float */

volatile float target[LINE_FLOATS];
volatile float gap[EVENTS][GAP_LINES][LINE_FLOATS];

/*
 * All L1-miss case.
 *
 * Each target reuse is separated by GAP_LINES distinct cache lines.  With a
 * 32 KiB / 32 B L1, the L1 capacity is 1024 cache lines, so target[0] is not
 * L1-resident when it is reused.
 */
YARD_ANALYZE
void ca_all_l1_miss(void)
{
  for (int r = 0; r < EVENTS; r++)
  {
    for (int i = 0; i < GAP_LINES; i++)
    {
      gap[r][i][0];
    }
    target[0];
  }
}

int main(void)
{
  ca_all_l1_miss();
  return 0;
}
