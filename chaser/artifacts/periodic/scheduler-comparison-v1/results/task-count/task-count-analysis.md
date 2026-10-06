# Task-count analysis

Regret: value / best Partitioned placement of the same case - 1 (feasible runs).

## Runs meeting every deadline

| cell | cases | g | c2 | p | p_cgb | p_ra | p_racgb |
|---|---:|---:|---:|---:|---:|---:|---:|
| mem00 U0.35 | 36 | 36 | 36 | 35 | 35 | 36 | 36 |
| mem00 U0.45 | 36 | 35 | 36 | 36 | 36 | 36 | 36 |
| mem25 U0.35 | 36 | 24 | 21 | 21 | 26 | 19 | 24 |
| mem25 U0.45 | 36 | 9 | 10 | 8 | 11 | 6 | 13 |
| mem50 U0.35 | 36 | 0 | 0 | 0 | 0 | 0 | 0 |
| mem50 U0.45 | 36 | 0 | 0 | 0 | 0 | 0 | 0 |

## TAT per cell

| cell | wfd median / regret / wins | cgb median / regret / wins | ra median / regret / wins | ra-cgb median / regret / wins |
|---|---|---|---|---|
| mem00 U0.35 | 175.7 / 19.65% / 1 | 175.7 / 19.65% / 1 | 148.1 / 0.13% / 35 | 148.1 / 0.13% / 35 |
| mem00 U0.45 | 232.9 / 17.18% / 2 | 232.9 / 17.18% / 2 | 198.9 / 0.08% / 34 | 198.9 / 0.08% / 34 |
| mem25 U0.35 | 341.8 / 11.01% / 4 | 361.8 / 9.86% / 3 | 362.9 / 17.93% / 5 | 309.1 / 3.88% / 16 |
| mem25 U0.45 | 384.5 / 9.44% / 2 | 387.4 / 7.16% / 2 | 351.4 / 6.70% / 2 | 380.2 / 1.73% / 10 |
| mem50 U0.35 | - | - | - | - |
| mem50 U0.45 | - | - | - | - |

## TET per cell

| cell | wfd median / regret / wins | cgb median / regret / wins | ra median / regret / wins | ra-cgb median / regret / wins |
|---|---|---|---|---|
| mem00 U0.35 | 505.2 / 0.24% / 25 | 505.2 / 0.24% / 25 | 511.1 / 1.43% / 11 | 511.1 / 1.43% / 11 |
| mem00 U0.45 | 651.9 / 0.27% / 29 | 651.9 / 0.27% / 29 | 657.7 / 1.58% / 7 | 657.7 / 1.58% / 7 |
| mem25 U0.35 | 872.3 / 7.16% / 5 | 826.4 / 2.32% / 15 | 948.8 / 15.39% / 0 | 840.2 / 2.94% / 9 |
| mem25 U0.45 | 992.2 / 7.30% / 1 | 944.0 / 1.12% / 8 | 962.9 / 10.62% / 0 | 928.7 / 0.62% / 7 |
| mem50 U0.35 | - | - | - | - |
| mem50 U0.45 | - | - | - | - |

## CLS-aware placements against release-aware (ra)

| scope | metric | pair | n | better / tie / worse | median | Holm p | only CLS-aware / only ra feasible |
|---|---|---|---:|---|---:|---:|---|
| mem25 U0.35 | TAT | cgb vs ra | 18 | 8 / 0 / 10 | 2.04% | 1 | 8 / 1 |
| mem25 U0.35 | TET | cgb vs ra | 18 | 17 / 0 / 1 | -9.38% | 0.00153 | 8 / 1 |
| mem25 U0.35 | TAT | ra-cgb vs ra | 19 | 13 / 0 / 6 | -6.57% | 0.376 | 5 / 0 |
| mem25 U0.35 | TET | ra-cgb vs ra | 19 | 18 / 0 / 1 | -7.65% | 0.000168 | 5 / 0 |
| mem25 U0.45 | TAT | cgb vs ra | 6 | 3 / 0 / 3 | 5.19% | 1 | 5 / 0 |
| mem25 U0.45 | TET | cgb vs ra | 6 | 6 / 0 / 0 | -7.60% | 0.376 | 5 / 0 |
| mem25 U0.45 | TAT | ra-cgb vs ra | 6 | 3 / 0 / 3 | -0.26% | 1 | 7 / 0 |
| mem25 U0.45 | TET | ra-cgb vs ra | 6 | 6 / 0 / 0 | -7.95% | 0.376 | 7 / 0 |
| mem50 U0.35 | TAT | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| mem50 U0.35 | TET | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| mem50 U0.35 | TAT | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| mem50 U0.35 | TET | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| mem50 U0.45 | TAT | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| mem50 U0.45 | TET | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| mem50 U0.45 | TAT | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| mem50 U0.45 | TET | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| memory cells, 12-14 tasks | TAT | cgb vs ra | 15 | 6 / 0 / 9 | 2.90% | 1 | 4 / 0 |
| memory cells, 12-14 tasks | TET | cgb vs ra | 15 | 15 / 0 / 0 | -7.03% | 0.00128 | 4 / 0 |
| memory cells, 12-14 tasks | TAT | ra-cgb vs ra | 15 | 8 / 0 / 7 | -1.28% | 1 | 2 / 0 |
| memory cells, 12-14 tasks | TET | ra-cgb vs ra | 15 | 14 / 0 / 1 | -6.39% | 0.00232 | 2 / 0 |
| memory cells, 15-17 tasks | TAT | cgb vs ra | 5 | 3 / 0 / 2 | -5.20% | - | 4 / 1 |
| memory cells, 15-17 tasks | TET | cgb vs ra | 5 | 4 / 0 / 1 | -11.85% | - | 4 / 1 |
| memory cells, 15-17 tasks | TAT | ra-cgb vs ra | 6 | 5 / 0 / 1 | -15.11% | 0.562 | 4 / 0 |
| memory cells, 15-17 tasks | TET | ra-cgb vs ra | 6 | 6 / 0 / 0 | -10.67% | 0.376 | 4 / 0 |
| memory cells, 18-20 tasks | TAT | cgb vs ra | 4 | 2 / 0 / 2 | 1.98% | - | 5 / 0 |
| memory cells, 18-20 tasks | TET | cgb vs ra | 4 | 4 / 0 / 0 | -14.32% | - | 5 / 0 |
| memory cells, 18-20 tasks | TAT | ra-cgb vs ra | 4 | 3 / 0 / 1 | -10.94% | - | 6 / 0 |
| memory cells, 18-20 tasks | TET | ra-cgb vs ra | 4 | 4 / 0 / 0 | -15.82% | - | 6 / 0 |
| memory cells, multiple of 4 tasks | TAT | cgb vs ra | 11 | 8 / 0 / 3 | -4.67% | 1 | 4 / 0 |
| memory cells, multiple of 4 tasks | TET | cgb vs ra | 11 | 11 / 0 / 0 | -11.22% | 0.0166 | 4 / 0 |
| memory cells, multiple of 4 tasks | TAT | ra-cgb vs ra | 11 | 8 / 0 / 3 | -10.83% | 0.191 | 3 / 0 |
| memory cells, multiple of 4 tasks | TET | ra-cgb vs ra | 11 | 10 / 0 / 1 | -11.48% | 0.0312 | 3 / 0 |
| memory cells, not a multiple of 4 tasks | TAT | cgb vs ra | 13 | 3 / 0 / 10 | 6.17% | 1 | 9 / 1 |
| memory cells, not a multiple of 4 tasks | TET | cgb vs ra | 13 | 12 / 0 / 1 | -7.03% | 0.0366 | 9 / 1 |
| memory cells, not a multiple of 4 tasks | TAT | ra-cgb vs ra | 14 | 8 / 0 / 6 | -1.78% | 1 | 9 / 0 |
| memory cells, not a multiple of 4 tasks | TET | ra-cgb vs ra | 14 | 14 / 0 / 0 | -6.32% | 0.00232 | 9 / 0 |

## Task count: WFD regret (TAT) and G / C2 against the best Partitioned placement

| scope | cases | WFD mean regret | G feasible / beats best P / median gap | C2 feasible / beats best P / median gap |
|---|---:|---:|---|---|
| 12-14 | 72 | 10.56% | 43 / 8 / 4.32% | 42 / 2 / 7.55% |
| 15-17 | 72 | 19.61% | 32 / 2 / 9.52% | 33 / 2 / 10.87% |
| 18-20 | 72 | 20.81% | 29 / 2 / 7.90% | 28 / 0 / 16.36% |
| multiple of 4 | 72 | 18.37% | 36 / 4 / 6.23% | 37 / 1 / 12.61% |
| not a multiple of 4 | 144 | 14.87% | 68 / 8 / 6.42% | 66 / 3 / 10.86% |

## Placement selector (TAT labels)

115 cases; labels {'wfd': 9, 'cgb': 4, 'ra': 76, 'ra-cgb': 26}; near-ties 74

### set-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 16.13% | 37.24% | 51.95% | 7.83% |
| always cgb | 15.20% | 37.18% | 51.95% | 3.48% |
| always ra | 4.00% | 26.35% | 70.28% | 66.09% |
| always ra-cgb | 1.13% | 6.71% | 38.06% | 22.61% |
| fixed (train) | 1.13% | 6.71% | 38.06% | 22.61% |
| R0 / classifier | 1.96% | 10.60% | 69.07% | 78.61% |
| R0 / regressor | 1.98% | 14.10% | 38.06% | 48.70% |
| R0-CLP / classifier | 1.72% | 7.89% | 69.07% | 81.57% |
| R0-CLP / regressor | 1.75% | 11.17% | 38.06% | 50.09% |
| R1 / classifier | 2.06% | 11.16% | 69.07% | 78.61% |
| R1 / regressor | 1.74% | 11.66% | 38.06% | 41.57% |
| R2 / classifier | 1.91% | 9.56% | 69.07% | 78.96% |
| R2 / regressor | 1.90% | 13.02% | 38.06% | 46.78% |
| R3 / classifier | 1.90% | 10.30% | 69.07% | 80.35% |
| R3 / regressor | 2.10% | 14.17% | 38.06% | 38.43% |
| R4 / classifier | 1.77% | 7.74% | 69.07% | 80.70% |
| R4 / regressor | 1.97% | 13.69% | 38.06% | 50.26% |

### condition-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 16.13% | 37.24% | 51.95% | 7.83% |
| always cgb | 15.20% | 37.18% | 51.95% | 3.48% |
| always ra | 4.00% | 26.35% | 70.28% | 66.09% |
| always ra-cgb | 1.13% | 6.71% | 38.06% | 22.61% |
| fixed (train) | 1.13% | 6.71% | 38.06% | 22.61% |
| R0 / classifier | 1.00% | 4.69% | 38.06% | 81.57% |
| R0 / regressor | 1.25% | 7.38% | 38.06% | 21.74% |
| R0-CLP / classifier | 0.99% | 4.69% | 38.06% | 83.13% |
| R0-CLP / regressor | 1.12% | 6.71% | 38.06% | 26.61% |
| R1 / classifier | 0.99% | 4.69% | 38.06% | 81.91% |
| R1 / regressor | 1.25% | 7.13% | 38.06% | 23.65% |
| R2 / classifier | 1.09% | 6.11% | 38.06% | 83.48% |
| R2 / regressor | 1.37% | 8.12% | 38.06% | 20.35% |
| R3 / classifier | 0.99% | 4.69% | 38.06% | 82.09% |
| R3 / regressor | 1.59% | 10.65% | 38.74% | 20.35% |
| R4 / classifier | 1.03% | 5.47% | 38.06% | 84.00% |
| R4 / regressor | 1.36% | 7.16% | 38.06% | 21.04% |


## Placement selector (TET labels)

115 cases; labels {'wfd': 60, 'cgb': 21, 'ra': 18, 'ra-cgb': 16}; near-ties 85

### set-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 2.27% | 13.28% | 26.67% | 52.17% |
| always cgb | 0.84% | 5.53% | 17.79% | 18.26% |
| always ra | 4.79% | 20.32% | 38.21% | 15.65% |
| always ra-cgb | 1.71% | 5.27% | 13.33% | 13.91% |
| fixed (train) | 1.34% | 5.51% | 14.60% | 11.30% |
| R0 / classifier | 0.92% | 5.50% | 15.11% | 65.39% |
| R0 / regressor | 1.10% | 5.47% | 13.33% | 39.48% |
| R0-CLP / classifier | 0.87% | 5.79% | 13.84% | 67.30% |
| R0-CLP / regressor | 1.16% | 5.47% | 14.60% | 43.30% |
| R1 / classifier | 0.86% | 5.28% | 13.33% | 62.09% |
| R1 / regressor | 1.15% | 5.37% | 14.35% | 31.13% |
| R2 / classifier | 0.89% | 5.19% | 14.60% | 61.22% |
| R2 / regressor | 1.01% | 5.26% | 14.60% | 46.61% |
| R3 / classifier | 0.79% | 4.64% | 14.73% | 65.39% |
| R3 / regressor | 1.10% | 5.36% | 15.24% | 37.22% |
| R4 / classifier | 0.91% | 5.53% | 14.60% | 62.96% |
| R4 / regressor | 1.07% | 5.47% | 14.60% | 44.35% |

### condition-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 2.27% | 13.28% | 26.67% | 52.17% |
| always cgb | 0.84% | 5.53% | 17.79% | 18.26% |
| always ra | 4.79% | 20.32% | 38.21% | 15.65% |
| always ra-cgb | 1.71% | 5.27% | 13.33% | 13.91% |
| fixed (train) | 1.40% | 5.17% | 13.33% | 13.91% |
| R0 / classifier | 0.98% | 5.73% | 13.33% | 59.48% |
| R0 / regressor | 1.19% | 4.20% | 13.33% | 17.57% |
| R0-CLP / classifier | 0.95% | 5.63% | 13.33% | 61.22% |
| R0-CLP / regressor | 1.19% | 5.30% | 13.33% | 14.43% |
| R1 / classifier | 0.88% | 4.72% | 13.33% | 59.30% |
| R1 / regressor | 1.20% | 4.67% | 13.33% | 17.04% |
| R2 / classifier | 0.88% | 5.15% | 13.33% | 61.04% |
| R2 / regressor | 1.31% | 6.00% | 13.33% | 13.91% |
| R3 / classifier | 0.89% | 4.88% | 13.33% | 59.83% |
| R3 / regressor | 1.27% | 5.16% | 13.33% | 14.43% |
| R4 / classifier | 0.96% | 5.94% | 13.33% | 59.65% |
| R4 / regressor | 1.28% | 5.60% | 13.33% | 12.70% |

