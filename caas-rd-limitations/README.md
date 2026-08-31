# CAAS/RD Limitation Experiments

This directory contains small experiments for showing where a
reuse-distance-only CAAS view is incomplete. `exp1` and `exp2` run on RTEMS
under the GR740 simulator; `exp3` runs on the host under cachegrind.

## Claims

- `exp1-cache-hierarchy`: standalone RD/CA does not encode the L1/L2 cache
  hierarchy boundary. Similar access patterns can show step changes in runtime
  when the working set crosses cache levels.
- `exp2-task-interference`: task-level `{CA, U}` does not encode placement,
  shared-cache pressure, or cache-set conflicts. A scheduler recommender that
  only sees those features can choose a worse architecture than a cache-aware
  placement.
- `exp3-ca-metric`: CA combines raw reuse distances linearly, so it keeps
  separating workloads that the cache hierarchy has already made
  indistinguishable. Shown with a single task and no interference, so the
  metric itself is the only thing under test.

## Build And Run

Build each RTEMS executable:

```sh
cd exp1-cache-hierarchy && make
cd ../exp2-task-interference && make
```

Run on the GR740 simulator:

```sh
make -C exp1-cache-hierarchy run > results/exp1.log
make -C exp2-task-interference run > results/exp2.log
```

The RTEMS programs print parseable lines:

```text
RESULT,experiment=exp2,case=GLOBAL,metric=elapsed_ns,value=...
```

Convert logs to CSV:

```sh
tools/parse_results.py results/exp1.log -o results/exp1.csv
tools/parse_results.py results/exp2.log -o results/exp2.csv
```

## YARDA And ML Input

Generate YARDA RDH exports for the standalone workloads:

```sh
tools/run_yarda.sh
```

The YARDA files mirror one periodic job body from the RTEMS workloads. Strided
loops such as `i += 32` are analyzed directly through YARDA's loop `step` field.

Build an RTEMS ML framework input JSON:

```sh
tools/build_ml_dataset.py \
  --rdh results/yarda/exp2_yarda_workload_unroll_rdh.json \
  --task-block exp2_standalone_a \
  --task-block exp2_standalone_b \
  --results-csv results/exp2.csv \
  -o results/ml_dataset.json
```

Run the saved RTEMS ML RandomForest model to obtain the scheduling architecture
label:

```sh
tools/rtems_ml_predict.py results/ml_dataset.json --model randomforest
```

Prediction labels match the existing framework: `0=Global`, `1=Clustered`,
`2=Partitioned`. Use `build_ml_dataset.py --label ...` only when creating
training/evaluation data with a known ground-truth label.

## Exp2 Task-Interference 구성

`exp2-task-interference`는 standalone task `{CA, U}` feature만 사용하는
scheduler 추천기가 co-scheduling 이후에 나타나는 cache-interference 효과를
놓칠 수 있음을 보이기 위한 실험이다.

실험은 최대 16개의 standalone job 함수인 `exp2_standalone_a()`부터
`exp2_standalone_p()`까지를 준비한다. 이 함수들은 RTEMS 실행과 YARDA 분석이
공유하는 단일 workload 정의다. 즉, RTEMS 주기 태스크가 호출하는 `job()`
본문과 YARDA가 분석하는 annotated 함수가 동일하다. 각 job은 task-private
array를 `EXP2_SWEEPS`번 sweep한다. TYPE-B preemptive-cache 실험에서는 앞의
`EXP2_B_VICTIMS`개 task를 작은 working set을 갖는 victim task로 두고, 나머지
task는 더 큰 working set을 갖는 polluter task로 둔다.

각 RTEMS task는 주기 태스크로 실행된다.

- `EXP2_JOBS`: task별 측정 job 반복 횟수
- `EXP2_TASK_PERIOD_TICKS`: deadline miss와 utilization 계산에 사용하는 period
- `avg_ns`: task의 `job()` 본문 평균 실행시간
- `max_ns`: task의 `job()` 본문 최대 실행시간
- `misses`: rate-monotonic deadline miss 횟수
- `utilization_ppm`: `avg_ns / period_ns`를 1,000,000 배율로 표현한 값

측정 비교는 세 가지 실행 case로 구성된다.

- `ALONE`: 각 task를 CPU 0에서 단독 실행한다. standalone 실행시간을 얻고,
  utilization과 ML 입력을 계산하기 위한 기준으로 사용한다.
- `GLOBAL`: task affinity를 설정하지 않는다. RTEMS SMP scheduler가 task를
  전역적으로 배치하거나 migration할 수 있다.
- `PARTITIONED`: task를 특정 core에 고정한다. TYPE-B에서는 utilization 기준으로
  task를 정렬한 뒤, low-CA task는 isolated core set에 배치하고 higher-CA victim
  task는 residual utilization이 가장 큰 non-isolated core에 배치하는
  cache-affinity-aware allocation 규칙을 사용한다.

TYPE-B case에서는 victim task를 먼저 시작하고 한 tick 뒤에 high-priority
polluter task를 시작한다. 이는 같은 core에서 polluter가 victim을 선점하고
private-cache 상태를 오염시키는 intra-core preemptive-cache-interference
상황을 만들기 위한 설정이다. 이러한 co-scheduling 및 cache pollution 정보는
standalone `{CA, U}` feature vector에 포함되지 않는다.

주요 비교 지표는 group `elapsed_ns`가 아니라 task-level `job()` 실행시간이다.
Mean job time은 평균적인 task-level slowdown을 보여주고, worst job time은
가장 느린 task를 나타내므로 real-time 관점의 병목과 deadline risk를 가장
직접적으로 드러낸다. 현재 task-count sweep은 4-core GR740 target에서 4, 8,
12, 16개 task를 사용하며, RandomForest 예측 결과와 실제 `GLOBAL` 및
`PARTITIONED` 실행 결과를 비교한다.

## Exp3 CA Metric Saturation 구성

`exp3-ca-metric`은 캐시 간섭 없이 CA 지표 자체의 한계를 보이기 위한 실험이다.
단일 태스크가 `distinct`개의 서로 다른 주소를 cache-line 간격으로 순환
접근하고, 그 순환을 `sweeps`번 반복한다.

이 접근 패턴에서는 재사용 히스토그램이 두 점(store에 의한 `RD = 0`과 다음
sweep의 `RD = distinct - 1`)으로 축약되므로 CA가 닫힌 형식으로 떨어진다.
따라서 수백만 접근 트레이스에 reuse-distance analyzer를 돌리지 않고도 CA를
정확히 계산할 수 있다.

```text
CA(D, S) = (2S - 1) / ((2S - 1) + (D - 1)(S - 1))
```

이 식은 `results/yarda/` 아래 export된 8개 블록 전부에서 YARDA의
element-granularity 출력과 정확히 일치한다. CA counting은 cache-line이 아니라
**주소 단위**이며, 이는 CAAS 논문의 계산 방식을 따른 것이다.

비용은 바이너리가 스스로 측정하지 않는다. cachegrind에 GR740 캐시 형상을
명령줄로 강제해서 외부에서 측정한다. GR740은 코어당 L1 16 KB, 공유 L2 2 MB이며
둘 다 4-way / 32 B line이다.

```sh
make -C exp3-ca-metric
tools/run_cachegrind_sweep.sh
tools/plot_ca_saturation.py
```

`ACCESSES`는 케이스마다 고정한다. 그래야 프로세스 시작 트래픽과 cold miss
비중(`1/sweeps`)이 working set 사이에서 비교 가능한 상태로 유지된다.
`DISTINCT_LIST`와 `ACCESSES`는 환경 변수로 덮어쓸 수 있다.

읽는 법: CA는 D에 반비례해 단조 감소하지만 miss rate는 L1(16 KB)과 L2(2 MB)
경계에서만 계단식으로 변한다. 같은 계층 안에 있는 두 워크로드는 CA가 수백 배
차이나도 실측 miss rate가 동일하다. 결과는 다음에 기록된다.

```text
results/exp3_ca_saturation.csv
results/exp3_ca_saturation.png
results/exp3_ca_saturation.pdf
```

### Exp3 측정 경로 제약

exp3의 비용 축은 시간이 아니라 miss rate다. laysim 라이선스가 없는 환경에서
작성했기 때문이다. cachegrind는 SPARC 바이너리가 아니라 같은 접근 패턴을 갖는
호스트 빌드를 실행한다. 이전되는 것은 접근 패턴과 명령줄로 강제한 캐시
형상이고, SPARC ISA와 GR740의 write-through L1, 메모리 컨트롤러 타이밍은
이전되지 않는다. 또한 cachegrind는 last-level cache를 단일 캐시로 모델링하므로
L2를 4코어가 공유한다는 사실이 반영되지 않는다. exp3은 단일 태스크 실험이라
여기서는 문제가 되지 않지만, 간섭 변형을 만들 때는 문제가 된다.

laysim이 가용한 환경에서는 exp1과 같은 방식으로 RTEMS 주기 태스크에
`rtems_clock_get_uptime_nanoseconds()`를 감아 ns 영역 측정을 추가할 수 있다.
현재 시간 영역에서 교차 확인된 구간은 exp1이 측정한 L1 -> L2 계단뿐이다.

| working set | 계층 | laysim ns/access | cachegrind |
|---:|---|---:|---|
| 8 KB | L1 hit | 108.676 | L1 miss 0.0% |
| 24 KB | L2 hit | 160.508 | L1 miss 99.6% |
| 512 KB | L2 hit | 160.398 | L1 miss 99.6% |
| 1.5 MB | L2 hit | 160.394 | L1 miss 99.6% |
| 2 MB 초과 | RAM | 미측정 | L2 miss 99.6% |

두 측정은 L1 계단의 위치와 L2 구간의 평탄성에서 일치한다. 아직 시간 영역에서
확인되지 않은 것은 L2 -> RAM 계단의 ns 크기다. 위 laysim 값은
`avg_ns / (working_set / 32 * EXP1_SWEEPS)`로 환산했으며 `EXP1_SWEEPS`는 256이다.

## Expected Reading

In `exp2`, the ML input contains only standalone task `{CA, U}` values. The
architecture cases are measured separately:

- `GLOBAL`: no task affinity; RTEMS SMP can place tasks globally.
- `PARTITIONED`: active tasks are pinned to cores. TYPE-B uses the
  cache-affinity-aware allocation rule with isolated/non-isolated core sets.

Compare the RandomForest prediction with the measured best architecture by
checking task `avg_ns`/`max_ns` and `misses` for these two cases. A mismatch
means the `{CA, U}`-only model selected an architecture that
does not match the measured cache-interference behavior.

The current two-architecture comparison is written to:

```text
results/exp2_global_partitioned_only.md
```

The high-CA four-task variant is written to:

```text
results/exp2_high_ca_architecture.md
```

The high-CA/high-utilization eight-task variant is written to:

```text
results/exp2_high_ca_high_u_architecture.md
```

The current no-deadline-miss sweep over task count, CA, and utilization is
summarized in us/ms units at:

```text
results/exp2_sweep_overview.md
results/exp2_sweep_summary.md
```

The strongest current failure case is TYPE-B: the RandomForest predicts
`GLOBAL`, but the measured task-level `job()` time favors `PARTITIONED` by more
than 20% with zero deadline misses:

```text
results/exp2_global_partitioned_only.md
```

The TYPE-B task-count sweep and matplotlib plot are written to:

```text
results/type_b_gp_task_sweep.md
results/type_b_gp_task_sweep_bar.png
results/type_b_gp_task_sweep_bar.pdf
results/type_b_gp_task_sweep.png
```

When the comparison objective is task-level `job()` execution time, use:

```text
results/exp2_job_time_comparison.md
```

That variant raises standalone CA to about `0.222` by using a small hot
conflict-stride footprint. For the scheduler-failure claim, prefer the
task-level `job()` time comparison over group `elapsed_ns`, because the periodic
task body is the measured execution-time quantity used to compute `U`. Scaling
features in the ML framework can change model training behavior, but it does not
change the raw CA value. A MinMax scaler must be fitted during training and
reused at inference; applying it only at inference would make saved-model
predictions inconsistent.
