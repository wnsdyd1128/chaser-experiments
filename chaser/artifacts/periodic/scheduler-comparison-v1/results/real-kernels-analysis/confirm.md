# Confirming the pre-run check (pre-registered; experiment 44 or 45)

118 sets judged; left out for a failed run: {'real-kernels-v1': 2}

## Hypotheses

- **H1** AUC for CHASER meeting every deadline: RF 0.981 vs D 0.901, difference +0.081 (95 % +0.031..+0.136), p 0.0010, Holm 0.0020 -> **supported**
  - reported: RF vs D + M +0.008 (95 % -0.007..+0.025), AUC D + M 0.973
- **H2** false accepts 16 of 112 accepted (14.3%, one-sided 95 % bound 20.9%) -> **not met**
- **H3** successful sets only with RF 0, only with D + M 0, McNemar p 1.0000, Holm 1.0000 -> **not supported**
- **H4** (secondary) Global/Clustered choices 0: saved 0, wrong switches 0, p 1.0000
- RF as the main method (H1, H3 supported and H2 met): **False**

## Outcomes (success / false accept / false reject / true reject)

| group | sets | CHASER met | any config met | RF | static D + M | always CHASER | RF status P / G-C / rejected / deferred |
|---|---:|---:|---:|---|---|---|---|
| all | 118 | 96 | 103 | 96 / 16 / 0 / 6 | 96 / 22 / 0 / 0 | 96 / 22 / 0 / 0 | 112 / 0 / 6 / 0 |
| real-kernels-v1 | 118 | 96 | 103 | 96 / 16 / 0 / 6 | 96 / 22 / 0 / 0 | 96 / 22 / 0 / 0 | 112 / 0 / 6 / 0 |
| real-kernels-v1 0.4 | 24 | 24 | 24 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 |
| real-kernels-v1 0.475 | 23 | 23 | 23 | 23 / 0 / 0 / 0 | 23 / 0 / 0 / 0 | 23 / 0 / 0 / 0 | 23 / 0 / 0 / 0 |
| real-kernels-v1 0.55 | 24 | 24 | 24 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 | 24 / 0 / 0 / 0 |
| real-kernels-v1 0.625 | 23 | 16 | 19 | 16 / 6 / 0 / 1 | 16 / 7 / 0 / 0 | 16 / 7 / 0 / 0 | 22 / 0 / 1 / 0 |
| real-kernels-v1 0.7 | 24 | 9 | 13 | 9 / 10 / 0 / 5 | 9 / 15 / 0 / 0 | 9 / 15 / 0 / 0 | 19 / 0 / 5 / 0 |

Decision time per set: median 0.48 s, max 0.68 s.
