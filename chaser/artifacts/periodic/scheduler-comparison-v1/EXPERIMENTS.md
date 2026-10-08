# 스케줄링 아키텍처 비교 실험 — 실험별 설계와 재현 방법

laysim(GR740)에서 Global, Clustered (1+3), Clustered (1+1+2), Partitioned EDF의
TET/TAT 격차가 task set 구성에 따라 어떻게 달라지는지 측정한 실험들의 문서다.
실험마다 개요, 목적, 변인(조작·통제·종속), 실험 방법, 재현 명령, 결과 파일을 적는다.
결과 수치와 결론은 이 문서에 담지 않는다. 결과는 `results/<실험>/`에 있다. 예외로 5절에는
트래픽 조건의 의미를 설명하려고 핵심 결과를 함께 적었다.

| # | 실험 | 스크립트 | 출력(`.cache/`) | 결과 묶음(`results/`) |
|---|---|---|---|---|
| 1 | 주기 분포 | `period-distribution/` | `period-distribution-v2` | `period-distribution` |
| 2 | release-aware P′ 대조 | `period-distribution/{placement,control}.py` | `period-distribution-cohort-v2` | `release-aware-control` |
| 3 | CLS 분포 | `cls-distribution/` | `cls-distribution-v1` | `cls-distribution` |
| 4 | 캐시 친화성 | `cache-affinity/` | `cache-affinity-v2`(O0), `cache-affinity-o2-v1`(O2) | `cache-affinity-o0`, `cache-affinity-o2` |
| 5 | CLS 양극단 | `cls-bimodal/` | `cls-bimodal-v2`, 확장 `cls-bimodal-v2-ext` | `cls-bimodal` |
| 6 | 부하 수준 | `cls-bimodal/`(`--design load-level`) | `load-level-v1` | `load-level` |
| 7 | task별 U 불균형 | `cls-bimodal/`(`--design u-imbalance`) | `u-imbalance-v1` | `u-imbalance` |
| 8 | CLS × 작업 집합 | `footprint/` | `l2-probe-v1`, `footprint-v1` | `footprint` |
| 9 | 고부하·큰 task | `high-load/` | `high-load-v1` | `high-load` |
| 10 | Partitioned 배치 불가 영역 | `high-load/`(`--design infeasible`) | `infeasible-v1` | `infeasible` |
| 11 | 고부하 + 메모리 경합 | `high-load/`(`--design memory`, `mem_check.py`) | `memory-load-v1` | `memory-load` |
| 12 | 배치 불가 영역의 G 대 C(설계 실패) | `high-load/`(`--design g-vs-c`) | `g-vs-c-v1` | `g-vs-c` |
| 13 | 배치 불가 영역의 G 대 C, 재설계 | `high-load/`(`--design g-vs-c-sync`) | `g-vs-c-sync-v1` | `g-vs-c-sync` |
| 16 | Feature 사전 점검(실험 5–9 재분석, 시뮬레이션 없음) | `feature-precheck/` | `feature-precheck-v1` | `feature-precheck` |
| 17 | 다요인 배치 정책 비교(P-first 후보 배치) | `policy-mix/` | `policy-mix-v1` | `policy-mix` |
| 18 | CLS 기준 묶음 배치(17의 같은 set) | `policy-mix/`(`--design policy-mix-cls`) | `policy-mix-cls-v1` | `policy-mix-cls` |
| 19 | 주기 분포 × 메모리 구성의 배치 경계 | `policy-mix/`(`--design policy-boundary`) | `policy-boundary-v1` | `policy-boundary` |
| 20 | task 수(12–20) × 메모리 압박 | `policy-mix/`(`--design task-count`) | `task-count-v1` | `task-count` |
| 21 | 작은 작업 집합의 저-CLS task × 주기 분포 × task 수 | `policy-mix/`(`--design small-memory`) | `small-memory-v1` | `small-memory` |
| 22 | 실험 1·2의 task 수 12–20 재실행 | `period-distribution/{tc_taskset,tc_run}.py` | `period-taskcount-v1`, `period-taskcount-cohort-v1` | `period-taskcount`, `period-taskcount-cohort` |
| 23 | CLS 분포·다양성 × 주기 분포 × task 수 | `policy-mix/`(`--design cls-spread`) | `cls-spread-v1` | `cls-spread` |
| 24 | 작은 작업 집합의 저-CLS task × 부하(탐색) | `policy-mix/`(`--design small-memory-load`) | `small-memory-load-v1` | `small-memory-load` |
| 25 | 접근 패턴 때문에 CLS가 낮은 task(L1 충돌 miss, 21절과 같은 set) | `policy-mix/`(`--design conflict-cls`, `conflict_calibrate.py`) | `conflict-calibration-v1`, `conflict-cls-v2`(v1은 게이트에서 멈춤) | `conflict-calibration`, `conflict-cls` |
| 26 | 무작위 배치 기준선(21·20·23절, 확장 24·25·19·17절의 set) | `policy-mix/`(`--design random-*`) | `random-small-memory-v1`, `random-task-count-v1`, `random-cls-spread-v1` | `random-small-memory`, `random-task-count`, `random-cls-spread` |
| 27 | 마감 위반 확증 실험(사전 등록, 새 set) | `policy-mix/`(`--design deadline-small`, `deadline-big`, `deadline_analysis.py`) | `deadline-small-v1`, `deadline-big-v1`, `deadline-confirm-v1` | `deadline-small`, `deadline-big`, `deadline-confirm` |
| 28 | CAAS 대비 단계별 비교(27절의 set, 사전 등록) | `policy-mix/`(`--design deadline-small-caas`, `deadline-big-caas`, `algorithm1.py`, `ca_table.py`, `ladder_analysis.py`) | `deadline-small-caas-v1`, `deadline-big-caas-v1`, `deadline-ladder-v1` | `ca-csrd`, `deadline-small-caas`, `deadline-big-caas`, `deadline-ladder` |

---

## 0. 모든 실험에 공통인 사항

### 0.1 플랫폼과 스케줄링 아키텍처

- 시뮬레이터: laysim GR740(`laysim-gr740-cli`), 4코어. 캐시 모델은
  `rtems/baseline/cache.yaml`: 코어별 L1D 16 KiB 4-way, 공유 L2 2 MiB 4-way,
  줄 32 B, 지연 L1 1 / L2 12 / 메모리 120 cycle. RTEMS tick 1 ms.
- 스케줄러는 모두 RTEMS EDF SMP이며 스케줄러 인스턴스와 코어 배정만 다르다.

| 이름 | 스케줄러 인스턴스(코어 집합) | task의 소속 |
|---|---|---|
| Global | {0,1,2,3} 하나 | 모든 코어에서 실행·이동 가능 |
| Clustered (1+3) | {0}, {1,2,3} | P 배치의 코어가 0이면 {0}, 아니면 {1,2,3} |
| Clustered (1+1+2) | {0}, {1}, {2,3} | P 코어 0→{0}, 1→{1}, 2·3→{2,3} |
| Partitioned | 코어마다 하나 | 설정의 `core` 필드에 고정 |

Clustered의 소속은 같은 설정의 Partitioned 코어 배정에서 정해진다. 그래서
"P 배치"를 바꾸면 Clustered도 함께 바뀐다(실험 2·3·5에서 쓰임).

### 0.2 workload와 task

- task는 16개. 모두 같은 순간에 첫 release(위상 0)하고, deadline = 주기다.
- task마다 전용 `volatile uint8_t` 배열을 32 B 간격(한 줄에 한 번)으로 읽는다.
  배열은 1로 초기화한다. job은 읽은 값의 합(= load 횟수)을 반환하고, 런타임이
  job마다 이 체크섬을 검증한다.
- job 본체 `kernel_<id>`는 `ape.inline`, 래퍼 `task_job_<id>`는 `ape.analyze`로
  표시되어 YARDA가 job 단위로 분석한다.
- 패턴: `cyclic`(배열 전체를 S회 순회)과 `hot-cold`(hot H줄을 R회 순회한 뒤
  cold 영역을 1회 순회하는 것을 S회 반복).

### 0.3 측정 지표(측정 계약 v3)

- **TET**: 측정 구간 모든 job의 CPU 시간 합. job CPU는
  `rtems_rate_monotonic_get_status`의 "지난 주기 이후 실행 시간"을 job 전후로 읽은 차이다.
- **TAT**: release cohort(명목 release 시각이 정확히 같은 job들)마다
  (마지막 완료 − 첫 시작)을 구해 합한 값. 일반적인 turnaround time이 아니다.
- **response time 합**: Σ(완료 − release).
- warm-up job은 모두 제외한다. deadline miss, 체크섬 불일치, release 불일치 등이
  있으면 그 run은 `execution_status = failed`이고 통계에서 빠진다.
- **단독 U**: Partitioned 빌드에서 task 하나만 활성화해(`chaser_mode = i+1`)
  돌린 뒤, 측정 job CPU 평균 ÷ 주기로 구한다.

### 0.4 통계

- laysim은 결정적이므로 통계 단위는 **무작위 task set**이다(셀당 20개).
  모든 set을 모든 아키텍처로 돌려 짝지은 비교를 한다.
- 셀 안: set별 상대 격차 (X_a − X_b) / X_b에 양측 Wilcoxon 부호순위 검정을 하고,
  (지표, 쌍)마다 셀들에 걸쳐 Holm 보정(α = 0.05)을 한다. 중앙값의 95% bootstrap CI는
  10,000회, 시드 0으로 구한다.
- 셀 간: set 번호가 같으면 모든 조건에서 같은 표준정규 난수를 쓴다(공통 난수).
  그래서 set을 블록으로 Friedman 검정과 Page 추세 검정을 한다(CV > 0 셀만).
- 분산이 0인 조건(예: 주기 CV 0)은 가능한 set이 하나뿐이라 set 1개만 돌린다.

### 0.5 공통 통제 변인

플랫폼과 캐시 구성, EDF, task 16개, 코어 4개, 동시 첫 release, 1 ms tick,
측정 계약 v3, 데이터 초기값 1, RTEMS·측정 코드 -O0.
실험이 바꾸지 않는 한 workload -O0, 배열 32 B 정렬.

### 0.6 실행 방식

- laysim은 run 하나에 코어 1개를 쓰고, 동시에 최대 84개, 시작 간격 1초로 돌린다
  (`period-distribution/run.py`의 `run_specs`, `launch_gate`).
- 같은 출력 폴더로 다시 실행하면 완료된 run은 건너뛴다. run header가 없는 run은
  `*.aborted-N`으로 옮기고 다시 돌린다.
- `supervisors/*.sh`는 실제로 쓴 단계 순서다. 경로 `W=/workspace/experiments/chaser`는
  새 환경에 맞게 바꾼다. 원래 실행은 실험 1–4 스크립트를 `.cache/configs/…`의 사본으로
  돌렸고, 그 사본은 저장소의 파일과 같다.

### 0.7 재현 준비

1. **환경**: README의 "재현 환경"과 `results/environment.json`(도구 해시). 결과를 수치까지
   같게 재현하려면 laysim 바이너리와 RTEMS 툴체인이 같아야 한다.
2. **코드 사본**: README "코드 기준"의 명령으로 만든다.
   - c2 = 4d03b93 + `c2-topology.patch`, `rtems/baseline/build/yarda` = YARDA a058a454 빌드(고정본 `.cache/yarda-a058a454-build`)
   - c3 = c2 + `cls-bimodal/padding.patch`, YARDA 374b2c9(+ frontend 2670c6e) 빌드
3. **공통 셸 변수**(아래 재현 명령에서 사용):

```sh
W=/path/to/chaser                                   # 저장소 루트
R=$W/artifacts/periodic/scheduler-comparison-v1
C2=$W/.cache/period-distribution-code-4d03b93-c2
C3=$W/.cache/period-distribution-code-4d03b93-c3
export DISPLAY=<laysim이 접속할 X 디스플레이> PYTHONUNBUFFERED=1
```

명령은 코드 사본 디렉터리를 현재 디렉터리로 두고 `PYTHONPATH=<사본>`으로 실행한다.

4. **빌드 산출물 복구**: 끝난 실험 출력의 실행 파일과 목적 파일은 2026-10-03에 지웠다(README
   "빌드 산출물 정리와 복구", 출력마다 `pruned-builds.jsonl`). 새로 처음부터 재현할 때는 해당되지 않는다.
   있는 출력의 원시 로그를 다시 읽는 단계(각 실행기의 `summarize`·`stats` 전 집계, 2절이 읽는 1절 출력)는
   먼저 `python3 $R/prepared_builds.py restore <출력>`으로 복구한다.

---

## 1. 주기 분포

### 개요
utilization이 모두 같은 task 16개의 주기를 정규분포에서 뽑고, 평균과 분산을 바꿔 가며
네 아키텍처의 TET/TAT를 비교한다.

### 목적
task set 안에서 주기가 다양해질수록(CV 증가) 아키텍처 간 TET/TAT 격차가 통계적으로
유의하게 생기는지, 평균 주기 μ가 그 격차에 영향을 주는지 확인한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 평균 주기 μ ∈ {20, 50, 80, 100, 500} ms; 주기 CV ∈ {0, 0.1, 0.2, 0.3}; 아키텍처 4종 |
| 통제 변인 | task U = 0.125(코어당 명목 0.5); workload cyclic 64줄(2 KiB), O0; job CPU 모델 5.58 µs + 6.044 µs × sweep으로 sweep 수를 정해 U를 맞춤; 주기 = (μ/10) × d(d는 180의 약수) 격자로 로그 반올림; 정규분포 ±3σ 자르기; 공통 난수(시드 20260929 + set); warm-up과 측정이 각각 180 × (μ/10) tick(모든 주기의 배수); P 배치는 주기 순 지그재그(코어마다 주기 순위 그룹별로 1개); 배열은 코어·주기 순으로 연속 배치 |
| 종속 변인 | TET, TAT(주 지표), response time 합, makespan(보조) |
| 조작 확인 | 단독 U(CV 0.3·set 0, μ마다; 게이트 5%) |

### 실험 방법
1. `prepare`: 305개 set(μ 5 × (CV 0: 1 set + CV 0.1–0.3: 20 set × 3))을 만들고
   G/C/P/C2 ELF를 빌드한 뒤 manifest 해시를 고정한다.
2. `u-check`: μ마다 CV 0.3·set 0의 16개 task를 단독 실행해 U 오차가 5% 이내인지 확인한다.
3. `pilot`: 셀마다 set 0을 네 아키텍처로 돌리고, 모두 통과해야 다음 단계로 간다.
4. `full`: 나머지 set을 set 번호 순으로 돌린다(1,220 run).
5. `stats.py`: 셀 검정과 셀 간 검정. `dedup.py`: 격자 반올림으로 같아진 set을 빼고
   다시 검정한다(민감도 분석).

### 재현 명령
```sh
cd $C2 && export PYTHONPATH=$C2
O=$W/.cache/period-distribution-v2
for s in prepare u-check pilot full; do python3 $R/period-distribution/run.py $s --output $O; done
python3 $R/period-distribution/stats.py $O
python3 $R/period-distribution/dedup.py $O
for f in v2_tat_bars v2_absolute_bars v2_gap_bars v2_makespan_bars v2_best_tat; do python3 $R/figures/$f.py; done
```
그림 스크립트는 `$W/.cache/period-distribution-v2`를 읽는다(`--dedup`: 중복 제거판).

### 결과 파일
`results/period-distribution/`: `protocol.json`, `results.jsonl`, `stats.json/md`,
`stats-dedup.json/md`, `results-dedup.jsonl`, `duplicates.json`, 그림(PNG·CSV),
`per-set.jsonl.gz`(set별 설정).

---

## 2. release-aware P′ 대조

### 개요
실험 1의 CV > 0 set 300개를 그대로 쓰고, Partitioned의 코어 배치만 release cohort를
고려한 배치로 바꿔 다시 돌린다.

### 목적
실험 1에서 Global이 Partitioned보다 TAT가 짧았던 이유가 Global의 동적 부하 분산
자체인지, 아니면 Partitioned의 지그재그 배치가 나빴기 때문인지 분리한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | P 코어 배치: 주기 순 지그재그(P, 실험 1) ↔ cohort 부하 하한 최소화(P′). 같은 배치에서 정해지는 Clustered (1+3)′, Clustered (1+1+2)′ |
| 통제 변인 | 실험 1과 같은 set(주기·U·sweep·task 순서·배열 배치 동일, `core` 필드만 다름); 코어당 task 4개 유지; Global은 코어 필드를 쓰지 않으므로 실험 1의 Global 결과를 기준으로 재사용 |
| 종속 변인 | TAT(주 지표), TET, response time 합 |
| 조작 확인 | `g-check`: 셀마다 set 0의 Global을 다시 돌려 TET/TAT가 실험 1과 같은지 확인 |

### 실험 방법
1. `placement.py`: 같은 cohort의 job은 같은 코어에서 직렬로 돌고, U가 같으므로 job CPU는
   주기에 비례한다. 그래서 한 반복 구간의 모든 release 시각에서 "가장 바쁜 코어의 주기 합"을
   더한 값을 목적 함수로 삼아 국소 탐색으로 최소화한다(무작위 재시작 20회, 코어당 4개 유지).
   P′의 목적 함수가 TAT와 같은 방향이라는 점에 주의한다.
2. `prepare`: 실험 1의 설정에서 `core`만 바꿔 빌드한다(소스·배열 배치 동일 확인).
3. `g-check` → `run`(P′, C′, C2′, 900 run) → `summarize`(실험 1의 G/P/C/C2 결과와 합침) → `stats`.

### 재현 명령
```sh
cd $C2 && export PYTHONPATH=$C2
M=$W/.cache/period-distribution-v2; O=$W/.cache/period-distribution-cohort-v2
for s in prepare g-check run summarize stats; do python3 $R/period-distribution/control.py $s --main $M --output $O; done
python3 $R/figures/v2_tat_bars_release_aware.py
```
실험 1이 먼저 끝나 있어야 한다.

### 결과 파일
`results/release-aware-control/`: `protocol.json`, `results.jsonl`(행마다 `ps`/`cs`/`c2s` =
실험 1의 지그재그 결과), `stats.json/md`, `g-check.json`, `per-set.jsonl.gz`.
그림은 `results/period-distribution/figures/v2-tat-bars-release-aware.*`.

---

## 3. CLS 분포

### 개요
주기를 고정하고, task마다 캐시 지역성 지표 CLS(yarda_cpp)를 정규분포에서 뽑아
네 아키텍처와 두 가지 P 배치의 TET/TAT를 비교한다.

### 목적
task 간 캐시 지역성의 분포(평균, 분산)가 아키텍처나 배치에 따라 TET/TAT 차이를
만드는지, 특히 CLS가 비슷한 task를 한 코어에 묶는 배치가 유리한지 확인한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 평균 CLS ∈ {0.3, 0.5, 0.7}; CLS CV ∈ {0, 0.1, 0.2, 0.3}; 주기 ∈ {20, 100} ms(모든 task 공통); P 배치 ∈ {CLS 지그재그, CLS 묶음}; 아키텍처(Global, 두 배치 각각의 Clustered (1+3)·(1+1+2)·Partitioned) |
| 통제 변인 | task U = 0.125; workload hot-cold(hot 64줄 = 2 KiB × R회 + cold 1024줄 = 32 KiB × 1회, S sweep), O0; (R, S)는 보정표에서 선택; 목표 CLS는 ±3σ 자르기와 보정 범위 안에서 가장 가까운 보정 수준으로 양자화; task 순서는 CLS 순이고 두 배치가 소스·배열 배치를 공유; warm-up·측정 job 각 10개; 공통 난수(시드 20260930 + set) |
| 종속 변인 | TET, TAT, task별 job CPU(단독 대비 증가율, 최악 task 증가율) |
| 조작 확인 | YARDA CLS 실현값(`cls.json`, α = 0.5, job을 빈 캐시에서 시작한다고 가정); 단독 U(주기·평균별 CV 0.3·set 0; 게이트 5%) |

### 실험 방법
1. **보정**(`calibrate.py`)
   - `measure`: R 격자의 각 값을 2 sweep·주기 100 ms로 단독 실행해 sweep당 CPU를 잰다.
   - `verify`: 주기마다 선형 모델로 U가 1.5% 이내인 정수 (R, S) 쌍을 모두 만들고,
     단독 실행으로 2% 이내인 쌍만 남긴다.
   - `analyze`: 남은 수준의 CLS를 yarda_cpp로 계산해 `calibration.json`에 저장한다.
2. `prepare`: set마다 두 배치를 빌드하고, 지그재그 빌드를 yarda_cpp로 분석해 실현 CLS를 기록한다.
3. `u-check` → `pilot`(set 0) → `full` → `stats`(주기별 `stats-p020`, `stats-p100`).
   set마다 7개 구성(Global; 두 배치 × Clustered (1+3), Clustered (1+1+2), Partitioned)을
   돌려 366 set × 7 = 2,562 run.

### 재현 명령
```sh
cd $C2 && export PYTHONPATH=$C2
O=$W/.cache/cls-distribution-v1
for s in measure verify analyze; do python3 $R/cls-distribution/calibrate.py $s --output $O/calibration; done
for s in prepare u-check pilot full stats; do python3 $R/cls-distribution/cls_run.py $s --output $O; done
python3 $R/figures/cls_figures.py; python3 $R/figures/cls_worst.py
```
prepare는 set마다 yarda 분석이 순차로 돌아 이 환경에서 약 3시간 걸렸다.

### 결과 파일
`results/cls-distribution/`: `calibration/{calibration,sweeps,sweep-cost}.json`,
`protocol.json`, `results.jsonl`, `isolated-u.json`, `stats-p020/p100.json/md`, 그림,
`per-set.jsonl.gz`(set별 설정과 `cls.json`).

---

## 4. 캐시 친화성 (O0, O2)

### 개요
코어당 작업 집합 크기와 job당 sweep 수를 바꿔, 코어를 옮길 때 L1 내용을 잃는 비용이
드러나는 조건에서 네 아키텍처를 비교한다. workload 최적화 O0와 O2로 각각 돌린다.

### 목적
L1 재사용이 가능한 조건에서 코어에 고정되는 Partitioned가 Global·Clustered보다
유리한지, 그 효과가 TET와 TAT 중 어디에 나타나는지, 최적화 수준에 따라 달라지는지 확인한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 코어당 작업 집합 ∈ {25, 50, 100, 150}% of L1(task당 평균 32/64/128/192줄); job당 sweep ∈ {2, 8, 32}; workload 최적화 ∈ {O0, O2}(별도 실행); 아키텍처 4종 |
| 통제 변인 | task별 줄 수 ±25% 균등 지터(시드 20261001 + set, 모든 조건 공유); 패턴 cyclic; P 배치 task i → 코어 i // 4(코어별 배열 연속); 주기 = U ≤ 0.125를 지키는 가장 짧은 정수 tick(1 tick이면 U ≤ 0.0625), 셀별로 1–5 ms; job CPU 모델 5.58 µs + 93.66 ns × sweep × 줄 수; warm-up·측정 job 각 10개; O2 실행은 O0와 같은 task·주기(`workload.c`만 -O2) |
| 종속 변인 | TET, TAT, task별 job CPU(→ load 1회당 시간과 캐시 페널티), 코어 이동 횟수 |
| 대조 측정 | 빈 job run(주기·아키텍처별 1회: 스케줄링·계측 오버헤드), set 0 단독 실행(task별 기준 CPU) |

### 실험 방법
1. `prepare [--optimization O2]`: 12개 셀 × 20 set을 빌드한다. O2에서는 `workload.c`만
   `-O2`로 컴파일됐는지 compile_commands로 검사한다.
2. `isolated`: 셀마다 set 0의 16개 task를 단독 실행한다(기준 CPU).
3. `pilot`(set 0) → `empty`(빈 job 대조) → `full`(240 set × 4 = 960 run) → `stats`.

### 재현 명령
```sh
cd $C2 && export PYTHONPATH=$C2
for opt in O0 O2; do
  O=$W/.cache/$([ $opt = O0 ] && echo cache-affinity-v2 || echo cache-affinity-o2-v1)
  python3 $R/cache-affinity/aff_run.py prepare --optimization $opt --output $O
  for s in isolated pilot empty full stats; do python3 $R/cache-affinity/aff_run.py $s --output $O; done
  python3 $R/figures/cache_affinity_bars.py $O
done
python3 $R/figures/cache_affinity_per_load.py $W/.cache/cache-affinity-v2 $W/.cache/cache-affinity-o2-v1 $W/.cache/cache-affinity-o2-v1/figures
python3 $R/cache-affinity/lru_check.py $W/.cache/cache-affinity-v2 $W/.cache/cache-affinity-o2-v1   # 사후 분석
```
`lru_check.py`는 job 기록만으로 두 가지를 계산한다.
- **task 단위 재사용 거리:** 같은 코어에서 이 task가 마지막으로 돈 뒤, 다른 task가 건드린 바이트 수다.
- **차가운 첫 sweep의 겹침:** 이 job의 첫 sweep 동안 첫 sweep 중인 다른 코어 수다.

작업 집합이 L1 이상일 때 Partitioned가 불리한 원인을 가리는 데 썼다.

### 결과 파일
`results/cache-affinity-o0/`, `results/cache-affinity-o2/`: `protocol.json`, `results.jsonl`
(task별 job CPU, 코어 이동 횟수 포함), `isolated.json`, `empty.json`, `stats.json/md`, `lru-check.json`,
그림(O2 쪽에 O0·O2 load당 시간 비교 포함), `per-set.jsonl.gz`.

---

## 5. CLS 양극단

### 개요
task set 안에서 CLS가 높은 모드와 낮은 모드 두 극단으로 갈리게 만들고, 낮은 CLS task의
비율과 모드 안의 흩어짐을 바꿔 가며 네 아키텍처와 두 가지 P 배치를 비교한다.
낮은 CLS task의 메모리 트래픽을 높은 CLS task와 맞춘 조건을 따로 둔다.

### 목적
1. CLS가 양극단으로 갈릴 때 아키텍처·배치 사이에 유의한 TET/TAT 격차가 생기는지 확인한다.
2. 그 격차가 CLS(재사용 품질) 때문인지, CLS가 낮은 task가 만드는 메모리 트래픽 때문인지 구분한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 낮은 CLS task 비율 p ∈ {0, 0.25, 0.5, 0.75, 1}; 모드 내 CV ∈ {0, 0.1, 0.2, 0.3}; 트래픽 ∈ {그대로, 맞춤}(맞춤은 v2에서 p = 0.5, 확장 `cls-bimodal-v2-ext`에서 p = 0.25·0.75); 아키텍처: Global, Clustered (1+3)·(1+1+2)(섞음 배치 기준), Partitioned 섞음, Partitioned 묶음(0 < p < 1) |
| 통제 변인 | 모드 중심 CLS 높음 0.90 / 낮음 0.13, CV는 가까운 경계까지의 거리에 적용(높음 = 1 − 0.10(1 + CV·z), 낮음 = 0.08 + 0.05(1 + CV·z), z는 ±3σ에서 자름); 주기 40 ms, task U 0.0625(job 2.5 ms); workload O2; hot-cold(높음: hot 16–256줄 × R + cold 1024줄, S sweep / 낮음: hot H줄 2회 + cold 1024줄); U 미세 조정용 sweep 끝 레지스터 연산(`pad_tail`, job의 8% 이하, 3라운드 이상); 트래픽 맞춤 = 낮은 task의 job당 L1 miss를 높은 모드 중심 수준(±5%)에 맞추고 남는 시간을 load당 레지스터 연산(`pad_rounds`, 3라운드 이상)으로 채움; 공통 난수(시드 20261001 + set: task 순서 순열과 슬롯별 z를 모든 p·CV·트래픽이 공유, 낮은 슬롯은 p에 대해 포함 관계); 두 배치가 소스·배열 배치 공유; warm-up·측정 job 각 10개 |
| 종속 변인 | TET, TAT, 모드별 job CPU 증가율(단독 대비), 코어 이동 횟수, (트래픽 그대로 격차 − 맞춤 격차) |
| 조작 확인 | yarda_cpp CLS가 설계식과 같음(허용 1e-9, 모든 task); job당 L1 miss, IR 명령어 1,000개당 L1 miss(yarda `ir-instructions`); 단독 U(서로 다른 수준마다 1회, 게이트 3%) |

### 트래픽 그대로와 트래픽 맞춤 — 무엇을 했고 어떻게 읽는가

**트래픽**은 task가 공유 L2로 보내는 요청의 양, 곧 **단위 시간당 L1 miss 수**다.
L1에서 놓친 접근만 네 코어가 함께 쓰는 통로를 거쳐 L2로 가므로, 여러 코어가 동시에
요청을 많이 보내면 서로 기다린다(경합).

**CLS와 트래픽은 다르다.** CLS는 접근 중 L1(과 L2)에서 해결되는 **비율**이고,
트래픽은 **개수**다.

> 트래픽(시간당 L1 miss) = 시간당 접근 횟수 × L1 miss 비율

CLS는 이 곱의 뒤쪽(비율)만 알려 준다. 비율이 같아도 접근을 얼마나 자주 하느냐에 따라
miss 개수는 크게 달라진다(불량률이 같아도 생산량이 적으면 불량품이 적은 것과 같다).
보통의 코드와 앞선 CLS 분포 실험(3절)에서는 miss 비율이 높은 task가 쉬지 않고 메모리를
읽어서, 낮은 CLS와 많은 트래픽이 늘 함께 나타났다(상관 −0.99). 두 조건은 이 결합을
인위적으로 끊어 둘을 따로 보기 위한 것이다.

**두 조건에서 한 일.** 바뀌는 것은 낮은 CLS task뿐이고, 높은 CLS task는 두 조건이 같다.
두 조건 모두 sweep마다 hot H줄을 2번, cold 1024줄(32 KiB, L1보다 큼)을 1번 읽는다.
그래서 **접근 패턴과 L1 miss 비율(CLS 약 0.13)이 같다.** job 길이도 2.5 ms로 같다.
다른 것은 2.5 ms를 무엇으로 채우느냐다.

```c
/* 트래픽 그대로: 배열 읽기만으로 채움 */
for (s = 0; s < 33; s++) { hot 2회 읽기; cold 1회 읽기; }      /* load가 쉬지 않고 이어짐 */

/* 트래픽 맞춤: 읽기를 줄이고 load마다 레지스터 계산을 끼움 */
for (s = 0; s < 10; s++)
    배열 읽기마다 { v = data[i]; sum += v;
                    for (k = 0; k < 8; k++) pad = (pad ^ v) * P; }  /* 메모리를 쓰지 않음 */
```

| task | 접근 패턴 | L1 miss 비율(CLS) | job당 접근 | job당 L1 miss | 1 µs당 L1 miss | IR 1,000개당 L1 miss |
|---|---|---|---|---|---|---|
| 높은 CLS | hot 수십–수천 회 + cold 1회 | 약 11%(0.90) | 약 97,000 | 약 10,500 | 약 4 | 약 11 |
| 낮은 CLS, 트래픽 그대로 | hot 2회 + cold 1회 | 약 95%(0.13) | 약 37,000 | 약 35,600 | 약 14 | 약 93 |
| 낮은 CLS, 트래픽 맞춤 | hot 2회 + cold 1회 | 약 95%(0.13) | 약 11,300 | 약 10,800 | 약 4 | 약 14 |

즉 트래픽 맞춤 task는 **캐시에 불친화적인 접근 패턴은 그대로인데, 메모리를 읽는 빈도만
높은 CLS task 수준으로 줄인 task**다. 두 조건의 차이는 "어떻게 읽느냐"가 아니라
"job 시간 중 얼마나 메모리에 매여 있느냐"(memory-bound 대 compute-bound)다.
"트래픽 맞춤은 접근이 적어서 CLS가 낮다"는 뜻이 아니다. 접근 횟수는 비율인 CLS를 바꾸지
않는다. 두 조건 모두 CLS가 낮은 이유는 L1보다 큰 cold 영역을 읽는 같은 패턴 때문이다.

**어떻게 읽는가.** 트래픽 그대로의 낮은 CLS task는 (가) 재사용이 나쁘고(CLS 낮음)
(나) 요청이 많은 두 성질을 함께 가지므로, 그것만으로는 격차의 원인을 가릴 수 없다.
트래픽 맞춤은 (가)는 그대로 두고 (나)만 없앤 조건이다.
- 트래픽 맞춤에서도 격차가 남으면 → CLS(재사용 품질) 자체의 효과다.
- 트래픽 맞춤에서 격차가 사라지면 → 요청이 많은 것(트래픽)의 효과다.

**결과(v2, 낮은 CLS task 8개).** 격차는 트래픽 그대로에서만 나타났다.
- CV 0.1의 TET 중앙값:

  | | Global | Clustered (1+3) | Clustered (1+1+2) | Partitioned 섞음 | Partitioned 묶음 |
  |---|---|---|---|---|---|
  | 트래픽 그대로 | 697 ms | 701 ms | 709 ms | 719 ms | **639 ms** |
  | 트래픽 맞춤 | 454 ms | 455 ms | 452 ms | 451 ms | 458 ms |

- (그대로 격차 − 맞춤 격차)는 Partitioned 묶음 대 섞음의 TET에서 −11.8 ~ −13.8%p였다.
  4개 CV 모두 20/20 set이 같은 방향이고 Holm 보정 후 유의하다.
- 단독 대비 CPU 증가율:
  - 트래픽 그대로: 낮은 CLS task는 섞음 +122%, 묶음 +79%. 묶으면 낮은 CLS task끼리
    같은 코어에서 차례로 돌아 동시에 겹치지 않는다.
  - 트래픽 맞춤: 모든 배치에서 +9–12%.

따라서 **격차를 만든 것은 CLS가 낮다는 것 자체가 아니라, 그런 task가 메모리를 자주 읽어
생기는 트래픽**이다. 스케줄링·배치를 판단하려면 CLS 하나로는 부족하고 접근 빈도를 함께
봐야 한다. 둘을 곱한 "명령어당 L1 miss"가 격차와 더 직접 연결되는 정적 지표다.
경합이 원인이라는 것은 CPU 시간 증가로 추론한 것이며, 버스·L2 경합을 카운터로 측정하지는
않았다.

**확장(p = 0.25·0.75, `cls-bimodal-v2-ext`).** 같은 set 번호로 트래픽 맞춤 셀을 추가해 v2의 트래픽
그대로 셀과 짝지었다(`bi_run.py --design matched-extension --baseline <v2 출력>`).
- (그대로 격차 − 맞춤 격차)는 Partitioned 묶음 대 섞음의 TET에서 p = 0.25일 때 −7.1 ~ −9.0%p,
  p = 0.75일 때 −7.4 ~ −8.7%p였다.
- 모든 CV에서 20/20 set이 같은 방향이고 Holm 보정 후 유의하다.
- 트래픽을 맞추면 섞은 Partitioned 대비 TET 격차는 대부분 ±1% 이내로 줄었다.

따라서 위 해석은 낮은 CLS task 수(4·8·12개)와 상관없이 성립한다.

### 실험 방법
1. **패딩 추가**(`padding.patch`): hot-cold에 `pad_rounds`(load마다 `pad = (pad ^ v) * P`)와
   `pad_tail`(sweep 끝, 누적 합에서 시작)을 추가한다. 최종 `pad` 값은 Python에서 닫힌 식으로
   미리 계산해 두고, 커널이 `sum += pad != 기대값`으로 비교한다. 그래서 체크섬은 바뀌지 않고,
   계산이 틀리면 실행 중 체크섬 검사에서 드러난다.
   - GCC -O2가 짧은 상수 루프를 펼쳐 라운드당 비용이 K에 따라 달라지므로,
     `#pragma GCC unroll 1`을 넣고 라운드 수를 3 이상으로 제한한다.
2. **보정**(`bi_calibrate.py`)
   - `measure`: 세 계열(높음 / 낮음-그대로 / 낮음-맞춤)에서 job 길이가 예산의 40–110%인
     무작위 수준을 적합용 72개, 검증용 36개 만들고, O2로 단독 실행한다.
   - `fit`: job 시간 선형 모델(특징 9개: 기본, sweep, 루프 진입, L1 적중, L2 적중,
     패딩 루프·라운드, tail 루프·라운드)을 맞춘다. 검증 오차 2% 초과나 CLS 설계식과
     yarda_cpp의 불일치가 하나라도 있으면 중단한다. 결과는 `model.json`에 저장한다.
3. **설계**(`bimodal.py`): 모델로 모드별 수준표를 만든다. 자유 정수(높음 R, 낮음-그대로 S,
   낮음-맞춤 K)는 예산을 넘지 않게 내림하고 나머지를 tail로 채운다. 목표 CLS에 가장 가까운
   수준을 고른다. P 배치는 CLS 지그재그(섞음) / CLS 순 연속(묶음, 낮은 task가 앞쪽 코어).
4. `prepare`: 442개 set을 빌드하고 모든 task를 yarda_cpp(hierarchy-rd + ir-instructions)로
   분석해 CLS가 설계식과 같은지 검사한다(`locality.json`).
5. `isolated`: 구조(H, R, S, K, tail)가 같은 task는 단독 실행 시간이 같으므로, 서로 다른
   수준 739개만 단독 실행해 U 3% 게이트를 통과시킨다.
6. `pilot`(set 0, 112 run) → `full`(2,088 run 중 나머지) → `stats`.
   - 트래픽별 셀 검정: `stats-as-is`, `stats-matched`.
   - 양방향 Page 추세 검정.
   - p = 0.5에서 set별 (그대로 격차 − 맞춤 격차) 검정: `stats-traffic-contrast.json`.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
O=$W/.cache/cls-bimodal-v2
for s in measure fit; do python3 $R/cls-bimodal/bi_calibrate.py $s --output $O/calibration; done
for s in prepare isolated pilot full stats; do python3 $R/cls-bimodal/bi_run.py $s --output $O; done
python3 $R/figures/cls_bimodal_bars.py $O
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/cls-bimodal $R/cls-bimodal   # 명세 테스트
```
원래 실행은 보정을 v1 출력(`cls-bimodal-v1/calibration`, 2026-10-05에 지움)에서 하고 v2로 복사했다. 보정 결과는 `results/cls-bimodal/calibration/`에 있다. job 시간
모델은 주기와 무관하므로 결과는 같다.

### 결과 파일
`results/cls-bimodal/`: `calibration/{model,measured}.json`, `protocol.json`, `results.jsonl`
(모드, CLS, L1 miss, 단독 CPU, 구성별 task CPU 포함), `isolated-u.json`, `stats-*.json/md`, 그림,
`per-set.jsonl.gz`(set별 설정과 `locality.json`).

---

## 6. 부하 수준(Utilization)

### 개요
task 구성과 job은 완전히 그대로 두고 주기만 바꿔 코어당 명목 U를 0.125에서 0.5까지 올린다.
부하가 높아질 때 네 아키텍처와 두 가지 P 배치의 TET/TAT, 그리고 deadline을 지키는지를 비교한다.

### 목적
1. 부하가 높아질수록 아키텍처·배치 간 TET/TAT 격차가 커지는지 확인한다.
2. 공동 실행 경합이 job을 늘려(5절 v1에서 최대 2.75배) schedulability를 깨는 부하 수준이
   아키텍처·배치마다 다른지 확인한다. 예: 낮은 CLS task를 묶은 Partitioned가 더 높은 부하까지 버티는가.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 주기 ∈ {80, 40, 30, 20} ms(task U {0.03125, 0.0625, 0.0833, 0.125}, 코어당 명목 U {0.125, 0.25, 0.333, 0.5}); 아키텍처: Global, Clustered (1+3)·(1+1+2)(섞음 배치 기준), Partitioned 섞음, Partitioned 묶음 |
| 통제 변인 | job 길이 2.5 ms(모든 주기에서 같은 수준표, 같은 job 코드); CLS 조건 고정: 높은 CLS 8개(중심 0.90) + 낮은 CLS 8개(중심 0.13), 모드 내 CV 0.1(경계까지 거리에 적용), 트래픽 그대로; workload O2, hot-cold; set 번호가 같으면 모든 주기에서 task 구성이 완전히 같고 주기만 다름(공통 난수, 시드 20261001 + set); 셀당 set 20개; warm-up·측정 job 각 10개(horizon = 주기 20개) |
| 종속 변인 | TET, TAT(deadline miss가 없는 run); schedulable 여부(run에 deadline miss가 있는가); 최대 response time ÷ 주기(완료된 job 기준); 모드별 job CPU 증가율(단독 대비) |
| 조작 확인 | yarda_cpp CLS가 설계식과 같음; 단독 U(job CPU는 주기와 무관하므로 수준마다 1회 실행, U = job CPU ÷ 주기, 게이트 3%); 주기 40 ms 수준은 5절 v2의 "트래픽 그대로, p = 0.5, CV 0.1" 셀과 입력이 같으므로 TET/TAT가 v2와 같아야 함(결정성 확인) |

U를 job 길이로 바꾸지 않고 주기로 바꾼 이유: 주기를 고정하고 job을 늘리면 부하와 job 길이가
함께 바뀐다. job 길이가 바뀌면 고정 스케줄링 비용의 비중(4절)과 job 안의 캐시 동작(sweep 수,
수준 구조)도 달라져 부하 효과와 섞인다. 주기만 바꾸면 job 하나하나가 같으므로 차이를 부하에 돌릴 수 있다.

### 실험 방법
1. 5절과 같은 시간 모델(`calibration/model.json`)과 수준표를 쓴다. job 예산이 2.5 ms로 같으므로
   보정을 다시 하지 않는다.
2. `prepare`: 주기 4개 × set 20개를 빌드하고 모든 task를 yarda_cpp로 분석한다.
3. `isolated`: 서로 다른 수준을 한 번씩 단독 실행하고, 각 set의 주기로 나눠 U를 구한다.
   시작 단계 오류(`arm_phase`)만으로 실패한 수준은 모델 예측 U를 쓴다(5절과 같은 규칙).
4. `pilot`(set 0) → `full`(4 × 20 × 5 = 400 run) → `stats`.
   - pilot은 deadline miss와 시작 단계 오류를 허용하고, 그 밖의 실패에서만 멈춘다.
   - deadline miss가 난 run은 실패로 버리지 않고 schedulable = 아니오로 집계한다.
     deadline miss 뒤에는 job 기록이 끊기므로 TET/TAT는 deadline miss가 없는 run에서만 비교한다.
   - TET/TAT: 주기별로 짝지은 Wilcoxon + Holm, 주기에 대한 Friedman·Page.
   - schedulable 비율: (주기, 구성)별로 집계하고, 구성 쌍마다 exact McNemar 검정(Holm 보정).
   - 최대 response time ÷ 주기: 짝지은 Wilcoxon.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
O=$W/.cache/load-level-v1
mkdir -p $O/calibration && cp $R/results/cls-bimodal/calibration/model.json $R/results/cls-bimodal/calibration/measured.json $O/calibration/   # 5절 보정 결과
for s in prepare isolated pilot full stats; do python3 $R/cls-bimodal/bi_run.py $s --design load-level --output $O; done
python3 $R/figures/level_bars.py $O
```

### 결과 파일
`results/load-level/`: `protocol.json`, `results.jsonl`(구성별 state, 최대 response time ÷ 주기 포함),
`isolated-u.json`, `stats-load-level.json/md`(주기별 셀 검정, schedulable 집계, McNemar, 추세),
그림 `load-level-{tet,tat,response}`(`figures/level_bars.py`), `per-set.jsonl.gz`.

---

## 7. task별 U 불균형

### 개요
코어당 총 U는 고정하고, task별 U를 로그정규분포로 흩뜨려 task 크기가 불균형한 task set을 만든다.
U를 고려하는 배치와 무시하는 배치를 포함한 Partitioned 네 가지와 Global·Clustered를 비교한다.

### 목적
1. task 크기가 불균형할 때 Partitioned의 코어 배치(bin-packing) 손실이 Global의 동적 분산 대비
   얼마나 큰지 확인한다.
2. CLS 기준 배치(경합)와 U 기준 배치(부하)가 충돌할 때 어느 쪽이 유리한지, 둘을 함께 고려한
   배치가 가장 좋은지 확인한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | task U의 CV ∈ {0, 0.25, 0.5, 0.75}(로그정규); 구성: Global, Clustered (1+3)·(1+1+2)(U 균형 배치 기준), Partitioned U 균형, Partitioned CLS 섞음, Partitioned CLS 묶음, Partitioned CLS 묶음 + U 균형 |
| 통제 변인 | 주기 40 ms(모든 task 공통, job 길이 = U_i × 40 ms); 총 U = 1.0(코어당 명목 0.25); CLS 조건은 6절과 같음(높은 8 + 낮은 8, 모드 내 CV 0.1, 트래픽 그대로); U와 CLS 모드는 서로 독립으로 배정; O2, hot-cold; 공통 난수(set 번호마다 U용·CLS용 난수 고정, CV만 크기를 바꿈); 셀당 set 20개; warm-up·측정 job 각 10개 |
| 종속 변인 | TET, TAT; schedulable 여부; 최대 response time ÷ 주기; 코어별 실측 CPU 합의 불균형(최대 ÷ 평균) |
| 조작 확인 | 실현된 U의 CV; yarda_cpp CLS가 설계식과 같음; 단독 U(task별 목표 U 대비, 게이트 3%) |

**U 추출.** 위치(task)마다 z ~ N(0, 1)을 ±2σ에서 자르고, w = exp(σ·z), σ = √ln(1 + CV²)로 둔다.
U_i = 1.0 × w_i ÷ Σw로 합을 맞춘 뒤, job 예산(U_i × 40 ms)을 10 µs 단위로 반올림한다.
±3σ가 아니라 ±2σ에서 자르는 이유는, CV 0.75에서 ±3σ면 task 하나의 U가 평균의 7배
가까이(job 약 15 ms) 나올 수 있기 때문이다. ±2σ면 대략 평균의 0.26–3.8배다.
- 자르기와 task 16개라는 표본 크기 때문에, 실현된 CV(set별 중앙값)는 목표보다 작다:
  0.25 → 0.21, 0.5 → 0.40, 0.75 → 0.60.
- job 예산은 0.52–7.63 ms 범위이고, 서로 다른 예산은 363개다.
- 가장 짧은 job(0.6 ms 안팎)에서는 수준표가 성겨 목표 CLS와의 오차가 최대 약 0.015다.
  실현 CLS는 yarda_cpp로 모든 task를 기록한다.

**Partitioned 배치(모두 코어당 4개).**
- U 균형: U가 큰 task부터, task가 4개 미만인 코어 중 U 합이 가장 작은 코어에 둔다(최악 적합 감소).
- CLS 섞음 / CLS 묶음: 5절과 같은 규칙. U는 보지 않는다.
- CLS 묶음 + U 균형: 낮은 CLS 8개를 코어 0·1에, 높은 CLS 8개를 코어 2·3에 두고, 각 그룹 안에서
  U 균형 규칙을 적용한다.

### 실험 방법
1. **시간 모델 범위 확인**(`bi_calibrate.py extend`): 기존 모델은 job 1.0–2.75 ms로 보정했다.
   - 이 설계가 실제로 쓸 수준 40개를 단독 실행해 예측 오차가 2% 이내인지 확인한다.
     예산 범위(0.52–7.63 ms)에서 고르게 고르고, 높은·낮은 모드 중심을 번갈아 쓴다.
   - 벗어나면 새 표본을 포함해 다시 맞춘다.
   - 실제 결과: 최대 오차 0.41%라 다시 맞추지 않았고, CLS 설계식도 모두 일치했다(`calibration/extend.json`).
2. 설계: task마다 자기 job 예산에 맞춘 수준표에서 목표 CLS에 가장 가까운 수준을 고른다.
3. `prepare` → `isolated`(task별 목표 U 대비 3% 게이트; 시작 단계 오류만 난 수준은 모델 U) →
   `pilot`(set 0, deadline miss 허용) → `full`(4 × 20 × 7 = 560 run) → `stats`.
4. 통계: CV 수준별 짝지은 Wilcoxon + Holm, CV에 대한 Friedman·Page, schedulable 비율은 McNemar.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
O=$W/.cache/u-imbalance-v1
mkdir -p $O/calibration && cp $R/results/cls-bimodal/calibration/model.json $R/results/cls-bimodal/calibration/measured.json $O/calibration/   # 5절 보정 결과
python3 $R/cls-bimodal/bi_calibrate.py extend --output $O/calibration   # v2 보정 폴더는 건드리지 않음
for s in prepare isolated pilot full stats; do python3 $R/cls-bimodal/bi_run.py $s --design u-imbalance --output $O; done
python3 $R/figures/level_bars.py $O
```

### 결과 파일
`results/u-imbalance/`: `calibration/{model,measured,extend}.json`, `protocol.json`, `results.jsonl`
(구성별 state, 최대 response time ÷ 주기, 코어 부하 불균형 포함), `isolated-u.json`,
`stats-u-imbalance.json/md`, 그림 `u-imbalance-{tet,tat,response,core-load}`(`figures/level_bars.py`),
`per-set.jsonl.gz`.

---

## 8. CLS × 작업 집합(L2 용량 경합)

### 개요
task 하나만 보는 CLS로는 잡히지 않는 "동시에 도는 task들의 L2 용량 경합"이 TAT 격차를 만드는지 본다.
특수 task 4개의 CLS 수준과 작업 집합 크기를 2 × 2로 바꾸고, 나머지 12개는 높은 CLS task로 고정한다.

### 배경(사전 측정, `footprint/l2_probe.py`)
- task N개(1–4)를 코어마다 하나씩 두고 같은 크기 배열을 동시에 반복 순회시켰다.
- 32 KiB 배열의 접근당 시간: 68 → 97 → 145 → 193 ns. 2개부터 약 48 ns × N이다.
  laysim의 공유 L2는 요청을 하나씩 처리한다(12 cycle, 250 MHz 가정 시 48 ns).
- 3 MiB 배열(항상 메모리): 약 220 ns × N. 메모리도 하나씩 처리한다.
- 768 KiB 배열: 2개 겹침 97 ns(L2 안), 3개 433 ns(부분적으로 밀려남), 4개 879 ns(완전히 밀려남).
  640 KiB는 4개 겹침에서만 밀려났다.
- 이 때문에 트래픽이 많은 task set의 TAT는 "전체 L2 요청 수 × 48 ns"에 묶인다(5절 데이터와 일치).
  배치·아키텍처가 TAT를 바꾸려면 전체 메모리 처리 시간 자체(L2 miss 수)를 바꿔야 한다.

### 목적
1. 큰 작업 집합 task가 동시에 도는지(아키텍처·배치가 정함)에 따라 TAT 격차가 생기는지 확인한다.
2. 그 격차가 CLS 수준이 아니라 작업 집합 크기에서 나오는지 확인한다.
   같은 CLS·같은 트래픽에서 작업 집합만 바꾸고, 같은 작업 집합에서 CLS만 바꿔 비교한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 특수 task 종류 ∈ {SL, BL, SH, BH}(작업 집합 32 / 768 KiB × CLS 낮음 / 높음); 구성: Global, Clustered (1+3)·(1+1+2)(섞음 배치 기준), Partitioned 섞음(코어마다 특수 task 1개), Partitioned 묶음(특수 task 4개를 코어 0에) |
| 통제 변인 | 모든 task의 단독 job 5.5 ms, 주기 200 ms(task U 0.0275, 코어당 0.11); 배경 task 12개(높은 CLS 중심 0.90, CV 0.1); 같은 CLS 수준의 SL/BL, SH/BH는 job당 load 수가 같고 L1 miss도 같거나 비슷함(SL 73,800 / BL 73,731, SH 52,224 / BH 49,280); workload O2, hot-cold; 공통 난수(set k의 task 위치·배경 CLS를 네 종류가 공유, `bimodal.draws`); warm-up 5 + 측정 10 job; 셀당 set 20개 |
| 종속 변인 | TET, TAT; schedulable 여부; 최대 response time ÷ 주기; 코어 부하 불균형; 특수 job 동시 실행 수(특수 job 하나가 도는 동안 함께 도는 다른 특수 job 수의 평균) |
| 조작 확인 | yarda_cpp CLS = 설계식(SL 0.088, BL 0.059, SH 0.670, BH 0.674); 단독 job 시간(게이트 3%) |

특수 task 모양(job당):

| 종류 | hot | hot 반복 | cold | sweep | 단독 job |
|---|---|---|---|---|---|
| SL | 1줄 | 2 | 1,024줄(32 KiB) | 72 | 5.5 ms |
| BL | 1줄 | 2 | 24,576줄(768 KiB) | 3 | 5.5 ms |
| SH | 64줄 | 31 | 1,024줄 | 48 | 5.5 ms |
| BH | 64줄 | 744 | 24,576줄 | 2 | 5.5 ms |

### 실험 방법
1. `prepare`: 4종류 × 20 set을 두 배치로 빌드하고, 모든 task의 CLS를 yarda_cpp로 확인한다.
2. `isolated`: 서로 다른 수준을 단독 실행해 job 시간을 5.5 ms ± 3%로 확인한다.
3. `pilot`(set 0, 20 run) → `full`(400 run 중 나머지) → `stats`.
4. 통계:
   - 종류별 구성 쌍의 짝지은 Wilcoxon + Holm.
   - **작업 집합 대비**: 같은 set의 (큰 쪽 격차 − 작은 쪽 격차)를 CLS 수준별로 검정.
   - **CLS 대비**: (낮은 쪽 격차 − 높은 쪽 격차)를 작업 집합별로 검정.
   - schedulable 비율은 McNemar로 검정.

### 예상(가설)
- 작은 작업 집합(SL, SH)에서는 5절처럼 TAT 격차가 작다.
- 큰 작업 집합(BL, BH)에서는 특수 task의 겹침에 따라 TAT가 갈린다. Partitioned 묶음은 겹침이 없어 가장 짧고,
  Partitioned 섞음은 코어 4개가 동시에 시작해 겹침이 많아 가장 길 수 있다. Global은 그 중간이다.
- 이 차이가 BL과 BH에서 비슷하면, TAT 격차는 CLS가 아니라 작업 집합 크기에서 나온다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 $R/footprint/l2_probe.py --output $W/.cache/l2-probe-v1
O=$W/.cache/footprint-v1
mkdir -p $O/calibration && cp $R/results/cls-bimodal/calibration/model.json $R/results/cls-bimodal/calibration/measured.json $O/calibration/   # 5절 보정 결과
for s in prepare isolated pilot full stats; do python3 $R/footprint/fp_run.py $s --output $O; done
python3 $R/figures/footprint_bars.py $O
```

### 결과 파일
- `results/l2-probe/`: `probe.json`(크기 × 동시 task 수별 접근당 시간), `per-set.jsonl.gz`.
- `results/footprint/`: `protocol.json`(특수 task 모양 포함), `results.jsonl`(구성별 state, 최대 response time ÷ 주기,
  코어 부하 불균형, 특수 job 동시 실행 수 포함), `isolated-u.json`, `stats-footprint.json/md`(종류별 셀 검정,
  작업 집합·CLS 대비, schedulable 집계), 그림 `footprint-{tet,tat,response,overlap}`, `per-set.jsonl.gz`.

---

## 9. 고부하·큰 task

### 개요
계산 위주 task 16개(L1에 들어가는 cyclic 2 KiB, 실험 1과 같은 O0 커널)로 메모리 경합을 거의 없앤 상태에서,
코어당 부하와 큰 task 포함 여부를 바꿔 Partitioned 배치가 빡빡해질 때 Global·Clustered가 이기는지 본다.

### 목적
1. 지금까지 "정보를 쓴 Partitioned가 Global·Clustered와 같거나 낫다"는 결과가 낮은 부하(코어당 U ≤ 0.5)에서만
   확인됐다. 높은 부하와 큰 task에서도 성립하는지 확인한다.
2. Clustered가 이길 수 있는 영역이 있는지 확인한다. Partitioned는 bin-packing 한계가 있고,
   Global EDF는 큰 task와 작은 task가 섞일 때 약하며, Clustered는 그 중간이다.
3. RF(아키텍처 추천)를 유지할지 판단할 근거를 만든다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 코어당 명목 U ∈ {0.5, 0.7, 0.85}(총 U 2.0 / 2.8 / 3.4); task 크기 ∈ {작은 task만, 큰 task 포함}; 구성 6개: Global, Clustered (1+3)·(1+1+2)(U 균형 배치 기준), Partitioned U 균형(WFD), Partitioned 정보 기반, Clustered (1+3) 정보 기반 |
| 통제 변인 | task 16개, 주기는 {20, 40, 80} ms에서 task마다 무작위(set마다 고정); workload는 cyclic 64줄(2 KiB, O0, L1 상주, 실험 1의 job 모델 5.58 µs + 6.044 µs × sweep); warm-up 2 hyperperiod(160 ms) + 측정 4 hyperperiod(320 ms); 공통 난수(set마다 주기·task 순서·U 비율 고정, 부하 수준은 크기만 바꿈); 셀당 set 20개 |
| 종속 변인 | schedulable 여부(주 지표); 최대 response time ÷ 주기; deadline을 모두 지킨 run의 TET·TAT; 코어 부하 불균형 |
| 조작 확인 | 단독 U(각 셀 set 0의 16개 task, 게이트 3%); 배치별 계획 코어 U(`high_load.core_u`) |

**task U 생성.**
- 작은 task만: 16개의 비율을 대칭 Dirichlet(α = 8)에서 뽑습니다. 가장 높은 부하(총 3.4)에서 모든 task ≤ 0.35, 가장 낮은 부하에서 모든 task ≥ 0.005인 표본만 받습니다.
- 큰 task 포함: 큰 task 2개를 U ~ 균등(0.5, 0.8)에서 뽑고(모든 부하에서 같음), 나머지 14개가 남은 U를 같은 방식으로 나눕니다.
- 순수 UUniFast는 총 U 3.4에서 16개 task의 최댓값이 보통 0.7 안팎이라, "작은 task만" 조건을 만족하는 표본이 사실상 나오지 않아 이 방식으로 바꿨다.

**배치.**
- U 균형(WFD): U가 큰 task부터 가장 덜 찬 코어에 둡니다. 코어당 task 수는 자유입니다.
- Partitioned 정보 기반: WFD에서 시작해 국소 탐색으로 "hyperperiod 안의 release 시점마다 가장 바쁜 코어의 release된 작업량"의 합을 최소화합니다(실험 2 P′의 U 일반화). 코어당 U ≤ 0.95를 지키고, 0.05는 스케줄링 오버헤드 여유입니다.
- Clustered (1+3) 정보 기반: 단일 코어 클러스터(코어 0)에 작은 task를 코어당 평균 U까지 넣고, 큰 task를 포함한 나머지는 3코어 클러스터에서 global EDF로 돌게 합니다.

### 실험 방법
1. `prepare`: 6 셀 × 20 set을 배치 3종으로 빌드한다(소스·배열 배치 동일 확인).
2. `isolated`: 각 셀 set 0의 task 16개를 단독 실행해 U 오차 3% 이내를 확인한다.
   O0 cyclic job 모델은 실험 1에서 이미 검증했다.
3. `pilot`(set 0, 36 run, deadline miss 허용) → `full`(720 run 중 나머지) → `stats`.
4. 통계:
   - schedulable 비율: 셀별 McNemar(Holm 보정).
   - 최대 response time ÷ 주기: 짝지은 Wilcoxon.
   - TET·TAT: 둘 다 deadline을 지킨 set끼리 짝지은 Wilcoxon과 Holm 보정.
   - 부하에 따른 격차 추세: Friedman과 양방향 Page 검정.

### 판단 기준
- 고부하·큰 task 셀에서 Global이나 Clustered가 schedulable 비율 또는 TAT에서 정보 기반 Partitioned를 유의하게 이기면,
  "부하·task 크기·locality로 P와 G/C의 경계를 학습하는" RF의 역할이 성립한다.
- 거기서도 정보 기반 Partitioned가 같거나 이기면, 정보 기반 Partitioned가 지배적이라는 결론이 되어 RF 설계를 재검토한다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
O=$W/.cache/high-load-v1
for s in prepare isolated pilot full stats; do python3 $R/high-load/hl_run.py $s --design high-load --output $O; done
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/high-load $R/high-load   # 명세 테스트
python3 $R/figures/high_load_bars.py $O
```

### 결과 파일
`results/high-load/`: `protocol.json`, `results.jsonl`(구성별 state, 최대 response time ÷ 주기, 계획 코어 U 포함),
`isolated-u.json`, `stats-high-load.json/md`(셀 검정, schedulable 집계와 McNemar, response 검정, 부하 추세),
그림 `high-load-{schedulable,response,tat,tet}-{light,heavy}`, `per-set.jsonl.gz`.

---

## 10. Partitioned 배치 불가 영역

### 개요
9절의 계산 위주 task 구성에서 큰 task 수를 늘려, 어떤 Partitioned 배치로도 코어당 U ≤ 1을 맞출 수 없는
task set을 만든다. 이때 Global과 Clustered 중 무엇이 deadline을 더 잘 지키는지 본다.

### 목적
1. Partitioned를 쓸 수 없는 영역에서 Global과 Clustered (1+3)·(1+1+2)의 schedulability를 비교한다.
   9절에서 Clustered (1+1+2)가 모든 셀에서 deadline을 지켜, 이 영역에서 Global보다 강할 가능성이 보였다.
2. 이 영역에서 G와 C 중 무엇을 고를지가 task set에 따라 달라지는지 확인한다. 달라진다면 정적 판정만으로는
   답할 수 없는 선택이 되어, RF 같은 추천 모델이 역할을 가질 수 있다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 큰 task 수 H ∈ {4, 5, 6}(U ~ 균등(0.51, 0.55], 두 개가 한 코어에 들어가면 1 초과 → H ≥ 5면 배치 불가, H = 4는 대조); 코어당 명목 U ∈ {0.85, 0.95}; 구성 7개: Global, Clustered (1+3)·(1+1+2)(U 균형 배치 기준), Partitioned U 균형, Partitioned 정보 기반, Clustered (1+3)·(1+1+2) 용량 기반 |
| 통제 변인 | 9절과 같음(task 16개, 주기 {20, 40, 80} ms, cyclic 2 KiB O0, warm-up 2 + 측정 4 hyperperiod). 작은 task는 Dirichlet(α = 8) 비율, 가장 높은 부하에서 ≤ 0.35, 가장 낮은 부하에서 ≥ 0.002. 공통 난수(set마다 주기·task 순서·큰 task 6개의 U와 위치 고정, H개만 사용; 작은 task 비율은 H마다 고정, 부하는 크기만 바꿈); **셀당 set 30개** |
| 종속 변인 | schedulable 여부(주 지표); 최대 response time ÷ 주기; deadline을 모두 지킨 run의 TET·TAT |
| 조작 확인 | 계획 코어 U(H ≥ 5에서 Partitioned 두 배치의 가장 바쁜 코어 > 1); 단독 U(각 셀 set 0, 게이트 3%) |

**용량 기반 Clustered.** task를 U 내림차순으로, 넣은 뒤의 "코어당 부하(클러스터 U 합 ÷ 코어 수)"가
가장 낮은 클러스터에 넣는다. (1+3)은 {0}, {1, 2, 3}, (1+1+2)는 {0}, {1}, {2, 3}이다.

### 실험 방법
1. `prepare`: 6 셀 × 30 set을 배치 4종(wfd, informed, c-cap, c2-cap)으로 빌드한다.
2. `isolated`: 각 셀 set 0의 task 16개를 단독 실행해 U 오차 3% 이내를 확인한다.
3. `pilot`(set 0, 42 run, deadline miss 허용) → `full`(1,260 run 중 나머지) → `stats`.
4. 통계:
   - schedulable 비율: 셀별 McNemar(Holm 보정).
   - TET·TAT: 둘 다 deadline을 지킨 set끼리 짝지은 Wilcoxon.
   - 큰 task 수에 따른 격차 추세: Friedman과 양방향 Page 검정.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
O=$W/.cache/infeasible-v1
for s in prepare isolated pilot full stats; do python3 $R/high-load/hl_run.py $s --design infeasible --output $O; done
python3 $R/figures/high_load_bars.py $O
```

### 결과 파일
`results/infeasible/`: `protocol.json`, `results.jsonl`, `isolated-u.json`, `stats-infeasible.json/md`(셀 검정,
schedulable 집계와 McNemar, response 검정, 큰 task 수 추세), 그림 `infeasible-{schedulable,response,tat,tet}-{h4,h5,h6}`,
`per-set.jsonl.gz`.

---

## 11. 고부하 + 메모리 경합

### 개요
트래픽이 많은 task와 적은 task가 섞인 task set에서 코어당 부하를 올리며, 메모리 경합으로 job이 늘어날 때
어느 구성이 먼저 deadline을 놓치는지, 트래픽 묶음 배치가 이를 막는지 본다. 낮은 CLS task의 트래픽을
높은 CLS task 수준으로 맞춘 조건을 경합 없는 대조군으로 둔다.

### 목적
1. 5절(CLS 양극단)에서 본 경합 효과가 부하가 높고 주기가 다양할 때 schedulability로 이어지는지 확인한다.
   5절 v1(주기 20 ms)에서는 명목 코어당 U 0.5에서도 deadline miss가 났다.
2. 8절에서 확인한 "공유 L2가 요청을 하나씩 처리한다"는 구조 아래에서, 배치·아키텍처가 경합으로 인한
   deadline miss를 줄일 수 있는지 확인한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 코어당 명목 U ∈ {0.3, 0.45, 0.6}(단독 실행 기준); 낮은 CLS task의 트래픽 ∈ {그대로, 맞춤}; 구성 5개: Global, Clustered (1+3)·(1+1+2), Partitioned U 균형(WFD, CLS를 보지 않음; Clustered 소속도 이 배치 기준), Partitioned 트래픽 묶음 + U 균형(낮은 CLS를 코어 0·1, 높은 CLS를 코어 2·3, 그룹 안에서 WFD) |
| 통제 변인 | task 16개 = 높은 CLS 8개(중심 0.90) + 낮은 CLS 8개(중심 0.13), 모드 내 CV 0.1, 위치 무작위(`bimodal.targets(0.5, 0.1, k)`); 주기 {20, 40, 80} ms(`hl_set.periods`); task U는 Dirichlet(α = 8) 비율(가장 높은 부하에서 ≤ 0.35, 가장 낮은 부하에서 ≥ 0.005); job 예산 = U × 주기(10 µs 단위), 예산마다 5절의 O2 시간 모델로 수준표를 만들어 목표 CLS에 가장 가까운 수준 선택; workload O2; warm-up 2 + 측정 4 hyperperiod; 공통 난수(set마다 주기·모드·CLS·U 비율 고정, 부하는 크기만, 트래픽은 낮은 CLS 수준 모양만 바꿈); 셀당 set 30개 |
| 종속 변인 | schedulable 여부(주 지표); 최대 response time ÷ 주기; deadline을 모두 지킨 run의 TET·TAT |
| 조작 확인 | 시간 모델 확인(`mem_check.py`: 설계 예산 범위 0.26–23.9 ms에서 고르게 고른 45개 수준을 단독 실행, 오차 2% 이내, yarda_cpp CLS = 설계식); 단독 U(각 셀 set 0, 게이트 3%) |

트래픽 맞춤의 낮은 CLS task 중 일부는 짧은 job에서 수준표가 성겨, 목표 CLS와 최대 0.058 차이가 난다(중앙값 0.0001).

### 실험 방법
1. `mem_check.py`: 시간 모델이 이 설계의 예산 범위에서 맞는지 확인한다(실패하면 중단).
2. `prepare`: 6 셀 × 30 set을 배치 2종으로 빌드한다.
3. `isolated`: 각 셀 set 0의 task 16개를 단독 실행해 U 오차 3% 이내를 확인한다.
4. `pilot`(set 0, 30 run, deadline miss 허용) → `full`(900 run 중 나머지) → `stats`.
5. 통계: schedulable 비율은 셀별 McNemar(Holm 보정)로 검정한다. TET·TAT는 짝지은 Wilcoxon, 부하 추세는 Friedman·Page로 검정한다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
O=$W/.cache/memory-load-v1
python3 $R/high-load/mem_check.py --output $O
for s in prepare isolated pilot full stats; do python3 $R/high-load/hl_run.py $s --design memory --output $O; done
python3 $R/figures/high_load_bars.py $O
```

### 결과 파일
`results/memory-load/`: `model-check.json`(45개 수준, 오차 최대 0.33%), `protocol.json`, `results.jsonl`,
`isolated-u.json`, `stats-memory.json/md`, 그림 `memory-{schedulable,response,tat,tet}-{as-is,matched}`,
`per-set.jsonl.gz`.

---

## 12. 배치 불가 영역의 G 대 C — 설계 실패(모든 run이 deadline miss)

### 개요
10절에서 배치가 불가능할 때 Global과 Clustered의 승자가 task set마다 갈렸다. 10절 데이터에서 그 차이와
관련이 큰 특징이 **큰 task의 주기**였으므로, 이를 조작 변인으로 두고 C가 유리한 조건과 G가 유리한 조건을
의도적으로 만들어 검증한다.

### 10절 데이터에서 찾은 신호
- 큰 task 6개(0.85)에서 Global 성공은 "주기 80 ms인 큰 task 0–2개"일 때 8/17, "3개 이상"일 때 11/13이었다.
  큰 task의 주기가 짧으면 동시 release되는 짧은 구간에 큰 job이 몰리고, global EDF는 이 몰림에 약하다.
- 단일 코어 클러스터에 혼자 둔 큰 task는 주기와 상관없이 U ≤ 1이면 deadline을 지킨다(단일 코어 EDF).
  Clustered (1+1+2)의 2코어 클러스터에 들어간 큰 task가 모두 80 ms면 12/12, 모두 20 ms면 3/8 성공이었다.
- 클러스터의 코어당 U가 1을 넘으면 Clustered는 항상 실패했다(큰 task 6개에서 (1+1+2) 0/30).

### 목적
1. 큰 task 5개·짧은 주기에서 Clustered (1+1+2)가 Global보다 유의하게 낫다(C 유리)는 것을 보인다.
2. 큰 task 6개·긴 주기에서 Global이 Clustered보다 유의하게 낫다(G 유리)는 것을 보인다.
3. 나머지 두 조합(5개·긴 주기, 6개·짧은 주기)을 함께 넣어, 승자가 "큰 task 수 × 큰 task 주기"로 갈리는지 본다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 큰 task 수 ∈ {5, 6}; 큰 task 주기 ∈ {20 ms(모두 짧게), 80 ms(모두 길게)}; 구성 3개: Global, Clustered (1+3) 용량 기반, Clustered (1+1+2) 용량 기반 |
| 통제 변인 | 10절과 같은 생성(코어당 0.85, 큰 task U 0.51–0.55, 작은 task Dirichlet(α = 8), 작은 task 주기는 {20, 40, 80} ms 무작위); **set 번호가 같으면 10절 set과 task U·위치·작은 task 주기가 같고 큰 task 주기만 다름**; 셀당 set 30개 |
| 종속 변인 | schedulable 여부(주 지표); 최대 response time ÷ 주기; deadline을 모두 지킨 run의 TET·TAT |

Partitioned는 배치가 불가능하므로 돌리지 않는다.

### 실험 방법
`prepare`(4 셀 × 30 set × 배치 3종) → `isolated`(각 셀 set 0) → `pilot`(set 0, 12 run) → `full`(360 run 중 나머지) → `stats`.
- 통계: schedulable 비율은 셀별 McNemar(Holm 보정)로 검정한다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
O=$W/.cache/g-vs-c-v1
for s in prepare isolated pilot full stats; do python3 $R/high-load/hl_run.py $s --design g-vs-c --output $O; done
python3 $R/figures/high_load_bars.py $O
```

### 결과: 설계 실패
- 네 셀 모두 세 구성이 30/30 deadline을 놓쳤다(360 run, 모두 `deadline_miss`; 단독 U 게이트는 0.41% 이내로 통과).
- 원인: 큰 task를 모두 **같은 주기**로 만들면서, 큰 job들이 매 주기 동시에 release되었다.
  큰 job은 각각 주기의 절반 넘게 필요하므로(U > 0.5), 한 코어는 한 주기 안에 큰 job을 하나만 끝낼 수 있다.
  큰 job 5–6개가 4개 코어에서 동시에 시작되면, 이 EDF 기반 스케줄러들은 모두 deadline을 지키지 못한다.
- 10절 데이터를 다시 보면, 성공을 가른 것은 주기의 길이가 아니라 **같은 주기를 공유하는 큰 task의 수**였다.
  큰 task 5개(0.85) 기준 Global 성공: 같은 주기 공유 최대 2개면 12/16, 3개면 5/11, 4개면 0/3.
  6개에서는 2개 3/4, 3개 14/21, 4개 2/4, 5개 0/1.
  "긴 주기가 유리하다"는 해석은 잘못이었다. 큰 task 주기가 섞여 release가 엇갈릴수록 유리하다.
- 이 실험은 10절 결과를 보고 세운 가설을 같은 set 번호로 검증하려 한 것이라, 독립적인 확인도 아니었다.

---

## 13. 배치 불가 영역의 G 대 C — 재설계(독립 set)

### 개요
12절의 실패 원인(큰 task를 모두 같은 주기로 만들어 큰 job이 동시에 몰림)을 고쳐, **같은 주기를 공유하는
큰 task 수**를 조작 변인으로 두고, 가설을 만든 10절과 겹치지 않는 **새 난수의 task set**으로 확인한다.

### 사전 등록한 주 가설과 표본 크기
- H1(C 유리): 큰 task 5개, 3개가 같은 주기(몰림)에서 Clustered (1+1+2) 용량 기반이 Global보다 deadline을 더 자주 지킨다.
- H2(G 유리): 큰 task 6개, 엇갈림·몰림 각각에서 Global이 Clustered (1+1+2) 용량 기반보다 더 자주 지킨다.
- 주 검정은 위 세 McNemar 검정이며, 셋에 Holm 보정을 한다. 방향이 가설과 같고 보정 후 p < 0.05일 때만 지지로 본다.
- 셀당 set 수 40: 10절 데이터를 pilot으로 쓴 시뮬레이션에서 H1의 검정력이 n = 30에서 0.91, n = 40에서 0.99,
  H2는 n = 20에서도 1.00이었다(α = 0.05/4).

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 큰 task 수 ∈ {5, 6}; 같은 주기 공유 ∈ {엇갈림(주기마다 최대 2개: 5개 2/2/1, 6개 2/2/2), 몰림(한 주기에 3개: 5개 3/1/1, 6개 3/2/1)}; 어느 주기가 몇 개를 받는지는 set마다 무작위; 구성 3개: Global, Clustered (1+3)·(1+1+2) 용량 기반 |
| 통제 변인 | 10절과 같은 생성 규칙(코어당 0.85, 큰 task U 0.51–0.55, 작은 task Dirichlet(α = 8), 작은 task 주기 {20, 40, 80} ms 무작위, 계산 위주 cyclic O0); **새 시드 20261701**; 같은 set의 엇갈림·몰림은 큰 task 주기만 다름; 셀당 set 40개 |
| 종속 변인 | schedulable 여부(주 지표); 최대 response time ÷ 주기; deadline을 모두 지킨 run의 TET·TAT |

### 실험 방법
1. `prepare`: 4 셀 × 40 set을 배치 3종(wfd, c-cap, c2-cap)으로 빌드한다.
2. `isolated`: 각 셀 set 0의 task 16개를 단독 실행해 U 오차를 확인한다(최대 0.43%).
3. `pilot`(set 0, 12 run) → `full`(480 run 중 나머지) → `stats`.
4. 통계: 주 검정은 위 세 McNemar(Holm 3개). 나머지 쌍(G 대 C(1+3), C(1+3) 대 C(1+1+2))의 McNemar와
   TET·TAT Wilcoxon은 탐색적 결과로 본다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
O=$W/.cache/g-vs-c-sync-v1
for s in prepare isolated pilot full stats; do python3 $R/high-load/hl_run.py $s --design g-vs-c-sync --output $O; done
python3 $R/figures/high_load_bars.py $O
```
주 가설 검정 결과는 `stats-g-vs-c-sync.json`의 `primary_tests`에 있다.

### 결과
480 run, 시작 실패 0. deadline을 모두 지킨 set 수(40개 중):

| 셀 | Global | Clustered (1+3) 용량 | Clustered (1+1+2) 용량 |
|---|---:|---:|---:|
| 큰 task 5, 엇갈림 | 34 | 30 | 31 |
| 큰 task 5, 몰림 | 23 | 30 | 24 |
| 큰 task 6, 엇갈림 | 40 | 7 | 0 |
| 큰 task 6, 몰림 | 24 | 13 | 0 |

- H1 **지지 안 됨**: 큰 task 5·몰림에서 (1+1+2)만 성공 5 set, Global만 성공 4 set(Holm p = 1.0).
- H2 **지지됨**: 큰 task 6에서 Global만 성공이 엇갈림 40 대 0(Holm p = 5.5e-12), 몰림 24 대 0(2.4e-7).
  다만 (1+1+2)의 실패는 구조적으로 예상된 것이다. 단일 코어 클러스터에는 큰 task를 하나씩만 넣을 수 있으므로
  2코어 클러스터에 큰 task가 4개 이상 들어가고, 그 U 합은 4 × 0.51 > 2이다.
- 탐색적 결과(사전 등록 아님):
  - 큰 task 6에서는 Global이 (1+3)보다도 낫다(33 대 0, 13 대 2, 둘 다 Holm p < 0.05).
  - 큰 task 5·몰림에서는 (1+3)만 성공 10 대 Global만 성공 3이다(Holm p = 0.18, 유의하지 않음).
    몰림으로 바꿔도 (1+3)의 성공 수는 30 → 30으로 그대로였다. 반면 Global은 34 → 23,
    (1+1+2)는 31 → 24로 떨어졌다.
  - 둘 다 성공한 set의 TET 차이는 +0.04–0.12%로 실질적으로 없다.
    TAT는 큰 task 5에서 Global이 (1+1+2)보다 4–5% 길다(유의).
- 결론: 배치가 불가능할 때는 클러스터 용량을 넘는 경우(큰 task 6) Global이 확실히 낫다.
  C가 유리한 조건은 이 설계로 확인하지 못했다.

### 결과 파일
`results/g-vs-c-sync/`: `protocol.json`, `results.jsonl`, `isolated-u.json`, `stats-g-vs-c-sync.json/md`(`primary_tests`,
셀별 McNemar, response·TET·TAT 검정), 그림 `g-vs-c-sync-{schedulable,response,tat,tet}`, `per-set.jsonl.gz`.

---

## 14. 폐기하거나 바꾼 설계

2026-10-05에 `.cache` 정리로 `cache-affinity-v1`, `cls-bimodal-v1`(`calibration.failed-unroll-0` 포함), `conflict-cls-v1` 출력을 지웠다.
같은 때 모든 빌드 폴더(`prepared/`)의 waf 라이브러리 사본(`.waf3-*`)도 지웠다. 이 사본은 manifest에 없고 waf를 실행하면 다시 풀린다.
지운 목록은 `.cache/cleanup-2026-10-05.log`에 있다. 아래 표에서 지운 출력의 행은 기록으로만 남는다.

| 출력(`.cache/`) | 내용 | 바꾼 이유 |
|---|---|---|
| `period-distribution-v1` | μ ∈ {20, 80, 320} ms, 격자 기준 20 | 기준 20인 격자가 μ = 50을 담지 못함 → 기준 10·격자 180(v2). 240 run 후 중단 |
| `cls-distribution-v1/calibration` 1차 | R 격자 + 정수 S | 정수 반올림으로 U 오차가 최대 27% → (R, S) 공동 탐색으로 교체 |
| `cache-affinity-v1` | 1 ms 주기에서 코어당 U 0.40 | pilot에서 G/C/C2 deadline miss → 1 ms 주기는 U ≤ 0.0625(v2) |
| `cls-bimodal-v1` | 주기 20 ms, U 0.125 | pilot에서 낮은 CLS task가 많은 셀이 deadline miss(공동 실행 job CPU가 단독의 최대 2.75배) → 같은 job을 주기 40 ms로(v2). pilot 결과는 `results/cls-bimodal-v1-pilot/` |
| `cls-bimodal-v1/calibration.failed-unroll-0` | 패딩 루프 펼침 방지 전 보정 | K ≤ 4 루프가 완전히 펼쳐져 시간 모델 검증 오차 12.8% → pragma와 3라운드 하한 추가 |

---

## 15. 결과 묶음 사용법

- `python3 export_results.py <실험> ...`이 `.cache`의 출력에서 설계 입력과 결과만
  `results/<실험>/`로 복사한다. 다시 만들 수 있는 빌드와 원시 run 로그는 복사하지 않는다.
- 파일 이름은 원래 출력 폴더와 같다. `period-distribution/stats.py`는
  `results/period-distribution/`을 인자로 다시 돌릴 수 있고, `stats.json`은 원본과
  바이트 단위로 같게 나온다. 다른 후처리 스크립트 중에는 `.cache` 경로, 준비된 빌드 또는
  압축 묶음 안의 set별 `configuration.json`을 요구하는 것이 있어 축약 번들만으로는
  재실행할 수 없다. 생성된 그림 PNG·CSV는 번들에 보존한다.
- `per-set.jsonl.gz`는 set별 `configuration.json`(prepare의 입력 그 자체), `cls.json`,
  `locality.json`, `summary.json`을 한 줄씩 담는다. 보정을 다시 하지 않고도 같은 task set을
  다시 빌드할 수 있다.
- `MANIFEST.json`은 복사한 파일의 SHA-256을, `results/environment.json`은 laysim·컴파일러·
  yarda_cpp 바이너리 해시와 Python 패키지 버전을 담는다.
- 재현 명령이 결과 묶음의 파일을 입력으로 쓰는 곳(6–8절의 5절 보정, 18–19절의 시간 모델 검증)은
  `.cache` 원본과 바이트 단위로 같은 파일이다. 반면 2절(1절 출력), 4절의 `lru_check.py`·load당 분석(4절 원시 로그),
  18절의 비교 분석·그림(17절 출력)은 앞 실험의 출력 폴더가 있어야 한다.

---

## 16. Feature 사전 점검 — 끝난 실험 재분석

### 개요
새 시뮬레이션 없이 실험 5–9의 결과 묶음에서 정적 task 정보만으로 feature를 만든다.
그 feature로 RF가 "더 나은 배치·아키텍처"를 고르는지 비교한다.
- 비교 대상은 계획의 RF 입력(R0: CLS 통계 + U 통계 11개)과 이를 넓힌 표현이다.
- 넓힌 표현은 주기, 트래픽·작업 집합 통계, 하드웨어 기준 task 유형의 bag-of-words를 더한다.

상세 설계와 결과는 [`feature-precheck/README.md`](feature-precheck/README.md)에 있다.

### 목적
1. R0로는 구분되지 않는데 결과가 다른 task set 쌍이 실제로 있는지 확인한다. 있다면 넓힌 표현이 그 쌍을 구분하는지 본다.
2. Partitioned 배치 정책 선택(P-first)과 아키텍처 선택에서 표현을 넓히면 TAT regret이 줄어드는지 확인한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 입력 표현 6종(R0, CLP+U, R1–R4); 학습 방식 3종(하드 레이블, 손해 가중치, 선택지별 regret 회귀); 교차 검증 2종(set 번호 단위 10겹, 조건 하나씩 제외) |
| 통제 변인 | 같은 표본과 레이블(측정 TAT 최소, 동률은 TET); 계획의 기준 RF 설정(트리 100, 깊이 제한 없음, max_features sqrt, 튜닝 없음); seed 42–46 |
| 종속 변인 | 고른 선택지의 TAT regret(고른 TAT ÷ 최선 TAT − 1)의 평균·95백분위·최대; 정확도; deadline을 놓친 선택 수; feature가 1% 이내로 같은데 레이블이 다른 set 쌍의 수 |

### 판단 대상
- **placement:** Partitioned 묶음 대 섞음. 실험 5–8의 677 set이다. 실험 6의 40 ms와 실험 7의 U CV 0은 실험 5와 같은 실행이라 뺐다.
- **hl-policy:** Partitioned WFD 대 정보 기반. 실험 9의 120 set이다.
- **hl-family:** Partitioned·Clustered·Global 중 계열별 최선. 실험 9의 120 set이며, deadline을 놓친 구성은 고를 수 없는 선택지로 둔다.

### 재현 명령
```sh
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/feature-precheck $R/feature-precheck   # feature 명세 테스트
python3 $R/feature-precheck/precheck.py --output $W/.cache/feature-precheck-v1 --jobs 6
python3 $R/figures/feature_precheck_bars.py $W/.cache/feature-precheck-v1
python3 $R/export_results.py feature-precheck
```
입력은 `results/`의 결과 묶음만 쓰므로 `.cache`의 원시 출력이 없어도 다시 돌릴 수 있다.

### 결과 파일
`results/feature-precheck/`에는 다음이 있다.
- `protocol.json`(입력 묶음 SHA-256, 설정, 표본 수, 레이블 분포)
- `samples.jsonl`, `results.json`, `predictions.jsonl`, `collisions.json`, `summary.md`
- 스크립트 사본
- 그림 `precheck-*`

---

## 17. 다요인 배치 정책 비교(P-first 후보 배치)

### 개요
P-first 프레임워크의 후보 배치들을 여러 메커니즘이 한 task set 안에 함께 있는 조건에서 비교한다.
메커니즘은 주기 다양성, 트래픽 많은 task, 768 KiB 작업 집합, U 분산, 큰 task다.
- 실험마다 따로 있던 배치 정책을 공통 라이브러리(`policy-mix/placement_lib.py`)로 모았다.
- 트래픽 묶음을 제약으로 둔 release 고려 배치(결합 정책)를 처음 시험한다.

### 목적
1. 결합 정책이 단일 정책(U 균형, 트래픽 묶음, release 고려)보다 나은지 확인한다.
2. 가장 좋은 배치가 task set이나 요인 수준에 따라 달라지는지 확인한다. 달라져야 배치 선택기가 필요하다.
3. 정적 feature로 그 차이를 예측할 수 있는지 확인한다(16절 사전 점검의 RF).
4. Global과 Clustered (1+1+2)가 가장 좋은 Partitioned 배치를 이기는 경우가 있는지 본다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | set마다 여섯 요인을 독립적으로 뽑는다(요인마다 따로 섞어 수준별 개수를 맞춤): 주기 {모두 40 ms, task마다 {20, 40, 80} ms}; 낮은 CLS 32 KiB task 수 {0, 4, 8}; 그 task의 트래픽 {그대로, 맞춤}; 768 KiB task(실험 8 BL 모양) 수 {0, 2, 4}; 가벼운 task U 비율의 Dirichlet α {32, 4}; 큰 task(U ~ 균등(0.5, 0.6), 높은 CLS) {0, 1}. 코어당 명목 U {0.3, 0.45}. 구성 6개: Global, Clustered (1+1+2)(U 균형 배치 기준), Partitioned U 균형 / 트래픽 묶음 + U 균형 / release 고려 / release 고려 + 트래픽 묶음 |
| 통제 변인 | task 16개, 높은 CLS 중심 0.90·낮은 CLS 중심 0.13(모드 내 CV 0.1); job 예산 = U × 주기(10 µs 단위)이고 5절의 O2 시간 모델로 수준을 고른다(768 KiB는 `mix_set.big_level`); workload O2; warm-up 2 + 측정 4 hyperperiod(80 ms); 공통 난수(set k는 두 부하에서 요인·주기·역할·CLS·U 비율을 공유하고, 부하는 가벼운 task의 U만 바꾼다); 배치 탐색 seed는 set마다 고정; 코어당 계획 U 상한 0.95; set 80개 |
| 종속 변인 | 모든 deadline 준수 여부; deadline을 지킨 run의 TAT·TET; 배치별 regret(같은 경우의 가장 좋은 배치 대비 TAT); 최대 response time ÷ 주기; 코어 부하 불균형 |
| 조작 확인 | 시간 모델 검증(`pm_check.py`: 네 종류 task 모양 48개를 단독 실행, 오차 2% 이내, yarda CLS = 설계식); 경우마다 yarda CLS = 계획값(`locality.json`); 단독 U(각 부하 set 0, 게이트 3%) |

**배치 정책**(`placement_lib.py`)은 task를 계획 U, 주기, 트래픽(job 실행 1 µs당 L1 miss)으로만 본다.
- **U 균형(wfd):** U가 큰 task부터 가장 덜 찬 코어에 넣는다.
- **트래픽 묶음 + U 균형(tg):** 트래픽이 많은 task(1 µs당 5.2개 초과, L2 처리 능력의 코어당 몫)를 모은다. 코어당 U 0.95를 넘지 않는 가장 적은 코어에 WFD로 넣고, 나머지 task는 전체 코어에 WFD로 넣는다.
- **release 고려(ra):** WFD에서 출발해 국소 탐색으로, hyperperiod 안 release 시점마다 가장 바쁜 코어의 release된 작업량을 합한 값을 최소화한다. 9절의 정보 기반 배치와 같은 결과를 내며, 회귀 테스트로 확인했다.
- **결합(ra-tg):** tg에서 출발해 ra와 같은 탐색을 한다. 다만 트래픽이 많은 task는 tg가 정한 코어 안에서만 움직인다. 가중치는 쓰지 않는다.

큰 768 KiB task는 sweep을 한 번 이상 해야 하므로, 낮은 부하에서도 예산이 그만큼 되는 task 중에서 고른다. 그래서 주기가 긴 task로 치우친다.

### 실험 방법
1. `pm_check.py`: 시간 모델을 검증한다. 실패하면 중단한다.
2. `prepare`: 160개 경우 × 배치 4종을 빌드한다. 경우마다 yarda_cpp로 task별 CLS를 대조하고 `locality.json`을 남긴다.
3. `isolated`: 각 부하의 set 0에서 task 16개를 단독 실행해 U 오차 3% 이내를 확인한다.
4. `pilot`(set 0, 12 run) → `full`(948 run) → `stats`(셀별 짝지은 Wilcoxon + Holm, schedulability McNemar).
5. `pm_analysis.py`는 다음을 계산한다.
   - 배치별 regret과 승수
   - 결합 대 단일 비교
   - 요인 수준별 분석
   - Global·Clustered (1+1+2) 대 최선 배치
   - 배치 선택 RF(set 단위, 메커니즘 조합 단위 교차 검증)

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
O=$W/.cache/policy-mix-v1
python3 $R/policy-mix/pm_check.py --output $O
for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --output $O; done
python3 $R/policy-mix/pm_analysis.py --output $O
python3 $R/figures/policy_mix_bars.py $O
```

### 결과 파일
`results/policy-mix/`에는 다음이 있다.
- `protocol.json`(set별 요인 포함), `model-check.json`, `results.jsonl`, `isolated-u.json`
- `stats-policy-mix.json/md`, `analysis.json/md`
- 그림 `policy-mix-*`
- `per-set.jsonl.gz`(경우별 설정, `locality.json`, `summary.json`)

---

## 18. CLS 기준 묶음 배치(17절의 같은 set)

### 개요
17절의 160개 경우에 CLS를 기준으로 묶는 Partitioned 배치 두 가지를 더해 돌린다.
17절의 트래픽 기준 배치와 경우별로 짝지어 비교한다. 연구 계획의 배치 지표인 CLS를 P-first 구조 안에서
트래픽과 정면으로 비교하는 첫 실험이다.

### 목적
1. 묶는 기준을 CLS로 바꿨을 때 TAT·TET가 트래픽 기준과 어떻게 달라지는지 확인한다.
2. 두 기준이 갈리는 조건이 어디인지와 그 차이의 크기를 정한다. 트래픽 그대로인 set에서는 낮은 CLS와 많은 트래픽이
   같은 task라 두 기준이 같은 배치를 낸다. 트래픽 맞춤인 set에서는 CLS 기준만 트래픽 적은 낮은 CLS task까지 묶는다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 묶는 기준: CLS(계획 CLS ≤ 0.5) 대 트래픽(17절). 배치 2종: CLS 묶음 + U 균형(cg), CLS 묶음 안의 release 고려(ra-cg). 짝: cg ↔ tg, ra-cg ↔ ra-tg |
| 통제 변인 | 17절과 같은 160개 경우(요인·역할·예산·수준·seed가 같고 설정 생성 함수도 같다. 17절 설정 640개가 바이트 단위로 재현됨을 확인). 묶음 알고리즘은 기준만 다르고 같다(`placement_lib._grouped`). CLS 기준 0.5는 이 설계의 두 모드(약 0.9, 0.13 이하) 사이 어디에 두어도 같은 분할이다. |
| 종속 변인 | 모든 deadline 준수 여부, TAT, TET, 같은 경우의 Partitioned 배치 6종 중 최선 대비 regret |
| 조작 확인 | 경우마다 yarda CLS = 계획값; 단독 U(각 부하 set 0, 게이트 3%); 시간 모델 검증은 task 모양이 같아 17절 결과(`model-check.json`)를 복사; 두 기준이 같은 배정을 내는 경우에는 결과가 같아야 한다(결정성 확인) |

### 실험 방법
1. `prepare`(배치 wfd·cg·ra-cg 빌드, yarda CLS 대조) → `isolated` → `pilot` → `full`(320 run) → `stats`.
2. `cls_compare.py`로 17절 결과와 경우별로 짝짓는다.
   - 같은 배정인 경우: 결과 일치를 확인한다.
   - 배정이 다른 경우: TAT·TET의 짝지은 상대 차이, 승·무·패, Wilcoxon + Holm, deadline miss 수를 낸다.
   - 여섯 배치 중 최선 대비 regret을 낸다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
O=$W/.cache/policy-mix-cls-v1
mkdir -p $O && cp $R/results/policy-mix/model-check.json $O/
for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design policy-mix-cls --output $O; done
python3 $R/policy-mix/cls_compare.py --cls $O --policy-mix $W/.cache/policy-mix-v1
python3 $R/figures/policy_mix_cls_bars.py $O $W/.cache/policy-mix-v1
```

### 결과 파일
`results/policy-mix-cls/`에는 다음이 있다.
- `protocol.json`, `model-check.json`(17절 복사), `results.jsonl`, `isolated-u.json`, `stats-policy-mix-cls.json/md`
- `cls-compare.json/md`
- 그림 `policy-mix-cls-{tat,tet}`
- `per-set.jsonl.gz`

---

## 19. 주기 분포 × 메모리 구성의 배치 경계

### 개요
주기 분포의 크기와 메모리 위주 task의 구성을 함께 단계적으로 바꾸며, 어떤 Partitioned 배치가 이기는지를 본다.
1–2절에서는 주기 분포가 클 때 release 고려 배치가 이겼고, 3·5·7·8절에서는 주기가 하나일 때 CLS 기준 묶음이
이겼다. 하지만 두 조건이 함께 바뀌는 실험은 없었다. 17·18절에서 묶음 규칙이 부하를 한 코어에 몰아넣었던 문제를
고친 부하 균등 CLS 묶음(cgb)을 쓴다.

### 목적
1. (가설 1) 주기 분포가 작고(CV 0, 0.1) 메모리 위주 task가 있으면 부하 균등 CLS 묶음이 release 고려보다 TAT가 짧다.
2. (가설 2) 주기 분포가 크고(CV 0.2, 0.3) 메모리 위주 task가 없으면 release 고려가 U 균형보다 TAT가 짧다.
3. (가설 3) 부하 균등 CLS 묶음 안의 release 고려(결합)가 모든 셀에서 이기는지 확인한다. 모든 셀에서 이기면
   선택기 없이 정책 하나로 충분하다는 결론이고, 지는 셀이 있으면 선택기의 근거가 된다.
4. yarda 정적 feature로 셀마다 다른 승자를 맞힐 수 있는지 확인한다(16절 RF, 셀 단위 교차 검증 포함).
5. TAT를 주 지표로 하되 TET도 같은 방식으로 보고한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | 주기 CV {0, 0.1, 0.2, 0.3}(평균 40 ms, 주기 = 40(1 + CV·z)을 로그 척도로 {20, 24, 30, 40, 48, 60, 80, 120} ms에 맞춤, z는 ±3σ 자른 정규); 낮은 CLS 32 KiB task(트래픽 그대로) 수 {0, 4, 8}; 768 KiB task(실험 8의 BL 모양) 수 {0, 2}. 완전 교차 24개 셀. 배치 4종: U 균형(wfd), 부하 균등 CLS 묶음(cgb), release 고려(ra), 부하 균등 CLS 묶음 안의 release 고려(ra-cgb) |
| 통제 변인 | task 16개, 나머지는 높은 CLS(중심 0.90, 모드 내 CV 0.1); 코어당 명목 U 0.4; task U 비율은 Dirichlet(α = 8); job 예산 = U × 주기, 5절의 O2 시간 모델(768 KiB는 `mix_set.big_level`); workload O2; warm-up 1 + 측정 2 hyperperiod(240 ms); 공통 난수(set k는 모든 셀에서 U 비율·CLS 편차·주기 편차·task 순서를 공유하고, 낮은 CLS 4개는 8개 안에 포함, 768 KiB task 2개는 셀마다 같은 task); 셀당 set 10개; 부하 균등 묶음의 코어 상한 = 평균 코어 부하 × 1.05(묶음의 가장 큰 task보다 작아지지 않음) |
| 종속 변인 | 모든 deadline 준수 여부; deadline을 지킨 run의 TAT·TET; 배치별 regret(같은 경우의 최선 배치 대비) |
| 조작 확인 | 실현 주기 CV(중앙값 0, 0.098, 0.186, 0.258); 경우마다 yarda CLS = 계획값; 단독 U(셀마다 set 0, 게이트 3%); job 예산 0.97–8.65 ms는 17절 시간 모델 검증 범위(0.21–43 ms, 같은 task 모양 종류) 안이라 그 결과를 복사 |

낮은 CLS task는 모두 트래픽도 많다. 그래서 이 실험에서는 CLS 기준과 트래픽 기준이 같은 task를 묶는다.

### 실험 방법
1. `prepare`(240개 경우 × 배치 4종, yarda CLS 대조) → `isolated`(셀마다 set 0) → `pilot`(셀마다 set 0, 96 run)
   → `full`(864 run) → `stats`.
2. `boundary_analysis.py`는 다음을 계산한다.
   - 셀별 배치 비교
   - 가설 1–3 검정(짝지은 상대 차이, Wilcoxon + Holm)
   - 고정 배치의 regret
   - TAT·TET 각각의 배치 선택 RF(set 단위, 셀 단위 교차 검증)

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
O=$W/.cache/policy-boundary-v1
mkdir -p $O && cp $R/results/policy-mix/model-check.json $O/
for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design policy-boundary --output $O; done
python3 $R/policy-mix/boundary_analysis.py --output $O
python3 $R/figures/policy_boundary_bars.py $O
```

### 결과 파일
`results/policy-boundary/`에는 다음이 있다.
- `protocol.json`(셀 정의, 768 KiB task 위치), `model-check.json`(17절 복사), `results.jsonl`, `isolated-u.json`
- `stats-policy-boundary.json/md`, `boundary-analysis.json/md`
- 그림 `policy-boundary-{tat,tet}-low{0,4,8}-big{0,2}`
- `per-set.jsonl.gz`

---

## 20. task 수(12–20) × 메모리 압박

### 개요
1–19절은 모두 task 16개(코어 수 4의 배수)였다. 실무의 task 수는 기능 분해로 정해지며 코어 수와 무관하다.
task 수를 12–20 사이에서 바꾸면서, 메모리 압박이 클 때 CLS 기반 배치가 release 고려 배치를 이기는지 본다.
17·18절에서는 주기가 다른 조건에서도 768 KiB task가 많으면 묶음이 이겼다. 19절은 768 KiB task가 최대 2개라 이 조건을 거의 담지 못했다.
같은 실험에서 Partitioned의 우위가 16개가 아닌 task 수에서도 유지되는지 확인한다.

### 목적
1. 768 KiB task가 전체 U의 25%·50%를 차지할 때, 부하 균등 CLS 묶음과 그 안의 release 고려가 release 고려보다
   TAT·TET·deadline 준수에서 나은지 확인한다.
2. 그 결과가 task 수(12–14, 15–17, 18–20)와 4의 배수 여부에 따라 달라지는지 확인한다.
3. task 수가 적어 나눠 담기가 거칠 때 Global·Clustered (1+1+2)가 최선 Partitioned 배치를 이기는지 확인한다.
4. yarda 정적 feature로 배치 승자를 맞힐 수 있는지 본다(16절 RF).

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | task 수 12–20(셀마다 값별로 set 4개, 12·16·20만 4의 배수); 768 KiB task(실험 8의 BL 모양, 트래픽 그대로)가 차지하는 U 비율 {0, 25%, 50%}(25% task는 50% task에 포함); 코어당 명목 U {0.35, 0.45}. 구성 6개: Global, Clustered (1+1+2)(U 균형 배치 기준), Partitioned U 균형(wfd) / 부하 균등 CLS 묶음(cgb) / release 고려(ra) / 부하 균등 CLS 묶음 안의 release 고려(ra-cgb) |
| 통제 변인 | 나머지 task는 높은 CLS(중심 0.90, 모드 내 CV 0.1); 주기는 task마다 {20, 40, 80} ms(조화 주기); task U 비율은 Dirichlet(α = 8), 가장 큰 task ≤ 0.35, 가장 작은 task ≥ 0.011; job 예산은 5절의 O2 시간 모델(768 KiB는 `mix_set.big_level`); workload O2; warm-up 2 + 측정 4 hyperperiod(80 ms); 공통 난수(set k는 모든 셀에서 task 수·주기·U 비율·CLS 편차·순서 공유); 셀당 set 36개 |
| 종속 변인 | 모든 deadline 준수 여부; deadline을 지킨 run의 TAT·TET; 최선 Partitioned 배치 대비 regret |
| 조작 확인 | 실현 메모리 U 비율(목표 25%에서 중앙값 0.248, 50%에서 0.490); 경우마다 yarda CLS = 계획값; 단독 U(셀마다 set 0, 게이트 3%); job 예산 0.44–20.8 ms는 17절 시간 모델 검증 범위 안이라 그 결과를 복사 |

768 KiB task는 낮은 부하에서도 768 KiB sweep을 한 번 할 수 있는 task 중에서 set 순서대로 고른다. 목표 U 비율에 가장 가까워지는 지점에서 멈춘다.
그래서 주기가 긴 task로 치우친다.

### 실험 방법
1. `prepare`(216 경우 × 배치 4종, yarda CLS 대조) → `isolated`(셀마다 set 0) → `pilot`(셀마다 set 0, 36 run)
   → `full`(1,260 run) → `stats`.
2. `taskcount_analysis.py`는 다음을 계산한다.
   - 셀별 deadline 준수
   - TAT·TET 셀별 비교
   - CLS 기반 배치 대 release 고려: 짝지은 차이, Wilcoxon + Holm, deadline 준수 불일치
   - task 수 그룹별·4의 배수 여부별 같은 대비와 G·C2 대 최선 Partitioned
   - TAT·TET 배치 선택 RF

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
O=$W/.cache/task-count-v1
mkdir -p $O && cp $W/.cache/policy-mix-v1/model-check.json $O/
for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design task-count --output $O; done
python3 $R/policy-mix/taskcount_analysis.py --output $O
python3 $R/figures/task_count_bars.py $O
```

### 결과 파일
`results/task-count/`에는 다음이 있다.
- `protocol.json`(set별 task 수와 768 KiB task 위치), `model-check.json`(17절 복사), `results.jsonl`, `isolated-u.json`
- `stats-task-count.json/md`, `task-count-analysis.json/md`
- 그림 `task-count-{tat,tet}-mem*-u*`, `task-count-schedulable-u*`
- `per-set.jsonl.gz`

---

## 21. 작은 작업 집합의 저-CLS task × 주기 분포 × task 수

### 개요
20절에서 CLS 기반 배치가 이긴 조건은 768 KiB task가 U의 25%를 차지할 때였다. 그런 task는 실무에서 흔하지 않다.
5절에서는 32 KiB만 읽는 저-CLS task로도 묶음이 이겼지만, 주기가 40 ms 하나였고 task가 16개로 고정이었다.
19절에서는 같은 32 KiB task를 쓰면서 주기를 다양하게 하자 TAT의 승자가 release 고려 배치로 바뀌었다. 이 실험도 task가 16개였다.
이 실험은 768 KiB task 없이, 32 KiB 저-CLS task의 U 비율과 주기 분포를 바꾸고 task 수를 12–20으로 다양하게 한다.
이를 통해 CLS 기반 배치가 이기는 조건을 찾는다. 19절에 대해서는 4의 배수가 아닌 task 수로 보충하는 역할도 한다.

### 목적
1. 32 KiB 저-CLS task가 U의 25%·50%를 차지할 때 다음 두 배치가 release 고려 배치(ra)보다 TAT·TET·deadline 준수에서 나은지 확인한다.
   - 부하 균등 CLS 묶음(cgb)
   - 그 묶음 안의 release 고려(ra-cgb)
2. 그 우열이 주기 CV(0–0.3)에 따라 어디서 바뀌는지 확인한다.
3. 그 결과가 task 수(12–14, 15–17, 18–20)와 4의 배수 여부에 따라 달라지는지 확인한다.
4. 저-CLS 0% 칸에서, 실험 1·2의 "release 고려 배치 대 U 균형 배치" 결론이 task 수 12–20에서도 유지되는지 본다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | **주기 CV** {0, 0.1, 0.2, 0.3}<br>**저-CLS task의 U 비율** {0, 25%, 50%}<br>- 저-CLS task는 5절 낮은 모드: cold 1,024줄(32 KiB), 트래픽 그대로<br>- 25% task는 50% task에 포함<br>**task 수** 12–20(set마다 하나, 각 값이 셀마다 3번)<br>**구성 6개**<br>- Global, Clustered (1+1+2): U 균형 배치 기준<br>- Partitioned 4종: wfd, cgb, ra, ra-cgb |
| 통제 변인 | **CLS**: 나머지 task는 높은 CLS(중심 0.90, 모드 내 CV 0.1). 저-CLS task는 모두 트래픽이 많아 CLS 묶음과 트래픽 묶음이 같은 task를 고른다<br>**주기**: 40 ms × (1 + CV·z), z는 ±3σ에서 자름. 로그 기준으로 {20, 24, 30, 40, 48, 60, 80, 120} ms 중 가장 가까운 값(hyperperiod 240 ms)<br>**부하**: 코어당 명목 U 0.4. task U 비율은 Dirichlet(α = 8), 가장 큰 task ≤ 0.35, 가장 작은 task ≥ 0.011<br>**workload**: O2, 5절 시간 모델<br>**측정 구간**: warm-up 1 + 측정 2 hyperperiod<br>**공통 난수**: set k는 모든 셀에서 task 수·U 비율·CLS 편차·주기 z·순서를 공유하고, CV는 주기 z의 배율만 바꾼다<br>**규모**: 셀 12개 × set 27개 |
| 종속 변인 | 모든 deadline 준수 여부; deadline을 지킨 run의 TAT·TET; 최선 Partitioned 배치 대비 regret |
| 조작 확인 | **실현 저-CLS U 비율**: 목표 25%에서 중앙값 0.253(0.19–0.29), 50%에서 0.507(0.46–0.55)<br>**CLS**: 경우마다 yarda CLS = 계획값<br>**단독 U**: 셀마다 set 0, 게이트 3%<br>**job 예산**: 0.46–12.86 ms. 17절 시간 모델 검증의 계열별 범위(높은 CLS 0.24–43.17 ms, 낮은 CLS 트래픽 그대로 0.23–18.12 ms) 안이라 그 결과를 복사 |

저-CLS task는 다음 조건을 만족하는 task 중에서 set 순서대로 고른다. 목표 U 비율에 가장 가까워지는 지점에서 멈춘다.
- 모든 CV 칸에서 job 예산이 낮은 CLS 계열의 검증 범위 안에 든다.

저-CLS 0% 칸에서는 cgb가 wfd와, ra-cgb가 ra와 같은 배치가 된다. 이 칸의 그 run들은 결정성 확인을 겸한다.

### 실험 방법
1. 단계는 다음 순서로 진행한다.
   - `prepare`: 324 경우 × 배치 4종, yarda CLS 대조
   - `isolated`: 셀마다 set 0
   - `pilot`: 셀마다 set 0, 72 run
   - `full`: 1,872 run
   - `stats`
2. `smallmem_analysis.py`는 20절의 분석을 셀(주기 CV × 저-CLS 비율)별로 계산한다. 추가로 같은 대비를 주기 CV별로도 계산한다(저-CLS 칸 합침).

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
O=$W/.cache/small-memory-v1
mkdir -p $O && cp $W/.cache/policy-mix-v1/model-check.json $O/
for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design small-memory --output $O; done
python3 $R/policy-mix/smallmem_analysis.py --output $O
python3 $R/figures/small_memory_bars.py $O
```
실제 실행은 `supervisors/small-memory-v1.sh`다.

### 결과 파일
`results/small-memory/`에는 다음이 있다.
- `protocol.json`(set별 task 수와 저-CLS task 위치), `model-check.json`(17절 복사), `results.jsonl`, `isolated-u.json`
- `stats-small-memory.json/md`, `small-memory-analysis.json/md`
- 그림 `small-memory-*`
- `per-set.jsonl.gz`

---

## 22. 실험 1·2의 task 수 12–20 재실행

### 개요
실험 1(주기 분포)과 실험 2(release 고려 P′ 대조)는 task 16개, 코어마다 4개였다.
같은 조건에서 task 수만 12–20으로 바꿔 다시 돌린다.
- task U는 n개가 나눠 가진다(task마다 2.0 / n). 그래서 코어당 명목 U는 실험 1과 같은 0.5다.
- 4의 배수가 아니면 지그재그 배치에서 코어별 task 수가 1개 차이 난다.

### 목적
1. 실험 1의 결론이 task 수 12–20과 4의 배수 여부에 관계없이 유지되는지 확인한다. 실험 1의 결론은 두 가지다.
   - 주기 CV가 커질수록 생기는 G/C/P 격차
   - 평균 주기 μ의 영향
2. 실험 2의 결론(release 고려 P′가 지그재그 P의 TAT 손해를 줄임)이 task 수에 따라 달라지는지 확인한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | **평균 주기 μ** {20, 50, 80, 100, 500} ms<br>**주기 CV** {0, 0.1, 0.2, 0.3}<br>**task 수** 12–20: set k는 12 + (k mod 9)개. CV > 0 셀은 set 18개(각 값 2번), CV 0 셀은 task 수마다 set 1개(9개)<br>**구성 7개**<br>- G, C (1+3), P, C2 (1+1+2): 주기 순 지그재그<br>- P′, C′, C2′: cohort 부하 하한 최소화 |
| 통제 변인 | 실험 1·2와 같다: 주기 격자·로그 반올림, ±3σ 자르기, workload cyclic 64줄(2 KiB) O0, job CPU 모델, warm-up과 측정이 각각 180 × (μ/10) tick, 배열은 코어·주기 순 연속<br>**task U**: 0.5 × 4 / n<br>**공통 난수**: 시드 20262201 + set. set k의 표준정규 n개를 모든 μ·CV가 공유<br>**P′ 국소 탐색**: 지그재그의 코어별 task 수를 유지한다. 16개이면 실험 2와 같은 배치이며, 실험 2의 300 set 배치가 모두 그대로 재현됨을 확인했다 |
| 종속 변인 | TAT(주 지표), TET, response time 합 |
| 조작 확인 | 단독 U: μ마다 CV 0.3·set 0(task 12개, task U가 가장 커 sweep이 가장 많음), 게이트 5%. `g-check`: 셀마다 set 0의 G를 P′ 빌드로 다시 돌려 main 단계의 G 결과와 같은지 확인 |

### 실험 방법
1. `tc_run.py`는 `run.py`·`control.py`의 설계 모듈 `taskset`을 `tc_taskset`으로 바꿔 실행한다. 단계와 옵션은 원래 실행기와 같다.
2. main 단계: `prepare`(315 set) → `u-check`(60 run) → `pilot`(셀마다 set 0, 80 run) → `full`(1,180 run) → `stats.py`.
3. control 단계: `prepare`(CV > 0의 270 set) → `g-check`(15 run) → `run`(810 run) → `summarize` → `stats`.
4. `tc_analysis.py`는 task 수 그룹별·4의 배수 여부별로 G 대 P, P′ 대 P, G 대 P′의 TAT·TET 격차를 계산한다.

### 재현 명령
```sh
cd $C2 && export PYTHONPATH=$C2
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/period-distribution $R/period-distribution/test_tc_taskset.py $R/period-distribution/test_placement.py
M=$W/.cache/period-taskcount-v1; O=$W/.cache/period-taskcount-cohort-v1
for s in prepare u-check pilot full; do python3 $R/period-distribution/tc_run.py main $s --output $M; done
python3 $R/period-distribution/stats.py $M
for s in prepare g-check run summarize stats; do python3 $R/period-distribution/tc_run.py control $s --main $M --output $O; done
python3 $R/period-distribution/tc_analysis.py --main $M --control $O
python3 $R/figures/period_taskcount_bars.py --main $M --control $O
```
실제 실행은 `supervisors/period-taskcount-v1.sh`다.

### 결과 파일
- `results/period-taskcount/`: `protocol.json`(set별 task 수·task U), `results.jsonl`, `stats.json/md`, `isolated-u.json`,
  `period-taskcount-analysis.json/md`, 그림, `per-set.jsonl.gz`
- `results/period-taskcount-cohort/`: `protocol.json`, `results.jsonl`(행마다 `ps`/`cs`/`c2s` = 지그재그 결과), `stats.json/md`,
  `g-check.json`, `per-set.jsonl.gz`

---

## 23. CLS 분포·다양성 × 주기 분포 × task 수

### 개요
21절까지의 CLS는 높은 모드(0.90)와 낮은 모드(0.13) 두 값으로 갈려 있었다.
이 실험은 3절의 질문(CLS의 평균과 퍼짐)을 지금 조건(O2, U 비균등, 주기 다양, task 12–20개)에서 다시 묻는다.
CLS는 task마다 연속 분포에서 뽑는다.
- CLS 0.5–0.85 task도 메모리를 자주 읽는다(1 µs당 L1 miss 약 9–11, L2 포화 기준 5.2).
- 그런데 기존 규칙(CLS ≤ 0.5만 묶음)은 이런 task를 묶지 않는다.

그래서 기존 규칙 옆에 상대 기준(set 안에서 CLS가 낮은 쪽 절반을 묶음)을 함께 비교한다.

### 목적
1. CLS 평균(높은 CLS 포함)과 다양성에 따라 CLS 고려 배치가 release 고려 배치보다 TAT·TET에서 나은 조건이 있는지 확인한다.
2. 절대 기준(CLS ≤ 0.5)과 상대 기준(set 안 하위 절반) 중 어느 쪽이 나은지 비교한다.
3. 그 결과가 주기 CV와 task 수에 따라 달라지는지 확인한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | **CLS 평균** {0.3, 0.6, 0.9}<br>**CLS 표준편차** {0, 0.1, 0.2}: 목표 CLS = 평균 + 표준편차 × z, z는 ±3σ에서 자름<br>**주기 CV** {0, 0.2}<br>**task 수** 12–20(set마다 하나, 셀마다 각 값 2번)<br>**구성 8개**<br>- Global, Clustered (1+1+2): U 균형 배치 기준<br>- Partitioned 6종: wfd, cgb, ra, ra-cgb, 그리고 상대 기준 cgr(부하 균등 상대 CLS 묶음)·ra-cgr(그 안의 release 고려) |
| 통제 변인 | **task 모양**: 모두 5절 높은 모드(hot H줄 × R회 + cold 32 KiB, 트래픽 그대로). sweep을 1,024회까지 허용해 긴 job도 중간 CLS에 닿게 했다(5절 표는 64회까지)<br>**CLS 수준**: 목표에 가장 가까운, job 예산이 허용하는 값(약 0.10–0.99). 그래서 넓은 퍼짐은 경계에서 잘린다<br>**상대 기준**: CLS를 소수 둘째 자리로 반올림해 순위를 매긴다. 같은 값의 task는 같은 쪽에 든다. 그래서 퍼짐 0이면 묶지 않아 wfd·ra와 같다<br>**주기·부하·측정 구간·공통 난수**: 21절과 같다. set k는 모든 셀에서 task 수·U 비율·CLS z·주기 z·순서를 공유한다<br>**규모**: 셀 18개 × set 18개 |
| 종속 변인 | 모든 deadline 준수 여부; deadline을 지킨 run의 TAT·TET; 최선 Partitioned 배치 대비 regret |
| 조작 확인 | **실현 CLS**(주기 CV 0.2 칸의 set 평균):<br>- 평균 0.3: 표준편차 0.09(목표 0.1), 0.16(목표 0.2)<br>- 평균 0.6: 0.09, 0.18<br>- 평균 0.9: 0.08, 0.14(실현 평균 0.86)<br>**묶음 크기**: 절대 기준은 평균 0.3에서 U의 88–100%(대부분 wfd와 같아짐), 0.6에서 16–29%, 0.9에서 0–2%를 묶는다. 상대 기준은 퍼짐이 있으면 약 51%를 묶는다<br>**CLS**: 경우마다 yarda CLS = 계획값<br>**job 예산**: 1.14–11.58 ms<br>**단독 U**: 셀마다 set 0의 모든 task, 게이트 3%. 이 설계의 모양은 17절 시간 모델 검증 밖이므로 이 게이트가 모델 검증을 겸한다 |

### 실험 방법
1. 단계는 다음 순서로 진행한다.
   - `prepare`: 324 경우 × 배치 6종, yarda CLS 대조
   - `isolated`: 셀마다 set 0
   - `pilot`: 셀마다 set 0, 144 run
   - `full`: 2,448 run
   - `stats`
2. `clsspread_analysis.py`는 셀별로 다음을 계산한다.
   - TAT·TET 비교
   - CLS 고려 4종 대 ra의 짝지은 대비
   - 상대 기준 대 절대 기준
   - CLS 평균·표준편차·task 수 그룹별 대비

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
O=$W/.cache/cls-spread-v1
for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design cls-spread --output $O; done
python3 $R/policy-mix/clsspread_analysis.py --output $O
python3 $R/figures/cls_spread_bars.py $O
```
실제 실행은 `supervisors/cls-spread-v1.sh`다(22절이 끝난 뒤 시작).

### 결과 파일
`results/cls-spread/`에는 다음이 있다.
- `protocol.json`(set별 task 수), `results.jsonl`, `isolated-u.json`
- `stats-cls-spread.json/md`, `cls-spread-analysis.json/md`
- 그림 `cls-spread-*`
- `per-set.jsonl.gz`

---

## 24. 작은 작업 집합의 저-CLS task × 부하 (탐색)

### 개요
21절(코어당 U 0.4)에서는 deadline miss가 없어서 배치 사이의 차이가 TAT·TET로만 드러났다.
11절에서는 task 절반이 메모리를 자주 읽을 때 트래픽 묶음이 U 균형보다 다음만큼 나았다.
- 코어당 U 0.3: TAT −4%
- 코어당 U 0.45: TAT −8%
- 코어당 U 0.6: 모든 구성이 deadline을 놓쳤다.

다만 11절은 release 고려 배치와 비교하지 않았고 task가 16개였다.
이 실험은 21절의 task set을 이 경계 근처의 부하로 올려, CLS 고려 배치가 deadline을 더 오래 지키는지 본다.
21–23절 결과를 본 뒤 고른 조건이므로 **탐색 실험**이다. 유망한 조건은 새 set으로 다시 확인해야 한다.

### 목적
1. 부하가 오를 때 다음 두 배치가 release 고려 배치(ra)보다 deadline 준수와 TAT·TET에서 나은지 확인한다.
   - 부하 균등 CLS 묶음(cgb)
   - 그 안의 release 고려(ra-cgb)
2. 그 차이가 주기 CV(0, 0.2)와 task 수에 따라 달라지는지 확인한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | **코어당 명목 U** {0.45, 0.5, 0.55, 0.6}<br>**32 KiB 저-CLS task의 U 비율** {25%, 50%}: 5절 낮은 모드, 트래픽 그대로. 25% task는 50% task에 포함<br>**주기 CV** {0, 0.2}<br>**task 수** 12–20(셀마다 각 값 2번)<br>**구성 6개**: Global, Clustered (1+1+2)(U 균형 기준), Partitioned wfd·cgb·ra·ra-cgb |
| 통제 변인 | 21절과 같은 task 모양·주기 격자·측정 구간<br>**U 비율**: 가장 큰 task ≤ 0.35(최고 부하 기준), 가장 작은 task ≥ 0.011(최저 부하 기준)<br>**공통 난수**: set k는 모든 셀·부하에서 task 수·U 비율·CLS 편차·주기 z·순서를 공유하고, 부하는 job 예산의 크기만 바꾼다<br>**규모**: 셀 4개 × 부하 4개 × set 18개 |
| 종속 변인 | 모든 deadline 준수 여부(주 지표); deadline을 지킨 run의 TAT·TET |
| 조작 확인 | **실현 저-CLS U 비율**(부하 0.5, CV 0.2): 목표 25%에서 중앙값 0.254(0.22–0.28), 50%에서 0.499(0.47–0.54)<br>**job 예산**: 0.65–18.14 ms. 저-CLS task는 모든 부하·CV에서 낮은 CLS 계열의 검증 범위 안에 드는 task 중에서 고르므로, 17절 모델 검증의 계열별 범위 안이다<br>**CLS**: yarda CLS = 계획값<br>**단독 U**: 셀·부하마다 set 0, 게이트 3% |

### 실험 방법
1. 단계는 다음 순서로 진행한다.
   - `prepare`: 288 경우 × 배치 4종
   - `isolated`
   - `pilot`: 셀·부하마다 set 0, 96 run
   - `full`: 1,632 run
   - `stats`(부하에 대한 Page 추세 포함)
2. 분석은 셀·부하별로 다음을 본다.
   - deadline 준수 수와 짝지은 불일치(한쪽만 지킨 경우)
   - TAT·TET 짝지은 비교

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
O=$W/.cache/small-memory-load-v1
mkdir -p $O && cp $W/.cache/policy-mix-v1/model-check.json $O/
for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design small-memory-load --output $O; done
```
실제 실행은 `supervisors/small-memory-load-v1.sh`다.

### 결과 파일
`results/small-memory-load/`에는 다음이 있다.
- `protocol.json`, `model-check.json`(17절 복사), `results.jsonl`, `isolated-u.json`
- `stats-small-memory-load.json/md`
- 분석과 그림
- `per-set.jsonl.gz`

---

## 25. 접근 패턴 때문에 CLS가 낮은 task (작은 작업 집합, L1 충돌 miss)

### 개요
21절의 저-CLS task는 32 KiB cold 영역을 훑는다. 이 영역은 L1(16 KiB)의 두 배라서, 이 task는 sweep마다 자기 코어의 L1을 통째로 밀어낸다.
실제로는 읽는 데이터가 작아도 접근 패턴 때문에 캐시를 못 쓰는 task가 있다. 예를 들어 행렬을 열 방향으로 읽거나, 2의 거듭제곱 간격으로 접근하는 경우다.

이 실험은 21절과 같은 set에서 저-CLS task만 그런 모양으로 바꾼다.
- 바꾼 모양: 43–61줄(1.4–1.9 KiB)을 4 KiB(L1 한 way 크기) 간격으로 읽는다.
- 그러면 task의 모든 줄이 L1의 한 집합에 몰린다.
- 4-way보다 줄이 많으므로 hot 반복을 빼면 매번 L1 miss가 나고, L2에서는 hit한다(줄마다 다른 L2 집합).

L2 요청량은 21절과 같고, 더럽히는 L1 범위만 한 집합으로 줄어든다.
그래서 CLS 묶음의 이득이 L2 대역폭 경합에서 오는지, 같은 코어의 L1 오염에서 오는지를 21절과 짝지어 가를 수 있다.

### 목적
1. 저-CLS가 작업 집합 크기가 아니라 접근 패턴에서 올 때도 CLS 고려 배치(cgb, ra-cgb)가 21절처럼 TET에서 이기고 TAT를 유지하는지 확인한다.
2. 같은 set의 21절 결과와 비교해, 21절의 이득 중 L1 오염이 차지하는 몫을 추정한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | **저-CLS task 모양**: 충돌형(이 실험). 21절의 스트리밍형과 같은 set으로 짝지음<br>**주기 CV** {0, 0.2}<br>**저-CLS U 비율** {25%, 50%}<br>**구성 6개**: 21절과 같음 |
| 통제 변인 | **같은 set**: 21절과 같은 시드(20262101)·task 수·U 비율·주기·역할·높은 CLS task·job 예산을 쓴다. 저-CLS 0% 칸은 21절과 같으므로 다시 돌리지 않는다<br>**충돌형 모양**: hot 1–4줄(연관도 4 이하라 반복이 L1에서 hit) × 2회 + cold 28–60줄. 모두 4,096 B 간격이라 한 L1 집합에 든다. 목표 CLS에 가장 가까운 (hot, cold)를 고르고, sweep 수와 tail로 예산을 맞춘다 |
| 종속 변인 | 21절과 같음. 추가로, 같은 set·배치에서 충돌형과 스트리밍형의 TAT·TET 차이 |
| 조작 확인 | **충돌형 task**(전체 652개):<br>- 계획 CLS 0.118–0.144(21절 스트리밍형 약 0.13)<br>- 1 µs당 L1 miss 13.5–14.0(스트리밍형과 같은 수준)<br>- sweep 186–3,964회<br>**yarda CLS**: 집합 단위 reuse distance(CSRD)를 쓰므로 충돌 miss를 반영한다. 계획 CLS(`bimodal.cls_model`, cold = C줄)와 같은지 prepare에서 확인한다. 사전 점검으로 한 경우(cv20-low50, set 0)를 빌드했고, 모든 task가 일치했다<br>**단독 U**: 셀마다 set 0, 게이트 3%. 충돌형 모양은 17절 시간 모델 검증 밖이므로 이 게이트가 모델 검증을 겸한다<br>**보정**: 첫 실행(`conflict-cls-v1`)은 이 게이트에서 멈췄다. 충돌형 task가 모델보다 4.2–5.3% 빨랐고(sweep당 약 0.17 µs), 높은 CLS task는 ±0.1%였다. 그래서 `conflict_calibrate.py`로 충돌형 수준 64개(hot 1–4 × cold 28–60 × sweep 150–3,500)를 단독 실행해 job당·sweep당·L1 적중당·L2 적중당 계수의 보정량을 맞췄다. 따로 뽑은 24개 수준으로 검증한 최대 오차는 0.17%다(보정 전 +3.2 ~ +8.5%). 결과는 `results/conflict-calibration/`에 있고, 다시 실행한 출력은 `conflict-cls-v2`다<br>**보정 후 충돌형 task**: 1 µs당 L1 miss 14.5–14.6으로, 21절 스트리밍형(약 13–14)보다 5–7% 높다. 같은 예산에서 접근을 더 많이 하는 모양이기 때문이다. 이 차이는 충돌형 쪽 경합을 키우는 방향이다 |

### 실험 방법
단계는 다음 순서로 진행한다.
- `prepare`: 108 경우 × 배치 4종, yarda CLS 대조
- `isolated`
- `pilot`: 셀마다 set 0, 24 run
- `full`: 624 run
- `stats`

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
C=$W/.cache/conflict-calibration-v1
for s in measure fit; do python3 $R/policy-mix/conflict_calibrate.py $s --output $C; done
# 설계는 results/conflict-calibration/conflict-model.json을 읽는다(C의 결과를 복사).
O=$W/.cache/conflict-cls-v2
for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design conflict-cls --output $O; done
```
실제 실행은 `supervisors/conflict-cls-v2.sh`다(26절 확장분이 끝난 뒤 시작). `conflict-cls-v1.sh`는 게이트에서 멈춘 첫 실행이다. 그 출력은 2026-10-05에 지웠고, 게이트 기록은 `results/conflict-calibration/conflict-cls-v1-isolated-u.json`에 있다.

### 결과 파일
`results/conflict-cls/`에는 다음이 있다.
- `protocol.json`(짝지은 21절 출력, 충돌 간격), `results.jsonl`, `isolated-u.json`
- `stats-conflict-cls.json/md`
- 분석과 그림
- `per-set.jsonl.gz`

---

## 26. 무작위 배치 기준선 (CAAS의 비교 기준)

### 개요
지금까지 CLS 기준 배치는 주로 release 고려 배치(ra)와 비교했다. 반면 CAAS 논문은 U 균형(WFD)과 지역성을 무시한 무작위 배치를 비교 기준으로 썼다.
U 균형 결과는 17–25절에 이미 있으므로, 이 실험은 무작위 배치만 같은 set에서 새로 돌린다.
돌린 결과는 기존 결과와 짝지어 다음을 비교한다.
- CLS 기준 배치(cgb, ra-cgb, 23절은 cgr·ra-cgr 포함)
- U 균형
- release 고려

### 목적
1. CLS 기준 Partitioned 배치가 무작위 배치보다 TAT·TET·deadline 준수에서 나은지 확인한다.
2. 비교 기준(무작위, U 균형, release 고려)에 따라 CLS 기준 배치의 효과가 얼마나 달라지는지 정리한다.

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | **배치**: 무작위 3회(`rnd0`–`rnd2`). 태스크마다 코어를 균등하게 뽑고, 어느 코어든 U 0.95를 넘으면 다시 뽑는다. set의 시드에서 결정적으로 뽑는다<br>**set**:<br>- 21절의 저-CLS 칸 8개(`random-small-memory`)<br>- 20절의 메모리 25% 칸, 두 부하(`random-task-count`)<br>- 23절의 CLS 평균 0.6·0.9이고 퍼짐이 있는 칸 8개(`random-cls-spread`)<br>**확장**(같은 정의, `supervisors/random-baseline-ext-v1.sh`):<br>- 24절의 모든 칸·부하(`random-small-memory-load`)<br>- 25절의 모든 칸(`random-conflict-cls`)<br>- 19절의 저-CLS 또는 768 KiB task가 있는 칸 20개(`random-policy-boundary`)<br>- 17절의 set(`random-policy-mix`, 17·18절과 짝지음) |
| 통제 변인 | 각 실험과 같은 task·set·시드·job 예산. 배치만 다르다. 20절 메모리 50% 칸은 모든 배치가 실패했고, 23절 CLS 평균 0.3 칸은 L2 과부하이며, 퍼짐 0 칸은 묶을 집단이 없어 제외한다 |
| 종속 변인 | deadline 준수 여부, TAT, TET. 같은 set의 기존 결과와 짝지어 비교한다 |
| 조작 확인 | 단독 U(셀마다 set 0, 게이트 3%); yarda CLS = 계획값 |

### 실험 방법
1. 설계마다 다음 단계를 차례로 진행한다.
   - `prepare`: wfd 빌드는 단독 U 게이트와 yarda용이며 실행하지 않는다
   - `isolated`
   - `pilot`
   - `full`
   - `stats`
2. 규모는 다음과 같다.
   - 21절: 216 경우 × 3
   - 20절: 72 경우 × 3
   - 23절: 144 경우 × 3
   - 모두 1,296 run
   - 확장분: 24절 288 경우 × 3, 25절 108 × 3, 19절 200 × 3, 17절 160 × 3, 모두 2,268 run
3. 분석은 두 단계로 한다.
   - `policy-mix/rt_metrics.py`는 출력마다 P run별 실시간 지표를 `rt-metrics.json`에 쓴다. 지표는 다음과 같다.
     - 상태(ok/deadline/startup)
     - 최악 응답시간 ÷ 주기
     - 최악 job CPU ÷ 계획 예산(전체 task와 메모리 task)
     - deadline 위반 job 수: 측정 구간에서 응답이 주기를 넘은 job과, 그 지연으로 다음 release가 연기되어(RTEMS rate monotonic) 구간 안에 실행되지 못한 job의 합. 측정 구간에 release되어야 할 job 수도 함께 기록한다
     원시 기록(measurements.jsonl의 첫 줄)만 읽으므로 빌드를 정리한 출력에도 쓸 수 있다.
   - `policy-mix/rt_compare.py`는 17–25절의 기존 출력과 무작위 출력을 같은 경우끼리 짝지어 비교한다.
     배치마다 deadline 준수, 위반 job 비율, 최악 실행시간·최악 응답시간의 중앙값(모든 배치·무작위 회차가 deadline을 지킨 경우)을 낸다.
     CLS 기준 배치마다 wfd·ra·무작위 대비 deadline 불일치, 위반 job 수 비교(어느 한쪽이라도 놓친 쌍), 최악 실행시간 상대 변화, 최악 응답시간 변화를 낸다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
for d in random-small-memory random-task-count random-cls-spread random-small-memory-load random-conflict-cls random-policy-boundary random-policy-mix; do
    O=$W/.cache/$d-v1
    for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design $d --output $O; done
done
# 실시간 지표: 출력마다 rt_metrics.py(--builds는 그 출력의 P 빌드), 그 다음 비교와 그림
python3 $R/policy-mix/rt_metrics.py --output $W/.cache/small-memory-v1 --builds wfd,cgb,ra,ra-cgb   # 다른 출력도 같은 방식
python3 $R/policy-mix/rt_compare.py --cache $W/.cache --output $R/results/rt-compare
python3 $R/figures/rt_compare_bars.py $R/results/rt-compare
```
실제 실행은 `supervisors/random-baseline-v1.sh`(25절이 끝난 뒤 시작)와, 그 뒤의 `supervisors/random-baseline-ext-v1.sh`다.
확장분의 설계 이름은 `random-small-memory-load`, `random-conflict-cls`, `random-policy-boundary`, `random-policy-mix`다.

### 결과 파일
17–25절의 실시간 지표 비교는 `results/rt-compare/`(`rt-compare.json/md`, 그림 `rt-compare-<절>`)에 있다. 각 출력의 `rt-metrics.json`은 해당 결과 묶음에 들어 있다.

`results/random-*/`(설계 이름과 같다)에는 각각 다음이 있다.
- `protocol.json`, `results.jsonl`, `isolated-u.json`
- `stats-*.json/md`
- `per-set.jsonl.gz`

---

## 27. 마감 위반 확증 실험 (사전 등록, 새 set)

### 개요
17–26절은 가설을 세운 탐색 실험이다. 그 결과로 연구 목표를 TAT/TET 개선에서 **공유 캐시 경합 아래의 실시간성 보호**로 바꿨다.
이 실험은 그 가설을 **새로 뽑은 set**으로 확인한다.
실행 전에 다음 세 가지를 고정했다.
- 가설과 판정 기준: 아래 표, `policy-mix/deadline_analysis.py` 첫머리
- 분석 스크립트와 그 테스트: `deadline_analysis.py`, `test_deadline_analysis.py`. `prepare` 때 `protocol.json`에 해시가 기록된다
- 정적 L2 요청량 예측: `prepare` 직후, 첫 run 전에 `prediction-l2-demand.json`에 기록한다. run 기록이 하나라도 있으면 스크립트가 거부한다

탐색 자료(17–26절)는 확증 표본에 합치지 않는다.
분석 스크립트는 24절 출력(탐색 자료)으로 코드 경로만 확인했다. 판정 기준은 그 전에 정했다. 그 뒤 바꾼 것은 V4 판정의 코드 오류 하나뿐이다(방향이 없는 검정에서 방향 값을 읽던 문제, 회귀 테스트 추가).

### 사전 등록한 가설과 판정

| 가설 | 판정(유의수준 0.05) |
|---|---|
| V1 | **32 KiB 유형**에서 정적 L2 요청량 기준(23절에서 정하고 24절에서 확인, < 0.9 성공·≥ 1.0 실패)이 마감 결과를 맞힌다. 경우 단위로, 성공 예측은 결정적 P 배치 4종(wfd, cgb, ra, ra-cgb)이 모두 마감을 지켰을 때, 실패 예측은 모두 놓쳤을 때 맞은 것으로 센다. 두 예측 모두 맞힌 비율의 단측 95% Clopper–Pearson 하한이 0.9 이상이면 지지된다. 무작위 배치는 코어 U가 0.95까지 가능하므로 보고만 한다. 768 KiB 유형은 L2 용량 경합을 반영하지 않는 기준이므로(20절) 보고만 한다 |
| V2 | ra-cgb는 ra보다, 그리고 wfd보다 위반 job이 적다. 유형·기준 배치마다, 둘 다 측정되고 한쪽이라도 위반한 쌍에서 위반 job 비율(위반 job ÷ release된 job) 차이의 양측 Wilcoxon 부호순위 검정. 4개 검정에 Holm. 한 유형에서 두 기준 배치 모두 유의하고, 중앙값 차이가 음수이며, ra-cgb가 적은 쌍이 더 많으면 그 유형에서 지지된다. 마감 준수의 exact McNemar는 보고한다 |
| V3 | ra-cgb는 메모리 task의 최악 실행시간 증가(최악 job CPU ÷ 계획 예산)가 ra, wfd보다 작다. 둘 다 모든 마감을 지킨 쌍에서 로그 비의 양측 Wilcoxon. 4개 검정에 Holm. 유의하고 중앙값 변화가 음수이면 지지된다 |
| V4 | ra-cgb의 TAT는 ra와 ±2% 안에서 같다. 둘 다 모든 마감을 지킨 쌍에서 로그 비의 TOST(log 1.02 미만, log 0.98 초과의 단측 Wilcoxon 두 개). 두 유형에 Holm |
| 보조 | V2·V3를 주기 CV별로, 그리고 ra-cgb 대 무작위 3회 평균(위반 job 비율, 세 회차 모두 마감을 지킨 경우의 로그 실행시간 증가)을 따로 한 묶음으로 Holm. 서술: 칸·배치별 마감 준수 run 수와 위반 job, 결정적 P가 모두 놓친 경우의 G/C 구제 수 |

- V5(위험 모델)는 모델을 아직 동결하지 않았으므로 이 실험에서 판정하지 않는다. 이 set은 이미 열리므로 V5는 별도 확증 자료로 확인한다.
- CAAS(CA-CSRD Algorithm 1) 배치는 아직 구현하지 않아 이번 실행에서 뺐다. set이 결정적이므로 뒤에 같은 set으로 덧붙일 수 있다.
- 측정 구간과 표본 수는 E0′의 pilot 없이 정했다. 측정 구간은 24절보다 길게(측정 3 hyperperiod) 정했고, set 수는 24절과 같은 칸당 18개로 시간 예산(약 6–7시간)에 맞춘 값이다. 검정력 계산에서 나온 값이 아니다.

### 사전 등록 보완 (2026-10-06 02:52 KST, 결과 열람 전)
- **V6 추가:** ra-cgb의 TET는 ra보다, 그리고 wfd보다 작다. 둘 다 모든 마감을 지킨 쌍에서 TET 로그 비의 양측 Wilcoxon, 4개 검정(유형 2 × 기준 배치 2)에 Holm. 유의하고 중앙값 변화가 음수이면 지지된다.
- **보완 시점까지 본 것:** 진행 확인을 위해 supervisor 로그의 칸별 성공·실패 run 수(모든 구성 합계)만 봤다. 배치별 비교, TET, 위반 job, 분석 출력은 보지 않았다.
- **분석 스크립트:** 두 출력의 `protocol.json`에 기록된 `deadline_analysis.py` 해시는 보완 전 버전이다. 보완 후 버전은 sha256 `55de28d255bd3a90e03a1bcd8ec36cb47a695a5adbeb6e32bbf0e360c5381a5b`이다. 바뀐 것은 V6 검정과 TET 필드 읽기이고, 최악 실행시간 검정을 TET와 같은 함수로 옮겼을 뿐 V1–V4의 계산은 그대로다(테스트 18개).

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | **메모리 task 유형**: 32 KiB 저-CLS(5절 낮은 모드, 트래픽 그대로, U 비율 50%) 또는 768 KiB(8절 BL 모양, U 비율 25%). 유형마다 설계가 따로다(`deadline-small`, `deadline-big`)<br>**코어당 명목 U**: 32 KiB는 0.45–0.6을 0.025 간격(7개), 768 KiB는 {0.30, 0.35, 0.40, 0.45}<br>**주기 CV** {0, 0.2}<br>**task 수** 12–20(유형마다 각 값 2번)<br>**구성 9개**: Global, Clustered (1+1+2)(wfd 기준), Partitioned wfd·cgb·ra·ra-cgb, 무작위 3회(rnd0–2) |
| 통제 변인 | **새 set**: seed 20262701–18(32 KiB), 20262751–68(768 KiB). 17–26절의 어떤 seed와도 겹치지 않는다(테스트로 확인)<br>**주기**: 평균 40 ms의 주기 격자 {20, …, 120} ms, 1 hyperperiod 240 ms. CV 0이면 모든 task가 40 ms<br>**측정 구간**: warm-up 1 + 측정 3 hyperperiod(24절은 측정 2)<br>**U 비율**: Dirichlet(8), 가장 큰 task ≤ 0.35(최고 부하 기준), 가장 작은 task ≥ 0.0125(최저 부하 기준, 20 ms 주기에서도 모델 검증 하한 이상)<br>**메모리 task 선택**: 모든 부하·CV에서 job 예산이 17절 모델 검증의 해당 계열 범위(32 KiB 0.23–18.12 ms, 768 KiB 1.7–15.15 ms) 안에 드는 task 중 set 순서의 앞에서부터, 목표 U 비율에 가장 가까워질 때까지<br>**공통 난수**: set k는 모든 칸·부하에서 task 수·U 비율·CLS 편차·주기 z·순서·메모리 task를 공유하고, 부하는 job 예산의 크기만 바꾼다 |
| 종속 변인 | **주 지표**: 위반 job 비율, 모든 마감 준수 여부, 메모리 task의 최악 실행시간 증가, 최악 응답시간 ÷ 주기(`rt_metrics.py`)<br>**보조 지표**: 마감을 지킨 run의 TAT·TET |
| 조작 확인 | **CLS**: yarda CLS = 계획값(`pm_run.py`)<br>**단독 U**: 칸·부하마다 set 0, 게이트 3%<br>**계획 U**: 명목 부하 × 4의 ±2%(테스트) |

### 실험 방법
1. 설계마다(`deadline-small` 다음 `deadline-big`) 다음 순서로 진행한다.
   - `prepare`: 32 KiB 252 경우, 768 KiB 144 경우 × 배치 7종
   - `predict`: `deadline_analysis.py predict`, 첫 run 전
   - `isolated`, `pilot`(칸·부하마다 set 0), `full`, `stats`(부하에 대한 Page 추세 포함)
   - `rt`: `rt_metrics.py --builds wfd,cgb,ra,ra-cgb,rnd0,rnd1,rnd2`
2. 두 설계가 끝나면 `deadline_analysis.py analyze`가 위 판정을 한 번에 낸다.
3. 규모는 396 경우 × 9 구성 = 3,564 run이다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
for d in deadline-small deadline-big; do
    O=$W/.cache/$d-v1
    mkdir -p $O && cp $W/.cache/policy-mix-v1/model-check.json $O/
    python3 $R/policy-mix/pm_run.py prepare --design $d --output $O
    python3 $R/policy-mix/deadline_analysis.py predict --output $O
    for s in isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design $d --output $O; done
    python3 $R/policy-mix/rt_metrics.py --output $O --builds wfd,cgb,ra,ra-cgb,rnd0,rnd1,rnd2
done
python3 $R/policy-mix/deadline_analysis.py analyze --small $W/.cache/deadline-small-v1 \
    --big $W/.cache/deadline-big-v1 --dest $W/.cache/deadline-confirm-v1
```
실제 실행은 `supervisors/deadline-confirm-v1.sh`다.

### 결과 파일
- `results/deadline-small/`, `results/deadline-big/`: `protocol.json`, `model-check.json`(17절 복사), `prediction-l2-demand.json`, `results.jsonl`, `isolated-u.json`, `rt-metrics.json`, `stats-*.json/md`, `per-set.jsonl.gz`
- `results/deadline-confirm/`: `deadline-confirm.json/md`(사전 등록한 판정)와 그림

---

## 28. CAAS 대비 단계별 비교 (27절의 set, 사전 등록)

### 개요
연구 방향을 "캐시 친화도 + utilization·release"로 정리하면서(연구 문서의 PLAN 0절), 평가의 중심을 CAAS에서 한 가지씩 바꾸는 단계별 비교로 정했다.
27절에는 단계 2(cgb)·3(ra-cgb)과 공통 비교 기준이 이미 있으므로, 같은 set에 단계 0·1의 Partitioned run만 덧붙인다.
가설·판정·분석 스크립트(`policy-mix/ladder_analysis.py`와 테스트)는 2026-10-06 03:03 KST에, 27·28절의 어떤 결과도 읽기 전에 고정했다. 고정한 해시: `ladder_analysis.py` sha256 `90e6c86c4a1cc629565d05819f4ca0838501b2aa59427a699e248f95c877353d`, `algorithm1.py` sha256 `2490ac646bd7369c8bcee0008fffd55049a1106c6fb14a949a8f02cf469a1aa6`.

| 단계 | 배치 | 바로 앞 단계와 다른 점 |
|---|---|---|
| 0 | caas: CA-CSRD + CAAS Algorithm 1 | 선행 연구. calibration-v2의 동결 정책(임곗값 0.178, 격리 코어 0, 비격리 코어 1–3, 코어 용량 1) |
| 1 | cls-a1: CLS + Algorithm 1 | 지표만 CLS로(임곗값 0.5, 균형 CLS 묶음의 기준과 같음) |
| 2 | cgb(27절) | 격리 코어 수를 부하 한도(평균 × 1.05)로 정함 |
| 3 | ra-cgb(27절) | 묶음 제약 안에서 release 시각 몰림을 줄임 |
| 31 | 재분석: 마감 지표 분리, TET·TAT 비교, 친화도 지표의 실패 예측력(시뮬레이션 없음) | `policy-mix/`(`rt_metrics.py`, `rt_compare.py`, `timing_compare.py`, `affinity_auc.py`) | — | `rt-compare`, `timing-compare`, `affinity-auc` |
| 32 | 요청량으로 제한한 CLS 묶음(탐색) | `policy-mix/`(`--design small-memory-load-k`, `task-count-k`) | `small-memory-load-k-v1`, `task-count-k-v1` | `small-memory-load-k`, `task-count-k` |
| 민감도 | cls-a1-cal: CLS + Algorithm 1, 같은 calibration의 동결 CLS 임곗값 0.887 | CAAS와 같은 출처의 임곗값 |

Algorithm 1은 `chaser/policy/allocator.py`(CAAS Algorithm 1 구현)를 그대로 쓴다. 격리 코어가 가득 차서 놓을 수 없는 task가 있으면
CAAS 규칙으로는 배치가 없으므로, 그 run은 **배치 불가**로 표시한다. 빌드를 위해 그 task는 전체에서 가장 덜 찬 코어에 넣지만(`algorithm1.py`),
이 대체 배치는 CAAS가 아니므로 분석에서 따로 다룬다.

### 사전 등록한 가설과 판정

유형(32 KiB, 768 KiB)마다 4단계, 모두 8개 검정에 Holm(유의수준 0.05). 진술한 방향으로 유의하면 그 유형에서 지지된다.

| 단계 | 비교 | 주 지표와 판정 |
|---|---|---|
| L1 지표 | cls-a1 대 caas | 위반 job 비율 차이의 양측 Wilcoxon(둘 다 측정되고 한쪽이라도 위반한 쌍, 27절 V2와 같은 함수). 위반이 적은 방향 |
| L2 utilization 균형 | cgb 대 cls-a1 | 배치 가능 여부를 포함한 마감 준수: "배치되고 모든 마감을 지킴"의 exact McNemar(양측). 배치 불가는 지키지 못한 것으로 센다. cgb가 더 많은 방향 |
| L3 release | ra-cgb 대 cgb | 둘 다 마감을 지킨 쌍의 TAT 로그 비 양측 Wilcoxon. TAT가 짧은 방향 |
| L4 전체 | ra-cgb 대 caas | 위반 job 비율(L1과 같은 검정). 위반이 적은 방향 |

- **배치 불가 run:** 위반 job·최악 실행시간·TET·TAT의 짝지은 검정에서 빼고, 배치 가능 여부를 포함한 마감 준수에서만 실패로 센다. 시작 실패와 기타 상태는 27절처럼 결측이다.
- **보조(Holm은 보조끼리):** 단계·유형마다 최악 실행시간 증가와 TET(둘 다 마감을 지킨 쌍), L1·L3·L4의 배치 가능 마감 준수, L2·L3의 위반 job. 민감도로 cls-a1-cal 대 caas(위반 job), cls-a1-cal 대 cls-a1(배치 가능 마감 준수).
- **서술:** 칸·배치마다 배치 가능 수, 마감 준수 수, 위반 job 비율. Algorithm 1 변형마다 task 역할별 격리 비율.

### 실행 전 정적 예측 (설정과 CA-CSRD 표에서 계산, 결과 열람 전)
- **배치 가능한 set 수(36개 중, 두 주기 칸 합):**
  - 32 KiB, caas와 cls-a1: U 0.45에서 34, 0.475에서 27, 0.5에서 14, 0.525에서 2, 0.55 이상 0. 저-CLS task가 U의 절반이라 코어 0 하나에 들어가지 않는다.
  - 32 KiB, cls-a1-cal: 16, 10, 2, 그 위로 0.
  - 768 KiB: 세 변형 모두 36(cls-a1-cal의 0.45만 34).
- **격리하는 task:**
  - 32 KiB: caas와 cls-a1 모두 저-CLS task를 전부 격리하고 고-CLS task는 하나도 격리하지 않는다. 저-CLS task의 CA-CSRD는 약 0.12로 CAAS 임곗값 아래다. 그래서 L1은 배치가 같아 차이가 없을 것으로 예상한다.
  - 768 KiB: caas는 768 KiB task 520개 중 320개만 격리한다. 한 번만 훑는 task는 CA-CSRD가 1.0이다. cls-a1은 520개 모두 격리한다.
  - cls-a1-cal은 고-CLS task도 일부 격리한다(32 KiB 6/216, 768 KiB 215/1754).

### 변인

| 구분 | 내용 |
|---|---|
| 조작 변인 | **배치**: caas, cls-a1, cls-a1-cal(이 절), cgb·ra-cgb·wfd·ra·무작위(27절) |
| 통제 변인 | 27절의 set·task·주기·측정 구간 전부(설계 모듈이 27절의 wfd 설정을 그대로 받고 코어만 바꾼다. 테스트로 확인) |
| 입력 | **CA-CSRD**: 27절 wfd 빌드의 yarda hierarchy-rd 분석에서 task별 L1 CSRD 히스토그램으로 `chaser.locality.ca.ca_csrd`를 계산(`ca_table.py`, `results/ca-csrd/`). 정적 분석만 읽는다<br>**CLS**: 설계의 계획값(= yarda CLS) |
| 종속 변인 | 27절과 같다(`rt_metrics.py`, results.jsonl) |
| 조작 확인 | yarda CLS = 계획값, 단독 U 게이트 3%(27절과 같은 task) |

### 실험 방법
1. `ca_table.py`로 27절 두 출력의 CA-CSRD 표를 만든다(완료).
2. 설계마다(`deadline-small-caas` 다음 `deadline-big-caas`) `prepare`(wfd + 세 변형), `isolated`, `pilot`, `full`, `stats`, `rt`(`--builds caas,cls-a1,cls-a1-cal`).
3. `ladder_analysis.py`가 27·28절 출력을 경우마다 짝지어 위 판정을 낸다.
4. 규모는 396 경우 × 3 = 1,188 run이다. 27절이 정상 종료(`supervisor.exit` = 0)한 뒤 시작한다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 -m pytest -q -p no:cacheprovider --rootdir=$R/policy-mix $R/policy-mix   # 명세 테스트
for t in small big; do
    python3 $R/policy-mix/ca_table.py --output $W/.cache/deadline-$t-v1 --dest $R/results/ca-csrd/deadline-$t.json
    O=$W/.cache/deadline-$t-caas-v1
    mkdir -p $O && cp $W/.cache/policy-mix-v1/model-check.json $O/
    for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design deadline-$t-caas --output $O; done
    python3 $R/policy-mix/rt_metrics.py --output $O --builds caas,cls-a1,cls-a1-cal
done
python3 $R/policy-mix/ladder_analysis.py --small $W/.cache/deadline-small-v1 --small-caas $W/.cache/deadline-small-caas-v1 \
    --big $W/.cache/deadline-big-v1 --big-caas $W/.cache/deadline-big-caas-v1 --dest $W/.cache/deadline-ladder-v1
```
실제 실행은 `supervisors/deadline-ladder-v1.sh`다.

### 결과 파일
- `results/ca-csrd/`: 두 유형의 task별 CA-CSRD 표와 원본 분석 파일 해시
- `results/deadline-small-caas/`, `results/deadline-big-caas/`: `protocol.json`, `results.jsonl`, `isolated-u.json`, `rt-metrics.json`, `stats-*.json/md`, `per-set.jsonl.gz`
- `results/deadline-ladder/`: `ladder.json/md`(사전 등록한 판정)와 그림

---

## 31. 재분석: 마감 지표 분리, TET·TAT 비교, 친화도 지표의 실패 예측력 (시뮬레이션 없음)

### 개요
30절에서 마감을 놓친 run의 늦은 job은 거의 모두 첫 hyperperiod(동시 release)에 있고, "위반 job"의 대부분은 그 뒤 밀린 release라는 것을 확인했다.
4장 근거를 탐색 자료로 정리하려고 다음 세 가지를 기존 출력에서 다시 계산한다. 모두 결과를 본 자료라 **탐색**이다.

### 분석 항목
1. **마감 지표 분리:** `rt_metrics.py`에 run 전체(warm-up 포함)의 늦은 job 수(`late_jobs_all`), 그중 warm-up의 수, 첫 늦은 job의 release 시각을 추가했다.
   `rt_compare.py`는 짝지은 비교에서 늦은 job 수를 밀린 release와 따로 보고한다. 17–26절 출력에 다시 적용했다.
2. **TET·TAT 짝지은 비교(`timing_compare.py`):** 19·20·21·23·24·25절과 무작위 기준에서 배치 쌍마다 둘 다 마감을 지킨 경우의 TET·TAT 중앙값 변화, Wilcoxon p(보정 없음, 서술용).
3. **친화도 지표의 실패 예측력(`affinity_auc.py`):** set마다 Σ U(1 − CLS), Σ U(1 − CA-CSRD), 정적 L2 요청량, 메모리 task U로 U 균형 배치의 마감 실패를 예측한 AUC. 20·23·24·17절.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
python3 $R/policy-mix/rt_metrics.py --output $W/.cache/<출력> --builds <그 출력의 P 빌드>   # 17–26절 출력마다
python3 $R/policy-mix/rt_compare.py --cache $W/.cache --output $R/results/rt-compare
python3 $R/policy-mix/timing_compare.py --cache $W/.cache --dest $R/results/timing-compare
python3 $R/policy-mix/affinity_auc.py --cache $W/.cache --runs task-count-v1,cls-spread-v1,small-memory-load-v1,policy-mix-v1 --dest $R/results/affinity-auc
```

### 결과 파일
`results/rt-compare/`(갱신), `results/timing-compare/`, `results/affinity-auc/`. 17–26절의 결과 묶음은 새 `rt-metrics.json`으로 다시 내보냈다.

---

## 32. 요청량으로 제한한 CLS 묶음 (탐색)

### 개요
29·30절에서 묶음 코어가 실효 부하로 과부하가 되고(메모리 task가 계획보다 길게 실행), 주기가 다양하면 release 고려 탐색이 다른 task를 묶음 코어로 옮긴다는 것을 봤다.
`placement_lib`에 두 배치를 추가했다.
- **cgk:** 친화도가 낮은 task를 가장 적은 코어에 모으되, 묶음 코어의 계획 부하가 코어 용량 ÷ 실행 증가 배수를 넘지 않게 한다.
  실행 증가 배수는 동시에 실행되는 task의 L1 miss 요청률 합(묶음 코어 수 × 묶음 task 평균 + 나머지 코어 수 × 다른 task 평균) ÷ L2 처리 능력(1 µs당 20.8 요청)이다. 묶음 코어에는 다른 task를 올리지 않는다. 나머지가 다른 코어에 들어가지 않으면 균형 CLS 묶음으로 돌아간다.
- **ra-cgk:** cgk에서 출발한 release 고려 탐색. 묶음 task는 묶음 코어 안에서만, 다른 task는 묶음 코어 밖에서만 옮긴다.

24절의 set 전체와 20절의 25% 칸에 두 배치를 덧붙여 기존 결과와 짝지어 비교한다. 결과를 본 자료이므로 **탐색**이다. 실행 전 정적 미리보기에서 cgk의 배치는 25%에서 단일 격리 코어(29절의 cls-a1)와 같고, 50%에서는 균형 CLS 묶음과 거의 같았다.

### 재현 명령
```sh
cd $C3 && export PYTHONPATH=$C3
for d in small-memory-load-k task-count-k; do
    O=$W/.cache/$d-v1
    mkdir -p $O && cp $W/.cache/policy-mix-v1/model-check.json $O/
    for s in prepare isolated pilot full stats; do python3 $R/policy-mix/pm_run.py $s --design $d --output $O; done
    python3 $R/policy-mix/rt_metrics.py --output $O --builds cgk,ra-cgk
done
```
실제 실행은 `supervisors/kgroup-v1.sh`다.

### 결과 파일
`results/small-memory-load-k/`, `results/task-count-k/`. 기존 결과와의 비교는 `results/kgroup-check/`(`policy-mix/kgroup_check.py --pair <24절 출력>:<small-memory-load-k-v1> --pair <20절 출력>:<task-count-k-v1>`, 그림 `figures/kgroup_bars.py`, 코어 부하는 `cv_miss_analysis.py --builds cgk,ra-cgk`).

