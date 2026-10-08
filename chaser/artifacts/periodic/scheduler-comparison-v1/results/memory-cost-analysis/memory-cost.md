# Experiment 41: same CLS and U, memory tasks hitting L2 (l2) or going to memory (mem) (pre-registered)

## Primary: sets meeting every deadline, exact McNemar, Holm over the placements

| placement | pairs | both met | only l2 met | only mem met | neither | p | Holm p | significant |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| wfd | 95 | 62 | 33 | 0 | 0 | 0.0000 | 0.0000 | True |
| cgb | 95 | 57 | 38 | 0 | 0 | 0.0000 | 0.0000 | True |

## Sets meeting every deadline per load (l2 / mem)

| placement, load | pairs | l2 | mem |
|---|---:|---:|---:|
| wfd 0.45 | 23 | 23 | 23 |
| wfd 0.5 | 24 | 24 | 23 |
| wfd 0.55 | 24 | 24 | 15 |
| wfd 0.6 | 24 | 24 | 1 |
| cgb 0.45 | 24 | 24 | 24 |
| cgb 0.5 | 23 | 23 | 20 |
| cgb 0.55 | 24 | 24 | 12 |
| cgb 0.6 | 24 | 24 | 1 |

## Secondary 1: AUC for a missed deadline on this experiment's runs

| runs | cache demand D | max(D, M) | f35 | f35 + p_mem statistics |
|---|---:|---:|---:|---:|
| pooled | 0.359 | 0.488 | 0.822 | 0.865 |
| wfd | 0.371 | 0.495 | 0.800 | 0.861 |
| cgb | 0.347 | 0.483 | 0.857 | 0.872 |

| cell | rows | missed | mean D | mean M | mean U-weighted (1 - CLS) | mean P(met), f35 | mean P(met), f35 + p_mem |
|---|---:|---:|---:|---:|---:|---:|---:|
| l2-low25 | 192 | 0 | 0.675 | 0.103 | 0.606 | 0.991 | 0.990 |
| mem-low25 | 190 | 71 | 0.420 | 0.531 | 0.606 | 0.972 | 0.618 |

## Secondary 2: whole-run late jobs, sign test

| placement | pairs | fewer in l2 | fewer in mem | late jobs l2 | late jobs mem | p |
|---|---:|---:|---:|---:|---:|---:|
| wfd | 95 | 33 | 0 | 0 | 80 | 0.0000 |
| cgb | 95 | 38 | 0 | 0 | 108 | 0.0000 |

## Late tasks by class (late / tasks)

| cell, placement | memory | other-with-memory | other-without-memory |
|---|---|---|---|
| l2-low25 wfd | 0 / 348 | 0 / 636 | 0 / 516 |
| l2-low25 cgb | 0 / 348 | 0 / 144 | 0 / 1008 |
| mem-low25 wfd | 8 / 344 | 17 / 630 | 55 / 513 |
| mem-low25 cgb | 2 / 344 | 0 / 138 | 106 / 1000 |
