# CLS-keyed against traffic-keyed placements

160 cases; identical assignments: cg = tg 110 (result mismatches 0), ra-cg = ra-tg 110 (result mismatches 0)

Relative difference = CLS-keyed / traffic-keyed - 1 (negative: the CLS key is better).

## Cases where the assignments differ

| pair | metric | n | CLS better / tie / worse | median | mean | Holm p | deadline misses (CLS / traffic) |
|---|---|---:|---|---:|---:|---:|---|
| cg vs tg | TAT | 39 | 12 / 0 / 27 | 2.56% | 15.51% | 6.84e-05 | 11 / 6 |
| cg vs tg | TET | 39 | 36 / 0 / 3 | -2.76% | -4.12% | 1.9e-08 | 11 / 6 |
| ra-cg vs ra-tg | TAT | 38 | 9 / 0 / 29 | 7.81% | 19.39% | 4.16e-06 | 12 / 7 |
| ra-cg vs ra-tg | TET | 38 | 36 / 0 / 2 | -3.08% | -3.95% | 2.91e-10 | 12 / 7 |

## Regret against the best of six placements (all cases, TAT)

| placement | mean regret | regret >= 5% | infeasible |
|---|---:|---:|---:|
| wfd | 6.23% | 45 | 35 |
| tg | 6.68% | 51 | 33 |
| ra | 1.67% | 11 | 35 |
| ra-tg | 3.76% | 25 | 35 |
| cg | 12.05% | 64 | 38 |
| ra-cg | 9.87% | 43 | 40 |

## Regret against the best of six placements (all cases, TET)

| placement | mean regret | regret >= 5% | infeasible |
|---|---:|---:|---:|
| wfd | 9.80% | 61 | 35 |
| tg | 1.74% | 20 | 33 |
| ra | 11.10% | 65 | 35 |
| ra-tg | 2.02% | 21 | 35 |
| cg | 0.34% | 3 | 38 |
| ra-cg | 0.69% | 3 | 40 |

## Regret against the best of six placements (differ cases, TAT)

| placement | mean regret | regret >= 5% | infeasible |
|---|---:|---:|---:|
| wfd | 5.79% | 14 | 7 |
| tg | 3.96% | 9 | 6 |
| ra | 1.67% | 3 | 8 |
| ra-tg | 1.02% | 3 | 7 |
| cg | 20.40% | 22 | 11 |
| ra-cg | 19.94% | 21 | 12 |

## Regret against the best of six placements (differ cases, TET)

| placement | mean regret | regret >= 5% | infeasible |
|---|---:|---:|---:|
| wfd | 7.12% | 21 | 7 |
| tg | 4.17% | 17 | 6 |
| ra | 8.56% | 24 | 8 |
| ra-tg | 4.04% | 18 | 7 |
| cg | 0.10% | 0 | 11 |
| ra-cg | 0.11% | 0 | 12 |
