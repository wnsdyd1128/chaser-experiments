# SIM 후속 진단: task/역할 재집계와 최적화 대조

기준: 2026-09-28 01:15 UTC. [기존 실험 점검](EXPERIMENT-AUDIT.md)의 후속 기록이다.
이 결과는 진단용이며 본 데이터셋이나 RF label로 사용하지 않는다.

## 기존 raw의 task별 재집계

`l1-set-pressure-v1`의 12개 G/C/P raw를 `load_batch(prepared, batch)`로 다시
검증했다. 각 실행은 20 warm-up + 180 measured jobs/task, 조건당 정책별 1회다.
아래 task 차이는 각 task의 **평균 job CPU**에서 `(G-P)/P`로 계산했다. Response는
nominal release부터 completion까지이며 TAT의 cohort span과 다른 지표다.

| 조건 | G/P 총 TET | task별 평균 CPU 차이 최소 / 중앙 / 최대 | task별 평균 response 차이 최소 / 최대 | task TET 차이의 양 / 음 / 순합 (ms) |
|---|---:|---:|---:|---:|
| N16 spaced | 0.51% | -1.99 / 0.61 / 2.04% | -59.68 / 157.77% | +7.037 / -2.566 / +4.471 |
| N16 compact | 2.38% | -0.19 / 2.78 / 4.02% | -58.55 / 162.32% | +20.719 / -0.101 / +20.619 |
| N20 spaced | 0.46% | -2.32 / 0.22 / 2.86% | -57.86 / 232.68% | +9.889 / -4.834 / +5.056 |
| N20 compact | 1.80% | -0.92 / 1.77 / 4.61% | -58.19 / 214.04% | +20.623 / -0.994 / +19.629 |

어느 조건에서도 task별 평균 CPU의 G/P 격차가 5%를 넘지 않았다. Spaced 조건은
양·음 task TET 차이가 상쇄됐다. Response는 task별 실행 순서와 대기 영향도 받아
범위가 넓지만, 그것만으로 cache miss를 추론할 수 없다. 관측 최대 job CPU는
G/C/P 각각 N16 compact에서 323.048/318.908/308.332 µs, N20 compact에서
326.328/323.863/314.092 µs였다. 최대 response는 각각
1501.947/1453.635/1395.831 µs와 1884.275/1838.755/1758.163 µs였다.
관측 최대는 WCET/WCRT 보장이 아니다.

## False-sharing의 역할별 재집계

동일 주기 5·25·100 ms 정식 실행은 각 주기마다 공유/독립 라인 × G/C/P × 5회,
총 30회 모두 `status=ok`로 종료됐다. 90개의 raw를 `load_batch()`로 재검증해
manifest, protocol, 1600 measured jobs, 200 cohorts, TET/TAT가 저장된
summary와 일치함을 확인했다. 5회는 각각 새 simulator 프로세스지만 모든 조건에서
TET/TAT가 반복마다 동일했다. 아래 역할별 값은 5회 중앙값이다.

| 주기 | 라인 | G/P 총 TET | G/P 총 TAT | Reader G/P TET | Writer G/P TET |
|---:|---|---:|---:|---:|---:|
| 5 ms | 공유 | 4.72% | 9.90% | 3.32% | 6.21% |
| 5 ms | 독립 | 6.74% | 21.81% | 10.88% | 3.27% |
| 25 ms | 공유 | 4.75% | 9.70% | 3.34% | 6.24% |
| 25 ms | 독립 | 6.46% | 21.59% | 10.27% | 3.27% |
| 100 ms | 공유 | 4.75% | 9.57% | 3.40% | 6.18% |
| 100 ms | 독립 | 6.34% | 21.53% | 10.22% | 3.08% |

독립 라인에서도 정책 격차가 나타나며 오히려 G/P TAT 격차가 더 크다. 따라서 이
수치로 공유 라인의 cache invalidation을 정책 격차의 원인으로 확정할 수 없다.
Reader/Writer 작업은 generic private-load 진단과도 다르다. 500 ms 정식 실행은
이 기준 시각에 30회 중 24회 완료했고 전체 종료 기록은 아직 없다.

## O0/O2 × sweeps 대조군

새 실험은 N16 compact, 2 KiB/task, 64개 byte load/sweep, 공통 주기 4 ms,
20 warm-up + 20 measured jobs/task로 계획했다. 조합은 sweeps 4/48 ×
workload.c 최적화 O0/O2의 네 조건이다. `init.c`와 `probe.c`는 모두 O0로 둔다.
주기·task 배치·배열 정렬은 고정한다. Sweeps를 바꾸면 CPU 이용률도 달라지므로
조건 간 정책 격차 차이를 cache 효과만으로 해석하지 않는다. 독립 P의 U 측정은
후속 통제 단계다.

설정·실행기: `.cache/configs/periodic-memory-gap/l1-set-pressure/optimization_sweeps.py`.
준비 결과: `.cache/periodic-memory-gap-v1/l1-optimization-sweeps-v1/`.
네 조건 모두 G/C/P ELF 생성과 manifest 검증을 통과했다. 같은 sweeps의
O0/O2는 `source/workload.c`와 실제 링크된 배열 배치가 byte 단위로 같다.
`compile_commands.json`은 workload만 O2이고 init/probe는 O0임을 확인했다.
기존 N16 compact·48 sweeps의 workload 소스와 새 O0 소스도 같다.
SPARC disassembly에서 O2 `task_job_t00`은 64회/48회 반복 속의 `ldub`를
유지하면서 내부 반복의 stack load/store가 제거됐다. Checksum 기대값은
4/48 sweeps 각각 256/3072다. 정식 SIM 시간 결과는 아직 기록하지 않았다.

```sh
PYTHONPATH=. python3 -u .cache/configs/periodic-memory-gap/l1-set-pressure/optimization_sweeps.py --prepare-only
PYTHONPATH=. DISPLAY=165.246.44.80:90.0 python3 -u .cache/configs/periodic-memory-gap/l1-set-pressure/optimization_sweeps.py --run-only
```

첫 명령은 이미 수행했고 output이 존재하므로 재현 시 새 `--output` 경로를 사용한다.
실제 실행은 같은 결과 디렉터리의 `supervisor.sh`를 백그라운드로 시작했다.
기존 500 ms false-sharing sweep의 `supervisor.exit`를 기다린 다음 네 조건을
순서대로 실행한다. `supervisor.log`, `supervisor.pid`, `supervisor.exit`로 상태와
종료 코드를 기록한다. 재실행은 새 output이 필요하다. 완료된 각 batch는 실행기가
`load_batch()`로 다시 검증하고 task별 평균·관측 최대 CPU/response를 저장한다.
