# Experiment 28: CAAS Algorithm 1 against the CLS steps (pre-registered)

alpha 0.05; unplaceable runs count as not meeting every deadline (deployability) and stay out of paired tests.

## Primary steps

| type | step | first vs second | metric | pairs | effect | Holm p | supported |
|---|---|---|---|---:|---|---:|---|
| small | L1 | cls-a1 vs caas | violated | 77 | +0.0000 (fewer 0 / 0) | - | False |
| small | L2 | cgb vs cls-a1 | deployable | 252 | only first 135 / only second 0 | 3.2e-40 | True |
| small | L3 | ra-cgb vs cgb | tat | 125 | -0.7% (89 / 32) | 8.9e-08 | True |
| small | L4 | ra-cgb vs caas | violated | 77 | -0.1333 (fewer 76 / 0) | 2.2e-13 | True |
| big | L1 | cls-a1 vs caas | violated | 143 | +0.0000 (fewer 24 / 14) | 0.022 | False |
| big | L2 | cgb vs cls-a1 | deployable | 142 | only first 3 / only second 6 | 1 | False |
| big | L3 | ra-cgb vs cgb | tat | 75 | -0.1% (41 / 23) | 0.037 | True |
| big | L4 | ra-cgb vs caas | violated | 144 | +0.0000 (fewer 24 / 28) | 1 | False |

## Secondary

| type | step | first vs second | metric | pairs | effect | Holm p | significant |
|---|---|---|---|---:|---|---:|---|
| small | L1 | cls-a1 vs caas | inflation | 1 | +0.0% (0 / 0) | - | False |
| small | L1 | cls-a1 vs caas | tet | 1 | +0.0% (0 / 0) | - | False |
| small | L1 | cls-a1 vs caas | deployable | 252 | only first 0 / only second 0 | 1 | False |
| small | L2 | cgb vs cls-a1 | inflation | 1 | +27.1% (0 / 1) | - | False |
| small | L2 | cgb vs cls-a1 | tet | 1 | +22.5% (0 / 1) | - | False |
| small | L2 | cgb vs cls-a1 | violated | 77 | -0.1333 (fewer 76 / 0) | 7.5e-13 | True |
| small | L3 | ra-cgb vs cgb | inflation | 125 | -0.2% (69 / 52) | 0.24 | False |
| small | L3 | ra-cgb vs cgb | tet | 125 | -0.1% (68 / 53) | 0.055 | False |
| small | L3 | ra-cgb vs cgb | violated | 252 | +0.0000 (fewer 39 / 44) | 1 | False |
| small | L4 | ra-cgb vs caas | inflation | 1 | +25.3% (0 / 1) | - | False |
| small | L4 | ra-cgb vs caas | tet | 1 | +22.3% (0 / 1) | - | False |
| small | L4 | ra-cgb vs caas | deployable | 252 | only first 131 / only second 0 | 1.6e-38 | True |
| small | S1 | cls-a1-cal vs caas | violated | 28 | +0.0000 (fewer 0 / 6) | 0.28 | False |
| small | S2 | cls-a1-cal vs cls-a1 | deployable | 252 | only first 0 / only second 1 | 1 | False |
| big | L1 | cls-a1 vs caas | inflation | 80 | -9.2% (45 / 4) | 4.7e-08 | True |
| big | L1 | cls-a1 vs caas | tet | 80 | +0.0% (37 / 12) | 0.015 | False |
| big | L1 | cls-a1 vs caas | deployable | 143 | only first 2 / only second 4 | 1 | False |
| big | L2 | cgb vs cls-a1 | inflation | 75 | +0.0% (26 / 18) | 1 | False |
| big | L2 | cgb vs cls-a1 | tet | 75 | +0.0% (35 / 9) | 0.24 | False |
| big | L2 | cgb vs cls-a1 | violated | 142 | +0.0000 (fewer 3 / 24) | 0.018 | False |
| big | L3 | ra-cgb vs cgb | inflation | 75 | +0.0% (36 / 28) | 1 | False |
| big | L3 | ra-cgb vs cgb | tet | 75 | +0.5% (21 / 43) | 0.45 | False |
| big | L3 | ra-cgb vs cgb | violated | 143 | +0.0000 (fewer 12 / 18) | 1 | False |
| big | L4 | ra-cgb vs caas | inflation | 75 | -8.6% (61 / 11) | 2.3e-06 | True |
| big | L4 | ra-cgb vs caas | tet | 75 | -2.8% (45 / 27) | 0.04 | True |
| big | L4 | ra-cgb vs caas | deployable | 144 | only first 2 / only second 9 | 0.52 | False |
| big | S1 | cls-a1-cal vs caas | violated | 142 | +0.0769 (fewer 9 / 74) | 2e-09 | False |
| big | S2 | cls-a1-cal vs cls-a1 | deployable | 143 | only first 0 / only second 33 | 4.4e-09 | False |

## Placed / met every deadline / violated jobs, small

| cell | wfd | cgb | ra | ra-cgb | caas | cls-a1 | cls-a1-cal |
|---|---|---|---|---|---|---|---|
| cv00-low50/u0450 | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 17/0/18 (10.2%) | 17/0/18 (10.2%) | 8/0/18 (12.8%) |
| cv00-low50/u0475 | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 14/0/18 (15.0%) | 14/0/18 (15.0%) | 5/0/18 (17.1%) |
| cv00-low50/u0500 | 18/17/18 (0.3%) | 18/17/18 (0.3%) | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 7/0/18 (18.2%) | 7/0/18 (18.2%) | 1/0/18 (20.0%) |
| cv00-low50/u0525 | 18/9/18 (3.5%) | 18/12/18 (2.8%) | 18/12/18 (3.1%) | 18/15/18 (1.4%) | 1/0/18 (20.0%) | 1/0/18 (20.0%) | 0/0/18 |
| cv00-low50/u0550 | 18/0/18 (14.9%) | 18/2/18 (11.8%) | 18/1/18 (11.5%) | 18/2/18 (9.4%) | 0/0/18 | 0/0/18 | 0/0/18 |
| cv00-low50/u0575 | 18/0/18 (21.5%) | 18/0/18 (16.7%) | 18/0/18 (17.0%) | 18/0/18 (15.6%) | 0/0/18 | 0/0/18 | 0/0/18 |
| cv00-low50/u0600 | 18/0/18 (26.7%) | 18/0/18 (21.2%) | 18/0/18 (23.6%) | 18/0/18 (18.8%) | 0/0/18 | 0/0/18 | 0/0/18 |
| cv20-low50/u0450 | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 17/1/18 (10.6%) | 17/1/18 (10.6%) | 8/0/18 (13.1%) |
| cv20-low50/u0475 | 18/17/18 (0.3%) | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 18/18/18 (0.0%) | 13/0/18 (17.3%) | 13/0/18 (17.3%) | 5/0/18 (14.3%) |
| cv20-low50/u0500 | 18/17/18 (0.7%) | 18/17/18 (0.3%) | 18/15/18 (1.4%) | 18/15/18 (1.4%) | 7/0/18 (20.3%) | 7/0/18 (20.3%) | 1/0/18 (27.3%) |
| cv20-low50/u0525 | 18/9/18 (5.2%) | 18/13/18 (3.1%) | 18/8/18 (6.2%) | 18/10/18 (4.7%) | 1/0/18 (23.7%) | 1/0/18 (23.7%) | 0/0/18 |
| cv20-low50/u0550 | 18/0/18 (11.8%) | 18/3/18 (12.3%) | 18/0/18 (15.4%) | 18/0/18 (14.7%) | 0/0/18 | 0/0/18 | 0/0/18 |
| cv20-low50/u0575 | 18/0/18 (18.7%) | 18/0/18 (18.0%) | 18/0/18 (21.2%) | 18/0/18 (22.6%) | 0/0/18 | 0/0/18 | 0/0/18 |
| cv20-low50/u0600 | 18/0/18 (26.4%) | 18/0/18 (26.4%) | 18/0/18 (29.6%) | 18/0/18 (26.5%) | 0/0/18 | 0/0/18 | 0/0/18 |

## Placed / met every deadline / violated jobs, big

| cell | wfd | cgb | ra | ra-cgb | caas | cls-a1 | cls-a1-cal |
|---|---|---|---|---|---|---|---|
| cv00-big25/u0300 | 18/15/18 (4.2%) | 17/14/17 (1.5%) | 18/15/18 (2.4%) | 18/16/18 (1.0%) | 18/16/18 (0.7%) | 18/16/18 (0.7%) | 18/9/18 (6.6%) |
| cv00-big25/u0350 | 18/13/18 (3.8%) | 18/12/18 (3.1%) | 18/12/18 (5.9%) | 18/12/18 (2.8%) | 18/12/18 (3.8%) | 18/12/18 (2.8%) | 18/6/18 (10.1%) |
| cv00-big25/u0400 | 18/9/18 (9.7%) | 18/8/18 (6.2%) | 18/7/18 (10.1%) | 18/8/18 (6.9%) | 18/9/18 (7.3%) | 18/8/18 (4.9%) | 18/4/18 (14.6%) |
| cv00-big25/u0450 | 18/5/18 (18.8%) | 18/1/18 (12.8%) | 18/4/18 (18.8%) | 18/1/18 (12.2%) | 18/4/18 (13.2%) | 18/4/18 (8.3%) | 17/2/18 (15.7%) |
| cv20-big25/u0300 | 18/14/18 (4.4%) | 18/14/18 (2.1%) | 18/14/18 (3.4%) | 18/14/18 (2.0%) | 18/15/18 (2.5%) | 18/14/18 (2.1%) | 18/10/18 (7.0%) |
| cv20-big25/u0350 | 18/13/18 (4.9%) | 18/13/18 (3.4%) | 18/12/18 (7.1%) | 18/11/18 (5.1%) | 18/11/18 (5.7%) | 18/11/18 (3.8%) | 18/9/18 (12.1%) |
| cv20-big25/u0400 | 18/8/18 (11.9%) | 18/9/18 (9.6%) | 18/8/18 (10.3%) | 18/9/18 (8.0%) | 18/9/18 (10.4%) | 18/9/18 (8.0%) | 18/5/18 (17.9%) |
| cv20-big25/u0450 | 18/5/18 (26.7%) | 18/7/18 (12.9%) | 18/7/18 (16.2%) | 18/6/18 (15.2%) | 18/8/18 (13.3%) | 17/8/17 (11.0%) | 17/4/18 (17.3%) |

## Isolated share per role (placeable runs)

- small caas: high 0/617, low 626/626
- small cls-a1: high 0/617, low 626/626
- small cls-a1-cal: high 6/216, low 216/216
- big caas: big 320/520, high 0/1784
- big cls-a1: big 520/520, high 0/1784
- big cls-a1-cal: big 510/510, high 215/1754
