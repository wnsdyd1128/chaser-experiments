# Experiments 1-2 with 12-20 tasks: task-count view

Gap (X_a - X_b) / X_b per set, averaged over the five means; negative = first is shorter.

| metric | pair | CV | scope | n | median | better / worse | Holm p |
|---|---|---:|---|---:|---:|---|---:|
| TAT | G vs snake P | 0.0 | all | 9 | +0.22% | 0 / 9 | 0.582 |
| TAT | G vs snake P | 0.0 | 12-14 | 3 | +0.20% | 0 / 3 | - |
| TAT | G vs snake P | 0.0 | 15-17 | 3 | +0.24% | 0 / 3 | - |
| TAT | G vs snake P | 0.0 | 18-20 | 3 | +0.22% | 0 / 3 | - |
| TAT | G vs snake P | 0.0 | multiple of 4 | 3 | +0.24% | 0 / 3 | - |
| TAT | G vs snake P | 0.0 | not a multiple of 4 | 6 | +0.21% | 0 / 6 | 1 |
| TAT | G vs snake P | 0.1 | all | 18 | -4.09% | 14 / 4 | 0.427 |
| TAT | G vs snake P | 0.1 | 12-14 | 6 | -2.08% | 4 / 2 | 1 |
| TAT | G vs snake P | 0.1 | 15-17 | 6 | -8.47% | 5 / 1 | 1 |
| TAT | G vs snake P | 0.1 | 18-20 | 6 | -2.75% | 5 / 1 | 1 |
| TAT | G vs snake P | 0.1 | multiple of 4 | 6 | +0.09% | 3 / 3 | 1 |
| TAT | G vs snake P | 0.1 | not a multiple of 4 | 12 | -8.47% | 11 / 1 | 0.516 |
| TAT | G vs snake P | 0.2 | all | 18 | -14.44% | 17 / 1 | 0.00403 |
| TAT | G vs snake P | 0.2 | 12-14 | 6 | -20.36% | 6 / 0 | 1 |
| TAT | G vs snake P | 0.2 | 15-17 | 6 | -9.04% | 5 / 1 | 1 |
| TAT | G vs snake P | 0.2 | 18-20 | 6 | -12.99% | 6 / 0 | 1 |
| TAT | G vs snake P | 0.2 | multiple of 4 | 6 | -10.48% | 6 / 0 | 1 |
| TAT | G vs snake P | 0.2 | not a multiple of 4 | 12 | -15.27% | 11 / 1 | 0.152 |
| TAT | G vs snake P | 0.3 | all | 18 | -19.89% | 18 / 0 | 0.00146 |
| TAT | G vs snake P | 0.3 | 12-14 | 6 | -24.18% | 6 / 0 | 1 |
| TAT | G vs snake P | 0.3 | 15-17 | 6 | -15.89% | 6 / 0 | 1 |
| TAT | G vs snake P | 0.3 | 18-20 | 6 | -15.78% | 6 / 0 | 1 |
| TAT | G vs snake P | 0.3 | multiple of 4 | 6 | -13.21% | 6 / 0 | 1 |
| TAT | G vs snake P | 0.3 | not a multiple of 4 | 12 | -20.32% | 12 / 0 | 0.084 |
| TAT | C (1+3) vs snake P | 0.0 | all | 9 | +0.05% | 1 / 8 | 1 |
| TAT | C (1+3) vs snake P | 0.0 | 12-14 | 3 | +0.08% | 0 / 3 | - |
| TAT | C (1+3) vs snake P | 0.0 | 15-17 | 3 | +0.05% | 1 / 2 | - |
| TAT | C (1+3) vs snake P | 0.0 | 18-20 | 3 | +0.02% | 0 / 3 | - |
| TAT | C (1+3) vs snake P | 0.0 | multiple of 4 | 3 | +0.05% | 0 / 3 | - |
| TAT | C (1+3) vs snake P | 0.0 | not a multiple of 4 | 6 | +0.05% | 1 / 5 | 1 |
| TAT | C (1+3) vs snake P | 0.1 | all | 18 | +0.11% | 7 / 11 | 1 |
| TAT | C (1+3) vs snake P | 0.1 | 12-14 | 6 | +0.11% | 2 / 4 | 1 |
| TAT | C (1+3) vs snake P | 0.1 | 15-17 | 6 | +0.13% | 2 / 4 | 1 |
| TAT | C (1+3) vs snake P | 0.1 | 18-20 | 6 | -0.03% | 3 / 3 | 1 |
| TAT | C (1+3) vs snake P | 0.1 | multiple of 4 | 6 | +0.11% | 2 / 4 | 1 |
| TAT | C (1+3) vs snake P | 0.1 | not a multiple of 4 | 12 | +0.11% | 5 / 7 | 1 |
| TAT | C (1+3) vs snake P | 0.2 | all | 18 | -0.42% | 10 / 8 | 1 |
| TAT | C (1+3) vs snake P | 0.2 | 12-14 | 6 | -0.83% | 3 / 3 | 1 |
| TAT | C (1+3) vs snake P | 0.2 | 15-17 | 6 | -0.04% | 3 / 3 | 1 |
| TAT | C (1+3) vs snake P | 0.2 | 18-20 | 6 | -1.32% | 4 / 2 | 1 |
| TAT | C (1+3) vs snake P | 0.2 | multiple of 4 | 6 | -0.00% | 3 / 3 | 1 |
| TAT | C (1+3) vs snake P | 0.2 | not a multiple of 4 | 12 | -0.79% | 7 / 5 | 1 |
| TAT | C (1+3) vs snake P | 0.3 | all | 18 | -4.50% | 15 / 3 | 0.0187 |
| TAT | C (1+3) vs snake P | 0.3 | 12-14 | 6 | -8.25% | 6 / 0 | 1 |
| TAT | C (1+3) vs snake P | 0.3 | 15-17 | 6 | -4.11% | 4 / 2 | 1 |
| TAT | C (1+3) vs snake P | 0.3 | 18-20 | 6 | -3.44% | 5 / 1 | 1 |
| TAT | C (1+3) vs snake P | 0.3 | multiple of 4 | 6 | -5.61% | 5 / 1 | 1 |
| TAT | C (1+3) vs snake P | 0.3 | not a multiple of 4 | 12 | -3.76% | 10 / 2 | 0.374 |
| TAT | C2 (1+1+2) vs snake P | 0.0 | all | 9 | +0.02% | 2 / 7 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.0 | 12-14 | 3 | +0.03% | 1 / 2 | - |
| TAT | C2 (1+1+2) vs snake P | 0.0 | 15-17 | 3 | +0.02% | 0 / 3 | - |
| TAT | C2 (1+1+2) vs snake P | 0.0 | 18-20 | 3 | +0.01% | 1 / 2 | - |
| TAT | C2 (1+1+2) vs snake P | 0.0 | multiple of 4 | 3 | +0.02% | 1 / 2 | - |
| TAT | C2 (1+1+2) vs snake P | 0.0 | not a multiple of 4 | 6 | +0.02% | 1 / 5 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.1 | all | 18 | +0.05% | 4 / 14 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.1 | 12-14 | 6 | +0.04% | 2 / 4 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.1 | 15-17 | 6 | +0.05% | 2 / 4 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.1 | 18-20 | 6 | +0.06% | 0 / 6 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.1 | multiple of 4 | 6 | +0.07% | 1 / 5 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.1 | not a multiple of 4 | 12 | +0.04% | 3 / 9 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.2 | all | 18 | +0.05% | 6 / 12 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.2 | 12-14 | 6 | +0.04% | 2 / 4 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.2 | 15-17 | 6 | +0.06% | 1 / 5 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.2 | 18-20 | 6 | -0.03% | 3 / 3 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.2 | multiple of 4 | 6 | +0.06% | 1 / 5 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.2 | not a multiple of 4 | 12 | +0.05% | 5 / 7 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.3 | all | 18 | +0.03% | 8 / 10 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.3 | 12-14 | 6 | -1.13% | 3 / 3 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.3 | 15-17 | 6 | +0.04% | 2 / 4 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.3 | 18-20 | 6 | -1.09% | 3 / 3 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.3 | multiple of 4 | 6 | -1.15% | 4 / 2 | 1 |
| TAT | C2 (1+1+2) vs snake P | 0.3 | not a multiple of 4 | 12 | +0.04% | 4 / 8 | 1 |
| TAT | P' vs snake P | 0.1 | all | 18 | -0.01% | 11 / 7 | 1 |
| TAT | P' vs snake P | 0.1 | 12-14 | 6 | +0.00% | 3 / 3 | 1 |
| TAT | P' vs snake P | 0.1 | 15-17 | 6 | -7.59% | 5 / 1 | 1 |
| TAT | P' vs snake P | 0.1 | 18-20 | 6 | -2.40% | 3 / 3 | 1 |
| TAT | P' vs snake P | 0.1 | multiple of 4 | 6 | +0.00% | 3 / 3 | 1 |
| TAT | P' vs snake P | 0.1 | not a multiple of 4 | 12 | -7.59% | 8 / 4 | 1 |
| TAT | P' vs snake P | 0.2 | all | 18 | -11.63% | 18 / 0 | 0.00146 |
| TAT | P' vs snake P | 0.2 | 12-14 | 6 | -17.82% | 6 / 0 | 1 |
| TAT | P' vs snake P | 0.2 | 15-17 | 6 | -6.84% | 6 / 0 | 1 |
| TAT | P' vs snake P | 0.2 | 18-20 | 6 | -10.84% | 6 / 0 | 1 |
| TAT | P' vs snake P | 0.2 | multiple of 4 | 6 | -9.36% | 6 / 0 | 1 |
| TAT | P' vs snake P | 0.2 | not a multiple of 4 | 12 | -13.73% | 12 / 0 | 0.084 |
| TAT | P' vs snake P | 0.3 | all | 18 | -19.85% | 18 / 0 | 0.00146 |
| TAT | P' vs snake P | 0.3 | 12-14 | 6 | -23.34% | 6 / 0 | 1 |
| TAT | P' vs snake P | 0.3 | 15-17 | 6 | -15.19% | 6 / 0 | 1 |
| TAT | P' vs snake P | 0.3 | 18-20 | 6 | -15.86% | 6 / 0 | 1 |
| TAT | P' vs snake P | 0.3 | multiple of 4 | 6 | -14.22% | 6 / 0 | 1 |
| TAT | P' vs snake P | 0.3 | not a multiple of 4 | 12 | -20.98% | 12 / 0 | 0.084 |
| TAT | G vs P' | 0.1 | all | 18 | -0.06% | 10 / 8 | 1 |
| TAT | G vs P' | 0.1 | 12-14 | 6 | -0.43% | 4 / 2 | 1 |
| TAT | G vs P' | 0.1 | 15-17 | 6 | +0.11% | 3 / 3 | 1 |
| TAT | G vs P' | 0.1 | 18-20 | 6 | +0.01% | 3 / 3 | 1 |
| TAT | G vs P' | 0.1 | multiple of 4 | 6 | +0.10% | 3 / 3 | 1 |
| TAT | G vs P' | 0.1 | not a multiple of 4 | 12 | -0.43% | 7 / 5 | 1 |
| TAT | G vs P' | 0.2 | all | 18 | -1.47% | 14 / 4 | 0.297 |
| TAT | G vs P' | 0.2 | 12-14 | 6 | -2.15% | 4 / 2 | 1 |
| TAT | G vs P' | 0.2 | 15-17 | 6 | -2.17% | 4 / 2 | 1 |
| TAT | G vs P' | 0.2 | 18-20 | 6 | -1.24% | 6 / 0 | 1 |
| TAT | G vs P' | 0.2 | multiple of 4 | 6 | -0.66% | 4 / 2 | 1 |
| TAT | G vs P' | 0.2 | not a multiple of 4 | 12 | -2.66% | 10 / 2 | 1 |
| TAT | G vs P' | 0.3 | all | 18 | -1.11% | 13 / 5 | 1 |
| TAT | G vs P' | 0.3 | 12-14 | 6 | -0.48% | 4 / 2 | 1 |
| TAT | G vs P' | 0.3 | 15-17 | 6 | -2.31% | 5 / 1 | 1 |
| TAT | G vs P' | 0.3 | 18-20 | 6 | -2.00% | 4 / 2 | 1 |
| TAT | G vs P' | 0.3 | multiple of 4 | 6 | -1.03% | 3 / 3 | 1 |
| TAT | G vs P' | 0.3 | not a multiple of 4 | 12 | -1.11% | 10 / 2 | 1 |
| TET | G vs snake P | 0.0 | all | 9 | +0.09% | 0 / 9 | 0.582 |
| TET | G vs snake P | 0.0 | 12-14 | 3 | +0.08% | 0 / 3 | - |
| TET | G vs snake P | 0.0 | 15-17 | 3 | +0.09% | 0 / 3 | - |
| TET | G vs snake P | 0.0 | 18-20 | 3 | +0.10% | 0 / 3 | - |
| TET | G vs snake P | 0.0 | multiple of 4 | 3 | +0.09% | 0 / 3 | - |
| TET | G vs snake P | 0.0 | not a multiple of 4 | 6 | +0.09% | 0 / 6 | 1 |
| TET | G vs snake P | 0.1 | all | 18 | +0.12% | 0 / 18 | 0.00146 |
| TET | G vs snake P | 0.1 | 12-14 | 6 | +0.10% | 0 / 6 | 1 |
| TET | G vs snake P | 0.1 | 15-17 | 6 | +0.12% | 0 / 6 | 1 |
| TET | G vs snake P | 0.1 | 18-20 | 6 | +0.13% | 0 / 6 | 1 |
| TET | G vs snake P | 0.1 | multiple of 4 | 6 | +0.13% | 0 / 6 | 1 |
| TET | G vs snake P | 0.1 | not a multiple of 4 | 12 | +0.12% | 0 / 12 | 0.084 |
| TET | G vs snake P | 0.2 | all | 18 | +0.13% | 0 / 18 | 0.00146 |
| TET | G vs snake P | 0.2 | 12-14 | 6 | +0.11% | 0 / 6 | 1 |
| TET | G vs snake P | 0.2 | 15-17 | 6 | +0.13% | 0 / 6 | 1 |
| TET | G vs snake P | 0.2 | 18-20 | 6 | +0.15% | 0 / 6 | 1 |
| TET | G vs snake P | 0.2 | multiple of 4 | 6 | +0.13% | 0 / 6 | 1 |
| TET | G vs snake P | 0.2 | not a multiple of 4 | 12 | +0.13% | 0 / 12 | 0.084 |
| TET | G vs snake P | 0.3 | all | 18 | +0.15% | 0 / 18 | 0.00146 |
| TET | G vs snake P | 0.3 | 12-14 | 6 | +0.14% | 0 / 6 | 1 |
| TET | G vs snake P | 0.3 | 15-17 | 6 | +0.14% | 0 / 6 | 1 |
| TET | G vs snake P | 0.3 | 18-20 | 6 | +0.18% | 0 / 6 | 1 |
| TET | G vs snake P | 0.3 | multiple of 4 | 6 | +0.18% | 0 / 6 | 1 |
| TET | G vs snake P | 0.3 | not a multiple of 4 | 12 | +0.14% | 0 / 12 | 0.084 |
| TET | C (1+3) vs snake P | 0.0 | all | 9 | +0.05% | 0 / 9 | 0.582 |
| TET | C (1+3) vs snake P | 0.0 | 12-14 | 3 | +0.05% | 0 / 3 | - |
| TET | C (1+3) vs snake P | 0.0 | 15-17 | 3 | +0.03% | 0 / 3 | - |
| TET | C (1+3) vs snake P | 0.0 | 18-20 | 3 | +0.05% | 0 / 3 | - |
| TET | C (1+3) vs snake P | 0.0 | multiple of 4 | 3 | +0.03% | 0 / 3 | - |
| TET | C (1+3) vs snake P | 0.0 | not a multiple of 4 | 6 | +0.05% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.1 | all | 18 | +0.08% | 0 / 18 | 0.00146 |
| TET | C (1+3) vs snake P | 0.1 | 12-14 | 6 | +0.06% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.1 | 15-17 | 6 | +0.08% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.1 | 18-20 | 6 | +0.08% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.1 | multiple of 4 | 6 | +0.08% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.1 | not a multiple of 4 | 12 | +0.08% | 0 / 12 | 0.084 |
| TET | C (1+3) vs snake P | 0.2 | all | 18 | +0.09% | 0 / 18 | 0.00146 |
| TET | C (1+3) vs snake P | 0.2 | 12-14 | 6 | +0.07% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.2 | 15-17 | 6 | +0.09% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.2 | 18-20 | 6 | +0.09% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.2 | multiple of 4 | 6 | +0.08% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.2 | not a multiple of 4 | 12 | +0.09% | 0 / 12 | 0.084 |
| TET | C (1+3) vs snake P | 0.3 | all | 18 | +0.08% | 0 / 18 | 0.00146 |
| TET | C (1+3) vs snake P | 0.3 | 12-14 | 6 | +0.07% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.3 | 15-17 | 6 | +0.10% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.3 | 18-20 | 6 | +0.11% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.3 | multiple of 4 | 6 | +0.11% | 0 / 6 | 1 |
| TET | C (1+3) vs snake P | 0.3 | not a multiple of 4 | 12 | +0.08% | 0 / 12 | 0.084 |
| TET | C2 (1+1+2) vs snake P | 0.0 | all | 9 | +0.03% | 0 / 9 | 0.582 |
| TET | C2 (1+1+2) vs snake P | 0.0 | 12-14 | 3 | +0.03% | 0 / 3 | - |
| TET | C2 (1+1+2) vs snake P | 0.0 | 15-17 | 3 | +0.03% | 0 / 3 | - |
| TET | C2 (1+1+2) vs snake P | 0.0 | 18-20 | 3 | +0.04% | 0 / 3 | - |
| TET | C2 (1+1+2) vs snake P | 0.0 | multiple of 4 | 3 | +0.03% | 0 / 3 | - |
| TET | C2 (1+1+2) vs snake P | 0.0 | not a multiple of 4 | 6 | +0.03% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.1 | all | 18 | +0.03% | 0 / 18 | 0.00146 |
| TET | C2 (1+1+2) vs snake P | 0.1 | 12-14 | 6 | +0.03% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.1 | 15-17 | 6 | +0.04% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.1 | 18-20 | 6 | +0.04% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.1 | multiple of 4 | 6 | +0.04% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.1 | not a multiple of 4 | 12 | +0.03% | 0 / 12 | 0.084 |
| TET | C2 (1+1+2) vs snake P | 0.2 | all | 18 | +0.04% | 0 / 18 | 0.00146 |
| TET | C2 (1+1+2) vs snake P | 0.2 | 12-14 | 6 | +0.03% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.2 | 15-17 | 6 | +0.04% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.2 | 18-20 | 6 | +0.04% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.2 | multiple of 4 | 6 | +0.04% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.2 | not a multiple of 4 | 12 | +0.04% | 0 / 12 | 0.084 |
| TET | C2 (1+1+2) vs snake P | 0.3 | all | 18 | +0.03% | 0 / 18 | 0.00146 |
| TET | C2 (1+1+2) vs snake P | 0.3 | 12-14 | 6 | +0.03% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.3 | 15-17 | 6 | +0.03% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.3 | 18-20 | 6 | +0.04% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.3 | multiple of 4 | 6 | +0.04% | 0 / 6 | 1 |
| TET | C2 (1+1+2) vs snake P | 0.3 | not a multiple of 4 | 12 | +0.03% | 0 / 12 | 0.084 |
| TET | P' vs snake P | 0.1 | all | 18 | +0.03% | 2 / 16 | 0.0187 |
| TET | P' vs snake P | 0.1 | 12-14 | 6 | +0.01% | 1 / 5 | 1 |
| TET | P' vs snake P | 0.1 | 15-17 | 6 | +0.01% | 1 / 5 | 1 |
| TET | P' vs snake P | 0.1 | 18-20 | 6 | +0.03% | 0 / 6 | 1 |
| TET | P' vs snake P | 0.1 | multiple of 4 | 6 | +0.02% | 2 / 4 | 1 |
| TET | P' vs snake P | 0.1 | not a multiple of 4 | 12 | +0.03% | 0 / 12 | 0.084 |
| TET | P' vs snake P | 0.2 | all | 18 | +0.02% | 1 / 17 | 0.0027 |
| TET | P' vs snake P | 0.2 | 12-14 | 6 | +0.01% | 0 / 6 | 1 |
| TET | P' vs snake P | 0.2 | 15-17 | 6 | +0.02% | 1 / 5 | 1 |
| TET | P' vs snake P | 0.2 | 18-20 | 6 | +0.02% | 0 / 6 | 1 |
| TET | P' vs snake P | 0.2 | multiple of 4 | 6 | +0.02% | 0 / 6 | 1 |
| TET | P' vs snake P | 0.2 | not a multiple of 4 | 12 | +0.02% | 1 / 11 | 0.152 |
| TET | P' vs snake P | 0.3 | all | 18 | +0.02% | 2 / 16 | 0.0187 |
| TET | P' vs snake P | 0.3 | 12-14 | 6 | +0.02% | 0 / 6 | 1 |
| TET | P' vs snake P | 0.3 | 15-17 | 6 | +0.01% | 1 / 5 | 1 |
| TET | P' vs snake P | 0.3 | 18-20 | 6 | +0.02% | 1 / 5 | 1 |
| TET | P' vs snake P | 0.3 | multiple of 4 | 6 | +0.01% | 0 / 6 | 1 |
| TET | P' vs snake P | 0.3 | not a multiple of 4 | 12 | +0.02% | 2 / 10 | 0.516 |
| TET | G vs P' | 0.1 | all | 18 | +0.10% | 0 / 18 | 0.00146 |
| TET | G vs P' | 0.1 | 12-14 | 6 | +0.09% | 0 / 6 | 1 |
| TET | G vs P' | 0.1 | 15-17 | 6 | +0.11% | 0 / 6 | 1 |
| TET | G vs P' | 0.1 | 18-20 | 6 | +0.10% | 0 / 6 | 1 |
| TET | G vs P' | 0.1 | multiple of 4 | 6 | +0.10% | 0 / 6 | 1 |
| TET | G vs P' | 0.1 | not a multiple of 4 | 12 | +0.10% | 0 / 12 | 0.084 |
| TET | G vs P' | 0.2 | all | 18 | +0.12% | 0 / 18 | 0.00146 |
| TET | G vs P' | 0.2 | 12-14 | 6 | +0.09% | 0 / 6 | 1 |
| TET | G vs P' | 0.2 | 15-17 | 6 | +0.12% | 0 / 6 | 1 |
| TET | G vs P' | 0.2 | 18-20 | 6 | +0.13% | 0 / 6 | 1 |
| TET | G vs P' | 0.2 | multiple of 4 | 6 | +0.12% | 0 / 6 | 1 |
| TET | G vs P' | 0.2 | not a multiple of 4 | 12 | +0.12% | 0 / 12 | 0.084 |
| TET | G vs P' | 0.3 | all | 18 | +0.14% | 0 / 18 | 0.00146 |
| TET | G vs P' | 0.3 | 12-14 | 6 | +0.11% | 0 / 6 | 1 |
| TET | G vs P' | 0.3 | 15-17 | 6 | +0.14% | 0 / 6 | 1 |
| TET | G vs P' | 0.3 | 18-20 | 6 | +0.15% | 0 / 6 | 1 |
| TET | G vs P' | 0.3 | multiple of 4 | 6 | +0.15% | 0 / 6 | 1 |
| TET | G vs P' | 0.3 | not a multiple of 4 | 12 | +0.13% | 0 / 12 | 0.084 |

## Median gap per task count

| metric | pair | CV | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TAT | G vs snake P | 0.0 | +0.2% | +0.2% | +0.2% | +0.3% | +0.2% | +0.0% | +0.1% | +0.2% | +0.3% |
| TAT | G vs snake P | 0.1 | -2.2% | -9.6% | +1.1% | -11.1% | +0.2% | -12.7% | -7.2% | -6.3% | -2.3% |
| TAT | G vs snake P | 0.2 | -13.9% | -26.2% | -15.3% | -4.5% | -13.4% | -14.4% | -16.7% | -12.9% | -10.5% |
| TAT | G vs snake P | 0.3 | -28.6% | -24.4% | -21.2% | -15.6% | -10.5% | -19.9% | -13.1% | -21.5% | -12.3% |
| TAT | C (1+3) vs snake P | 0.0 | +0.0% | +0.1% | +0.1% | +0.2% | +0.1% | -0.0% | +0.0% | +0.0% | +0.1% |
| TAT | C (1+3) vs snake P | 0.1 | +0.1% | -9.5% | +0.2% | +0.9% | +0.1% | -0.0% | -0.0% | -0.7% | -2.3% |
| TAT | C (1+3) vs snake P | 0.2 | -0.8% | -9.4% | -2.2% | +0.1% | -1.6% | -0.4% | -3.9% | -2.5% | +0.9% |
| TAT | C (1+3) vs snake P | 0.3 | -13.5% | -10.6% | -4.5% | -5.1% | -5.6% | +0.6% | -3.6% | -4.9% | -1.8% |
| TAT | C2 (1+1+2) vs snake P | 0.0 | -0.0% | +0.0% | +0.1% | +0.1% | +0.0% | +0.0% | -0.0% | +0.0% | +0.0% |
| TAT | C2 (1+1+2) vs snake P | 0.1 | +0.0% | -3.2% | +0.1% | +0.1% | -0.0% | -0.1% | +0.0% | +0.1% | +0.1% |
| TAT | C2 (1+1+2) vs snake P | 0.2 | +0.0% | -5.1% | -1.9% | +0.1% | -0.0% | +0.1% | -1.0% | -0.3% | +0.1% |
| TAT | C2 (1+1+2) vs snake P | 0.3 | -1.1% | -6.5% | +0.0% | +0.1% | -2.2% | +0.0% | -1.1% | -1.1% | -1.2% |
| TAT | P' vs snake P | 0.1 | -0.0% | -6.5% | +0.0% | -11.4% | +0.0% | -10.5% | -5.5% | -6.2% | -2.4% |
| TAT | P' vs snake P | 0.2 | -13.9% | -22.0% | -13.7% | -4.5% | -12.0% | -11.4% | -14.9% | -11.7% | -9.4% |
| TAT | P' vs snake P | 0.3 | -27.6% | -22.0% | -24.4% | -11.2% | -9.1% | -18.0% | -10.1% | -21.5% | -13.4% |
| TAT | G vs P' | 0.1 | -2.2% | -3.1% | +1.1% | +0.3% | +0.2% | -2.4% | -1.7% | -0.0% | +0.1% |
| TAT | G vs P' | 0.2 | -0.1% | -5.4% | -1.7% | +0.0% | -1.4% | -3.4% | -2.0% | -1.3% | -1.2% |
| TAT | G vs P' | 0.3 | -1.3% | -3.1% | +4.5% | -4.6% | -1.4% | -2.3% | -3.1% | -0.1% | +1.4% |
| TET | G vs snake P | 0.0 | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% |
| TET | G vs snake P | 0.1 | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% |
| TET | G vs snake P | 0.2 | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.2% | +0.2% | +0.1% |
| TET | G vs snake P | 0.3 | +0.1% | +0.1% | +0.1% | +0.1% | +0.2% | +0.1% | +0.2% | +0.2% | +0.2% |
| TET | C (1+3) vs snake P | 0.0 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.1% | +0.1% | +0.0% |
| TET | C (1+3) vs snake P | 0.1 | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% |
| TET | C (1+3) vs snake P | 0.2 | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% |
| TET | C (1+3) vs snake P | 0.3 | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% |
| TET | C2 (1+1+2) vs snake P | 0.0 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| TET | C2 (1+1+2) vs snake P | 0.1 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| TET | C2 (1+1+2) vs snake P | 0.2 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| TET | C2 (1+1+2) vs snake P | 0.3 | +0.0% | +0.0% | +0.0% | +0.0% | +0.1% | +0.0% | +0.0% | +0.0% | +0.0% |
| TET | P' vs snake P | 0.1 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| TET | P' vs snake P | 0.2 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| TET | P' vs snake P | 0.3 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| TET | G vs P' | 0.1 | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% |
| TET | G vs P' | 0.2 | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% | +0.1% |
| TET | G vs P' | 0.3 | +0.1% | +0.1% | +0.1% | +0.1% | +0.2% | +0.1% | +0.2% | +0.2% | +0.2% |
