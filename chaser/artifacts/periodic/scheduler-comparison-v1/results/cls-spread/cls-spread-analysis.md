# CLS spread analysis

Regret: value / best Partitioned placement of the same case - 1. Startup failures are excluded,
not counted as infeasible.

## Runs: ok / deadline miss / excluded

| cell | g | c2 | p | p_cgb | p_ra | p_racgb | p_cgr | p_racgr |
|---|---|---|---|---|---|---|---|---|
| cls30-sd00-cv00 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 |
| cls30-sd00-cv20 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 |
| cls30-sd10-cv00 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 |
| cls30-sd10-cv20 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 | 0 / 18 / 0 |
| cls30-sd20-cv00 | 0 / 18 / 0 | 3 / 15 / 0 | 3 / 14 / 1 | 3 / 15 / 0 | 6 / 12 / 0 | 6 / 12 / 0 | 3 / 15 / 0 | 4 / 14 / 0 |
| cls30-sd20-cv20 | 4 / 14 / 0 | 4 / 14 / 0 | 4 / 14 / 0 | 3 / 15 / 0 | 3 / 15 / 0 | 2 / 16 / 0 | 3 / 15 / 0 | 5 / 13 / 0 |
| cls60-sd00-cv00 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls60-sd00-cv20 | 17 / 0 / 1 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls60-sd10-cv00 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls60-sd10-cv20 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls60-sd20-cv00 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls60-sd20-cv20 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls90-sd00-cv00 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 17 / 0 / 1 | 17 / 0 / 1 | 18 / 0 / 0 | 17 / 0 / 1 |
| cls90-sd00-cv20 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls90-sd10-cv00 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls90-sd10-cv20 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls90-sd20-cv00 | 18 / 0 / 0 | 17 / 0 / 1 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| cls90-sd20-cv20 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |

## TAT per cell (median ms / mean regret / wins)

| cell | wfd | cgb | ra | ra-cgb | cgr | ra-cgr |
|---|---|---|---|---|---|---|
| cls30-sd00-cv00 | - | - | - | - | - | - |
| cls30-sd00-cv20 | - | - | - | - | - | - |
| cls30-sd10-cv00 | - | - | - | - | - | - |
| cls30-sd10-cv20 | - | - | - | - | - | - |
| cls30-sd20-cv00 | 471.2 / 0.76% / 0 | 471.7 / 0.42% / 0 | 471.0 / 0.02% / 3 | 471.0 / 0.01% / 5 | 466.5 / 0.55% / 0 | 467.4 / 0.11% / 1 |
| cls30-sd20-cv20 | 906.8 / 10.77% / 1 | 920.5 / 15.76% / 1 | 905.0 / 2.95% / 0 | 848.8 / 3.01% / 0 | 855.1 / 0.69% / 2 | 928.8 / 3.48% / 3 |
| cls60-sd00-cv00 | 397.0 / 1.23% / 1 | 397.0 / 1.23% / 1 | 392.2 / 0.01% / 17 | 392.2 / 0.01% / 17 | 397.0 / 1.23% / 1 | 392.2 / 0.01% / 17 |
| cls60-sd00-cv20 | 609.2 / 19.21% / 0 | 609.2 / 19.21% / 0 | 506.6 / 0.00% / 18 | 506.6 / 0.00% / 18 | 609.2 / 19.21% / 0 | 506.6 / 0.00% / 18 |
| cls60-sd10-cv00 | 390.8 / 1.20% / 0 | 393.5 / 1.23% / 0 | 389.3 / 0.14% / 13 | 391.4 / 0.46% / 4 | 394.5 / 1.47% / 1 | 388.8 / 0.36% / 2 |
| cls60-sd10-cv20 | 608.2 / 18.19% / 0 | 601.7 / 18.64% / 0 | 516.9 / 0.19% / 12 | 515.7 / 1.58% / 5 | 604.8 / 18.30% / 0 | 519.9 / 3.62% / 4 |
| cls60-sd20-cv00 | 372.4 / 1.20% / 2 | 375.4 / 1.47% / 0 | 374.4 / 0.44% / 8 | 372.1 / 0.61% / 3 | 373.8 / 1.13% / 5 | 371.2 / 0.60% / 1 |
| cls60-sd20-cv20 | 561.4 / 17.33% / 0 | 550.8 / 17.23% / 0 | 487.6 / 0.71% / 8 | 495.5 / 2.34% / 7 | 575.9 / 16.79% / 0 | 498.8 / 2.76% / 6 |
| cls90-sd00-cv00 | 236.8 / 3.44% / 3 | 236.8 / 3.44% / 3 | 227.4 / 0.08% / 15 | 227.4 / 0.08% / 15 | 236.8 / 3.44% / 3 | 227.4 / 0.08% / 15 |
| cls90-sd00-cv20 | 363.7 / 28.14% / 0 | 363.7 / 28.14% / 0 | 288.7 / 0.00% / 18 | 288.7 / 0.00% / 18 | 363.7 / 28.14% / 0 | 288.7 / 0.00% / 18 |
| cls90-sd10-cv00 | 229.6 / 4.06% / 1 | 229.6 / 4.06% / 1 | 225.4 / 0.74% / 7 | 225.4 / 0.74% / 7 | 231.8 / 3.90% / 2 | 226.2 / 1.24% / 8 |
| cls90-sd10-cv20 | 360.4 / 29.28% / 0 | 360.4 / 29.28% / 0 | 279.3 / 0.03% / 15 | 279.3 / 0.03% / 15 | 348.5 / 27.23% / 0 | 285.4 / 3.57% / 3 |
| cls90-sd20-cv00 | 234.6 / 4.26% / 3 | 234.6 / 4.29% / 2 | 230.1 / 1.30% / 7 | 230.1 / 1.49% / 8 | 239.8 / 4.79% / 3 | 230.8 / 1.21% / 4 |
| cls90-sd20-cv20 | 361.8 / 27.87% / 0 | 358.3 / 27.54% / 0 | 285.0 / 0.15% / 10 | 284.7 / 0.41% / 11 | 350.7 / 27.86% / 0 | 291.8 / 3.06% / 6 |

## TET per cell (median ms / mean regret / wins)

| cell | wfd | cgb | ra | ra-cgb | cgr | ra-cgr |
|---|---|---|---|---|---|---|
| cls30-sd00-cv00 | - | - | - | - | - | - |
| cls30-sd00-cv20 | - | - | - | - | - | - |
| cls30-sd10-cv00 | - | - | - | - | - | - |
| cls30-sd10-cv20 | - | - | - | - | - | - |
| cls30-sd20-cv00 | 1800.2 / 1.77% / 0 | 1805.0 / 0.35% / 1 | 1846.0 / 1.81% / 2 | 1842.1 / 1.75% / 2 | 1782.4 / 0.34% / 2 | 1791.9 / 0.41% / 1 |
| cls30-sd20-cv20 | 1800.2 / 3.39% / 0 | 1829.5 / 0.34% / 2 | 1778.0 / 3.36% / 0 | 1792.8 / 2.60% / 0 | 1782.8 / 6.10% / 0 | 1691.8 / 0.00% / 5 |
| cls60-sd00-cv00 | 1527.3 / 0.01% / 17 | 1527.3 / 0.01% / 17 | 1554.2 / 1.65% / 1 | 1554.2 / 1.65% / 1 | 1527.3 / 0.01% / 17 | 1554.2 / 1.65% / 1 |
| cls60-sd00-cv20 | 1412.3 / 0.09% / 16 | 1412.3 / 0.09% / 16 | 1476.2 / 5.81% / 2 | 1476.2 / 5.81% / 2 | 1412.3 / 0.09% / 16 | 1476.2 / 5.81% / 2 |
| cls60-sd10-cv00 | 1509.1 / 1.01% / 3 | 1506.8 / 0.92% / 6 | 1527.4 / 2.22% / 0 | 1516.8 / 1.90% / 0 | 1511.7 / 0.74% / 8 | 1514.4 / 1.27% / 1 |
| cls60-sd10-cv20 | 1380.9 / 3.17% / 4 | 1364.0 / 2.54% / 6 | 1441.4 / 9.08% / 0 | 1444.4 / 8.74% / 0 | 1388.7 / 3.25% / 6 | 1443.3 / 7.50% / 2 |
| cls60-sd20-cv00 | 1447.0 / 1.98% / 5 | 1415.9 / 1.43% / 4 | 1433.6 / 2.70% / 0 | 1399.5 / 1.82% / 4 | 1424.4 / 1.33% / 2 | 1418.9 / 1.15% / 5 |
| cls60-sd20-cv20 | 1294.2 / 2.50% / 5 | 1293.9 / 2.93% / 5 | 1387.2 / 8.54% / 0 | 1354.6 / 6.28% / 3 | 1298.1 / 2.93% / 6 | 1372.2 / 6.04% / 1 |
| cls90-sd00-cv00 | 898.4 / 0.84% / 11 | 898.4 / 0.84% / 11 | 893.0 / 1.04% / 7 | 893.0 / 1.04% / 7 | 898.4 / 0.84% / 11 | 893.0 / 1.04% / 7 |
| cls90-sd00-cv20 | 859.6 / 0.10% / 16 | 859.6 / 0.10% / 16 | 877.4 / 2.79% / 2 | 877.4 / 2.79% / 2 | 859.6 / 0.10% / 16 | 877.4 / 2.79% / 2 |
| cls90-sd10-cv00 | 868.3 / 1.75% / 3 | 868.3 / 1.75% / 3 | 879.4 / 1.56% / 2 | 879.4 / 1.56% / 2 | 856.9 / 0.50% / 8 | 862.7 / 0.61% / 5 |
| cls90-sd10-cv20 | 824.1 / 0.69% / 7 | 824.1 / 0.69% / 7 | 845.3 / 2.98% / 0 | 845.3 / 2.98% / 0 | 826.3 / 0.38% / 9 | 845.1 / 2.08% / 2 |
| cls90-sd20-cv00 | 881.3 / 2.70% / 2 | 881.3 / 2.54% / 2 | 900.0 / 2.15% / 1 | 899.5 / 2.32% / 1 | 870.2 / 0.86% / 4 | 866.3 / 0.53% / 10 |
| cls90-sd20-cv20 | 832.6 / 1.20% / 1 | 832.6 / 1.17% / 4 | 864.2 / 3.64% / 0 | 863.8 / 3.57% / 0 | 828.3 / 0.43% / 11 | 851.8 / 2.35% / 3 |

## Paired contrasts

| scope | metric | pair | n | better / tie / worse | median | Holm p | only first / only second meets deadlines |
|---|---|---|---:|---|---:|---:|---|
| cls30-sd00-cv00 | TAT | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TET | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TAT | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TET | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TAT | cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TET | cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TAT | ra-cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TET | ra-cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TAT | cgr vs cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TET | cgr vs cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TAT | ra-cgr vs ra-cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv00 | TET | ra-cgr vs ra-cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TAT | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TET | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TAT | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TET | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TAT | cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TET | cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TAT | ra-cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TET | ra-cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TAT | cgr vs cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TET | cgr vs cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TAT | ra-cgr vs ra-cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd00-cv20 | TET | ra-cgr vs ra-cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TAT | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TET | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TAT | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TET | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TAT | cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TET | cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TAT | ra-cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TET | ra-cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TAT | cgr vs cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TET | cgr vs cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TAT | ra-cgr vs ra-cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv00 | TET | ra-cgr vs ra-cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TAT | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TET | cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TAT | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TET | ra-cgb vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TAT | cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TET | cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TAT | ra-cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TET | ra-cgr vs ra | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TAT | cgr vs cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TET | cgr vs cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TAT | ra-cgr vs ra-cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd10-cv20 | TET | ra-cgr vs ra-cgb | 0 | 0 / 0 / 0 | - | - | 0 / 0 |
| cls30-sd20-cv00 | TAT | cgb vs ra | 3 | 0 / 0 / 3 | 0.51% | - | 0 / 3 |
| cls30-sd20-cv00 | TET | cgb vs ra | 3 | 2 / 0 / 1 | -1.82% | - | 0 / 3 |
| cls30-sd20-cv00 | TAT | ra-cgb vs ra | 6 | 2 / 4 / 0 | 0.00% | - | 0 / 0 |
| cls30-sd20-cv00 | TET | ra-cgb vs ra | 6 | 1 / 4 / 1 | 0.00% | - | 0 / 0 |
| cls30-sd20-cv00 | TAT | cgr vs ra | 3 | 0 / 0 / 3 | 0.46% | - | 0 / 3 |
| cls30-sd20-cv00 | TET | cgr vs ra | 3 | 3 / 0 / 0 | -2.34% | - | 0 / 3 |
| cls30-sd20-cv00 | TAT | ra-cgr vs ra | 4 | 1 / 0 / 3 | 0.09% | - | 0 / 2 |
| cls30-sd20-cv00 | TET | ra-cgr vs ra | 4 | 4 / 0 / 0 | -2.39% | - | 0 / 2 |
| cls30-sd20-cv00 | TAT | cgr vs cgb | 2 | 1 / 0 / 1 | -0.00% | - | 1 / 1 |
| cls30-sd20-cv00 | TET | cgr vs cgb | 2 | 1 / 0 / 1 | 0.24% | - | 1 / 1 |
| cls30-sd20-cv00 | TAT | ra-cgr vs ra-cgb | 4 | 1 / 0 / 3 | 0.09% | - | 0 / 2 |
| cls30-sd20-cv00 | TET | ra-cgr vs ra-cgb | 4 | 4 / 0 / 0 | -2.18% | - | 0 / 2 |
| cls30-sd20-cv20 | TAT | cgb vs ra | 1 | 0 / 0 / 1 | 29.28% | - | 2 / 2 |
| cls30-sd20-cv20 | TET | cgb vs ra | 1 | 1 / 0 / 0 | -3.87% | - | 2 / 2 |
| cls30-sd20-cv20 | TAT | ra-cgb vs ra | 2 | 0 / 1 / 1 | 1.50% | - | 0 / 1 |
| cls30-sd20-cv20 | TET | ra-cgb vs ra | 2 | 1 / 1 / 0 | -0.13% | - | 0 / 1 |
| cls30-sd20-cv20 | TAT | cgr vs ra | 2 | 2 / 0 / 0 | -4.21% | - | 1 / 1 |
| cls30-sd20-cv20 | TET | cgr vs ra | 2 | 1 / 0 / 1 | 1.16% | - | 1 / 1 |
| cls30-sd20-cv20 | TAT | ra-cgr vs ra | 3 | 1 / 0 / 2 | 1.84% | - | 2 / 0 |
| cls30-sd20-cv20 | TET | ra-cgr vs ra | 3 | 3 / 0 / 0 | -4.39% | - | 2 / 0 |
| cls30-sd20-cv20 | TAT | cgr vs cgb | 1 | 1 / 0 / 0 | -24.90% | - | 2 / 2 |
| cls30-sd20-cv20 | TET | cgr vs cgb | 1 | 0 / 0 / 1 | 2.43% | - | 2 / 2 |
| cls30-sd20-cv20 | TAT | ra-cgr vs ra-cgb | 2 | 1 / 0 / 1 | -0.54% | - | 3 / 0 |
| cls30-sd20-cv20 | TET | ra-cgr vs ra-cgb | 2 | 2 / 0 / 0 | -2.48% | - | 3 / 0 |
| cls60-sd00-cv00 | TAT | cgb vs ra | 18 | 1 / 0 / 17 | 1.21% | 0.00186 | 0 / 0 |
| cls60-sd00-cv00 | TET | cgb vs ra | 18 | 17 / 0 / 1 | -1.66% | 0.00186 | 0 / 0 |
| cls60-sd00-cv00 | TAT | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv00 | TET | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv00 | TAT | cgr vs ra | 18 | 1 / 0 / 17 | 1.21% | 0.00186 | 0 / 0 |
| cls60-sd00-cv00 | TET | cgr vs ra | 18 | 17 / 0 / 1 | -1.66% | 0.00186 | 0 / 0 |
| cls60-sd00-cv00 | TAT | ra-cgr vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv00 | TET | ra-cgr vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv00 | TAT | cgr vs cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv00 | TET | cgr vs cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv00 | TAT | ra-cgr vs ra-cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv00 | TET | ra-cgr vs ra-cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv20 | TAT | cgb vs ra | 18 | 0 / 0 / 18 | 19.12% | 0.00106 | 0 / 0 |
| cls60-sd00-cv20 | TET | cgb vs ra | 18 | 16 / 0 / 2 | -4.30% | 0.00431 | 0 / 0 |
| cls60-sd00-cv20 | TAT | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv20 | TET | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv20 | TAT | cgr vs ra | 18 | 0 / 0 / 18 | 19.12% | 0.00106 | 0 / 0 |
| cls60-sd00-cv20 | TET | cgr vs ra | 18 | 16 / 0 / 2 | -4.30% | 0.00431 | 0 / 0 |
| cls60-sd00-cv20 | TAT | ra-cgr vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv20 | TET | ra-cgr vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv20 | TAT | cgr vs cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv20 | TET | cgr vs cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv20 | TAT | ra-cgr vs ra-cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd00-cv20 | TET | ra-cgr vs ra-cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls60-sd10-cv00 | TAT | cgb vs ra | 18 | 0 / 0 / 18 | 0.98% | 0.00106 | 0 / 0 |
| cls60-sd10-cv00 | TET | cgb vs ra | 18 | 16 / 0 / 2 | -0.91% | 0.0152 | 0 / 0 |
| cls60-sd10-cv00 | TAT | ra-cgb vs ra | 18 | 4 / 2 / 12 | 0.22% | 1 | 0 / 0 |
| cls60-sd10-cv00 | TET | ra-cgb vs ra | 18 | 10 / 2 / 6 | -0.19% | 1 | 0 / 0 |
| cls60-sd10-cv00 | TAT | cgr vs ra | 18 | 3 / 0 / 15 | 0.78% | 0.0618 | 0 / 0 |
| cls60-sd10-cv00 | TET | cgr vs ra | 18 | 15 / 0 / 3 | -1.30% | 0.0152 | 0 / 0 |
| cls60-sd10-cv00 | TAT | ra-cgr vs ra | 18 | 4 / 0 / 14 | 0.25% | 1 | 0 / 0 |
| cls60-sd10-cv00 | TET | ra-cgr vs ra | 18 | 17 / 0 / 1 | -0.53% | 0.0196 | 0 / 0 |
| cls60-sd10-cv00 | TAT | cgr vs cgb | 18 | 8 / 0 / 10 | 0.03% | 1 | 0 / 0 |
| cls60-sd10-cv00 | TET | cgr vs cgb | 18 | 10 / 0 / 8 | -0.33% | 1 | 0 / 0 |
| cls60-sd10-cv00 | TAT | ra-cgr vs ra-cgb | 18 | 10 / 0 / 8 | -0.11% | 1 | 0 / 0 |
| cls60-sd10-cv00 | TET | ra-cgr vs ra-cgb | 18 | 13 / 0 / 5 | -0.48% | 0.476 | 0 / 0 |
| cls60-sd10-cv20 | TAT | cgb vs ra | 18 | 0 / 0 / 18 | 17.15% | 0.00106 | 0 / 0 |
| cls60-sd10-cv20 | TET | cgb vs ra | 18 | 17 / 0 / 1 | -5.61% | 0.00431 | 0 / 0 |
| cls60-sd10-cv20 | TAT | ra-cgb vs ra | 18 | 3 / 3 / 12 | 0.20% | 0.329 | 0 / 0 |
| cls60-sd10-cv20 | TET | ra-cgb vs ra | 18 | 10 / 3 / 5 | -0.39% | 1 | 0 / 0 |
| cls60-sd10-cv20 | TAT | cgr vs ra | 18 | 0 / 0 / 18 | 16.89% | 0.00106 | 0 / 0 |
| cls60-sd10-cv20 | TET | cgr vs ra | 18 | 18 / 0 / 0 | -4.79% | 0.00106 | 0 / 0 |
| cls60-sd10-cv20 | TAT | ra-cgr vs ra | 18 | 4 / 0 / 14 | 2.71% | 0.414 | 0 / 0 |
| cls60-sd10-cv20 | TET | ra-cgr vs ra | 18 | 14 / 0 / 4 | -0.73% | 0.269 | 0 / 0 |
| cls60-sd10-cv20 | TAT | cgr vs cgb | 18 | 8 / 0 / 10 | 0.63% | 1 | 0 / 0 |
| cls60-sd10-cv20 | TET | cgr vs cgb | 18 | 9 / 0 / 9 | 0.17% | 1 | 0 / 0 |
| cls60-sd10-cv20 | TAT | ra-cgr vs ra-cgb | 18 | 9 / 0 / 9 | -0.04% | 1 | 0 / 0 |
| cls60-sd10-cv20 | TET | ra-cgr vs ra-cgb | 18 | 13 / 0 / 5 | -0.47% | 1 | 0 / 0 |
| cls60-sd20-cv00 | TAT | cgb vs ra | 18 | 3 / 0 / 15 | 0.75% | 0.0315 | 0 / 0 |
| cls60-sd20-cv00 | TET | cgb vs ra | 18 | 14 / 0 / 4 | -0.85% | 0.356 | 0 / 0 |
| cls60-sd20-cv00 | TAT | ra-cgb vs ra | 18 | 5 / 1 / 12 | 0.09% | 1 | 0 / 0 |
| cls60-sd20-cv00 | TET | ra-cgb vs ra | 18 | 11 / 1 / 6 | -0.84% | 1 | 0 / 0 |
| cls60-sd20-cv00 | TAT | cgr vs ra | 18 | 8 / 0 / 10 | 0.04% | 1 | 0 / 0 |
| cls60-sd20-cv00 | TET | cgr vs ra | 18 | 13 / 0 / 5 | -0.95% | 1 | 0 / 0 |
| cls60-sd20-cv00 | TAT | ra-cgr vs ra | 18 | 6 / 0 / 12 | 0.05% | 1 | 0 / 0 |
| cls60-sd20-cv00 | TET | ra-cgr vs ra | 18 | 14 / 0 / 4 | -1.21% | 0.139 | 0 / 0 |
| cls60-sd20-cv00 | TAT | cgr vs cgb | 18 | 8 / 2 / 8 | 0.00% | 1 | 0 / 0 |
| cls60-sd20-cv00 | TET | cgr vs cgb | 18 | 8 / 2 / 8 | 0.00% | 1 | 0 / 0 |
| cls60-sd20-cv00 | TAT | ra-cgr vs ra-cgb | 18 | 6 / 2 / 10 | 0.15% | 1 | 0 / 0 |
| cls60-sd20-cv00 | TET | ra-cgr vs ra-cgb | 18 | 9 / 2 / 7 | -0.03% | 1 | 0 / 0 |
| cls60-sd20-cv20 | TAT | cgb vs ra | 18 | 0 / 0 / 18 | 16.29% | 0.00106 | 0 / 0 |
| cls60-sd20-cv20 | TET | cgb vs ra | 18 | 18 / 0 / 0 | -5.72% | 0.00106 | 0 / 0 |
| cls60-sd20-cv20 | TAT | ra-cgb vs ra | 18 | 9 / 1 / 8 | -0.05% | 1 | 0 / 0 |
| cls60-sd20-cv20 | TET | ra-cgb vs ra | 18 | 16 / 1 / 1 | -1.11% | 0.00504 | 0 / 0 |
| cls60-sd20-cv20 | TAT | cgr vs ra | 18 | 0 / 0 / 18 | 13.30% | 0.00106 | 0 / 0 |
| cls60-sd20-cv20 | TET | cgr vs ra | 18 | 18 / 0 / 0 | -4.69% | 0.00106 | 0 / 0 |
| cls60-sd20-cv20 | TAT | ra-cgr vs ra | 18 | 7 / 0 / 11 | 0.86% | 1 | 0 / 0 |
| cls60-sd20-cv20 | TET | ra-cgr vs ra | 18 | 17 / 0 / 1 | -1.84% | 0.00261 | 0 / 0 |
| cls60-sd20-cv20 | TAT | cgr vs cgb | 18 | 11 / 2 / 5 | -1.68% | 1 | 0 / 0 |
| cls60-sd20-cv20 | TET | cgr vs cgb | 18 | 8 / 2 / 8 | 0.00% | 1 | 0 / 0 |
| cls60-sd20-cv20 | TAT | ra-cgr vs ra-cgb | 18 | 7 / 3 / 8 | 0.00% | 1 | 0 / 0 |
| cls60-sd20-cv20 | TET | ra-cgr vs ra-cgb | 18 | 8 / 3 / 7 | 0.00% | 1 | 0 / 0 |
| cls90-sd00-cv00 | TAT | cgb vs ra | 17 | 2 / 0 / 15 | 3.82% | 0.0209 | 0 / 0 |
| cls90-sd00-cv00 | TET | cgb vs ra | 17 | 10 / 0 / 7 | -0.21% | 1 | 0 / 0 |
| cls90-sd00-cv00 | TAT | ra-cgb vs ra | 17 | 0 / 17 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv00 | TET | ra-cgb vs ra | 17 | 0 / 17 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv00 | TAT | cgr vs ra | 17 | 2 / 0 / 15 | 3.82% | 0.0209 | 0 / 0 |
| cls90-sd00-cv00 | TET | cgr vs ra | 17 | 10 / 0 / 7 | -0.21% | 1 | 0 / 0 |
| cls90-sd00-cv00 | TAT | ra-cgr vs ra | 17 | 0 / 17 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv00 | TET | ra-cgr vs ra | 17 | 0 / 17 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv00 | TAT | cgr vs cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv00 | TET | cgr vs cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv00 | TAT | ra-cgr vs ra-cgb | 17 | 0 / 17 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv00 | TET | ra-cgr vs ra-cgb | 17 | 0 / 17 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv20 | TAT | cgb vs ra | 18 | 0 / 0 / 18 | 25.58% | 0.00106 | 0 / 0 |
| cls90-sd00-cv20 | TET | cgb vs ra | 18 | 16 / 0 / 2 | -2.32% | 0.00816 | 0 / 0 |
| cls90-sd00-cv20 | TAT | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv20 | TET | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv20 | TAT | cgr vs ra | 18 | 0 / 0 / 18 | 25.58% | 0.00106 | 0 / 0 |
| cls90-sd00-cv20 | TET | cgr vs ra | 18 | 16 / 0 / 2 | -2.32% | 0.00816 | 0 / 0 |
| cls90-sd00-cv20 | TAT | ra-cgr vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv20 | TET | ra-cgr vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv20 | TAT | cgr vs cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv20 | TET | cgr vs cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv20 | TAT | ra-cgr vs ra-cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd00-cv20 | TET | ra-cgr vs ra-cgb | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd10-cv00 | TAT | cgb vs ra | 18 | 1 / 0 / 17 | 2.55% | 0.0315 | 0 / 0 |
| cls90-sd10-cv00 | TET | cgb vs ra | 18 | 8 / 0 / 10 | 0.54% | 1 | 0 / 0 |
| cls90-sd10-cv00 | TAT | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd10-cv00 | TET | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd10-cv00 | TAT | cgr vs ra | 18 | 3 / 0 / 15 | 2.69% | 0.166 | 0 / 0 |
| cls90-sd10-cv00 | TET | cgr vs ra | 18 | 13 / 0 / 5 | -1.10% | 0.888 | 0 / 0 |
| cls90-sd10-cv00 | TAT | ra-cgr vs ra | 18 | 9 / 0 / 9 | 0.02% | 1 | 0 / 0 |
| cls90-sd10-cv00 | TET | ra-cgr vs ra | 18 | 15 / 0 / 3 | -0.61% | 0.0764 | 0 / 0 |
| cls90-sd10-cv00 | TAT | cgr vs cgb | 18 | 10 / 0 / 8 | -0.46% | 1 | 0 / 0 |
| cls90-sd10-cv00 | TET | cgr vs cgb | 18 | 14 / 0 / 4 | -0.76% | 0.546 | 0 / 0 |
| cls90-sd10-cv00 | TAT | ra-cgr vs ra-cgb | 18 | 9 / 0 / 9 | 0.02% | 1 | 0 / 0 |
| cls90-sd10-cv00 | TET | ra-cgr vs ra-cgb | 18 | 15 / 0 / 3 | -0.61% | 0.0764 | 0 / 0 |
| cls90-sd10-cv20 | TAT | cgb vs ra | 18 | 0 / 0 / 18 | 24.97% | 0.00106 | 0 / 0 |
| cls90-sd10-cv20 | TET | cgb vs ra | 18 | 17 / 0 / 1 | -1.76% | 0.00186 | 0 / 0 |
| cls90-sd10-cv20 | TAT | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd10-cv20 | TET | ra-cgb vs ra | 18 | 0 / 18 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd10-cv20 | TAT | cgr vs ra | 18 | 0 / 0 / 18 | 25.13% | 0.00106 | 0 / 0 |
| cls90-sd10-cv20 | TET | cgr vs ra | 18 | 17 / 0 / 1 | -2.10% | 0.00186 | 0 / 0 |
| cls90-sd10-cv20 | TAT | ra-cgr vs ra | 18 | 3 / 0 / 15 | 0.99% | 0.0196 | 0 / 0 |
| cls90-sd10-cv20 | TET | ra-cgr vs ra | 18 | 14 / 0 / 4 | -0.82% | 0.233 | 0 / 0 |
| cls90-sd10-cv20 | TAT | cgr vs cgb | 18 | 7 / 0 / 11 | 3.29% | 1 | 0 / 0 |
| cls90-sd10-cv20 | TET | cgr vs cgb | 18 | 10 / 0 / 8 | -0.44% | 1 | 0 / 0 |
| cls90-sd10-cv20 | TAT | ra-cgr vs ra-cgb | 18 | 3 / 0 / 15 | 0.99% | 0.0196 | 0 / 0 |
| cls90-sd10-cv20 | TET | ra-cgr vs ra-cgb | 18 | 14 / 0 / 4 | -0.82% | 0.233 | 0 / 0 |
| cls90-sd20-cv00 | TAT | cgb vs ra | 18 | 4 / 0 / 14 | 2.95% | 0.166 | 0 / 0 |
| cls90-sd20-cv00 | TET | cgb vs ra | 18 | 8 / 0 / 10 | 0.20% | 1 | 0 / 0 |
| cls90-sd20-cv00 | TAT | ra-cgb vs ra | 18 | 1 / 14 / 3 | 0.00% | - | 0 / 0 |
| cls90-sd20-cv00 | TET | ra-cgb vs ra | 18 | 1 / 14 / 3 | 0.00% | - | 0 / 0 |
| cls90-sd20-cv00 | TAT | cgr vs ra | 18 | 4 / 0 / 14 | 3.18% | 0.166 | 0 / 0 |
| cls90-sd20-cv00 | TET | cgr vs ra | 18 | 13 / 0 / 5 | -1.22% | 1 | 0 / 0 |
| cls90-sd20-cv00 | TAT | ra-cgr vs ra | 18 | 8 / 0 / 10 | 0.02% | 1 | 0 / 0 |
| cls90-sd20-cv00 | TET | ra-cgr vs ra | 18 | 16 / 0 / 2 | -1.37% | 0.0764 | 0 / 0 |
| cls90-sd20-cv00 | TAT | cgr vs cgb | 18 | 10 / 0 / 8 | -0.89% | 1 | 0 / 0 |
| cls90-sd20-cv00 | TET | cgr vs cgb | 18 | 14 / 0 / 4 | -1.84% | 0.546 | 0 / 0 |
| cls90-sd20-cv00 | TAT | ra-cgr vs ra-cgb | 18 | 8 / 0 / 10 | 0.02% | 1 | 0 / 0 |
| cls90-sd20-cv00 | TET | ra-cgr vs ra-cgb | 18 | 17 / 0 / 1 | -1.37% | 0.00186 | 0 / 0 |
| cls90-sd20-cv20 | TAT | cgb vs ra | 18 | 0 / 0 / 18 | 20.63% | 0.00106 | 0 / 0 |
| cls90-sd20-cv20 | TET | cgb vs ra | 18 | 16 / 0 / 2 | -1.54% | 0.0196 | 0 / 0 |
| cls90-sd20-cv20 | TAT | ra-cgb vs ra | 18 | 2 / 14 / 2 | 0.00% | - | 0 / 0 |
| cls90-sd20-cv20 | TET | ra-cgb vs ra | 18 | 4 / 14 / 0 | 0.00% | - | 0 / 0 |
| cls90-sd20-cv20 | TAT | cgr vs ra | 18 | 0 / 0 / 18 | 22.44% | 0.00106 | 0 / 0 |
| cls90-sd20-cv20 | TET | cgr vs ra | 18 | 17 / 0 / 1 | -2.59% | 0.00186 | 0 / 0 |
| cls90-sd20-cv20 | TAT | ra-cgr vs ra | 18 | 6 / 0 / 12 | 1.28% | 0.619 | 0 / 0 |
| cls90-sd20-cv20 | TET | ra-cgr vs ra | 18 | 14 / 0 / 4 | -1.32% | 0.233 | 0 / 0 |
| cls90-sd20-cv20 | TAT | cgr vs cgb | 18 | 7 / 0 / 11 | 3.41% | 1 | 0 / 0 |
| cls90-sd20-cv20 | TET | cgr vs cgb | 18 | 13 / 0 / 5 | -0.87% | 1 | 0 / 0 |
| cls90-sd20-cv20 | TAT | ra-cgr vs ra-cgb | 18 | 6 / 0 / 12 | 1.37% | 1 | 0 / 0 |
| cls90-sd20-cv20 | TET | ra-cgr vs ra-cgb | 18 | 14 / 0 / 4 | -1.32% | 0.312 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 12-14 tasks | TAT | ra-cgb vs ra | 24 | 3 / 14 / 7 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 12-14 tasks | TET | ra-cgb vs ra | 24 | 5 / 14 / 5 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 12-14 tasks | TAT | ra-cgr vs ra | 24 | 10 / 0 / 14 | 0.03% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 12-14 tasks | TET | ra-cgr vs ra | 24 | 18 / 0 / 6 | -0.49% | 0.139 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 15-17 tasks | TAT | ra-cgb vs ra | 24 | 4 / 11 / 9 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 15-17 tasks | TET | ra-cgb vs ra | 24 | 10 / 11 / 3 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 15-17 tasks | TAT | ra-cgr vs ra | 24 | 11 / 0 / 13 | 0.02% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 15-17 tasks | TET | ra-cgr vs ra | 24 | 20 / 0 / 4 | -0.79% | 0.046 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 18-20 tasks | TAT | ra-cgb vs ra | 24 | 3 / 10 / 11 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 18-20 tasks | TET | ra-cgb vs ra | 24 | 7 / 10 / 7 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 18-20 tasks | TAT | ra-cgr vs ra | 24 | 6 / 0 / 18 | 0.52% | 0.651 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, 18-20 tasks | TET | ra-cgr vs ra | 24 | 24 / 0 / 0 | -1.30% | 1.69e-05 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, multiple of 4 tasks | TAT | ra-cgb vs ra | 24 | 2 / 13 / 9 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, multiple of 4 tasks | TET | ra-cgb vs ra | 24 | 5 / 13 / 6 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, multiple of 4 tasks | TAT | ra-cgr vs ra | 24 | 9 / 0 / 15 | 0.16% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, multiple of 4 tasks | TET | ra-cgr vs ra | 24 | 19 / 0 / 5 | -0.46% | 0.277 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, not a multiple of 4 tasks | TAT | ra-cgb vs ra | 48 | 8 / 22 / 18 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, not a multiple of 4 tasks | TET | ra-cgb vs ra | 48 | 17 / 22 / 9 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, not a multiple of 4 tasks | TAT | ra-cgr vs ra | 48 | 18 / 0 / 30 | 0.10% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.0, not a multiple of 4 tasks | TET | ra-cgr vs ra | 48 | 43 / 0 / 5 | -1.30% | 2.52e-08 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 12-14 tasks | TAT | ra-cgb vs ra | 24 | 6 / 14 / 4 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 12-14 tasks | TET | ra-cgb vs ra | 24 | 9 / 14 / 1 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 12-14 tasks | TAT | ra-cgr vs ra | 24 | 10 / 0 / 14 | 0.13% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 12-14 tasks | TET | ra-cgr vs ra | 24 | 20 / 0 / 4 | -1.00% | 0.00696 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 15-17 tasks | TAT | ra-cgb vs ra | 24 | 5 / 11 / 8 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 15-17 tasks | TET | ra-cgb vs ra | 24 | 10 / 11 / 3 | 0.00% | 0.886 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 15-17 tasks | TAT | ra-cgr vs ra | 24 | 9 / 0 / 15 | 0.67% | 0.845 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 15-17 tasks | TET | ra-cgr vs ra | 24 | 17 / 0 / 7 | -0.38% | 0.476 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 18-20 tasks | TAT | ra-cgb vs ra | 24 | 3 / 11 / 10 | 0.00% | 0.353 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 18-20 tasks | TET | ra-cgb vs ra | 24 | 11 / 11 / 2 | 0.00% | 0.886 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 18-20 tasks | TAT | ra-cgr vs ra | 24 | 1 / 0 / 23 | 5.75% | 5.04e-05 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, 18-20 tasks | TET | ra-cgr vs ra | 24 | 22 / 0 / 2 | -1.69% | 0.000417 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, multiple of 4 tasks | TAT | ra-cgb vs ra | 24 | 4 / 13 / 7 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, multiple of 4 tasks | TET | ra-cgb vs ra | 24 | 8 / 13 / 3 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, multiple of 4 tasks | TAT | ra-cgr vs ra | 24 | 5 / 0 / 19 | 0.99% | 0.0203 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, multiple of 4 tasks | TET | ra-cgr vs ra | 24 | 19 / 0 / 5 | -0.51% | 0.035 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, not a multiple of 4 tasks | TAT | ra-cgb vs ra | 48 | 10 / 23 / 15 | 0.00% | 1 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, not a multiple of 4 tasks | TET | ra-cgb vs ra | 48 | 22 / 23 / 3 | 0.00% | 0.0081 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, not a multiple of 4 tasks | TAT | ra-cgr vs ra | 48 | 15 / 0 / 33 | 1.50% | 0.00172 | 0 / 0 |
| CLS 0.6-0.9 with spread, CV 0.2, not a multiple of 4 tasks | TET | ra-cgr vs ra | 48 | 40 / 0 / 8 | -1.56% | 1.21e-06 | 0 / 0 |

## G and C2 against the best Partitioned placement

| CLS mean | cases | G ok / ok without any P / beats best P (TAT, TET) / median TAT gap | C2 likewise |
|---|---:|---|---|
| 0.3 | 108 | 4 / 0 / 4, 0 / -16.90% | 7 / 0 / 2, 3 / 0.37% |
| 0.6 | 108 | 107 / 0 / 3, 40 / 4.37% | 108 / 0 / 2, 31 / 3.20% |
| 0.9 | 108 | 108 / 0 / 4, 27 / 7.37% | 107 / 0 / 0, 23 / 8.67% |

## Placement selector (TAT labels)

229 cases; labels {'wfd': 11, 'cgb': 1, 'ra': 151, 'ra-cgb': 17, 'cgr': 13, 'ra-cgr': 36}; near-ties 200

### set-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 12.75% | 38.17% | 77.58% | 4.80% |
| always cgb | 12.85% | 38.28% | 77.58% | 0.44% |
| always ra | 0.34% | 2.40% | 5.84% | 65.94% |
| always ra-cgb | 0.65% | 3.23% | 9.05% | 7.42% |
| always cgr | 12.46% | 35.33% | 73.20% | 5.68% |
| always ra-cgr | 1.41% | 8.32% | 15.18% | 15.72% |
| fixed (train) | 0.34% | 2.40% | 5.84% | 65.94% |
| R0 / classifier | 0.61% | 2.90% | 22.14% | 62.36% |
| R0 / regressor | 0.52% | 2.77% | 14.72% | 59.30% |
| R0-CLP / classifier | 0.53% | 3.03% | 13.58% | 62.01% |
| R0-CLP / regressor | 0.41% | 2.71% | 10.44% | 57.90% |
| R1 / classifier | 0.49% | 2.90% | 9.05% | 62.18% |
| R1 / regressor | 0.44% | 2.61% | 9.04% | 55.90% |
| R2 / classifier | 0.48% | 2.91% | 10.25% | 62.36% |
| R2 / regressor | 0.58% | 3.19% | 11.34% | 55.11% |
| R3 / classifier | 0.52% | 2.99% | 9.74% | 62.01% |
| R3 / regressor | 0.60% | 3.30% | 12.32% | 53.36% |
| R4 / classifier | 0.53% | 2.93% | 11.81% | 62.62% |
| R4 / regressor | 0.60% | 3.13% | 12.50% | 54.32% |

### condition-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 12.75% | 38.17% | 77.58% | 4.80% |
| always cgb | 12.85% | 38.28% | 77.58% | 0.44% |
| always ra | 0.34% | 2.40% | 5.84% | 65.94% |
| always ra-cgb | 0.65% | 3.23% | 9.05% | 7.42% |
| always cgr | 12.46% | 35.33% | 73.20% | 5.68% |
| always ra-cgr | 1.41% | 8.32% | 15.18% | 15.72% |
| fixed (train) | 0.34% | 2.40% | 5.84% | 65.94% |
| R0 / classifier | 1.90% | 14.12% | 35.39% | 55.81% |
| R0 / regressor | 0.67% | 2.97% | 29.90% | 53.97% |
| R0-CLP / classifier | 1.95% | 14.32% | 34.38% | 55.55% |
| R0-CLP / regressor | 0.61% | 2.86% | 29.90% | 54.50% |
| R1 / classifier | 0.97% | 3.29% | 34.38% | 62.01% |
| R1 / regressor | 0.36% | 2.42% | 5.96% | 52.23% |
| R2 / classifier | 1.11% | 3.84% | 35.39% | 59.65% |
| R2 / regressor | 0.36% | 2.58% | 5.84% | 58.52% |
| R3 / classifier | 0.86% | 2.98% | 34.63% | 62.88% |
| R3 / regressor | 0.42% | 2.69% | 7.61% | 51.70% |
| R4 / classifier | 1.07% | 3.32% | 35.39% | 61.75% |
| R4 / regressor | 0.35% | 2.51% | 5.84% | 58.08% |


## Placement selector (TET labels)

229 cases; labels {'wfd': 90, 'cgb': 28, 'ra': 17, 'ra-cgb': 6, 'cgr': 54, 'ra-cgr': 34}; near-ties 165

### set-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 1.38% | 5.06% | 9.46% | 39.30% |
| always cgb | 1.23% | 4.46% | 13.62% | 12.23% |
| always ra | 3.64% | 10.03% | 19.85% | 7.42% |
| always ra-cgb | 3.33% | 10.02% | 18.91% | 2.62% |
| always cgr | 1.02% | 4.71% | 14.87% | 23.58% |
| always ra-cgr | 2.64% | 10.01% | 18.55% | 14.85% |
| fixed (train) | 1.26% | 4.54% | 12.15% | 31.88% |
| R0 / classifier | 1.26% | 5.62% | 14.23% | 44.10% |
| R0 / regressor | 1.11% | 4.38% | 14.08% | 26.11% |
| R0-CLP / classifier | 1.31% | 5.51% | 14.87% | 44.45% |
| R0-CLP / regressor | 1.11% | 4.43% | 14.87% | 24.63% |
| R1 / classifier | 1.02% | 4.27% | 12.97% | 46.03% |
| R1 / regressor | 0.93% | 3.96% | 9.77% | 26.90% |
| R2 / classifier | 1.10% | 4.38% | 12.97% | 45.94% |
| R2 / regressor | 0.94% | 3.89% | 12.13% | 26.46% |
| R3 / classifier | 1.12% | 4.64% | 13.60% | 46.38% |
| R3 / regressor | 0.99% | 4.37% | 11.64% | 27.77% |
| R4 / classifier | 1.12% | 4.41% | 13.60% | 47.25% |
| R4 / regressor | 0.94% | 3.95% | 12.10% | 27.16% |

### condition-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 1.38% | 5.06% | 9.46% | 39.30% |
| always cgb | 1.23% | 4.46% | 13.62% | 12.23% |
| always ra | 3.64% | 10.03% | 19.85% | 7.42% |
| always ra-cgb | 3.33% | 10.02% | 18.91% | 2.62% |
| always cgr | 1.02% | 4.71% | 14.87% | 23.58% |
| always ra-cgr | 2.64% | 10.01% | 18.55% | 14.85% |
| fixed (train) | 1.41% | 5.15% | 9.46% | 39.30% |
| R0 / classifier | 1.34% | 5.46% | 14.87% | 45.07% |
| R0 / regressor | 0.91% | 4.46% | 10.09% | 28.73% |
| R0-CLP / classifier | 1.45% | 6.05% | 14.87% | 42.88% |
| R0-CLP / regressor | 0.99% | 4.87% | 11.92% | 28.73% |
| R1 / classifier | 0.90% | 4.22% | 14.62% | 50.48% |
| R1 / regressor | 0.71% | 3.83% | 11.44% | 33.28% |
| R2 / classifier | 1.11% | 4.66% | 14.87% | 44.02% |
| R2 / regressor | 0.73% | 3.65% | 12.75% | 30.31% |
| R3 / classifier | 0.93% | 4.53% | 14.87% | 51.18% |
| R3 / regressor | 0.84% | 4.15% | 12.88% | 28.65% |
| R4 / classifier | 1.06% | 4.63% | 14.87% | 46.29% |
| R4 / regressor | 0.77% | 4.10% | 11.89% | 30.04% |

