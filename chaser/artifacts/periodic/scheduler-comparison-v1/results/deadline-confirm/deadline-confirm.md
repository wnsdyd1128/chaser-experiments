# Experiment 27: pre-registered deadline confirmation

Candidate ra-cgb against ra, wfd; alpha 0.05.

## V1: static L2 demand verdicts

| type | verdict | cases | correct | lower bound | P runs met | random runs met |
|---|---|---:|---:|---:|---:|---:|
| small | ok | 88 | 88 | 0.967 | 352 / 352 | 146 / 264 |
| small | miss | 84 | 84 | 0.965 | 0 / 336 | 0 / 252 |
| small | uncertain | 80 | - | - | 165 / 320 | 7 / 240 |
| small | supported | True | | | | |
| big | ok | 143 | 66 | 0.391 | 313 / 572 | 130 / 429 |
| big | miss | 0 | 0 | - | 0 / 0 | 0 / 0 |
| big | uncertain | 0 | - | - | 0 / 0 | 0 / 0 |
| big | supported | False | | | | |

## V2: violated jobs (ra-cgb - reference, ratio of released jobs)

| type | reference | pairs | violating | fewer ra-cgb / ref | median difference | only ra-cgb / only ref met | Holm p | significant |
|---|---|---:|---:|---|---:|---|---:|---|
| small | ra | 252 | 130 | 64 / 27 | +0.0000 | 10 / 4 | 0.019 | False |
| small | wfd | 252 | 135 | 74 / 35 | -0.0317 | 15 / 6 | 0.018 | True |
| big | ra | 144 | 73 | 36 / 19 | +0.0000 | 6 / 8 | 0.011 | False |
| big | wfd | 144 | 74 | 40 / 23 | -0.0413 | 7 / 12 | 0.0057 | True |

## V3: worst memory-task inflation

| type | reference | pairs | median change | wins / losses | Holm p | significant |
|---|---|---:|---:|---|---:|---|
| small | ra | 122 | -15.2% | 109 / 13 | 9.4e-20 | True |
| small | wfd | 117 | -16.1% | 116 / 1 | 2.5e-20 | True |
| big | ra | 71 | -20.0% | 65 / 6 | 3.1e-12 | True |
| big | wfd | 70 | -17.5% | 62 / 8 | 1.5e-11 | True |

## V4: TAT equivalence with ra

| type | pairs | median ratio | TOST Holm p | equivalent |
|---|---:|---:|---:|---|
| small | 122 | 0.9962 | 8.6e-07 | True |
| big | 71 | 1.0288 | 0.99 | False |

## V6: TET (amendment registered before any result was read)

| type | reference | pairs | median change | wins / losses | Holm p | significant |
|---|---|---:|---:|---|---:|---|
| small | ra | 122 | -6.3% | 111 / 11 | 3.1e-19 | True |
| small | wfd | 117 | -7.1% | 103 / 14 | 4.5e-17 | True |
| big | ra | 71 | -7.6% | 68 / 3 | 7.1e-13 | True |
| big | wfd | 70 | -5.1% | 62 / 8 | 1.6e-09 | True |

## Secondary

| metric | type | cell | reference | pairs | effect | Holm p | significant |
|---|---|---|---|---:|---:|---:|---|
| violated | small | cv00 | ra | 126 | -0.0500 | 0.0091 | True |
| inflation | small | cv00 | ra | 66 | -13.5% | 2.9e-10 | True |
| violated | small | cv00 | wfd | 126 | -0.0714 | 2.9e-08 | True |
| inflation | small | cv00 | wfd | 61 | -12.7% | 2.1e-10 | True |
| violated | small | cv20 | ra | 126 | +0.0000 | 0.39 | False |
| inflation | small | cv20 | ra | 56 | -20.6% | 3.3e-09 | True |
| violated | small | cv20 | wfd | 126 | +0.0000 | 0.39 | False |
| inflation | small | cv20 | wfd | 56 | -18.6% | 1.1e-09 | True |
| violated | small | all | random | 252 | -0.0978 | 6.9e-34 | True |
| inflation | small | all | random | 21 | -8.2% | 0.0058 | True |
| violated | big | cv00 | ra | 72 | +0.0000 | 0.033 | False |
| inflation | big | cv00 | ra | 34 | -19.9% | 1.4e-06 | True |
| violated | big | cv00 | wfd | 72 | +0.0000 | 0.081 | False |
| inflation | big | cv00 | wfd | 36 | -14.2% | 7.1e-07 | True |
| violated | big | cv20 | ra | 72 | -0.0099 | 0.39 | False |
| inflation | big | cv20 | ra | 37 | -20.5% | 4.7e-10 | True |
| violated | big | cv20 | wfd | 72 | -0.0495 | 0.081 | False |
| inflation | big | cv20 | wfd | 34 | -21.7% | 2e-06 | True |
| violated | big | all | random | 144 | -0.1168 | 3.7e-20 | True |
| inflation | big | all | random | 23 | -7.9% | 9.2e-05 | True |

## G/C where every deterministic P missed

| type | cases | G met | C2 met | either |
|---|---:|---:|---:|---:|
| small | 108 | 2 | 0 | 2 |
| big | 53 | 2 | 0 | 2 |

## Runs that met every deadline, small (violated jobs / released for P)

| cell | wfd | cgb | ra | ra-cgb | random | g | c2 |
|---|---|---|---|---|---|---|---|
| cv00-low50/u0450 | 18/18 (0.0%) | 18/18 (0.0%) | 18/18 (0.0%) | 18/18 (0.0%) | 41/54 (2.2%) | 18/18 | 18/18 |
| cv00-low50/u0475 | 18/18 (0.0%) | 18/18 (0.0%) | 18/18 (0.0%) | 18/18 (0.0%) | 23/54 (5.2%) | 17/17 | 18/18 |
| cv00-low50/u0500 | 17/18 (0.3%) | 17/18 (0.3%) | 18/18 (0.0%) | 18/18 (0.0%) | 7/54 (9.4%) | 14/18 | 14/18 |
| cv00-low50/u0525 | 9/18 (3.5%) | 12/18 (2.8%) | 12/18 (3.1%) | 15/18 (1.4%) | 1/54 (14.9%) | 6/18 | 9/18 |
| cv00-low50/u0550 | 0/18 (14.9%) | 2/18 (11.8%) | 1/18 (11.5%) | 2/18 (9.4%) | 0/54 (21.6%) | 0/18 | 0/18 |
| cv00-low50/u0575 | 0/18 (21.5%) | 0/18 (16.7%) | 0/18 (17.0%) | 0/18 (15.6%) | 0/54 (25.9%) | 0/18 | 0/18 |
| cv00-low50/u0600 | 0/18 (26.7%) | 0/18 (21.2%) | 0/18 (23.6%) | 0/18 (18.8%) | 0/54 (31.8%) | 0/18 | 0/18 |
| cv20-low50/u0450 | 18/18 (0.0%) | 18/18 (0.0%) | 18/18 (0.0%) | 18/18 (0.0%) | 42/54 (2.7%) | 18/18 | 18/18 |
| cv20-low50/u0475 | 17/18 (0.3%) | 18/18 (0.0%) | 18/18 (0.0%) | 18/18 (0.0%) | 24/54 (6.9%) | 18/18 | 17/18 |
| cv20-low50/u0500 | 17/18 (0.7%) | 17/18 (0.3%) | 15/18 (1.4%) | 15/18 (1.4%) | 13/54 (11.5%) | 17/18 | 16/18 |
| cv20-low50/u0525 | 9/18 (5.2%) | 13/18 (3.1%) | 8/18 (6.2%) | 10/18 (4.7%) | 2/54 (18.4%) | 11/18 | 14/18 |
| cv20-low50/u0550 | 0/18 (11.8%) | 3/18 (12.3%) | 0/18 (15.4%) | 0/18 (14.7%) | 0/54 (24.2%) | 2/18 | 0/18 |
| cv20-low50/u0575 | 0/18 (18.7%) | 0/18 (18.0%) | 0/18 (21.2%) | 0/18 (22.6%) | 0/54 (29.9%) | 0/18 | 0/18 |
| cv20-low50/u0600 | 0/18 (26.4%) | 0/18 (26.4%) | 0/18 (29.6%) | 0/18 (26.5%) | 0/54 (35.9%) | 0/18 | 0/18 |

## Runs that met every deadline, big (violated jobs / released for P)

| cell | wfd | cgb | ra | ra-cgb | random | g | c2 |
|---|---|---|---|---|---|---|---|
| cv00-big25/u0300 | 15/18 (4.2%) | 14/17 (1.5%) | 15/18 (2.4%) | 16/18 (1.0%) | 31/54 (6.7%) | 15/18 | 14/17 |
| cv00-big25/u0350 | 13/18 (3.8%) | 12/18 (3.1%) | 12/18 (5.9%) | 12/18 (2.8%) | 19/54 (11.5%) | 13/18 | 13/18 |
| cv00-big25/u0400 | 9/18 (9.7%) | 8/18 (6.2%) | 7/18 (10.1%) | 8/18 (6.9%) | 9/54 (19.6%) | 7/18 | 8/18 |
| cv00-big25/u0450 | 5/18 (18.8%) | 1/18 (12.8%) | 4/18 (18.8%) | 1/18 (12.2%) | 4/54 (30.6%) | 3/18 | 4/18 |
| cv20-big25/u0300 | 14/18 (4.4%) | 14/18 (2.1%) | 14/18 (3.4%) | 14/18 (2.0%) | 33/54 (6.8%) | 15/18 | 14/18 |
| cv20-big25/u0350 | 13/18 (4.9%) | 13/18 (3.4%) | 12/18 (7.1%) | 11/18 (5.1%) | 20/54 (15.6%) | 11/17 | 11/18 |
| cv20-big25/u0400 | 8/18 (11.9%) | 9/18 (9.6%) | 8/18 (10.3%) | 9/18 (8.0%) | 12/54 (22.8%) | 9/18 | 7/18 |
| cv20-big25/u0450 | 5/18 (26.7%) | 7/18 (12.9%) | 7/18 (16.2%) | 6/18 (15.2%) | 4/54 (31.4%) | 8/18 | 5/18 |
