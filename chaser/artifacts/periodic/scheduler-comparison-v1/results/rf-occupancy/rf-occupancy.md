# Pre-run check: static D + M rule against the RF (experiment 42, development check)

11733 rows (P rows 6893); static threshold t* = 0.975 (accepted P rows miss at most 1%)

## P rows: AUC for meeting every deadline, each experiment held out

| score | 17 and 18 mixed tasks | 19 placement boundary | 20 768 KiB | 21 32 KiB | 23 continuous CLS | 24 32 KiB under load | 25 conflict-miss | 27 32 KiB | 27 768 KiB | 41 memory cost | all |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D | 0.832 | - | 0.929 | - | 0.999 | 0.994 | - | 0.993 | 0.759 | 0.359 | 0.752 |
| D + M | 0.972 | - | 0.989 | - | 0.997 | 0.991 | - | 0.987 | 0.966 | 0.986 | 0.977 |
| RF f35 | 0.966 | - | 0.954 | - | 0.999 | 0.994 | - | 0.994 | 0.927 | 0.822 | 0.974 |
| RF f35m | 0.985 | - | 0.980 | - | 0.999 | 0.995 | - | 0.994 | 0.958 | 0.982 | 0.991 |
| RF f35m (seed 1) | 0.986 | - | 0.981 | - | 0.999 | 0.995 | - | 0.994 | 0.959 | 0.982 | 0.991 |

Judgment: RF f35m above D + M by more than the seed noise (0.001) in 4 of 7 experiments -> main method: **static rule**

## P rows alone: accept or reject (development rows, held out by experiment for the RF)

| method | P rows | accepted | false accept | false reject |
|---|---:|---:|---:|---:|
| D + M < 0.975 | 6893 | 4554 | 24 | 685 |
| RF f35m, tau 0.5 | 6893 | 5295 | 165 | 85 |
| RF f35m, tau 0.8 | 6893 | 4809 | 42 | 448 |

## Decision simulation on the sets with CHASER, G4 and C1+1+2 runs (held out by experiment for the RF)

| method | sets | accepted (met / false accept) | rejected (false reject) | chose other | saved | wrong switch |
|---|---:|---|---|---:|---:|---:|
| D + M < 0.975 (CHASER or reject) | 1792 | 1149 (1142 / 7) | 643 (205) | 0 | 0 | 0 |
| RF f35m, tau 0.5 | 1792 | 1315 (1284 / 31) | 477 (47) | 951 | 21 | 8 |
| RF f35m, tau 0.8 | 1792 | 1229 (1220 / 9) | 563 (126) | 900 | 7 | 5 |
| RF f35m, tau 0.5, CHASER + G/C only | 1792 | 1311 (1272 / 39) | 481 (46) | 7 | 4 | 1 |
| RF f35m, tau 0.8, CHASER + G/C only | 1792 | 1228 (1222 / 6) | 564 (121) | 17 | 4 | 0 |

Always CHASER: 1293 of 1792 sets meet every deadline; the best candidate meets 1354; rescuable 61.
