# CAAS/RD Limitation Experiments

This directory contains two small RTEMS experiments for showing where a
reuse-distance-only CAAS view is incomplete.

## Claims

- `exp1-cache-hierarchy`: standalone RD/CA does not encode the L1/L2 cache
  hierarchy boundary. Similar access patterns can show step changes in runtime
  when the working set crosses cache levels.
- `exp2-task-interference`: task-level `{CA, U}` does not encode placement,
  shared-cache pressure, or cache-set conflicts. A scheduler recommender that
  only sees those features can choose a worse architecture than a cache-aware
  placement.

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
