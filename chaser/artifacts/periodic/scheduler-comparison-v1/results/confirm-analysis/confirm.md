# Experiment 44: confirming the pre-run check (pre-registered)

357 sets judged; left out for a failed run: {'confirm-big-v1': 1, 'confirm-mem-v1': 2}

## Hypotheses

- **H1** AUC for CHASER meeting every deadline: RF 0.982 vs D 0.746, difference +0.236 (95 % +0.187..+0.288), p 0.0000, Holm 0.0000 -> **supported**
  - reported: RF vs D + M +0.022 (95 % +0.011..+0.035), AUC D + M 0.960
- **H2** false accepts 2 of 193 accepted (1.0%, one-sided 95 % bound 3.2%) -> **met**
- **H3** successful sets only with RF 35, only with D + M 1, McNemar p 0.0000, Holm 0.0000 -> **supported**
- **H4** (secondary) Global/Clustered choices 10: saved 2, wrong switches 0, p 0.5000
- RF as the main method (H1, H3 supported and H2 met): **True**

## Outcomes (success / false accept / false reject / true reject)

| group | sets | CHASER met | any config met | RF | static D + M | always CHASER | RF status P / G-C / rejected / deferred |
|---|---:|---:|---:|---|---|---|---|
| all | 357 | 218 | 262 | 191 / 2 / 69 / 95 | 157 / 5 / 100 / 95 | 218 / 139 / 0 / 0 | 183 / 10 / 164 / 0 |
| confirm-small-v1 | 120 | 65 | 70 | 59 / 0 / 11 / 50 | 39 / 0 / 31 / 50 | 65 / 55 / 0 / 0 | 57 / 2 / 61 / 0 |
| confirm-small-v1 0.45 | 24 | 24 | 24 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 |
| confirm-small-v1 0.4875 | 24 | 24 | 24 | 24 / 0 / 0 / 0 | 14 / 0 / 10 / 0 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 |
| confirm-small-v1 0.525 | 24 | 16 | 20 | 11 / 0 / 9 / 4 | 1 / 0 / 19 / 4 | 16 / 8 / 0 / 0 | 9 / 2 / 13 / 0 |
| confirm-small-v1 0.5625 | 24 | 1 | 2 | 0 / 0 / 2 / 22 | 0 / 0 / 2 / 22 | 1 / 23 / 0 / 0 | 0 / 0 / 24 / 0 |
| confirm-small-v1 0.6 | 24 | 0 | 0 | 0 / 0 / 0 / 24 | 0 / 0 / 0 / 24 | 0 / 24 / 0 / 0 | 0 / 0 / 24 / 0 |
| confirm-big-v1 | 119 | 73 | 93 | 63 / 1 / 29 / 26 | 49 / 1 / 43 / 26 | 73 / 46 / 0 / 0 | 62 / 2 / 55 / 0 |
| confirm-big-v1 0.3 | 24 | 23 | 24 | 21 / 0 / 3 / 0 | 16 / 0 / 8 / 0 | 23 / 1 / 0 / 0 | 21 / 0 / 3 / 0 |
| confirm-big-v1 0.3375 | 24 | 21 | 24 | 17 / 1 / 6 / 0 | 14 / 1 / 9 / 0 | 21 / 3 / 0 / 0 | 17 / 1 / 6 / 0 |
| confirm-big-v1 0.375 | 24 | 12 | 21 | 11 / 0 / 10 / 3 | 9 / 0 / 12 / 3 | 12 / 12 / 0 / 0 | 10 / 1 / 13 / 0 |
| confirm-big-v1 0.4125 | 23 | 10 | 13 | 8 / 0 / 5 / 10 | 7 / 0 / 6 / 10 | 10 / 13 / 0 / 0 | 8 / 0 / 15 / 0 |
| confirm-big-v1 0.45 | 24 | 7 | 11 | 6 / 0 / 5 / 13 | 3 / 0 / 8 / 13 | 7 / 17 / 0 / 0 | 6 / 0 / 18 / 0 |
| confirm-mem-v1 | 118 | 80 | 99 | 69 / 1 / 29 / 19 | 69 / 4 / 26 / 19 | 80 / 38 / 0 / 0 | 64 / 6 / 48 / 0 |
| confirm-mem-v1 0.45 | 24 | 24 | 24 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 |
| confirm-mem-v1 0.4875 | 23 | 23 | 23 | 23 / 0 / 0 / 0 | 23 / 0 / 0 / 0 | 23 / 0 / 0 / 0 | 23 / 0 / 0 / 0 |
| confirm-mem-v1 0.525 | 23 | 19 | 23 | 15 / 1 / 7 / 0 | 14 / 3 / 6 / 0 | 19 / 4 / 0 / 0 | 12 / 4 / 7 / 0 |
| confirm-mem-v1 0.5625 | 24 | 12 | 20 | 5 / 0 / 15 / 4 | 6 / 1 / 13 / 4 | 12 / 12 / 0 / 0 | 3 / 2 / 19 / 0 |
| confirm-mem-v1 0.6 | 24 | 2 | 9 | 2 / 0 / 7 / 15 | 2 / 0 / 7 / 15 | 2 / 22 / 0 / 0 | 2 / 0 / 22 / 0 |

Decision time per set: median 0.44 s, max 0.66 s.
