# Real-time metrics across experiments 17-25

Inflation: worst memory-task job CPU / planned budget; response: worst (completion - release) / period.
Medians over the cases where every placement and random draw met every deadline.

## 17-18 policy mix

160 cases, 71 with every run meeting every deadline

| placement | met every deadline | violated jobs / released | median worst inflation | median worst response |
|---|---|---|---:|---:|
| wfd | 125 / 159 | 1689 / 21856 | 1.83 | 0.58 |
| tg | 127 / 159 | 1112 / 21864 | 1.55 | 0.59 |
| ra | 125 / 158 | 1453 / 21728 | 1.88 | 0.60 |
| ra-tg | 125 / 160 | 1172 / 22008 | 1.55 | 0.60 |
| cg | 122 / 158 | 1568 / 21736 | 1.53 | 0.60 |
| ra-cg | 120 / 159 | 1612 / 21880 | 1.54 | 0.60 |
| random | 321 / 480 | 6300 / 66024 | 1.66 | 0.71 |

| contrast | deadline only first / only second | fewer violated jobs first / second (median difference) | inflation change (wins / both ok) | response change |
|---|---|---|---|---:|
| cg vs wfd | 5 / 7 | 22 / 16 (-8) | -21.3% (81 / 98) | -0.001 |
| cg vs ra | 4 / 6 | 20 / 18 (-1) | -22.4% (81 / 99) | +0.004 |
| cg vs random | 62 / 11 | 109 / 46 (-8) | -10.3% (180 / 250) | -0.104 |
| ra-cg vs wfd | 4 / 9 | 22 / 18 (-1) | -20.4% (81 / 97) | -0.001 |
| ra-cg vs ra | 3 / 8 | 19 / 19 (+0) | -22.1% (80 / 98) | -0.001 |
| ra-cg vs random | 54 / 12 | 109 / 44 (-8) | -9.9% (180 / 252) | -0.102 |
| tg vs wfd | 6 / 4 | 26 / 10 (-8) | -19.3% (70 / 102) | -0.000 |
| tg vs ra | 5 / 3 | 24 / 11 (-8) | -21.2% (80 / 103) | +0.001 |
| tg vs random | 66 / 3 | 124 / 27 (-16) | -5.2% (163 / 261) | -0.120 |
| ra-tg vs wfd | 4 / 5 | 24 / 12 (-8) | -19.4% (75 / 102) | -0.001 |
| ra-tg vs ra | 3 / 4 | 23 / 11 (-8) | -18.4% (70 / 103) | +0.000 |
| ra-tg vs random | 57 / 3 | 123 / 25 (-16) | -4.0% (166 / 264) | -0.123 |

## 19 period spread x memory mix

200 cases, 166 with every run meeting every deadline

| placement | met every deadline | violated jobs / released | median worst inflation | median worst response |
|---|---|---|---:|---:|
| wfd | 199 / 199 | 0 / 38678 | 2.24 | 0.59 |
| cgb | 200 / 200 | 0 / 38870 | 1.96 | 0.58 |
| ra | 200 / 200 | 0 / 38870 | 2.31 | 0.59 |
| ra-cgb | 200 / 200 | 0 / 38870 | 1.96 | 0.57 |
| random | 564 / 598 | 606 / 116230 | 2.00 | 0.70 |

| contrast | deadline only first / only second | fewer violated jobs first / second (median difference) | inflation change (wins / both ok) | response change |
|---|---|---|---|---:|
| cgb vs wfd | 0 / 0 | 0 / 0 (-) | -11.8% (178 / 199) | -0.001 |
| cgb vs ra | 0 / 0 | 0 / 0 (-) | -13.5% (177 / 200) | -0.006 |
| cgb vs random | 34 / 0 | 34 / 0 (-12) | -5.5% (369 / 564) | -0.089 |
| ra-cgb vs wfd | 0 / 0 | 0 / 0 (-) | -12.0% (178 / 199) | -0.007 |
| ra-cgb vs ra | 0 / 0 | 0 / 0 (-) | -14.2% (181 / 200) | -0.005 |
| ra-cgb vs random | 34 / 0 | 34 / 0 (-12) | -5.6% (374 / 564) | -0.099 |

## 20 768 KiB tasks at 25 % of U

72 cases, 3 with every run meeting every deadline

| placement | met every deadline | violated jobs / released | median worst inflation | median worst response |
|---|---|---|---:|---:|
| wfd | 29 / 72 | 2352 / 10992 | 2.30 | 0.46 |
| cgb | 37 / 72 | 1152 / 10992 | 2.30 | 0.52 |
| ra | 25 / 72 | 2868 / 10992 | 2.58 | 0.44 |
| ra-cgb | 37 / 72 | 1168 / 10992 | 2.30 | 0.50 |
| random | 45 / 216 | 9221 / 32976 | 2.51 | 0.63 |

| contrast | deadline only first / only second | fewer violated jobs first / second (median difference) | inflation change (wins / both ok) | response change |
|---|---|---|---|---:|
| cgb vs wfd | 10 / 2 | 34 / 3 (-16) | -18.1% (21 / 27) | -0.025 |
| cgb vs ra | 13 / 1 | 34 / 6 (-16) | -21.0% (21 / 24) | +0.025 |
| cgb vs random | 67 / 1 | 151 / 16 (-32) | -8.5% (31 / 44) | -0.086 |
| ra-cgb vs wfd | 10 / 2 | 30 / 6 (-16) | -12.8% (23 / 27) | -0.074 |
| ra-cgb vs ra | 12 / 0 | 29 / 7 (-16) | -20.2% (21 / 25) | -0.025 |
| ra-cgb vs random | 67 / 1 | 149 / 16 (-32) | -8.5% (28 / 44) | -0.112 |

## 21 32 KiB low-CLS tasks

216 cases, 178 with every run meeting every deadline

| placement | met every deadline | violated jobs / released | median worst inflation | median worst response |
|---|---|---|---:|---:|
| wfd | 216 / 216 | 0 / 42964 | 2.36 | 0.60 |
| cgb | 216 / 216 | 0 / 42964 | 1.95 | 0.59 |
| ra | 214 / 214 | 0 / 42672 | 2.31 | 0.60 |
| ra-cgb | 216 / 216 | 0 / 42964 | 1.95 | 0.59 |
| random | 607 / 647 | 756 / 128734 | 2.01 | 0.72 |

| contrast | deadline only first / only second | fewer violated jobs first / second (median difference) | inflation change (wins / both ok) | response change |
|---|---|---|---|---:|
| cgb vs wfd | 0 / 0 | 0 / 0 (-) | -16.4% (200 / 216) | -0.008 |
| cgb vs ra | 0 / 0 | 0 / 0 (-) | -15.6% (198 / 214) | -0.000 |
| cgb vs random | 40 / 0 | 40 / 0 (-16) | -6.8% (405 / 607) | -0.120 |
| ra-cgb vs wfd | 0 / 0 | 0 / 0 (-) | -16.1% (198 / 216) | -0.013 |
| ra-cgb vs ra | 0 / 0 | 0 / 0 (-) | -15.3% (199 / 214) | -0.000 |
| ra-cgb vs random | 40 / 0 | 40 / 0 (-16) | -6.7% (407 / 607) | -0.116 |

## 23 continuous CLS (mean 0.6-0.9, SD > 0)

144 cases, 50 with every run meeting every deadline

| placement | met every deadline | violated jobs / released | median worst inflation | median worst response |
|---|---|---|---:|---:|
| wfd | 144 / 144 | 0 / 28072 | 2.24 | 0.74 |
| cgb | 144 / 144 | 0 / 28072 | 2.23 | 0.76 |
| ra | 144 / 144 | 0 / 28072 | 2.23 | 0.72 |
| ra-cgb | 144 / 144 | 0 / 28072 | 2.20 | 0.73 |
| cgr | 144 / 144 | 0 / 28072 | 2.19 | 0.78 |
| ra-cgr | 144 / 144 | 0 / 28072 | 2.18 | 0.73 |
| random | 394 / 426 | 588 / 83022 | 2.13 | 0.83 |

| contrast | deadline only first / only second | fewer violated jobs first / second (median difference) | inflation change (wins / both ok) | response change |
|---|---|---|---|---:|
| cgb vs wfd | 0 / 0 | 0 / 0 (-) | -0.7% (47 / 74) | +0.002 |
| cgb vs ra | 0 / 0 | 0 / 0 (-) | -0.5% (43 / 74) | +0.008 |
| cgb vs random | 32 / 0 | 32 / 0 (-12) | +3.4% (64 / 190) | -0.088 |
| ra-cgb vs wfd | 0 / 0 | 0 / 0 (-) | -0.6% (48 / 74) | -0.005 |
| ra-cgb vs ra | 0 / 0 | 0 / 0 (-) | +0.2% (32 / 74) | +0.001 |
| ra-cgb vs random | 32 / 0 | 32 / 0 (-12) | +3.5% (61 / 190) | -0.096 |
| cgr vs wfd | 0 / 0 | 0 / 0 (-) | -1.2% (54 / 74) | +0.003 |
| cgr vs ra | 0 / 0 | 0 / 0 (-) | -0.9% (44 / 74) | +0.012 |
| cgr vs random | 32 / 0 | 32 / 0 (-12) | +2.5% (66 / 190) | -0.081 |
| ra-cgr vs wfd | 0 / 0 | 0 / 0 (-) | -1.0% (56 / 74) | -0.009 |
| ra-cgr vs ra | 0 / 0 | 0 / 0 (-) | -0.9% (56 / 74) | +0.001 |
| ra-cgr vs random | 32 / 0 | 32 / 0 (-12) | +2.1% (72 / 190) | -0.093 |

## 24 32 KiB low-CLS tasks under load

288 cases, 60 with every run meeting every deadline

| placement | met every deadline | violated jobs / released | median worst inflation | median worst response |
|---|---|---|---:|---:|
| wfd | 217 / 288 | 2498 / 56608 | 2.01 | 0.68 |
| cgb | 220 / 287 | 2076 / 56426 | 1.58 | 0.66 |
| ra | 216 / 287 | 3116 / 56426 | 2.09 | 0.67 |
| ra-cgb | 221 / 288 | 2272 / 56608 | 1.58 | 0.67 |
| random | 363 / 864 | 18352 / 169824 | 1.95 | 0.83 |

| contrast | deadline only first / only second | fewer violated jobs first / second (median difference) | inflation change (wins / both ok) | response change |
|---|---|---|---|---:|
| cgb vs wfd | 8 / 4 | 41 / 18 (-6) | -17.5% (188 / 212) | -0.014 |
| cgb vs ra | 6 / 2 | 47 / 14 (-12) | -19.9% (194 / 214) | -0.010 |
| cgb vs random | 300 / 0 | 465 / 25 (-24) | -16.5% (275 / 360) | -0.125 |
| ra-cgb vs wfd | 9 / 5 | 35 / 23 (+0) | -17.7% (184 / 212) | -0.013 |
| ra-cgb vs ra | 8 / 4 | 45 / 16 (-12) | -20.3% (192 / 212) | -0.009 |
| ra-cgb vs random | 301 / 1 | 459 / 27 (-22.5) | -17.2% (282 / 362) | -0.125 |

## 25 conflict-miss low-CLS tasks

108 cases, 85 with every run meeting every deadline

| placement | met every deadline | violated jobs / released | median worst inflation | median worst response |
|---|---|---|---:|---:|
| wfd | 108 / 108 | 0 / 21196 | 2.40 | 0.62 |
| cgb | 107 / 107 | 0 / 20992 | 1.97 | 0.60 |
| ra | 107 / 107 | 0 / 21006 | 2.33 | 0.61 |
| ra-cgb | 107 / 107 | 0 / 20992 | 1.98 | 0.60 |
| random | 300 / 323 | 430 / 63420 | 2.02 | 0.75 |

| contrast | deadline only first / only second | fewer violated jobs first / second (median difference) | inflation change (wins / both ok) | response change |
|---|---|---|---|---:|
| cgb vs wfd | 0 / 0 | 0 / 0 (-) | -16.5% (99 / 107) | -0.010 |
| cgb vs ra | 0 / 0 | 0 / 0 (-) | -15.0% (102 / 106) | -0.003 |
| cgb vs random | 23 / 0 | 23 / 0 (-16) | -6.4% (193 / 297) | -0.121 |
| ra-cgb vs wfd | 0 / 0 | 0 / 0 (-) | -17.6% (99 / 107) | -0.013 |
| ra-cgb vs ra | 0 / 0 | 0 / 0 (-) | -16.0% (100 / 106) | -0.005 |
| ra-cgb vs random | 23 / 0 | 23 / 0 (-16) | -6.5% (192 / 297) | -0.122 |

