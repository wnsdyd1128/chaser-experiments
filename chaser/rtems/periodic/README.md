# Periodic G/C/P measurement harness

## Main-experiment split policy

The agreed split is **train/test/validation = 60%/20%/20% within each of the
five workload families**. It evaluates new tasksets from known families.
Deduplicate identical execution inputs before splitting. Keep each taskset's
repeated measurements, G/C/P results, representations and policy variants in
one split. Distinct parameter configurations may cross splits within a family.
The frozen seed is **20260921**. Use largest-remainder integer allocation with
ties resolved train, validation, test. Families need at least three unique inputs;
if rounding leaves a split empty, transfer one from the largest group (same tie
order). Record per-family counts and the membership hash. Train is
for fitting, validation for calibration/model selection, and test for final evaluation.
Do not redraw membership based on performance or replace excluded test samples.

The [input-freeze-v1 artifact](../../artifacts/periodic/input-freeze-v1/README.md)
freezes the 207 unique V3 tasksets: **train 126 / validation 41 / test 40**, with all
five families in every split. It retains the 93 excluded duplicates and the 11
excluded development probes. V1–V3 archives and their family-held-out proposals
remain historical evidence. `rtems_periodic_pool --version 1/2/3` still reproduces
those proposals; use `tools.rtems_periodic_freeze` for the main-experiment freeze.

Schema 2 assigns each workload by its policy-independent input signature, using
ascending SHA-256 of `[policy_id, seed, family_id, input_signature]`. Names,
eligibility flags, policy and task-to-core placement do not create new tasksets;
ordered work, shape, sweep, period and horizon remain part of the identity.
`freeze_split()` and `tools.build_dataset` default to this policy. Dataset workload
rows must include `input_signature` from the frozen population; every policy uses
the same workload ID and signature. The explicit `family-70-20-10-v1` option is
for legacy reproduction. Existing files are validated and reused without reseeding;
changed membership, input identities or assignments are rejected.

## Measurement and learning order

1. Freeze input configurations and split membership — completed in input-freeze-v1.
2. Validate final ELF analysis/layout and collect independent U and static features.
3. Measure validation mappings, then freeze theta and allocation policy.
4. Measure G/C/P under each frozen policy and finalize eligible architecture labels.
5. Fit RF/scaler on train, select models on validation, and evaluate on test.

Independent U precedes calibration because the allocator consumes U. Theta
calibration does not require RF or architecture labels. Changing theta can change
C/P mappings and their labels, so final labels and RF follow policy freezing.
S2 may optionally run earlier under an already fixed CAAS baseline policy; that
does not supply labels for a later changed allocator. This is not the default order.

The input freeze preserves V3 sweep/period/horizon and predeclares measured bounds
`u_max=0.25`, `U_max=2.0`. Estimated U does not prove these bounds or deadline
feasibility. Retain failures and exclusions in their original split without
replacement. Runtime eligibility, dataset sufficiency and wall-time/storage budget
remain pending; the input freeze does not declare a training-ready dataset.


This harness builds RF dataset measurements and supports later allocation/system
experiments. The first pilot uses explicit placements, **not calibrated theta or
a trained RF**. It does not establish a performance improvement or target cache
accuracy. The measurement backend is the installed `laysim-gr740`, not silicon.

Pre-label frozen-input collection is available through
`python3 -m tools.rtems_periodic_characterize prepare|run`.
`prepare --workers N` builds, analyzes, and compresses up to N tasksets concurrently
in separate snapshot directories (1--8, default 8). Each worker retains the same
full-event XZ preset 6 compression and verification; peak JSON and compressor
memory scales with N. Progress records completed tasksets in completion order.
`run --workers N` shares a single pool of at most N independent simulators across
up to N in-flight tasksets. A free slot can execute another taskset's batch while
slower batches finish; simulator concurrency stays bounded globally (1--8, default 8).
Progress records tasksets in completion order. A single SIGINT to the collector
PID stops admitting tasksets and waits for submitted batches to finish; do not
signal the simulator process group or interrupt the drain a second time.
Complete batches are revalidated on resume, including batches whose taskset
summary was not published before the interrupt. Existing incomplete batches
remain failures and are never overwritten.
Use `prepare --workers 8 --prepare-workers 16` to increase preparation concurrency
without changing the simulator worker count in `protocol.json`. The optional
`--prepare-workers` override accepts 1--16 and applies only to `prepare`.
Previously completed preset 9 extreme archives remain valid and are reused;
each analysis manifest records the actual preset and original byte identity.
Preparation shares a separate four-worker compression queue. Producers reserve
one of 16 raw-file slots **before** running the event exporter; slots include
generating, queued, and compressing files. Linux `prlimit` enforces a 1 GiB limit
on each exporter output file and disables core dumps. Thus newly generated raw
event JSON is bounded by 16 GiB across the collector. When full, producers wait.
`prepare-compression.json` records these limits. Compressed outputs, other build
artifacts, and previously preserved interrupted directories are additional disk
usage; this is not a cap on the entire output tree.
Compression removes raw JSON only after successful restoration verification.
Any export/validation/compression failure stops new queue admissions and preserves
the failing evidence; already submitted compression jobs finish. A taskset is
complete only after all its compression futures succeed and its manifest is
written. A file exceeding 1 GiB is a reported failure, never truncated evidence
accepted as a successful analysis.
Complete snapshots are revalidated and reused; incomplete snapshots are preserved
and reported as failures. Stop an existing collector before resuming the same output.
See [characterization v1](../../artifacts/periodic/characterization-v1/README.md)
for the original serial collection record, lossless event compression, commands,
and remaining collection work.

Collector progress and feature records use `dataset_stage` instead of the former
`dataset_ready: false` flag. `phase` remains the command (`prepare` or `run`).

| `dataset_stage` | Meaning |
|---|---|
| `preparing` | ELF analysis/compression collection is in progress |
| `prepared` | All planned ELF analysis/compression results passed verification |
| `prepare_failed` | Preparation finished with one or more failed inputs |
| `characterizing` | Independent U and feature collection is in progress |
| `characterized` | Independent U and feature processing completed successfully |
| `characterization_failed` | Characterization finished with failed inputs |

Each workload record carries its own completed/failed stage; the top-level stage
describes the whole collection. `characterized` does not assert utilization bounds,
defined features, policy calibration, labels, or training eligibility; those checks
remain separate. `protocol.json` contains fixed measurement settings, not progress.
Resuming a legacy protocol removes only its false readiness flag after checking
all measurement parameters. Immutable frozen-input and historical artifacts retain
their original schema.

## Terminology

| Term | Korean term | Meaning |
|---|---|---|
| Task | 태스크 | One periodic execution unit with a private data array |
| Taskset | 태스크 집합 | Tasks executed together; one RF sample |
| Memory access pattern | 메모리 접근 패턴 | Address and traversal rules within a task |
| Workload template | 워크로드 생성 원형 | Rules for constructing tasks and tasksets |
| Workload family | 워크로드군 | Tasksets connected by a common template or reuse of base tasks |
| Within-family stratified random split | 워크로드군 내 층화 무작위 분할 | Random assignment of unique tasksets within each family: train/test/validation = 60/20/20 |

A workload family includes parameter and role variants, not only identical
access sequences. Reusing base tasks across templates connects their families
transitively. Sharing a template does not mean sharing runtime memory. All five
families appear in every split; unique tasksets are the assignment units.
The existing `family_id` identifies a workload family. Provenance relationships
may still be called lineage in code; identifiers and archived evidence are
unchanged by this terminology choice.

## Build, analyze, and execute

Run from the CHASER workspace. Prerequisites are the installed GR740 RTEMS SDK,
Clang/opt 14, waf, and the YARDA targets built by `scripts/verify`.

```sh
python3 -m tools.rtems_periodic prepare configs/periodic-example.json \
  --output .cache/periodic-example
python3 -m tools.rtems_periodic analyze .cache/periodic-example
python3 -m tools.rtems_periodic run .cache/periodic-example \
  --architecture g --runs 10 --output .cache/periodic-example-g
python3 -m tools.rtems_periodic run .cache/periodic-example \
  --architecture c --runs 10 --output .cache/periodic-example-c
python3 -m tools.rtems_periodic run .cache/periodic-example \
  --architecture p --runs 10 --output .cache/periodic-example-p
```

Preparation refuses existing directories and copies source, generated config,
topology/linker settings, waf/wscript, and cache configuration. Waf selects
`/opt/rtems/6` explicitly and compiles **one shared workload object** for all three
ELFs. `build/compile_commands.json` retains all actual compiler invocations,
including the three separately configured `init.c` compilations. Manifest hashes
cover the object files, ELFs, sources, build log and SDK compiler/libraries.

The task configuration contains literal `distinct`, byte `stride`, `sweeps`,
`period_ticks`, and explicit allocator `core`. Tasks read separate volatile byte
arrays initialized to one. A job executes a fixed access sequence and returns a
load-count checksum modulo 2^32. The compiler is not asked to inline helpers;
YARDA expands their `ape.inline` annotations under each `ape.analyze` job root.
The task source and sweep count stay identical across G/C/P and independent runs.

`horizon_ticks` must be a multiple of every task period. Each task executes
`horizon_ticks / period_ticks` jobs; the period tick is 1 ms. Tasks are bounded to
1–16, at most 4096 total jobs, and at most 16 MiB of aligned workload data.
The cold job locality is a feature, not a prediction of warm, concurrent periodic
cache activity. Array data and cache state are not reset between sweeps or jobs.

### Workload patterns

Source-informed synthetic recipes are specified in [RECIPES.md](RECIPES.md).
They require an even `width` in 2–32 and complete blocks in `distinct`.
Generate the mixed v2 input pool (without measurements or labels) in a fresh directory:

```sh
python3 -m tools.rtems_periodic_pool --version 2 --output .cache/periodic-candidates-v2
```

The preserved [candidates-v2 artifact](../../artifacts/periodic/candidates-v2/README.md)
contains 180 tasksets, three conservative recipe families and a provisional split.
PolyBench remains reserved for external evaluation. Omitting `--version` retains v1 generation.

Audit the prepared pool before choosing final membership:

```sh
python3 -m tools.rtems_periodic_pool_audit --pool .cache/periodic-candidates-v2 \
  --output .cache/periodic-candidates-v2-audit.json
```

The audit verifies the pool manifest and reports duplicate generator inputs,
estimated utilization by coverage cell, role/core/period correlations and run
budgets. It preserves all candidates and refuses to overwrite the report.
V2 has 123 distinct input configurations among 180 named candidates; its LLC
cells repeat identical inputs across all three target-U tags. See the
[readiness audit](../../artifacts/periodic/readiness-v1/README.md) before interpreting
candidate counts or target U as achieved coverage. No measured evidence is reused
between different ELFs, and the audit does not freeze a split.

`--version 3` adds the [staged/triangular recipes](STAGED-RECIPES.md), yielding five
source-informed families. It retains one copy of each identical generator input
and records every duplicate configuration and its representative in `pool.json`.
The split remains provisional; additional families do not establish sufficiency.

Omitting `pattern` retains the original cyclic source and plan fields. The three
supported values specify byte-element access order, not an application family:

| Pattern | One job |
|---|---|
| `cyclic` | Traverse all `distinct` elements, repeat `sweeps` times |
| `hot-cold` | Traverse H `hot_repeats` times, then C `cold_repeats` times; repeat that block `sweeps` times |
| `phase` | Perform all `sweeps * hot_repeats` H traversals, then all `sweeps * cold_repeats` C traversals |

Both region patterns require `hot_distinct`, `hot_repeats`, and `cold_repeats`.
H consists of the first `hot_distinct` accessed elements; C contains the remaining
`distinct - hot_distinct` elements in the same private array. Each is nonempty;
both repeat counts are integers in 1–1000000. These fields are rejected for cyclic
workloads. All traversals use the same byte stride. Region patterns execute
`sweeps * (hot_distinct * hot_repeats + (distinct - hot_distinct) * cold_repeats)`
loads per job. Phase ordering restarts each job; it does not depend on job index.
Its kernel contains the region sweep loops and the wrapper invokes it once.

For equal parameters, hot/cold and phase have the same data layout and load count
but different access order. Small literal sequences test the reference checker
and the emitted APE against each final ELF. Analysis budgets include every nested
loop trip, not just the number of loads. The checksum alone does not prove access
order because all elements are initialized to one.

`configs/periodic-patterns-example.json` is a development-only, two-task example:
each task touches 1088 lines (34 KiB) and executes 10240 loads per job. Use the
same prepare/analyze/run commands with fresh output paths. This example is not a
frozen training dataset or evidence of sufficient independent families. Pattern
names and parameter changes do not establish family independence.
The [pattern validation evidence](../../artifacts/periodic/patterns-v1/README.md)
preserves 50 timing/U runs, three diagnostics and ten empty runs from this example.

### Development probes and resource boundaries

`tools.rtems_periodic_probes` freezes eleven two-task probes for line layout,
L1/LLC capacity boundaries, hot/cold and phase order. Eight additional inputs
exercise 4/8/12/16 tasks, balanced/skewed 4096-job counts, exactly 16 MiB of
aligned data, and one LLC-sized task among fifteen small tasks. All inputs are
development-only and ineligible for training or held-out evaluation.

```sh
python3 -m tools.rtems_periodic_probes init /tmp/chaser-probes-new
python3 -m tools.rtems_periodic_probes build /tmp/chaser-probes-new
python3 -m tools.rtems_periodic_probes build /tmp/chaser-probes-new --group boundaries
python3 -m tools.rtems_periodic_probes run /tmp/chaser-probes-new --stage smoke
python3 -m tools.rtems_periodic_probes run /tmp/chaser-probes-new --stage repeat --workers 8
python3 -m tools.rtems_periodic_probes run /tmp/chaser-probes-new --stage diagnostic
python3 -m tools.rtems_periodic_probes run /tmp/chaser-probes-new --stage empty
python3 -m tools.rtems_periodic_probes run /tmp/chaser-probes-new \
  --group boundaries --stage boundary --timeout 600
python3 -m tools.rtems_periodic_probe_report /tmp/chaser-probes-new \
  --output /tmp/chaser-probes-report.json
```

The simulator needs an accessible X display even in batch mode. Select it with
`DISPLAY` in the collection environment. Every stage refuses an existing output
directory; `--only` selects that stage's entire population and cannot append to a
previous stage. Preserve failures and use a fresh root for a changed environment.
Repeated collection requires successful smoke and analysis tied to the same
snapshot. The full-suite reporter rechecks every planned batch and recalculates
independent U; it does not generate labels or RF samples.

Build and analysis costs are separate. Linux `wait4` RSS is the largest process
high-water mark, not the simultaneous memory sum. The 4096-job logical limit is
also distinct from C's `TASK_COUNT * MAX_JOBS` static record reservation and from
the cost of printing all records. Boundary inputs receive build/runtime checks;
the eleven primary probes receive full G/C/P linked-stream analysis.
See the [feasibility evidence](../../artifacts/periodic/feasibility-v1/README.md)
for measured costs, runtime failures, and the additional operating-budget probes.

## Scheduler and release evidence

| Architecture | EDF SMP scheduler ownership | Assignment |
|---|---|---|
| G / 0 | `{0,1,2,3}` | All tasks share one scheduler |
| C / 1 | `{0}`, `{1,2,3}` | Core 0 maps to the singleton; other cores to the shared domain |
| P / 2 | Four singleton schedulers | Task uses its configured core |

All workers request the full online affinity mask. Scheduler ownership defines
the domain; C does not approximate a cluster with a partial affinity mask. The
coordinator is pinned to core 0 and blocks during measurement. Scheduler ID,
processor set, affinity and job endpoint cores are checked. Optional dispatch
traces check all recorded worker dispatches, rather than inferring migration
behavior from job endpoints.

Workers are prepared before a future nominal tick `t0`. Each arms its real
`rtems_rate_monotonic_period()` at that tick, then waits at an automatic barrier.
The barrier allows all workers, including those sharing one core, to arm before
any workload begins. Subsequent jobs block on their actual task periods. Release
is `t0_ns + job_index * period_ticks * tick_ns`, never the dispatch timestamp.

### Public measurement contract v2

New plans and run headers identify `chaser-periodic-measurement-v2`. Normal timing,
independent U and empty-job runs use public RTEMS APIs. They never call
`probe_period()` or install the dispatch extension. The same ELF contains an
optional diagnostic path selected by `--trace`; workload, layout, topology and
release settings therefore stay identical between timing and diagnostic runs.
Workers cancel their period after the last recorded job and wait at a cleanup
barrier. Once all measurements finish, the coordinator removes the diagnostic
extension and releases cleanup. Period deletion and task exit cannot contend on
the object allocator while another worker is still measuring. Dispatch validation
covers preparation and measurement; teardown dispatches are outside its scope.

Both public tick readings around the first `period()` call must equal `t0_tick`.
For each job, two `get_status()` calls supply CPU time, wall time since period
initiation, state and postponed-job count. Uptime brackets each status call.
If a call observes wall duration `w` between uptime readings `lo` and `hi`, its
epoch is constrained to `[lo-w, hi-w]`. The before/after intervals must overlap
(allowing 1 ns of conversion rounding). Their intersection must be narrower than
one tick and entirely within one tick of the nominal release. Preemption may
widen either individual interval; unresolved uncertainty fails validation.

These bounds check consistency with one accounting epoch and the release phase;
they do not directly observe the private watchdog or EDF deadline. Normal raw
jobs omit `epoch_*`, `timer_*` and `edf_*` fields, and validators reject their
presence. `ready_ns` remains null because neither path measures the exact ready
transition. No slack is added to completion deadline checks, including the last
job where no later `period()` call can report a timeout.

Only `--trace` calls `probe.c` to read the locked period epoch, watchdog and EDF
priority node and installs the dispatch recorder through `rtems_extension_create()`.
This path depends on the installed SDK ABI; manifest hashes identify its libraries.
The private `SBT_1S` offset is removed to match zero-based uptime. Watchdog and EDF
deadlines must match nominal ticks exactly, and the private epoch must agree with
the public status bounds. Diagnostic timing never enters U or label datasets.
Historical v1 plans/logs remain readable using their original private-probe rules;
the archived `pilot-v1` evidence is unchanged.
The [v2 validation evidence](../../artifacts/periodic/public-api-v2/README.md)
preserves 90 timing/U runs, four diagnostics, ten empty runs, and one expected
final-job failure, along with superseded attempts and v1 revalidation.

## Metrics and failure handling

Per job, `executed_since_last_period` from the public rate-monotonic status API is
sampled before and after workload execution within the uptime interval. All records
are buffered in RAM; printing happens after every worker finishes.

- `TET = sum(cpu_after_ns - cpu_before_ns)` over all measured jobs.
- `TAT = sum(completion_ns - nominal_release_ns)` over all measured jobs.
- `makespan_ns = max(completion_ns) - t0_ns` is retained separately.
- `mean_elapsed_ns` and `max_elapsed_ns` summarize `completion_ns - start_ns`.
  Elapsed includes preemption after start and excludes waiting before start.
- CPU sample overhead inside the measured interval is included and never subtracted.
- Timeout, missing/duplicate job, checksum error, wrong domain, shifted period,
  accounting error, deadline miss and postponed job cause failure, including on
  the final job. Partial records and sums remain in the raw results.

Simulator exit zero is insufficient. The runner requires complete structured
records, validates them, hashes raw logs, and checks the prepared ELF before and
after execution. GNU timeout bounds each PTY/simulator process group. A batch
never replaces unsuccessful attempts. `load_batch()` rechecks raw evidence before
the dataset adapter consumes it. Failed runs retain their identity and cannot
produce successful labels.

## Independent utilization and diagnostic modes

Use `--architecture p --mode N` for **only task N−1 on core 0**, with the same P ELF,
arrays, initialization, job code, periods and job counts. The runner writes only
the mode/trace/empty control words through a preserved simulator boot batch; it
does not patch the ELF or recompile the workload.

```sh
python3 -m tools.rtems_periodic run .cache/periodic-example \
  --architecture p --mode 1 --runs 10 --output .cache/periodic-example-u0
python3 -m tools.rtems_periodic run .cache/periodic-example \
  --architecture c --trace --runs 1 --output .cache/periodic-example-c-trace
python3 -m tools.rtems_periodic run .cache/periodic-example \
  --architecture p --mode 1 --empty --runs 10 --output .cache/periodic-example-overhead
```

Characterization requires ten successful independent runs for every task:
`U_i = sum(job CPU ns) / (10 * K_i * period_ns)`. It is an observed mean, not WCET
or a schedulability guarantee. Trace, empty-job and characterization records are
rejected by the normal timing-to-label adapter. Trace overflow invalidates the run.
Empty-job CPU cost is reported separately and not subtracted from measured jobs.

## Analysis and pilot

Workload arrays occupy a fixed section beginning at `0x01000000`, aligned to
4096 bytes per array and outside the heap. Linker size/overlap checks and final
symbol checks reject layout movement. Analysis keeps both the emitted root and
its unchanged helper; it never edits APE loop bounds or multiplies one cold count.
Every final G/C/P ELF is independently analyzed. Coverage, access count and
order/address/size/kind are checked against the generated workload, followed by
cross-ELF comparison of the linked stream and CA/CSRD/CLP/CLS. This checks modeled
streams and compiler/checksum correspondence; it is not a GR740 access trace.

```sh
python3 -m tools.rtems_periodic_pilot prepare --output .cache/periodic-pilot-new
python3 -m tools.rtems_periodic_pilot run .cache/periodic-pilot-new \
  --output .cache/periodic-pilot-new-runs --workers 8 --timeout 120
```

The fixed pilot has ten tasksets with 4–6 tasks, about 9600 loads per job,
10/20 ms periods and a 40 ms horizon. The exploratory CPU target is 1–3 ms; no
architecture-specific adjustment is made to meet it. All variants belong to one
pilot family and are ineligible for training or held-out evaluation. Explicit
core-order mapping is identified as a pilot policy, with no calibrated theta.
The complete design schedules 300 G/C/P runs and 490 independent-U runs.

Only complete workloads generate provisional G/C/P labels and 11-feature rows.
Results report all attempts, failures/exclusions, independent CPU times, simulator
wall time and storage cost. Next steps are independent family design and budget,
fixed train/validation/test membership, validation theta/policy calibration, then
final label collection and RF training. Pilot variants must not enter the final
held-out test family.

One RF sample represents one taskset for a given representation and policy.
The 40 provisional rows are ten tasksets expressed four ways, not forty
independent tasksets; the 790 executions are measurement repetitions. The current
cyclic-load pilot touches at most 64 cache lines per task, so allocated array size
must not be mistaken for active working-set size. Broader access patterns,
working sets, task counts and controlled total utilization remain to be designed
and collected; candidate axes are documented in the
[dataset plan](../../system-prompt-extraction/plan/MEASUREMENT-CONTRACT.md#81-pilot의-의미와-본-학습-dataset-구성-방향).

## Candidate pool and family audit

Generate inputs before theta calibration or final label collection:

```sh
python3 -m tools.rtems_periodic_pool --output .cache/periodic-candidates-new
```

The output contains 240 executable input configurations in `configs/`, `pool.json`,
`registry.json`, `split-proposal.json`, budget/coverage in `summary.json`, and a
hash manifest with implementation copies. Existing output directories are refused.
Each configuration can be passed to `tools.rtems_periodic prepare`; its explicit
round-robin mapping is provisional and is not a calibrated allocation policy.

Ten additional affine, load-only structures cover tile reuse, overlapping windows,
lane scans, forward/reverse scans, mirrored pairs, hub/spoke reuse, tile reversal,
hot-region reuse between cold tiles, three-region cycles, and coarse/fine scans.
Their literal trace definitions and actual G/C/P ELF streams are tested. Every
structure requires `distinct` to be a multiple of 24; no region parameters apply.
These are synthetic structural recipes, not ten independent application sources.

The registry derives family membership from shared recipes and base-task lineage,
including transitive links. Numeric/period/stride/task-count variants stay together;
whole-array and tiled forward/reverse scans are conservatively merged. Known cyclic,
hot/cold and phase development lineages are excluded from the primary population,
even if renamed. The resulting **nine candidate families** have a deterministic
6/2/1 train/validation/test proposal (144/72/24 tasksets). This is a proposal, not a
final frozen experiment or proof of sufficient diversity. A single test family is
a material limitation. Correctness-only fixtures do not supply timing or labels.

Each family spans 4/8/12/16 tasks, layout/L1/LLC profiles and target total U 0.5/1.5.
All tasksets have heterogeneous periods in ratio 1:2, a four-base-period horizon,
and at most 48 jobs (64 allocated record slots). Proposed bounds are task U<=0.25
and total U<=2.0. Periods are derived from a **CPU estimate** of twice the largest
development mean ns/load times the new job's load count. This unvalidated transfer
estimate is not measured U, WCET, or a deadline guarantee. Actual estimated U and
target U are stored separately; measured U and snapshot hashes remain absent.
Independent ten-run characterization of each final P ELF and common G/C/P
eligibility are still required. No test outcome may be used to retune these inputs.

The base budget is 24,000 independent-U plus 7,200 G/C/P runs per policy; build,
analysis, theta search, other policies/alpha and diagnostics are additional costs.
Final bounds, initial/expansion budgets, sufficiency thresholds and full-pool costs
remain to be resolved before final membership/split freeze. No final labels or RF
samples are generated by this command. See the preserved
[candidate input artifact](../../artifacts/periodic/candidates-v1/README.md).
