# CAAS/RD Limitation Experiments

This directory contains small experiments for showing where a
reuse-distance-only CAAS view is incomplete. Each experiment carries its own
README with the design, the commands, and the measured numbers; this file
carries only what they share.

| experiment | what it shows | measured with |
|---|---|---|
| [exp1-cache-hierarchy](exp1-cache-hierarchy/README.md) | RD/CA does not encode the L1/L2 boundary | RTEMS under laysim |
| [exp2-task-interference](exp2-task-interference/README.md) | task-level `{CA, U}` does not encode placement or interference | RTEMS under laysim, RandomForest |
| [exp3-ca-metric](exp3-ca-metric/README.md) | CA keeps separating workloads the hierarchy has made identical | cachegrind, RTEMS under laysim |
| [exp4-ca-mean-rd](exp4-ca-mean-rd/README.md) | CA reads the reuse histogram only through its weighted mean | RTEMS under laysim, cachegrind |
| [exp5-1-ca-arch-mismatch](exp5-1-ca-arch-mismatch/README.md) | one `{CA, U}` vector, opposite best architectures; the model's answer costs up to 30% | RTEMS under laysim, RandomForest |
| [exp5-2-ca-cluster-mismatch](exp5-2-ca-cluster-mismatch/README.md) | the same, with `CLUSTERED` as the ground truth | RTEMS under laysim, RandomForest |

## Claims

- [`exp1-cache-hierarchy`](exp1-cache-hierarchy/README.md): standalone RD/CA
  does not encode the L1/L2 cache hierarchy boundary. Similar access patterns
  can show step changes in runtime when the working set crosses cache levels.
- [`exp2-task-interference`](exp2-task-interference/README.md): task-level
  `{CA, U}` does not encode placement, shared-cache pressure, or cache-set
  conflicts. A scheduler recommender that only sees those features can choose a
  worse architecture than a cache-aware placement.
- [`exp3-ca-metric`](exp3-ca-metric/README.md): CA combines raw reuse distances
  linearly, so it keeps separating workloads that the cache hierarchy has
  already made indistinguishable. Shown with a single task and no interference,
  so the metric itself is the only thing under test.
- [`exp4-ca-mean-rd`](exp4-ca-mean-rd/README.md): CA depends on the reuse
  histogram only through its weighted mean, so two workloads with the same mean
  RD but different histogram shapes get the same CA while sitting on opposite
  sides of the L1 boundary.
- [`exp5-1-ca-arch-mismatch`](exp5-1-ca-arch-mismatch/README.md): because CA
  counts address reuse rather than cached lines, two task sets can carry one
  `{CA, U}` feature vector into opposite best scheduling architectures. The
  CAAS RandomForest answers `GLOBAL` for all sixteen measured cases; that answer
  costs 21.7% to 30.3% of victim job time on six of them, at task-set sizes of
  8, 12 and 16 tasks, and nothing on their packed twins, which carry the same
  feature vector.
- [`exp5-2-ca-cluster-mismatch`](exp5-2-ca-cluster-mismatch/README.md): the
  same blindness with `CLUSTERED` as the ground truth. Two task sets again
  share one `{CA, U}`; for one of them the measured best placement is a
  two-scheduler cluster and the model's `GLOBAL` costs 10.3% of victim response
  time, for the other `GLOBAL` is fine.

## Build And Run

Every RTEMS experiment shares `common.mk`, so it builds and runs the same way.
Commands are given from this directory.

```sh
make -C <experiment>
script -q -c "make -C <experiment> run" results/<experiment>.log
```

`make run` calls `laysim-gr740-cli -r -core0` on the built executable. The
`script` wrapper is there because laysim writes to a terminal. Experiments with
several compile-time cases have a runner under `tools/` that rebuilds and runs
each case instead; their READMEs name it.

The RTEMS programs print parseable lines:

```text
RESULT,experiment=exp2,case=GLOBAL,metric=elapsed_ns,value=...
```

Convert a log to CSV:

```sh
tools/parse_results.py results/<experiment>.log -o results/<experiment>.csv
```

## YARDA And ML Input

Generate YARDA RDH exports for the standalone workloads:

```sh
tools/run_yarda.sh
```

The YARDA files mirror one periodic job body from the RTEMS workloads. Strided
loops such as `i += 32` are analyzed directly through YARDA's loop `step` field.
Where the access pattern is a plain cyclic sweep, CA has a closed form and the
experiment computes it directly rather than running the analyzer; exp3 states
that form and checks it against YARDA.

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
training/evaluation data with a known ground-truth label. Scaling features in
the ML framework can change model training behavior, but it does not change the
raw CA value. A MinMax scaler must be fitted during training and reused at
inference; applying it only at inference would make saved-model predictions
inconsistent.

## Figures

Figures are written next to the data in `results/`, as PNG at 300 dpi and as PDF
for typesetting. They carry data only: the sentence that explains a figure lives
in its experiment's README under "그림 캡션", ready to be used as a paper
caption. One visual grammar holds across all of them.

| element | meaning |
|---|---|
| red | `GLOBAL` |
| blue | `PARTITIONED` |
| green | `CLUSTERED` |
| grey | tie, or a placement that needs information CAAS does not carry |
| black line | CA, the CAAS feature; over a bar, a value a model predicts |
| solid / hatched bar | mean / worst case |
| filled dot | placement the measurement picked |
| open ring | placement CAAS predicted |
| red percentage | what the prediction costs against the measured best |

The two marks sit on one line above the bars, so only the bar they stand over
carries meaning: apart is a misprediction, the dot centred in the ring is
agreement. A percentage is set in red once it passes the 5% band that separates
an architecture preference from a placement detail.

## Results

Every log, CSV, report and figure lands in `results/`, which is ignored by git.
Each experiment's README lists the files it writes. Build directories are
`b-*/` and are ignored as well.
