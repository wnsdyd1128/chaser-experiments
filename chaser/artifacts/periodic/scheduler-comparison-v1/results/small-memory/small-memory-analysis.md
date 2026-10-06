# Small-memory analysis

Regret: value / best Partitioned placement of the same case - 1. Startup failures are excluded,
not counted as infeasible.

## Runs: ok / deadline miss / excluded

| cell | g | c2 | p | p_cgb | p_ra | p_racgb |
|---|---|---|---|---|---|---|
| cv00-low00 | 26 / 0 / 1 | 26 / 0 / 1 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 |
| cv00-low25 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 |
| cv00-low50 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 |
| cv10-low00 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 |
| cv10-low25 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 |
| cv10-low50 | 26 / 0 / 1 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 |
| cv20-low00 | 27 / 0 / 0 | 27 / 0 / 0 | 26 / 0 / 1 | 26 / 0 / 1 | 27 / 0 / 0 | 27 / 0 / 0 |
| cv20-low25 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 26 / 0 / 1 | 27 / 0 / 0 |
| cv20-low50 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 |
| cv30-low00 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 26 / 0 / 1 | 26 / 0 / 1 |
| cv30-low25 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 26 / 0 / 1 | 27 / 0 / 0 |
| cv30-low50 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 | 27 / 0 / 0 |

## TAT per cell

| cell | wfd median / regret / wins | cgb median / regret / wins | ra median / regret / wins | ra-cgb median / regret / wins |
|---|---|---|---|---|
| cv00-low00 | 232.8 / 3.15% / 4 | 232.8 / 3.15% / 4 | 226.2 / 0.13% / 24 | 226.2 / 0.13% / 24 |
| cv00-low25 | 283.1 / 3.04% / 5 | 281.1 / 1.62% / 7 | 282.8 / 2.17% / 7 | 278.4 / 1.23% / 10 |
| cv00-low50 | 363.9 / 2.77% / 2 | 355.4 / 0.94% / 11 | 354.8 / 1.31% / 6 | 355.3 / 0.58% / 10 |
| cv10-low00 | 312.7 / 16.80% / 0 | 312.7 / 16.80% / 0 | 273.9 / 0.00% / 27 | 273.9 / 0.00% / 27 |
| cv10-low25 | 374.7 / 15.18% / 1 | 362.6 / 12.54% / 3 | 328.0 / 1.36% / 15 | 333.3 / 2.85% / 8 |
| cv10-low50 | 471.2 / 13.49% / 2 | 472.0 / 13.04% / 0 | 424.8 / 1.97% / 13 | 428.1 / 2.97% / 12 |
| cv20-low00 | 365.4 / 25.60% / 0 | 365.4 / 25.60% / 0 | 295.5 / 0.00% / 27 | 295.5 / 0.00% / 27 |
| cv20-low25 | 414.5 / 19.46% / 1 | 418.5 / 18.98% / 0 | 352.7 / 0.67% / 15 | 361.1 / 3.96% / 11 |
| cv20-low50 | 531.4 / 14.63% / 0 | 515.8 / 12.89% / 1 | 464.5 / 1.44% / 15 | 463.6 / 2.00% / 11 |
| cv30-low00 | 372.6 / 22.05% / 2 | 372.6 / 22.05% / 2 | 294.9 / 0.03% / 25 | 294.9 / 0.03% / 25 |
| cv30-low25 | 426.0 / 18.94% / 0 | 422.3 / 18.70% / 1 | 357.3 / 1.36% / 14 | 360.9 / 2.10% / 12 |
| cv30-low50 | 536.9 / 12.10% / 0 | 541.9 / 12.87% / 1 | 488.3 / 2.39% / 10 | 487.2 / 1.56% / 16 |

## TET per cell

| cell | wfd median / regret / wins | cgb median / regret / wins | ra median / regret / wins | ra-cgb median / regret / wins |
|---|---|---|---|---|
| cv00-low00 | 887.2 / 0.61% / 14 | 887.2 / 0.61% / 14 | 888.6 / 0.72% / 14 | 888.6 / 0.72% / 14 |
| cv00-low25 | 1065.9 / 4.11% / 0 | 1023.8 / 0.63% / 15 | 1077.7 / 4.97% / 1 | 1031.8 / 1.04% / 12 |
| cv00-low50 | 1336.2 / 6.02% / 3 | 1273.7 / 0.78% / 15 | 1360.1 / 7.06% / 0 | 1275.1 / 0.60% / 10 |
| cv10-low00 | 865.5 / 0.14% / 23 | 865.5 / 0.14% / 23 | 877.8 / 1.24% / 4 | 877.8 / 1.24% / 4 |
| cv10-low25 | 1020.4 / 4.39% / 2 | 993.1 / 0.93% / 12 | 1031.1 / 5.60% / 2 | 988.2 / 1.69% / 11 |
| cv10-low50 | 1287.2 / 5.79% / 4 | 1227.1 / 1.45% / 13 | 1297.9 / 8.22% / 0 | 1223.4 / 2.09% / 10 |
| cv20-low00 | 856.1 / 0.01% / 25 | 856.1 / 0.01% / 25 | 878.5 / 2.23% / 2 | 878.5 / 2.23% / 2 |
| cv20-low25 | 983.9 / 2.93% / 8 | 954.2 / 0.53% / 14 | 1035.7 / 7.94% / 0 | 970.3 / 3.04% / 5 |
| cv20-low50 | 1185.3 / 3.90% / 11 | 1173.2 / 1.45% / 12 | 1263.9 / 9.60% / 0 | 1238.3 / 4.53% / 4 |
| cv30-low00 | 852.2 / 0.05% / 26 | 852.2 / 0.05% / 26 | 876.3 / 2.90% / 1 | 876.3 / 2.90% / 1 |
| cv30-low25 | 971.9 / 3.10% / 4 | 942.5 / 0.69% / 21 | 1015.3 / 8.07% / 1 | 968.5 / 4.13% / 1 |
| cv30-low50 | 1178.3 / 4.89% / 4 | 1146.4 / 1.01% / 18 | 1270.6 / 12.09% / 0 | 1188.9 / 4.42% / 5 |

## Paired contrasts

| scope | metric | pair | n | better / tie / worse | median | Holm p | only first / only second meets deadlines |
|---|---|---|---:|---|---:|---:|---|
| cv00-low25 | TAT | cgb vs ra | 27 | 14 / 0 / 13 | -0.07% | 1 | 0 / 0 |
| cv00-low25 | TET | cgb vs ra | 27 | 25 / 0 / 2 | -3.83% | 2.16e-05 | 0 / 0 |
| cv00-low25 | TAT | ra-cgb vs ra | 27 | 16 / 0 / 11 | -1.72% | 1 | 0 / 0 |
| cv00-low25 | TET | ra-cgb vs ra | 27 | 24 / 0 / 3 | -3.65% | 3.52e-05 | 0 / 0 |
| cv00-low50 | TAT | cgb vs ra | 27 | 16 / 0 / 11 | -0.41% | 1 | 0 / 0 |
| cv00-low50 | TET | cgb vs ra | 27 | 26 / 0 / 1 | -5.72% | 3.08e-06 | 0 / 0 |
| cv00-low50 | TAT | ra-cgb vs ra | 27 | 17 / 0 / 10 | -0.65% | 1 | 0 / 0 |
| cv00-low50 | TET | ra-cgb vs ra | 27 | 26 / 0 / 1 | -5.39% | 2.24e-06 | 0 / 0 |
| cv10-low25 | TAT | cgb vs ra | 27 | 5 / 0 / 22 | 11.88% | 0.000539 | 0 / 0 |
| cv10-low25 | TET | cgb vs ra | 27 | 23 / 0 / 4 | -4.77% | 0.000343 | 0 / 0 |
| cv10-low25 | TAT | ra-cgb vs ra | 27 | 10 / 0 / 17 | 0.87% | 1 | 0 / 0 |
| cv10-low25 | TET | ra-cgb vs ra | 27 | 24 / 0 / 3 | -2.27% | 0.000123 | 0 / 0 |
| cv10-low50 | TAT | cgb vs ra | 27 | 4 / 0 / 23 | 9.36% | 0.000215 | 0 / 0 |
| cv10-low50 | TET | cgb vs ra | 27 | 25 / 0 / 2 | -6.46% | 0.000123 | 0 / 0 |
| cv10-low50 | TAT | ra-cgb vs ra | 27 | 14 / 0 / 13 | -0.01% | 1 | 0 / 0 |
| cv10-low50 | TET | ra-cgb vs ra | 27 | 26 / 0 / 1 | -6.30% | 4.69e-06 | 0 / 0 |
| cv20-low25 | TAT | cgb vs ra | 26 | 1 / 0 / 25 | 16.98% | 3.99e-06 | 0 / 0 |
| cv20-low25 | TET | cgb vs ra | 26 | 26 / 0 / 0 | -6.78% | 2.24e-06 | 0 / 0 |
| cv20-low25 | TAT | ra-cgb vs ra | 26 | 11 / 0 / 15 | 0.39% | 1 | 0 / 0 |
| cv20-low25 | TET | ra-cgb vs ra | 26 | 25 / 0 / 1 | -4.36% | 9.24e-06 | 0 / 0 |
| cv20-low50 | TAT | cgb vs ra | 27 | 2 / 0 / 25 | 11.31% | 4.26e-05 | 0 / 0 |
| cv20-low50 | TET | cgb vs ra | 27 | 26 / 0 / 1 | -6.93% | 3.08e-06 | 0 / 0 |
| cv20-low50 | TAT | ra-cgb vs ra | 27 | 12 / 0 / 15 | 0.03% | 1 | 0 / 0 |
| cv20-low50 | TET | ra-cgb vs ra | 27 | 24 / 0 / 3 | -3.39% | 5.32e-05 | 0 / 0 |
| cv30-low25 | TAT | cgb vs ra | 26 | 1 / 0 / 25 | 16.28% | 3.99e-06 | 0 / 0 |
| cv30-low25 | TET | cgb vs ra | 26 | 23 / 0 / 3 | -7.89% | 2.38e-05 | 0 / 0 |
| cv30-low25 | TAT | ra-cgb vs ra | 26 | 11 / 0 / 15 | 0.28% | 1 | 0 / 0 |
| cv30-low25 | TET | ra-cgb vs ra | 26 | 23 / 0 / 3 | -2.92% | 2.38e-05 | 0 / 0 |
| cv30-low50 | TAT | cgb vs ra | 27 | 3 / 0 / 24 | 10.33% | 3.52e-05 | 0 / 0 |
| cv30-low50 | TET | cgb vs ra | 27 | 27 / 0 / 0 | -9.85% | 1.18e-06 | 0 / 0 |
| cv30-low50 | TAT | ra-cgb vs ra | 27 | 16 / 0 / 11 | -0.24% | 1 | 0 / 0 |
| cv30-low50 | TET | ra-cgb vs ra | 27 | 25 / 0 / 2 | -7.82% | 9.24e-06 | 0 / 0 |
| CV 0.0, low-CLS cells | TAT | cgb vs ra | 54 | 30 / 0 / 24 | -0.38% | 1 | 0 / 0 |
| CV 0.0, low-CLS cells | TET | cgb vs ra | 54 | 51 / 0 / 3 | -4.84% | 4.3e-08 | 0 / 0 |
| CV 0.0, low-CLS cells | TAT | ra-cgb vs ra | 54 | 33 / 0 / 21 | -0.76% | 0.54 | 0 / 0 |
| CV 0.0, low-CLS cells | TET | ra-cgb vs ra | 54 | 50 / 0 / 4 | -4.64% | 3.93e-08 | 0 / 0 |
| CV 0.1, low-CLS cells | TAT | cgb vs ra | 54 | 9 / 0 / 45 | 10.73% | 1.09e-06 | 0 / 0 |
| CV 0.1, low-CLS cells | TET | cgb vs ra | 54 | 48 / 0 / 6 | -5.31% | 9.58e-07 | 0 / 0 |
| CV 0.1, low-CLS cells | TAT | ra-cgb vs ra | 54 | 24 / 0 / 30 | 0.52% | 1 | 0 / 0 |
| CV 0.1, low-CLS cells | TET | ra-cgb vs ra | 54 | 50 / 0 / 4 | -4.22% | 8.83e-08 | 0 / 0 |
| CV 0.2, low-CLS cells | TAT | cgb vs ra | 53 | 3 / 0 / 50 | 14.33% | 5.56e-08 | 0 / 0 |
| CV 0.2, low-CLS cells | TET | cgb vs ra | 53 | 52 / 0 / 1 | -6.93% | 2.73e-08 | 0 / 0 |
| CV 0.2, low-CLS cells | TAT | ra-cgb vs ra | 53 | 23 / 0 / 30 | 0.16% | 1 | 0 / 0 |
| CV 0.2, low-CLS cells | TET | ra-cgb vs ra | 53 | 49 / 0 / 4 | -4.06% | 8.24e-08 | 0 / 0 |
| CV 0.3, low-CLS cells | TAT | cgb vs ra | 53 | 4 / 0 / 49 | 13.80% | 5.32e-08 | 0 / 0 |
| CV 0.3, low-CLS cells | TET | cgb vs ra | 53 | 50 / 0 / 3 | -8.24% | 3.93e-08 | 0 / 0 |
| CV 0.3, low-CLS cells | TAT | ra-cgb vs ra | 53 | 27 / 0 / 26 | -0.06% | 1 | 0 / 0 |
| CV 0.3, low-CLS cells | TET | ra-cgb vs ra | 53 | 48 / 0 / 5 | -4.25% | 7.97e-08 | 0 / 0 |
| low 25%, CV > 0 | TAT | cgb vs ra | 79 | 7 / 0 / 72 | 16.05% | 6.38e-12 | 0 / 0 |
| low 25%, CV > 0 | TET | cgb vs ra | 79 | 72 / 0 / 7 | -6.37% | 7.9e-12 | 0 / 0 |
| low 25%, CV > 0 | TAT | ra-cgb vs ra | 79 | 32 / 0 / 47 | 0.51% | 0.715 | 0 / 0 |
| low 25%, CV > 0 | TET | ra-cgb vs ra | 79 | 72 / 0 / 7 | -3.57% | 1.36e-11 | 0 / 0 |
| low 50%, CV > 0 | TAT | cgb vs ra | 81 | 9 / 0 / 72 | 10.51% | 2e-11 | 0 / 0 |
| low 50%, CV > 0 | TET | cgb vs ra | 81 | 78 / 0 / 3 | -7.97% | 2.1e-12 | 0 / 0 |
| low 50%, CV > 0 | TAT | ra-cgb vs ra | 81 | 42 / 0 / 39 | -0.06% | 1 | 0 / 0 |
| low 50%, CV > 0 | TET | ra-cgb vs ra | 81 | 75 / 0 / 6 | -4.77% | 4.8e-12 | 0 / 0 |
| CV 0.0, no low-CLS tasks | TAT | ra vs wfd | 27 | 23 / 1 / 3 | -2.51% | 3.95e-05 | 0 / 0 |
| CV 0.0, no low-CLS tasks | TET | ra vs wfd | 27 | 13 / 1 / 13 | 0.00% | 1 | 0 / 0 |
| CV 0.1, no low-CLS tasks | TAT | ra vs wfd | 27 | 27 / 0 / 0 | -14.13% | 1.18e-06 | 0 / 0 |
| CV 0.1, no low-CLS tasks | TET | ra vs wfd | 27 | 4 / 0 / 23 | 0.83% | 0.0253 | 0 / 0 |
| CV 0.2, no low-CLS tasks | TAT | ra vs wfd | 26 | 26 / 0 / 0 | -21.08% | 2.24e-06 | 0 / 0 |
| CV 0.2, no low-CLS tasks | TET | ra vs wfd | 26 | 1 / 0 / 25 | 2.24% | 9.24e-06 | 0 / 0 |
| CV 0.3, no low-CLS tasks | TAT | ra vs wfd | 26 | 25 / 0 / 1 | -18.95% | 3.99e-06 | 0 / 0 |
| CV 0.3, no low-CLS tasks | TET | ra vs wfd | 26 | 1 / 0 / 25 | 3.03% | 1.76e-05 | 0 / 0 |
| CV 0, 12-14 tasks | TAT | cgb vs ra | 18 | 10 / 0 / 8 | -0.24% | 1 | 0 / 0 |
| CV 0, 12-14 tasks | TET | cgb vs ra | 18 | 16 / 0 / 2 | -4.56% | 0.00507 | 0 / 0 |
| CV 0, 12-14 tasks | TAT | ra-cgb vs ra | 18 | 9 / 0 / 9 | 0.08% | 1 | 0 / 0 |
| CV 0, 12-14 tasks | TET | ra-cgb vs ra | 18 | 16 / 0 / 2 | -4.24% | 0.00395 | 0 / 0 |
| CV 0, 15-17 tasks | TAT | cgb vs ra | 18 | 11 / 0 / 7 | -0.68% | 1 | 0 / 0 |
| CV 0, 15-17 tasks | TET | cgb vs ra | 18 | 18 / 0 / 0 | -4.01% | 0.000343 | 0 / 0 |
| CV 0, 15-17 tasks | TAT | ra-cgb vs ra | 18 | 12 / 0 / 6 | -1.47% | 1 | 0 / 0 |
| CV 0, 15-17 tasks | TET | ra-cgb vs ra | 18 | 16 / 0 / 2 | -4.43% | 0.00145 | 0 / 0 |
| CV 0, 18-20 tasks | TAT | cgb vs ra | 18 | 9 / 0 / 9 | -0.10% | 1 | 0 / 0 |
| CV 0, 18-20 tasks | TET | cgb vs ra | 18 | 17 / 0 / 1 | -5.32% | 0.000595 | 0 / 0 |
| CV 0, 18-20 tasks | TAT | ra-cgb vs ra | 18 | 12 / 0 / 6 | -1.39% | 0.343 | 0 / 0 |
| CV 0, 18-20 tasks | TET | ra-cgb vs ra | 18 | 18 / 0 / 0 | -5.31% | 0.000343 | 0 / 0 |
| CV 0, multiple of 4 tasks | TAT | cgb vs ra | 18 | 10 / 0 / 8 | -0.52% | 1 | 0 / 0 |
| CV 0, multiple of 4 tasks | TET | cgb vs ra | 18 | 18 / 0 / 0 | -5.72% | 0.000343 | 0 / 0 |
| CV 0, multiple of 4 tasks | TAT | ra-cgb vs ra | 18 | 12 / 0 / 6 | -1.36% | 1 | 0 / 0 |
| CV 0, multiple of 4 tasks | TET | ra-cgb vs ra | 18 | 18 / 0 / 0 | -5.19% | 0.000343 | 0 / 0 |
| CV 0, not a multiple of 4 tasks | TAT | cgb vs ra | 36 | 20 / 0 / 16 | -0.38% | 1 | 0 / 0 |
| CV 0, not a multiple of 4 tasks | TET | cgb vs ra | 36 | 33 / 0 / 3 | -4.74% | 3.39e-07 | 0 / 0 |
| CV 0, not a multiple of 4 tasks | TAT | ra-cgb vs ra | 36 | 21 / 0 / 15 | -0.51% | 1 | 0 / 0 |
| CV 0, not a multiple of 4 tasks | TET | ra-cgb vs ra | 36 | 32 / 0 / 4 | -4.61% | 3.39e-07 | 0 / 0 |
| CV > 0, 12-14 tasks | TAT | cgb vs ra | 52 | 5 / 0 / 47 | 11.53% | 2.51e-07 | 0 / 0 |
| CV > 0, 12-14 tasks | TET | cgb vs ra | 52 | 47 / 0 / 5 | -6.02% | 1.02e-06 | 0 / 0 |
| CV > 0, 12-14 tasks | TAT | ra-cgb vs ra | 52 | 22 / 0 / 30 | 0.22% | 1 | 0 / 0 |
| CV > 0, 12-14 tasks | TET | ra-cgb vs ra | 52 | 43 / 0 / 9 | -2.44% | 2.52e-06 | 0 / 0 |
| CV > 0, 15-17 tasks | TAT | cgb vs ra | 54 | 6 / 0 / 48 | 14.01% | 5.01e-08 | 0 / 0 |
| CV > 0, 15-17 tasks | TET | cgb vs ra | 54 | 52 / 0 / 2 | -7.98% | 2.24e-08 | 0 / 0 |
| CV > 0, 15-17 tasks | TAT | ra-cgb vs ra | 54 | 30 / 0 / 24 | -0.56% | 1 | 0 / 0 |
| CV > 0, 15-17 tasks | TET | ra-cgb vs ra | 54 | 51 / 0 / 3 | -4.23% | 3.18e-08 | 0 / 0 |
| CV > 0, 18-20 tasks | TAT | cgb vs ra | 54 | 5 / 0 / 49 | 12.59% | 8.1e-08 | 0 / 0 |
| CV > 0, 18-20 tasks | TET | cgb vs ra | 54 | 51 / 0 / 3 | -6.42% | 2.87e-08 | 0 / 0 |
| CV > 0, 18-20 tasks | TAT | ra-cgb vs ra | 54 | 22 / 0 / 32 | 0.66% | 1 | 0 / 0 |
| CV > 0, 18-20 tasks | TET | ra-cgb vs ra | 54 | 53 / 0 / 1 | -5.43% | 2.14e-08 | 0 / 0 |
| CV > 0, multiple of 4 tasks | TAT | cgb vs ra | 52 | 6 / 0 / 46 | 11.41% | 2.94e-07 | 0 / 0 |
| CV > 0, multiple of 4 tasks | TET | cgb vs ra | 52 | 50 / 0 / 2 | -8.14% | 5.56e-08 | 0 / 0 |
| CV > 0, multiple of 4 tasks | TAT | ra-cgb vs ra | 52 | 23 / 0 / 29 | 0.49% | 1 | 0 / 0 |
| CV > 0, multiple of 4 tasks | TET | ra-cgb vs ra | 52 | 49 / 0 / 3 | -6.35% | 6.11e-08 | 0 / 0 |
| CV > 0, not a multiple of 4 tasks | TAT | cgb vs ra | 108 | 10 / 0 / 98 | 13.72% | 3.16e-16 | 0 / 0 |
| CV > 0, not a multiple of 4 tasks | TET | cgb vs ra | 108 | 100 / 0 / 8 | -6.53% | 3.79e-16 | 0 / 0 |
| CV > 0, not a multiple of 4 tasks | TAT | ra-cgb vs ra | 108 | 51 / 0 / 57 | 0.13% | 1 | 0 / 0 |
| CV > 0, not a multiple of 4 tasks | TET | ra-cgb vs ra | 108 | 98 / 0 / 10 | -3.38% | 1.19e-15 | 0 / 0 |
| CV > 0, no low-CLS tasks, 12-14 tasks | TAT | ra vs wfd | 26 | 25 / 0 / 1 | -16.68% | 3.99e-06 | 0 / 0 |
| CV > 0, no low-CLS tasks, 12-14 tasks | TET | ra vs wfd | 26 | 2 / 0 / 24 | 2.30% | 6.41e-05 | 0 / 0 |
| CV > 0, no low-CLS tasks, 15-17 tasks | TAT | ra vs wfd | 26 | 26 / 0 / 0 | -15.06% | 2.24e-06 | 0 / 0 |
| CV > 0, no low-CLS tasks, 15-17 tasks | TET | ra vs wfd | 26 | 4 / 0 / 22 | 1.44% | 0.00395 | 0 / 0 |
| CV > 0, no low-CLS tasks, 18-20 tasks | TAT | ra vs wfd | 27 | 27 / 0 / 0 | -21.74% | 1.18e-06 | 0 / 0 |
| CV > 0, no low-CLS tasks, 18-20 tasks | TET | ra vs wfd | 27 | 0 / 0 / 27 | 2.27% | 1.18e-06 | 0 / 0 |
| CV > 0, no low-CLS tasks, multiple of 4 tasks | TAT | ra vs wfd | 26 | 26 / 0 / 0 | -16.82% | 2.24e-06 | 0 / 0 |
| CV > 0, no low-CLS tasks, multiple of 4 tasks | TET | ra vs wfd | 26 | 3 / 0 / 23 | 1.78% | 0.000232 | 0 / 0 |
| CV > 0, no low-CLS tasks, not a multiple of 4 tasks | TAT | ra vs wfd | 53 | 52 / 0 / 1 | -17.83% | 2.6e-08 | 0 / 0 |
| CV > 0, no low-CLS tasks, not a multiple of 4 tasks | TET | ra vs wfd | 53 | 3 / 0 / 50 | 2.21% | 3.53e-07 | 0 / 0 |

## G and C2 against the best Partitioned placement

| scope | cases | G ok / beats best P (TAT, TET) / median TAT gap | C2 ok / beats best P (TAT, TET) / median TAT gap |
|---|---:|---|---|
| 12-14 | 108 | 108 / 10, 13 / 4.36% | 107 / 4, 23 / 9.64% |
| 15-17 | 108 | 107 / 8, 9 / 5.89% | 108 / 0, 19 / 11.53% |
| 18-20 | 108 | 107 / 11, 9 / 5.59% | 108 / 1, 17 / 10.76% |
| multiple of 4 | 108 | 107 / 7, 8 / 5.75% | 107 / 1, 26 / 11.10% |
| not a multiple of 4 | 216 | 215 / 22, 23 / 5.25% | 216 / 4, 33 / 10.12% |

## Placement selector (TAT labels)

324 cases; labels {'wfd': 17, 'cgb': 24, 'ra': 196, 'ra-cgb': 87}; near-ties 182

### set-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 13.90% | 32.88% | 50.87% | 5.25% |
| always cgb | 13.23% | 32.96% | 50.87% | 7.41% |
| always ra | 1.07% | 5.32% | 9.88% | 60.49% |
| always ra-cgb | 1.45% | 8.61% | 20.76% | 26.85% |
| fixed (train) | 1.42% | 8.50% | 19.37% | 33.95% |
| R0 / classifier | 1.26% | 5.95% | 24.51% | 60.00% |
| R0 / regressor | 1.85% | 9.84% | 34.36% | 46.11% |
| R0-CLP / classifier | 1.22% | 5.89% | 23.06% | 60.31% |
| R0-CLP / regressor | 1.75% | 8.70% | 34.36% | 45.86% |
| R1 / classifier | 1.02% | 5.22% | 15.17% | 62.28% |
| R1 / regressor | 1.54% | 6.64% | 34.36% | 48.15% |
| R2 / classifier | 1.01% | 5.04% | 14.28% | 62.22% |
| R2 / regressor | 1.31% | 6.27% | 26.46% | 46.30% |
| R3 / classifier | 0.92% | 4.77% | 12.23% | 62.78% |
| R3 / regressor | 1.36% | 6.10% | 34.36% | 50.74% |
| R4 / classifier | 0.98% | 4.96% | 13.45% | 62.35% |
| R4 / regressor | 1.12% | 5.64% | 20.13% | 47.53% |

### condition-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 13.90% | 32.88% | 50.87% | 5.25% |
| always cgb | 13.23% | 32.96% | 50.87% | 7.41% |
| always ra | 1.07% | 5.32% | 9.88% | 60.49% |
| always ra-cgb | 1.45% | 8.61% | 20.76% | 26.85% |
| fixed (train) | 1.39% | 8.38% | 20.76% | 27.47% |
| R0 / classifier | 1.83% | 10.38% | 29.06% | 58.09% |
| R0 / regressor | 1.24% | 6.62% | 29.06% | 49.81% |
| R0-CLP / classifier | 1.70% | 9.35% | 29.06% | 58.46% |
| R0-CLP / regressor | 1.20% | 6.77% | 21.49% | 50.86% |
| R1 / classifier | 1.07% | 4.99% | 20.11% | 61.11% |
| R1 / regressor | 0.94% | 4.83% | 21.62% | 48.83% |
| R2 / classifier | 1.14% | 5.63% | 17.19% | 59.94% |
| R2 / regressor | 0.97% | 5.07% | 20.19% | 47.47% |
| R3 / classifier | 1.14% | 5.41% | 22.56% | 60.31% |
| R3 / regressor | 0.95% | 5.24% | 14.28% | 49.57% |
| R4 / classifier | 1.12% | 5.57% | 17.17% | 60.49% |
| R4 / regressor | 0.98% | 5.05% | 23.15% | 48.70% |


## Placement selector (TET labels)

324 cases; labels {'wfd': 124, 'cgb': 120, 'ra': 24, 'ra-cgb': 56}; near-ties 184

### set-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 3.00% | 9.90% | 15.56% | 38.27% |
| always cgb | 0.69% | 3.65% | 9.62% | 37.04% |
| always ra | 5.88% | 14.01% | 22.37% | 7.41% |
| always ra-cgb | 2.38% | 8.42% | 11.49% | 17.28% |
| fixed (train) | 0.69% | 3.65% | 9.62% | 37.04% |
| R0 / classifier | 0.80% | 4.12% | 8.84% | 63.15% |
| R0 / regressor | 0.90% | 4.13% | 9.38% | 48.15% |
| R0-CLP / classifier | 0.76% | 4.15% | 8.47% | 63.02% |
| R0-CLP / regressor | 0.85% | 4.02% | 9.29% | 51.05% |
| R1 / classifier | 0.66% | 3.61% | 8.54% | 64.75% |
| R1 / regressor | 0.79% | 3.91% | 8.73% | 46.79% |
| R2 / classifier | 0.69% | 3.65% | 8.57% | 64.26% |
| R2 / regressor | 0.80% | 4.04% | 8.95% | 49.38% |
| R3 / classifier | 0.63% | 3.38% | 8.54% | 65.06% |
| R3 / regressor | 0.78% | 3.95% | 8.75% | 49.94% |
| R4 / classifier | 0.68% | 3.69% | 8.54% | 64.63% |
| R4 / regressor | 0.80% | 4.05% | 9.19% | 49.94% |

### condition-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 3.00% | 9.90% | 15.56% | 38.27% |
| always cgb | 0.69% | 3.65% | 9.62% | 37.04% |
| always ra | 5.88% | 14.01% | 22.37% | 7.41% |
| always ra-cgb | 2.38% | 8.42% | 11.49% | 17.28% |
| fixed (train) | 0.69% | 3.65% | 9.62% | 37.04% |
| R0 / classifier | 0.82% | 4.72% | 11.25% | 61.91% |
| R0 / regressor | 0.73% | 3.89% | 11.25% | 54.07% |
| R0-CLP / classifier | 0.82% | 4.66% | 11.25% | 61.98% |
| R0-CLP / regressor | 0.69% | 3.85% | 11.25% | 54.57% |
| R1 / classifier | 0.67% | 3.43% | 11.25% | 63.15% |
| R1 / regressor | 0.66% | 3.41% | 9.33% | 44.51% |
| R2 / classifier | 0.65% | 3.40% | 11.25% | 63.52% |
| R2 / regressor | 0.67% | 3.53% | 8.54% | 45.93% |
| R3 / classifier | 0.71% | 3.64% | 11.25% | 62.16% |
| R3 / regressor | 0.69% | 3.54% | 8.54% | 45.86% |
| R4 / classifier | 0.67% | 3.57% | 11.25% | 63.33% |
| R4 / regressor | 0.67% | 3.61% | 8.63% | 46.42% |

