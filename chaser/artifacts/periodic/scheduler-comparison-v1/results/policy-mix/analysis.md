# Policy-mix analysis

Regret: measured TAT of a placement / the best placement of the same case - 1, over runs that met
every deadline; infeasible = runs with a deadline miss.

## Schedulable runs

| load | g | c2 | p | p_tg | p_ra | p_ratg |
|---|---:|---:|---:|---:|---:|---:|
| 0.3 | 68/80 | 67/80 | 70/80 | 71/80 | 70/80 | 72/80 |
| 0.45 | 52/80 | 56/80 | 55/80 | 56/80 | 55/80 | 53/80 |

## Placements (all)

| placement | mean regret | p95 | regret >= 5% | infeasible | wins | unique wins |
|---|---:|---:|---:|---:|---:|---:|
| wfd | 6.15% | 21.83% | 45 | 35 | 38 | 12 |
| tg | 6.60% | 27.42% | 51 | 33 | 41 | 7 |
| ra | 1.59% | 8.79% | 11 | 35 | 66 | 30 |
| ra-tg | 3.68% | 19.32% | 25 | 35 | 67 | 23 |

## Placements (load 0.3)

| placement | mean regret | p95 | regret >= 5% | infeasible | wins | unique wins |
|---|---:|---:|---:|---:|---:|---:|
| wfd | 6.05% | 24.02% | 25 | 10 | 22 | 10 |
| tg | 6.44% | 29.23% | 29 | 9 | 24 | 2 |
| ra | 1.65% | 8.59% | 7 | 10 | 35 | 18 |
| ra-tg | 3.47% | 16.59% | 17 | 8 | 38 | 11 |

## Placements (load 0.45)

| placement | mean regret | p95 | regret >= 5% | infeasible | wins | unique wins |
|---|---:|---:|---:|---:|---:|---:|
| wfd | 6.28% | 21.72% | 20 | 25 | 16 | 2 |
| tg | 6.82% | 21.77% | 22 | 24 | 17 | 5 |
| ra | 1.52% | 7.92% | 4 | 25 | 31 | 12 |
| ra-tg | 3.97% | 20.38% | 8 | 27 | 29 | 12 |

## ra-tg against single placements (both feasible)

| pair | n | ra-tg better / tie / worse | median difference | Holm p |
|---|---:|---|---:|---:|
| ra-tg vs wfd | 120 | 68 / 10 / 42 | -0.56% | 0.0238 |
| ra-tg vs tg | 124 | 53 / 55 / 16 | 0.00% | 5.83e-07 |
| ra-tg vs ra | 121 | 46 / 30 / 45 | 0.00% | 0.282 |

## Mean regret by factor level

### periods

| level | cases | wfd | tg | ra | ra-tg |
|---|---:|---:|---:|---:|---:|
| mixed | 80 | 10.29% (6 wins) | 9.31% (13 wins) | 1.85% (38 wins) | 4.02% (39 wins) |
| single | 80 | 1.06% (32 wins) | 3.39% (28 wins) | 1.28% (28 wins) | 3.29% (28 wins) |

### low

| level | cases | wfd | tg | ra | ra-tg |
|---|---:|---:|---:|---:|---:|
| 0 | 54 | 6.66% (17 wins) | 5.96% (14 wins) | 2.00% (24 wins) | 1.26% (24 wins) |
| 4 | 54 | 6.92% (9 wins) | 7.26% (13 wins) | 1.42% (24 wins) | 5.13% (20 wins) |
| 8 | 52 | 4.74% (12 wins) | 6.54% (14 wins) | 1.34% (18 wins) | 4.64% (23 wins) |

### traffic

| level | cases | wfd | tg | ra | ra-tg |
|---|---:|---:|---:|---:|---:|
| as-is | 80 | 6.86% (17 wins) | 9.62% (14 wins) | 1.89% (32 wins) | 6.94% (21 wins) |
| matched | 80 | 5.54% (21 wins) | 4.07% (27 wins) | 1.33% (34 wins) | 0.77% (46 wins) |

### big

| level | cases | wfd | tg | ra | ra-tg |
|---|---:|---:|---:|---:|---:|
| 0 | 54 | 4.82% (22 wins) | 6.12% (22 wins) | 0.69% (37 wins) | 2.52% (33 wins) |
| 2 | 54 | 6.95% (11 wins) | 8.29% (11 wins) | 1.41% (24 wins) | 5.04% (23 wins) |
| 4 | 52 | 7.64% (5 wins) | 4.08% (8 wins) | 4.63% (5 wins) | 3.36% (11 wins) |

### alpha

| level | cases | wfd | tg | ra | ra-tg |
|---|---:|---:|---:|---:|---:|
| 32.0 | 80 | 5.67% (21 wins) | 5.20% (24 wins) | 1.87% (33 wins) | 3.30% (32 wins) |
| 4.0 | 80 | 6.64% (17 wins) | 8.12% (17 wins) | 1.31% (33 wins) | 4.07% (35 wins) |

### heavy

| level | cases | wfd | tg | ra | ra-tg |
|---|---:|---:|---:|---:|---:|
| 0 | 80 | 10.41% (15 wins) | 11.53% (8 wins) | 1.40% (31 wins) | 6.17% (24 wins) |
| 1 | 80 | 2.35% (23 wins) | 2.33% (33 wins) | 1.77% (35 wins) | 1.53% (43 wins) |

## Global and Clustered (1+1+2) against the best placement

| configuration | feasible | beats best placement | median gap | feasible when no placement is |
|---|---:|---:|---:|---:|
| g | 120/160 | 9 | 5.83% | 0 |
| c2 | 123/160 | 18 | 2.33% | 0 |

## Placement selector (feature pre-check RF)

132 cases (excluded with no feasible placement: 28); labels {'wfd': 38, 'tg': 26, 'ra': 45, 'ra-tg': 23}; near-ties 90

### set-level cross-validation

| method | mean regret | p95 | max | accuracy | infeasible choices |
|---|---:|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% | 0.0 |
| always wfd | 6.15% | 21.83% | 46.56% | 28.79% | 7.0 |
| always tg | 6.60% | 27.42% | 45.03% | 19.70% | 5.0 |
| always ra | 1.59% | 8.79% | 17.11% | 34.09% | 7.0 |
| always ra-tg | 3.68% | 19.32% | 45.03% | 17.42% | 7.0 |
| fixed (train) | 1.59% | 8.79% | 17.11% | 34.09% | 7.0 |
| R0 / classifier | 3.46% | 17.88% | 39.56% | 30.91% | 5.4 |
| R0 / weighted | 2.36% | 12.69% | 34.28% | 25.45% | 8.8 |
| R0 / regressor | 2.61% | 11.88% | 46.56% | 26.82% | 8.0 |
| R0-CLP / classifier | 2.74% | 14.54% | 40.06% | 36.67% | 5.4 |
| R0-CLP / weighted | 1.83% | 9.22% | 42.66% | 31.36% | 7.8 |
| R0-CLP / regressor | 2.21% | 10.21% | 41.86% | 29.24% | 6.4 |
| R1 / classifier | 1.75% | 8.68% | 45.03% | 52.73% | 6.0 |
| R1 / weighted | 1.99% | 10.40% | 33.40% | 26.52% | 7.6 |
| R1 / regressor | 2.74% | 12.54% | 46.56% | 26.36% | 7.2 |
| R2 / classifier | 1.14% | 5.88% | 17.11% | 56.67% | 6.0 |
| R2 / weighted | 1.56% | 8.65% | 31.26% | 33.03% | 8.2 |
| R2 / regressor | 1.82% | 8.20% | 37.15% | 28.18% | 5.6 |
| R3 / classifier | 1.19% | 5.65% | 21.70% | 53.03% | 5.2 |
| R3 / weighted | 1.42% | 6.26% | 23.04% | 29.55% | 8.6 |
| R3 / regressor | 1.82% | 8.66% | 46.56% | 29.39% | 4.2 |
| R4 / classifier | 1.13% | 6.84% | 16.04% | 57.12% | 4.6 |
| R4 / weighted | 1.57% | 8.44% | 31.26% | 30.91% | 7.8 |
| R4 / regressor | 1.59% | 8.05% | 24.16% | 28.64% | 5.8 |

### condition-level cross-validation

| method | mean regret | p95 | max | accuracy | infeasible choices |
|---|---:|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% | 0.0 |
| always wfd | 6.15% | 21.83% | 46.56% | 28.79% | 7.0 |
| always tg | 6.60% | 27.42% | 45.03% | 19.70% | 5.0 |
| always ra | 1.59% | 8.79% | 17.11% | 34.09% | 7.0 |
| always ra-tg | 3.68% | 19.32% | 45.03% | 17.42% | 7.0 |
| fixed (train) | 1.59% | 8.79% | 17.11% | 34.09% | 7.0 |
| R0 / classifier | 3.15% | 17.16% | 46.25% | 28.48% | 5.0 |
| R0 / weighted | 3.55% | 18.13% | 45.95% | 22.73% | 7.2 |
| R0 / regressor | 3.16% | 14.14% | 46.56% | 23.79% | 7.8 |
| R0-CLP / classifier | 2.75% | 14.36% | 44.65% | 32.88% | 8.2 |
| R0-CLP / weighted | 2.10% | 10.21% | 41.36% | 29.70% | 9.8 |
| R0-CLP / regressor | 2.76% | 11.97% | 46.56% | 24.85% | 7.2 |
| R1 / classifier | 2.27% | 11.01% | 45.03% | 45.61% | 6.0 |
| R1 / weighted | 2.84% | 15.93% | 44.08% | 25.30% | 7.4 |
| R1 / regressor | 3.34% | 15.03% | 46.56% | 24.39% | 7.0 |
| R2 / classifier | 2.07% | 10.46% | 45.03% | 52.42% | 5.8 |
| R2 / weighted | 1.54% | 8.73% | 28.76% | 35.91% | 7.8 |
| R2 / regressor | 2.12% | 8.65% | 46.56% | 29.85% | 4.6 |
| R3 / classifier | 2.29% | 10.83% | 45.03% | 48.03% | 6.4 |
| R3 / weighted | 1.81% | 8.62% | 37.80% | 30.15% | 8.2 |
| R3 / regressor | 2.49% | 11.99% | 46.56% | 27.42% | 4.4 |
| R4 / classifier | 2.04% | 9.25% | 45.03% | 51.97% | 5.8 |
| R4 / weighted | 1.41% | 7.89% | 22.05% | 36.21% | 7.8 |
| R4 / regressor | 1.84% | 8.44% | 40.67% | 31.21% | 3.6 |

