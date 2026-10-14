# Experiment 48: CHASER placement on capped low-locality kernels (pre-registered)

240 cases; candidate ra-cgb against wfd, ra; alpha 0.05

## V2: violated jobs (ratio of released jobs)

| reference | pairs | violating | fewer ra-cgb / ref | median difference | only ra-cgb / only ref met | McNemar p | Holm p | significant |
|---|---:|---:|---|---:|---|---:|---:|---|
| wfd | 240 | 156 | 106 / 45 | -0.0752 | 24 / 12 | 0.0652 | 1.33e-08 | True |
| ra | 239 | 148 | 92 / 28 | -0.0669 | 16 / 6 | 0.0525 | 2.25e-10 | True |

## V3: worst low-task job CPU / budget

| reference | pairs | median change | wins / losses | Holm p | significant |
|---|---:|---:|---|---:|---|
| wfd | 84 | -12.0% | 76 / 8 | 1.29e-12 | True |
| ra | 91 | -12.4% | 82 / 9 | 2.52e-14 | True |

## V6: TET

| reference | pairs | median change | wins / losses | Holm p | significant |
|---|---:|---:|---|---:|---|
| wfd | 84 | -4.1% | 73 / 11 | 7.19e-13 | True |
| ra | 91 | -4.1% | 84 / 7 | 1.94e-15 | True |

## V4: TAT equivalence with ra (+-2 %)

pairs 91, median ratio 0.9925, TOST Holm p 0.00832, equivalent True

## Supported

V2: True, V3: True, V4: True, V6: True

## Secondary

| metric | cell | first vs reference | pairs | effect | Holm p | significant |
|---|---|---|---:|---:|---:|---|
| violated | cv00-lowloc50 | ra-cgb vs wfd | 120 | -0.1213 | 4.93e-11 | True |
| inflation | cv00-lowloc50 | ra-cgb vs wfd | 42 | -18.4% | 2.96e-08 | True |
| violated | cv00-lowloc50 | ra-cgb vs ra | 120 | -0.1082 | 1.84e-09 | True |
| inflation | cv00-lowloc50 | ra-cgb vs ra | 52 | -15.9% | 1.8e-08 | True |
| violated | cv20-lowloc50 | ra-cgb vs wfd | 120 | -0.0068 | 0.839 | False |
| inflation | cv20-lowloc50 | ra-cgb vs wfd | 42 | -9.1% | 1.02e-08 | True |
| violated | cv20-lowloc50 | ra-cgb vs ra | 119 | +0.0000 | 0.0612 | False |
| inflation | cv20-lowloc50 | ra-cgb vs ra | 39 | -9.1% | 1.02e-08 | True |
| violated | all | cgb vs wfd | 237 | -0.0833 | 1.3e-12 | True |
| inflation | all | cgb vs wfd | 91 | -11.9% | 9.44e-11 | True |
| tet | all | cgb vs wfd | 91 | -3.5% | 1.17e-10 | True |

## Runs that met every deadline (met / measured)

| cell | wfd | cgb | ra | ra-cgb |
|---|---|---|---|---|
| cv00-lowloc50 u060 | 22/24 | 24/24 | 24/24 | 24/24 |
| cv00-lowloc50 u065 | 16/24 | 18/24 | 19/24 | 21/24 |
| cv00-lowloc50 u070 | 4/24 | 9/24 | 7/24 | 13/24 |
| cv00-lowloc50 u075 | 0/24 | 4/24 | 2/24 | 4/24 |
| cv00-lowloc50 u080 | 0/24 | 0/24 | 0/24 | 0/24 |
| cv20-lowloc50 u060 | 24/24 | 23/23 | 22/23 | 23/24 |
| cv20-lowloc50 u065 | 18/24 | 19/22 | 14/24 | 14/24 |
| cv20-lowloc50 u070 | 10/24 | 15/24 | 7/24 | 9/24 |
| cv20-lowloc50 u075 | 2/24 | 4/24 | 2/24 | 0/24 |
| cv20-lowloc50 u080 | 0/24 | 0/24 | 0/24 | 0/24 |
