# Experiment 47: CHASER placement on real low-locality kernels (pre-registered)

240 cases; candidate ra-cgb against wfd, ra; alpha 0.05

## V2: violated jobs (ratio of released jobs)

| reference | pairs | violating | fewer ra-cgb / ref | median difference | only ra-cgb / only ref met | McNemar p | Holm p | significant |
|---|---:|---:|---|---:|---|---:|---:|---|
| wfd | 240 | 240 | 195 / 26 | -0.1667 | 0 / 0 | 1 | 6.47e-31 | True |
| ra | 240 | 240 | 205 / 14 | -0.1543 | 0 / 3 | 0.25 | 1.24e-32 | True |

## V3: worst low-task job CPU / budget

| reference | pairs | median change | wins / losses | Holm p | significant |
|---|---:|---:|---|---:|---|
| wfd | 0 | - | 0 / 0 | - | False |
| ra | 0 | - | 0 / 0 | - | False |

## V6: TET

| reference | pairs | median change | wins / losses | Holm p | significant |
|---|---:|---:|---|---:|---|
| wfd | 0 | - | 0 / 0 | - | False |
| ra | 0 | - | 0 / 0 | - | False |

## V4: TAT equivalence with ra (+-2 %)

pairs 0, median ratio -, TOST Holm p -, equivalent False

## Supported

V2: True, V3: False, V4: False, V6: False

## Secondary

| metric | cell | first vs reference | pairs | effect | Holm p | significant |
|---|---|---|---:|---:|---:|---|
| violated | cv00-lowloc50 | ra-cgb vs wfd | 120 | -0.1820 | 5.79e-17 | True |
| inflation | cv00-lowloc50 | ra-cgb vs wfd | 0 | - | - | False |
| violated | cv00-lowloc50 | ra-cgb vs ra | 120 | -0.1667 | 1.55e-17 | True |
| inflation | cv00-lowloc50 | ra-cgb vs ra | 0 | - | - | False |
| violated | cv20-lowloc50 | ra-cgb vs wfd | 120 | -0.1546 | 3.98e-14 | True |
| inflation | cv20-lowloc50 | ra-cgb vs wfd | 0 | - | - | False |
| violated | cv20-lowloc50 | ra-cgb vs ra | 120 | -0.1333 | 6.02e-16 | True |
| inflation | cv20-lowloc50 | ra-cgb vs ra | 0 | - | - | False |
| violated | all | cgb vs wfd | 240 | -0.1226 | 3.58e-27 | True |
| inflation | all | cgb vs wfd | 0 | - | - | False |
| tet | all | cgb vs wfd | 0 | - | - | False |

## Runs that met every deadline (met / measured)

| cell | wfd | cgb | ra | ra-cgb |
|---|---|---|---|---|
| cv00-lowloc50 u040 | 0/24 | 0/24 | 0/24 | 0/24 |
| cv00-lowloc50 u045 | 0/24 | 0/24 | 0/24 | 0/24 |
| cv00-lowloc50 u050 | 0/24 | 0/24 | 0/24 | 0/24 |
| cv00-lowloc50 u055 | 0/24 | 0/24 | 0/24 | 0/24 |
| cv00-lowloc50 u060 | 0/24 | 0/24 | 0/24 | 0/24 |
| cv20-lowloc50 u040 | 0/24 | 2/24 | 3/24 | 0/24 |
| cv20-lowloc50 u045 | 0/24 | 0/24 | 0/24 | 0/24 |
| cv20-lowloc50 u050 | 0/24 | 0/24 | 0/24 | 0/24 |
| cv20-lowloc50 u055 | 0/24 | 0/24 | 0/24 | 0/24 |
| cv20-lowloc50 u060 | 0/24 | 0/24 | 0/24 | 0/24 |
