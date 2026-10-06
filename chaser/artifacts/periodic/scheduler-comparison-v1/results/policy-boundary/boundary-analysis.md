# Policy-boundary analysis

Regret: a placement value / the best placement of the same case - 1, over runs that met every deadline.

## TAT per cell

| cell | cases | wfd median / regret / wins | cgb median / regret / wins | ra median / regret / wins | ra-cgb median / regret / wins | deadline misses |
|---|---:|---|---|---|---|---|
| cv00-low0-big0 | 10 | 230.4 / 2.14% / 3 | 230.4 / 2.14% / 3 | 225.6 / 0.16% / 7 | 225.6 / 0.16% / 7 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv00-low0-big2 | 10 | 257.2 / 1.46% / 5 | 253.6 / 1.66% / 2 | 255.8 / 1.19% / 3 | 259.5 / 2.88% / 1 | wfd 1, cgb 0, ra 0, ra-cgb 0 |
| cv00-low4-big0 | 10 | 282.3 / 0.92% / 3 | 286.8 / 1.69% / 3 | 296.6 / 2.38% / 2 | 286.6 / 1.42% / 3 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv00-low4-big2 | 10 | 323.5 / 0.70% / 6 | 323.1 / 1.69% / 3 | 333.5 / 2.36% / 0 | 322.4 / 1.30% / 2 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv00-low8-big0 | 10 | 363.4 / 1.76% / 2 | 356.5 / 1.15% / 4 | 364.8 / 3.21% / 0 | 357.6 / 0.39% / 5 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv00-low8-big2 | 10 | 404.2 / 1.04% / 4 | 404.9 / 0.52% / 4 | 407.5 / 1.95% / 0 | 406.6 / 0.70% / 2 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low0-big0 | 10 | 320.3 / 20.54% / 0 | 320.3 / 20.54% / 0 | 265.9 / 0.00% / 10 | 265.9 / 0.00% / 10 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low0-big2 | 10 | 339.6 / 18.45% / 0 | 345.0 / 18.27% / 0 | 292.2 / 0.09% / 7 | 297.2 / 2.42% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low4-big0 | 10 | 377.6 / 16.05% / 1 | 381.0 / 15.57% / 0 | 336.7 / 0.97% / 6 | 348.1 / 3.29% / 3 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low4-big2 | 10 | 415.6 / 12.93% / 2 | 419.5 / 11.56% / 1 | 389.9 / 1.53% / 3 | 381.6 / 1.96% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low8-big0 | 10 | 478.7 / 14.55% / 0 | 448.9 / 10.13% / 0 | 434.2 / 1.63% / 4 | 429.4 / 1.13% / 6 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low8-big2 | 10 | 545.7 / 14.41% / 0 | 549.1 / 12.61% / 1 | 494.5 / 1.50% / 6 | 491.9 / 1.63% / 3 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low0-big0 | 10 | 351.5 / 20.69% / 1 | 351.5 / 20.69% / 1 | 294.5 / 0.00% / 9 | 294.5 / 0.00% / 9 | wfd 0, cgb 0, ra 1, ra-cgb 1 |
| cv20-low0-big2 | 10 | 377.9 / 20.49% / 0 | 364.3 / 19.29% / 0 | 318.6 / 0.89% / 4 | 318.2 / 1.42% / 6 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low4-big0 | 10 | 415.5 / 19.02% / 0 | 411.7 / 16.54% / 0 | 356.3 / 0.98% / 7 | 368.5 / 3.10% / 3 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low4-big2 | 10 | 465.3 / 16.82% / 0 | 435.2 / 12.62% / 0 | 402.7 / 1.38% / 5 | 411.4 / 2.47% / 5 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low8-big0 | 10 | 522.5 / 13.80% / 0 | 525.7 / 13.24% / 0 | 473.7 / 1.63% / 4 | 473.5 / 1.29% / 6 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low8-big2 | 10 | 633.6 / 11.82% / 0 | 586.5 / 10.04% / 0 | 553.2 / 1.66% / 6 | 552.8 / 3.12% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low0-big0 | 10 | 353.4 / 21.48% / 0 | 353.4 / 21.48% / 0 | 299.7 / 0.00% / 10 | 299.7 / 0.00% / 10 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low0-big2 | 10 | 385.3 / 18.87% / 0 | 389.9 / 19.54% / 0 | 324.0 / 0.48% / 6 | 329.4 / 0.95% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low4-big0 | 10 | 417.7 / 16.00% / 0 | 427.8 / 16.24% / 0 | 369.4 / 0.96% / 6 | 378.8 / 3.93% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low4-big2 | 10 | 471.5 / 14.64% / 0 | 472.8 / 13.33% / 0 | 425.8 / 1.31% / 5 | 428.8 / 2.36% / 5 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low8-big0 | 10 | 535.9 / 11.21% / 0 | 557.7 / 14.17% / 0 | 492.6 / 1.75% / 7 | 487.8 / 1.95% / 3 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low8-big2 | 10 | 656.9 / 8.51% / 0 | 645.7 / 8.53% / 0 | 593.1 / 1.15% / 5 | 613.1 / 3.37% / 5 | wfd 0, cgb 0, ra 0, ra-cgb 0 |

Fixed placements over all cases (TAT): wfd 12.48%, cgb 11.80%, ra 1.22%, ra-cgb 1.73%

## TET per cell

| cell | cases | wfd median / regret / wins | cgb median / regret / wins | ra median / regret / wins | ra-cgb median / regret / wins | deadline misses |
|---|---:|---|---|---|---|---|
| cv00-low0-big0 | 10 | 890.4 / 1.10% / 6 | 890.4 / 1.10% / 6 | 886.4 / 0.74% / 4 | 886.4 / 0.74% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv00-low0-big2 | 10 | 982.4 / 1.73% / 2 | 972.9 / 0.82% / 5 | 973.3 / 1.47% / 2 | 976.4 / 1.21% / 2 | wfd 1, cgb 0, ra 0, ra-cgb 0 |
| cv00-low4-big0 | 10 | 1068.1 / 3.17% / 0 | 1051.2 / 1.01% / 3 | 1123.7 / 5.38% / 0 | 1040.0 / 0.13% / 9 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv00-low4-big2 | 10 | 1229.2 / 5.74% / 0 | 1179.2 / 0.60% / 6 | 1239.3 / 6.74% / 0 | 1166.6 / 0.63% / 5 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv00-low8-big0 | 10 | 1349.6 / 5.68% / 1 | 1281.0 / 1.32% / 2 | 1399.7 / 8.45% / 0 | 1274.9 / 0.16% / 8 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv00-low8-big2 | 10 | 1546.0 / 5.27% / 0 | 1477.6 / 0.41% / 6 | 1550.5 / 5.96% / 0 | 1476.5 / 0.62% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low0-big0 | 10 | 865.5 / 0.04% / 9 | 865.5 / 0.04% / 9 | 882.2 / 1.97% / 1 | 882.2 / 1.97% / 1 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low0-big2 | 10 | 942.2 / 0.40% / 6 | 938.5 / 0.78% / 4 | 951.4 / 2.96% / 0 | 945.7 / 1.71% / 1 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low4-big0 | 10 | 1038.9 / 3.47% / 1 | 1007.3 / 0.41% / 6 | 1068.3 / 6.07% / 0 | 1016.3 / 1.40% / 3 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low4-big2 | 10 | 1160.9 / 4.82% / 2 | 1138.8 / 1.04% / 7 | 1201.7 / 8.52% / 0 | 1156.3 / 3.19% / 1 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low8-big0 | 10 | 1305.7 / 4.98% / 0 | 1263.2 / 1.81% / 4 | 1330.0 / 7.96% / 0 | 1232.6 / 1.65% / 6 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv10-low8-big2 | 10 | 1458.7 / 4.80% / 1 | 1402.4 / 1.23% / 3 | 1522.2 / 7.76% / 1 | 1436.4 / 2.39% / 5 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low0-big0 | 10 | 856.0 / 0.01% / 9 | 856.0 / 0.01% / 9 | 878.8 / 2.47% / 1 | 878.8 / 2.47% / 1 | wfd 0, cgb 0, ra 1, ra-cgb 1 |
| cv20-low0-big2 | 10 | 913.2 / 0.57% / 6 | 915.0 / 0.56% / 4 | 951.8 / 4.12% / 0 | 944.3 / 3.31% / 1 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low4-big0 | 10 | 1012.0 / 3.51% / 1 | 983.3 / 0.46% / 7 | 1021.9 / 6.45% / 0 | 987.5 / 2.12% / 2 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low4-big2 | 10 | 1086.4 / 3.82% / 2 | 1065.0 / 1.01% / 6 | 1139.4 / 8.04% / 0 | 1105.5 / 3.44% / 2 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low8-big0 | 10 | 1247.9 / 5.20% / 2 | 1176.3 / 1.30% / 4 | 1330.3 / 12.15% / 0 | 1230.6 / 3.98% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv20-low8-big2 | 10 | 1363.2 / 5.45% / 1 | 1360.1 / 1.61% / 5 | 1449.6 / 10.92% / 0 | 1367.8 / 3.50% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low0-big0 | 10 | 852.0 / 0.00% / 10 | 852.0 / 0.00% / 10 | 866.1 / 1.80% / 0 | 866.1 / 1.80% / 0 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low0-big2 | 10 | 911.9 / 1.10% / 4 | 907.3 / 0.48% / 5 | 936.2 / 4.47% / 0 | 932.7 / 3.08% / 1 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low4-big0 | 10 | 988.9 / 3.38% / 1 | 962.1 / 0.45% / 7 | 1023.3 / 8.03% / 0 | 987.9 / 2.64% / 2 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low4-big2 | 10 | 1109.1 / 4.28% / 1 | 1060.7 / 0.57% / 6 | 1159.9 / 9.33% / 0 | 1092.0 / 2.46% / 3 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low8-big0 | 10 | 1235.1 / 6.90% / 0 | 1171.0 / 0.77% / 6 | 1282.9 / 11.54% / 0 | 1210.3 / 3.87% / 4 | wfd 0, cgb 0, ra 0, ra-cgb 0 |
| cv30-low8-big2 | 10 | 1421.9 / 5.16% / 2 | 1356.5 / 1.05% / 6 | 1448.1 / 8.58% / 0 | 1381.0 / 3.18% / 2 | wfd 0, cgb 0, ra 0, ra-cgb 0 |

Fixed placements over all cases (TET): wfd 3.36%, cgb 0.79%, ra 6.34%, ra-cgb 2.15%

## Hypothesis tests

| test | metric | pair | n | better / tie / worse | median | mean | Holm p |
|---|---|---|---:|---|---:|---:|---:|
| H1 period CV <= 0.1 with memory-bound tasks | TAT | cgb vs ra | 100 | 38 / 0 / 62 | 2.38% | 5.80% | 1.91e-05 |
| H2 period CV >= 0.2 without memory-bound tasks | TAT | ra vs wfd | 19 | 19 / 0 / 0 | -18.27% | -17.66% | 1.91e-05 |
| H3 combined against each placement | TAT | ra-cgb vs wfd | 238 | 201 / 0 / 37 | -8.64% | -8.90% | 2.03e-32 |
| H3 combined against each placement | TAT | ra-cgb vs cgb | 239 | 200 / 4 / 35 | -7.47% | -8.37% | 1.23e-31 |
| H3 combined against each placement | TAT | ra-cgb vs ra | 239 | 98 / 40 / 101 | 0.00% | 0.54% | 0.278 |
| H1 period CV <= 0.1 with memory-bound tasks | TET | cgb vs ra | 100 | 92 / 0 / 8 | -4.44% | -4.76% | 5.14e-16 |
| H2 period CV >= 0.2 without memory-bound tasks | TET | ra vs wfd | 19 | 1 / 0 / 18 | 1.78% | 2.11% | 2.29e-05 |
| H3 combined against each placement | TET | ra-cgb vs wfd | 238 | 135 / 0 / 103 | -0.76% | -1.08% | 0.000397 |
| H3 combined against each placement | TET | ra-cgb vs cgb | 239 | 77 / 4 / 158 | 1.08% | 1.38% | 4e-09 |
| H3 combined against each placement | TET | ra-cgb vs ra | 239 | 177 / 40 / 22 | -3.57% | -3.81% | 1.43e-30 |

## Placement selector (TAT labels)

240 cases; labels {'wfd': 27, 'cgb': 17, 'ra': 122, 'ra-cgb': 74}; near-ties 111

### set-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 12.48% | 32.12% | 44.26% | 11.25% |
| always cgb | 11.80% | 31.15% | 44.26% | 7.08% |
| always ra | 1.22% | 5.11% | 9.25% | 50.83% |
| always ra-cgb | 1.73% | 7.80% | 18.54% | 30.83% |
| fixed (train) | 1.22% | 5.11% | 9.25% | 50.83% |
| R0 / classifier | 2.30% | 8.56% | 39.79% | 45.92% |
| R0 / weighted | 1.94% | 7.31% | 40.36% | 44.83% |
| R0 / regressor | 1.74% | 6.22% | 39.66% | 46.33% |
| R0-CLP / classifier | 1.83% | 6.81% | 37.52% | 47.42% |
| R0-CLP / weighted | 1.66% | 6.47% | 31.12% | 44.17% |
| R0-CLP / regressor | 1.24% | 5.59% | 11.24% | 49.00% |
| R1 / classifier | 1.31% | 6.09% | 11.24% | 51.83% |
| R1 / weighted | 1.53% | 6.59% | 11.54% | 44.17% |
| R1 / regressor | 1.75% | 6.88% | 39.66% | 48.08% |
| R2 / classifier | 1.29% | 6.07% | 10.85% | 51.58% |
| R2 / weighted | 1.44% | 6.37% | 13.05% | 44.33% |
| R2 / regressor | 1.66% | 6.31% | 39.66% | 48.83% |
| R3 / classifier | 1.35% | 6.88% | 11.24% | 51.92% |
| R3 / weighted | 1.44% | 6.52% | 11.10% | 45.08% |
| R3 / regressor | 1.70% | 7.10% | 40.07% | 49.08% |
| R4 / classifier | 1.35% | 6.46% | 10.85% | 50.08% |
| R4 / weighted | 1.46% | 6.87% | 11.14% | 44.08% |
| R4 / regressor | 1.61% | 6.36% | 39.66% | 48.17% |

### condition-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 12.48% | 32.12% | 44.26% | 11.25% |
| always cgb | 11.80% | 31.15% | 44.26% | 7.08% |
| always ra | 1.22% | 5.11% | 9.25% | 50.83% |
| always ra-cgb | 1.73% | 7.80% | 18.54% | 30.83% |
| fixed (train) | 1.22% | 5.11% | 9.25% | 50.83% |
| R0 / classifier | 1.69% | 7.93% | 34.16% | 51.17% |
| R0 / weighted | 1.50% | 6.69% | 34.16% | 49.83% |
| R0 / regressor | 0.89% | 4.62% | 16.45% | 54.92% |
| R0-CLP / classifier | 1.64% | 7.60% | 25.14% | 49.08% |
| R0-CLP / weighted | 1.41% | 6.94% | 23.17% | 47.33% |
| R0-CLP / regressor | 1.19% | 5.55% | 16.45% | 50.58% |
| R1 / classifier | 0.66% | 3.37% | 8.93% | 62.58% |
| R1 / weighted | 0.74% | 3.68% | 8.81% | 55.33% |
| R1 / regressor | 0.66% | 3.28% | 16.45% | 59.67% |
| R2 / classifier | 0.72% | 3.61% | 9.05% | 61.42% |
| R2 / weighted | 0.75% | 3.80% | 11.25% | 55.58% |
| R2 / regressor | 0.80% | 3.76% | 16.45% | 58.08% |
| R3 / classifier | 0.75% | 3.72% | 9.30% | 61.17% |
| R3 / weighted | 0.80% | 3.72% | 13.49% | 55.17% |
| R3 / regressor | 0.73% | 3.43% | 16.45% | 58.75% |
| R4 / classifier | 0.80% | 3.83% | 11.30% | 60.08% |
| R4 / weighted | 0.77% | 3.77% | 9.05% | 54.92% |
| R4 / regressor | 0.87% | 4.28% | 16.45% | 58.00% |


## Placement selector (TET labels)

240 cases; labels {'wfd': 67, 'cgb': 99, 'ra': 9, 'ra-cgb': 65}; near-ties 115

### set-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 3.36% | 10.03% | 14.12% | 27.92% |
| always cgb | 0.79% | 3.60% | 9.01% | 41.25% |
| always ra | 6.34% | 13.52% | 24.08% | 3.75% |
| always ra-cgb | 2.15% | 7.37% | 13.57% | 27.08% |
| fixed (train) | 0.79% | 3.60% | 9.01% | 41.25% |
| R0 / classifier | 1.16% | 5.28% | 10.49% | 51.50% |
| R0 / weighted | 1.27% | 5.93% | 11.22% | 38.58% |
| R0 / regressor | 0.83% | 3.69% | 9.01% | 42.08% |
| R0-CLP / classifier | 1.26% | 6.04% | 11.58% | 53.00% |
| R0-CLP / weighted | 1.30% | 6.21% | 11.86% | 42.42% |
| R0-CLP / regressor | 0.91% | 3.83% | 9.19% | 42.33% |
| R1 / classifier | 1.06% | 5.00% | 11.69% | 52.92% |
| R1 / weighted | 1.01% | 4.55% | 12.66% | 42.67% |
| R1 / regressor | 0.83% | 3.69% | 9.58% | 43.42% |
| R2 / classifier | 1.08% | 5.80% | 10.92% | 53.08% |
| R2 / weighted | 0.97% | 4.75% | 10.69% | 51.58% |
| R2 / regressor | 0.81% | 3.65% | 9.01% | 45.33% |
| R3 / classifier | 1.03% | 5.18% | 11.25% | 55.67% |
| R3 / weighted | 1.07% | 5.32% | 11.31% | 45.67% |
| R3 / regressor | 0.81% | 3.71% | 9.01% | 45.75% |
| R4 / classifier | 1.05% | 5.34% | 10.62% | 54.08% |
| R4 / weighted | 1.04% | 5.56% | 11.53% | 52.17% |
| R4 / regressor | 0.84% | 3.72% | 9.01% | 45.42% |

### condition-level cross-validation

| method | mean regret | p95 | max | accuracy |
|---|---:|---:|---:|---:|
| oracle | 0.00% | 0.00% | 0.00% | 100.00% |
| always wfd | 3.36% | 10.03% | 14.12% | 27.92% |
| always cgb | 0.79% | 3.60% | 9.01% | 41.25% |
| always ra | 6.34% | 13.52% | 24.08% | 3.75% |
| always ra-cgb | 2.15% | 7.37% | 13.57% | 27.08% |
| fixed (train) | 0.79% | 3.60% | 9.01% | 41.25% |
| R0 / classifier | 1.00% | 4.39% | 8.91% | 52.50% |
| R0 / weighted | 1.00% | 4.38% | 8.91% | 42.50% |
| R0 / regressor | 0.72% | 3.31% | 7.21% | 50.25% |
| R0-CLP / classifier | 0.95% | 4.24% | 9.80% | 54.75% |
| R0-CLP / weighted | 0.94% | 4.30% | 7.77% | 45.83% |
| R0-CLP / regressor | 0.75% | 3.40% | 7.21% | 48.33% |
| R1 / classifier | 0.80% | 3.59% | 8.45% | 56.50% |
| R1 / weighted | 0.85% | 3.77% | 7.86% | 44.58% |
| R1 / regressor | 0.68% | 3.31% | 7.21% | 49.58% |
| R2 / classifier | 0.75% | 3.54% | 7.21% | 58.08% |
| R2 / weighted | 0.74% | 3.58% | 7.21% | 54.33% |
| R2 / regressor | 0.71% | 3.35% | 7.21% | 48.92% |
| R3 / classifier | 0.76% | 3.61% | 7.79% | 59.42% |
| R3 / weighted | 0.77% | 3.63% | 7.32% | 49.67% |
| R3 / regressor | 0.67% | 3.29% | 7.21% | 50.42% |
| R4 / classifier | 0.72% | 3.39% | 7.21% | 59.08% |
| R4 / weighted | 0.68% | 3.33% | 7.26% | 55.75% |
| R4 / regressor | 0.72% | 3.29% | 7.21% | 49.25% |

