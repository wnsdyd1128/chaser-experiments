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
   - c2 = 4d03b93 + `c2-topology.patch`, `rtems/baseline/build/yarda` = YARDA a058a454 빌드
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
원래 실행은 보정을 v1 출력(`cls-bimodal-v1/calibration`)에서 하고 v2로 복사했다. job 시간
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
mkdir -p $O && cp -a $W/.cache/cls-bimodal-v2/calibration $O/calibration
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
mkdir -p $O && cp -a $W/.cache/cls-bimodal-v2/calibration $O/calibration
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
mkdir -p $O && cp -a $W/.cache/cls-bimodal-v2/calibration $O/calibration
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

## 11. 폐기하거나 바꾼 설계

| 출력(`.cache/`) | 내용 | 바꾼 이유 |
|---|---|---|
| `period-distribution-v1` | μ ∈ {20, 80, 320} ms, 격자 기준 20 | 기준 20인 격자가 μ = 50을 담지 못함 → 기준 10·격자 180(v2). 240 run 후 중단 |
| `cls-distribution-v1/calibration` 1차 | R 격자 + 정수 S | 정수 반올림으로 U 오차가 최대 27% → (R, S) 공동 탐색으로 교체 |
| `cache-affinity-v1` | 1 ms 주기에서 코어당 U 0.40 | pilot에서 G/C/C2 deadline miss → 1 ms 주기는 U ≤ 0.0625(v2) |
| `cls-bimodal-v1` | 주기 20 ms, U 0.125 | pilot에서 낮은 CLS task가 많은 셀이 deadline miss(공동 실행 job CPU가 단독의 최대 2.75배) → 같은 job을 주기 40 ms로(v2). pilot 결과는 `results/cls-bimodal-v1-pilot/` |
| `cls-bimodal-v1/calibration.failed-unroll-0` | 패딩 루프 펼침 방지 전 보정 | K ≤ 4 루프가 완전히 펼쳐져 시간 모델 검증 오차 12.8% → pragma와 3라운드 하한 추가 |

---

## 12. 결과 묶음 사용법

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
