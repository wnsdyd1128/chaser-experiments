# Experiment 46: technical report (pre-registered) and RF calibration

144 sets judged; left out: {'heldout-kernels-v1': 6}

## Task values (median [5th, 95th percentile])

| source | tasks | CLS | p_mem | L1 misses per µs | working set KiB | CLS <= 0.5 |
|---|---:|---|---|---|---|---:|
| real kernels | 2355 | 0.998 [0.995, 0.999] | 0.0013 [0.0006, 0.0024] | 0.102 [0.044, 0.353] | 13.4 [5.8, 31.2] | 0.0% |
| real: polybench-2mm-u32 | 605 | 0.998 [0.997, 0.999] | 0.0015 [0.0007, 0.0029] | 0.131 [0.052, 0.218] | 16.6 [6.6, 34.5] | 0.0% |
| real: polybench-doitgen-u32 | 560 | 0.999 [0.995, 0.999] | 0.0010 [0.0006, 0.0021] | 0.081 [0.041, 0.354] | 11.6 [5.8, 28.3] | 0.0% |
| real: polybench-syrk-u32 | 610 | 0.998 [0.995, 0.999] | 0.0015 [0.0008, 0.0025] | 0.104 [0.050, 0.350] | 14.5 [6.1, 32.6] | 0.0% |
| real: polybench-trmm-u32 | 580 | 0.999 [0.985, 0.999] | 0.0011 [0.0006, 0.0022] | 0.082 [0.042, 1.042] | 12.2 [5.6, 24.8] | 0.0% |
| synthetic: confirm-small-v1 | 1875 | 0.877 [0.124, 0.914] | 0.0096 [0.0034, 0.0241] | 4.960 [3.747, 14.402] | 33.9 [33.3, 39.2] | 49.3% |
| synthetic: confirm-big-v1 | 1858 | 0.897 [0.000, 0.915] | 0.0105 [0.0043, 1.0000] | 4.332 [3.722, 13.430] | 37.2 [33.2, 768.0] | 22.2% |
| synthetic: confirm-mem-v1 | 1851 | 0.896 [0.127, 0.916] | 0.0071 [0.0033, 0.8731] | 4.067 [3.699, 4.788] | 35.3 [20.6, 39.5] | 23.4% |

Placement: CHASER's mapping differs from the U-balanced one in 150 of 150 sets; 0 of 2355 tasks have CLS <= 0.5.

## Per load

| load | sets | CHASER met | RF status | mean RF probability (min) | mean D | mean M | mean D + M (max) |
|---|---:|---:|---|---|---:|---:|---|
| 0.4 | 29 | 29 | {'P': 29} | 1.000 (0.998) | 0.010 | 0.034 | 0.044 (0.064) |
| 0.475 | 30 | 30 | {'P': 30} | 0.997 (0.989) | 0.013 | 0.038 | 0.051 (0.064) |
| 0.55 | 30 | 30 | {'P': 30} | 0.970 (0.958) | 0.019 | 0.042 | 0.062 (0.096) |
| 0.625 | 28 | 28 | {'P': 28} | 0.953 (0.935) | 0.020 | 0.046 | 0.066 (0.087) |
| 0.7 | 27 | 27 | {'P': 27} | 0.929 (0.879) | 0.027 | 0.051 | 0.078 (0.132) |

## Calibration: RF probability for CHASER against the observed outcome

| experiment | probability bin | sets | CHASER met | share met | mean probability |
|---|---|---:|---:|---:|---:|
| experiment 44 | [0.00, 0.50) | 136 | 14 | 10.3% | 0.102 |
| experiment 44 | [0.50, 0.80) | 38 | 23 | 60.5% | 0.643 |
| experiment 44 | [0.80, 0.90) | 21 | 20 | 95.2% | 0.866 |
| experiment 44 | [0.90, 0.95) | 24 | 23 | 95.8% | 0.927 |
| experiment 44 | [0.95, 0.99) | 44 | 44 | 100.0% | 0.976 |
| experiment 44 | [0.99, 1.00) | 94 | 94 | 100.0% | 0.998 |
| experiment 46 | [0.80, 0.90) | 5 | 5 | 100.0% | 0.883 |
| experiment 46 | [0.90, 0.95) | 22 | 22 | 100.0% | 0.934 |
| experiment 46 | [0.95, 0.99) | 62 | 62 | 100.0% | 0.965 |
| experiment 46 | [0.99, 1.00) | 55 | 55 | 100.0% | 0.999 |

## RF false accepts

| set | RF probability | D + M |
|---|---:|---:|
