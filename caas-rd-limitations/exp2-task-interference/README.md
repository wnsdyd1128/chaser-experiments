# Exp2: Task Interference

명령은 실험 루트 `caas-rd-limitations/`에서 실행한다. 문서 안의 경로는
모두 그 기준이다. 공통 빌드 규약과 CAAS 모델 입력 경로는
[../README.md](../README.md)에 있다.

## 구성

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
