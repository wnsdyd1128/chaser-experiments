# CHASER RTEMS / GR740 baseline test

`rtems/baseline/` contains purpose-built C workloads and an RTEMS init task.
The same `workload.c` is compiled into three separate SPARC RTEMS 6 / GR740 executables and
into LLVM IR for APE extraction. All RD analysis uses **yarda_cpp**.
Python selects APE records, computes scalar/features, and runs tests; it does not compute RD/CSRD.

## Cases

Each job increments eight volatile bytes over 65,537 sweeps. The nonzero final
byte value (1) lets the runtime check reject untouched, zero-initialized arrays.

| Case | Stride | 32 B lines | GR740 L1 mapping |
|---|---:|---:|---|
| packed | 1 B | 1 | One line |
| spread | 32 B | 8 | Eight different sets |
| conflict | 4096 B | 8 | One set, exceeding four ways |

All three have element RDH `{0: 524296, 7: 524288}`, 1,048,584 reuses,
8 cold references, and CA `131073 / 589825` (about 0.222224).
CA excludes cold references. Packed has line CA 1; spread and conflict retain
the same line Global RD. This demonstrates the Global-RD representation's
blindness to set mapping; it does not measure cache misses or prove a timing gap.

Each ELF runs one selected job, reports elapsed nanoseconds, and checks only
that job’s bytes. Unselected jobs and arrays are discarded by the linker. It is a workload integration test, not an SMP
scheduling comparison. `cache.yaml` supplies GR740 geometry with YARDA's supported
LRU/write-allocate policy; it is not an exact model of GR740 write policy.

## Verify

```sh
sh scripts/verify
```

Requires the existing RTEMS toolchain, LLVM 14, CMake, YARDA dependencies,
pytest, and scikit-learn (also used by the existing CAAS RF framework).
Set `YARDA_DIR` to relocate the source checkout. The script builds a
fresh C++ analyzer inside `rtems/baseline/build/yarda`, builds the three RTEMS ELFs,
extracts APE from C, analyzes element and cache-line RD, and runs assertions.
The APE frontend plugin defaults to `rtems/baseline/build/yarda/libMemoryAccessPatterns.so`.

Verified with YARDA `6059896` containing `8b12a00` (unroll loop-limit fix):
**12 pytest tests passed**, including SPARC ELF validation and checks that each
ELF contains only its selected job and checker. The workload exceeds
the default cumulative limit, and succeeds with an explicit limit of 2,000,000.
The old YARDA `build-release/backend/yarda_cpp` was stale; rebuilding was necessary.

YARDA exports are saved to `exports/element.rdh.json` and `exports/line.rdh.json`.
Generated ELF, APE, and build logs live under `rtems/baseline/build/`.
Working outputs can be regenerated; the verified baseline snapshot is preserved separately
in `artifacts/baseline/rtems-v1/`.

## Separate builds and runs

```sh
make -C rtems/baseline all
# Or build one case:
make -C rtems/baseline build/packed.exe
```

Outputs: `build/packed.exe`, `build/spread.exe`, `build/conflict.exe`.
Each command below starts a separate simulator process:

```sh
cd rtems/baseline
script -q -e -c 'make run-packed' build/laysim-packed.log
script -q -e -c 'make run-spread' build/laysim-spread.log
script -q -e -c 'make run-conflict' build/laysim-conflict.log
```

Success requires one `RESULT` line for the selected case with a positive elapsed
time, followed by `CHASER PASS`. The split executables each completed in a fresh laysim process with one RESULT,
CHASER PASS, and RTEMS shutdown. No explicit warm-up or repetition was added.
The Init task is not pinned to a core; `-core0` selects where the ELF is loaded.

| Case | Independent run elapsed ns |
|---|---:|
| packed | 59,868,128 |
| spread | 59,869,992 |
| conflict | 89,546,204 |

These single-run timings establish execution, not a statistical performance claim.

The earlier `baseline.exe`, `laysim-final.log`, and `runtime-result.json` under
`build/` describe the superseded sequential integration test. They are retained
as historical evidence and are not results for the separate executables.
Its observed times (packed 59,869,908 ns; spread 59,868,252 ns; conflict 89,544,968 ns)
are not an isolated performance comparison. That run passed after matching the
reference example's FPU configuration. No physical GR740 measurements or cache
miss counters have been collected.

## Frozen baseline

`artifacts/baseline/rtems-v1/manifest.json` records element CA, reuse counts,
independent execution results, YARDA commit, tool hashes, and SHA-256 for each
preserved file. The snapshot includes C sources, Makefile, cache YAML, APE,
element/line RDH, the three executed ELFs, logs, and verification code.
Element and line RDH hashes matched after regeneration. Snapshot serialization
is deterministic for identical inputs, and an existing snapshot cannot be overwritten.
Runtime measurements themselves are not required to be byte-identical on rerun.

```sh
python3 tools/freeze_baseline.py --output artifacts/baseline/<new-version>
```

Run the three independent simulator commands first, then `sh scripts/verify`.
Freezing a new snapshot requires those fresh logs and a saved verification log
(`sh scripts/verify > rtems/baseline/build/verify.log 2>&1`). Each selected case,
PASS marker and shutdown are checked; simulator exit status alone does not establish success.
Normal verification tests use an isolated copy of the frozen evidence and do not
require working simulator logs, a working verify.log, or an installed laysim binary.
They also check every frozen file against its manifest hash. Toolchain, YARDA
source and the LLVM frontend build dependencies are still required for the build/analysis checks.
This baseline covers the three CHASER C workloads, not a reproduction of the
historical exp2 snapshot or an exact physical-address model of the linked ELF.

## L1 CSRD and CLP (stage 2)

D1 is settled: `CA_CSRD` uses only the L1 CSRD histogram. `chaser/ca.py`
shares the CAAS formula between Global RD and L1 CSRD, excludes cold accesses,
and returns `None` if there is no reuse. LLC is not folded into this scalar.

```sh
make -C rtems/baseline hierarchy
python3 -m tools.export_locality
```

The hierarchy target selects each job and its object from the generated APE v2,
then runs **yarda_cpp** with the corresponding executed SPARC ELF and cache YAML.
Python selects JSON records and computes the final scalar; it does not compute RD.
Each input is one task with independent cold caches. Linked ELF addresses are
used with core 0 geometry; this is not a reconstruction of RTEMS scheduling,
migration, interrupt accesses, or physical cache state from the measured run.

Outputs: `exports/packed.csrd.json`, `spread.csrd.json`, `conflict.csrd.json`.
`exports/locality.json` summarizes all three CA variants and CLP, and includes
hashes of the source exports. CLP order is L1 hit, LLC first hit, all-cache miss.

| Case | Element CA | Line Global CA | L1 CSRD CA | L1 CSRD histogram |
|---|---:|---:|---:|---|
| packed | 0.22222354 | 1 | 1 | `{0: 1048591}` |
| spread | 0.22222354 | 0.22222354 | 1 | `{0: 1048584}` |
| conflict | 0.22222354 | 0.22222354 | 0.22222354 | `{0: 524296, 7: 524288}` |

Conflict has 524,296 L1 hits, 524,288 LLC first hits and 8 all-cache misses.
Spread has only 8 cold L1 misses; packed has 1. These are **model counters**,
not measured GR740 counters. The line Global RD control isolates the set effect
between spread and conflict; element-to-line comparison also includes grouping.

`sh scripts/verify`: 12 tests pass, including expected histograms, CA,
CLP conservation, complete resolution, and input hashes. A direct repeated
analysis produced byte-identical CSRD exports, and all analyzed ELF hashes
matched the frozen executed ELF hashes. The stage-1 snapshot is unchanged.

## Stage 1 acceptance and downstream feature interface

Stage 1 acceptance uses the purpose-built CHASER workloads and their closed-form
RD/CA expectations, deterministic analysis and preserved standalone execution evidence.
This replaces the original plan's historical CAAS workload reproduction requirement;
no exp2 reproduction is claimed. The frozen rtems-v1 bytes and manifest are unchanged.
Its nine previously ignored build files are now eligible for Git tracking through
narrow ignore exceptions; include them with the change when committing.

`chaser.features.locality_scalar(kind, record, alpha=...)` selects `caas-ca`,
`ca-line`, `ca-csrd`, or precomputed `cls`. Records use the field names from
`exports/locality.json`: `ca_caas_element`, `ca_global_line`, `ca_csrd_l1`.
CLS records additionally carry a string-keyed map such as `cls: {"0.5": 0.75}`.
`chaser.cls` computes `CLS = p_L1 + (K_L1 / K_LLC)^alpha * p_LLC`
from unconditional first-hit ratios and cache capacities in bytes. Empty profiles
produce `None`; missing alpha results are rejected by the selector.

The normal locality export includes alpha values `0, 0.3, 0.5, 0.7, 1.0`.
To recompute a sweep from existing analyzer exports without rerunning analysis:

```sh
python3 -m tools.run_cls_sweep --alpha 0,0.3,0.5,0.7,1.0
# Optional separate output:
python3 -m tools.run_cls_sweep --alpha 0,0.5,1 --output exports/cls-sweep.json
```

The default output is `exports/locality.json`, retaining CA, CLP, analysis IDs,
source hashes, and modeled-access counts alongside CLS. Per-case provenance
preserves the analyzer version (including its Git revision and dirty marker),
input hashes including the cache config hash, selected path, and cache hierarchy
with capacity, line size, and associativity. Capacities come from that analyzed
hierarchy, so subsequent config edits do not change the meaning of stored CLP.
These records feed `fit_rf(..., 'cls', seed=42, alpha=0.5)` and
`allocate(..., kind='cls', alpha=0.5, threshold=...)` directly. Each alpha requires
its own RF/scaler training. Alpha 0.5 is the primary setting; this sweep implements
scalar generation, not measured RF sensitivity or scheduling experiments.

Join each record with its task's `utilization` by task ID before calling
`build_features(records, kind, alpha=...)`. The result is an ordered list matching
`FEATURE_NAMES`: five locality statistics (mean, population std, min, max, median),
then six utilization statistics (the same five plus sum). Legacy `ca_*` names stay
fixed across representations. No scaling is applied here. Empty workloads,
undefined/nonfinite scalars or utilization, negative utilization, and locality
outside [0, 1] are rejected rather than silently converted to zero. Dataset assembly
must still select a common complete-case workload set across all variants.

Verification on 2026-09-16: `sh scripts/verify` passed all 23 tests both in the
working tree and in a temporary checkout containing the proposed files but no
working build directory or simulator logs. The Makefile preserves per-case APE
inputs for provenance checks. No new simulator measurements were taken.

## RF consumption of selected features

`chaser.rf.fit_rf(cases, workloads, labels, kind, seed=...)` joins locality
records and utilization by task ID, builds the existing 11 features, and trains
a fresh sklearn RandomForestClassifier. It uses the same implementation and
parameters as the CAAS wrapper: 100 trees, unlimited depth, and an explicit seed.
The external framework and legacy saved weights are not loaded.

Each workload is a mapping `{task_id: utilization}`; `cases` is the mapping from
`locality.json`. Missing task IDs, missing/invalid utilization, undefined scalars,
empty workloads, and invalid/mismatched labels are rejected. Labels follow
`0=Global`, `1=Clustered`, `2=Partitioned`.

The returned model keeps its representation (and CLS alpha, if supplied).
Its MinMaxScaler is fitted on training features and reused during prediction.
Train a separate model for each representation using the same training workloads,
labels and seed. The caller supplies the family-level split and common complete-case
workload set; this API does not create a research dataset or measure accuracy.

Runnable wiring example, with **synthetic labels and utilization only**:

```python
import json
from pathlib import Path
from chaser.rf import LABEL_NAMES, fit_rf

cases = json.loads(Path('exports/locality.json').read_text())['cases']
workloads = [{'packed': 0.1}, {'spread': 0.5}, {'conflict': 0.9}]
labels = [0, 1, 2]  # Test fixtures, not measured scheduling winners.
for kind in ('caas-ca', 'ca-csrd'):
    model = fit_rf(cases, workloads, labels, kind, seed=42)
    predictions = model.predict(cases, workloads)
    print(kind, [LABEL_NAMES[label] for label in predictions])
```

For experiments, replace these fixtures with training data and labels from the
measurement pipeline, then predict on held-out workloads. This completes the RF
consumer connection; S2 evaluation remains separate work.

## Offline allocator connection (stage 2)

`chaser.allocator.allocate` consumes the same locality cases and task-ID-to-U
mapping as the RF interface. It returns `Placement(mapping, residual, infeasible)`.
Types and annotations target Python 3.10.

```python
from chaser.allocator import CoreGroups, allocate

# Explicit example configuration, not a calibrated experimental default.
cores = CoreGroups(isolated=(0,), non_isolated=(1, 2, 3))
placement = allocate(cases, {'spread': 0.6, 'conflict': 0.3}, cores,
                     kind='ca-csrd', threshold=0.5)
```

The policy follows Algorithm 1 as transcribed in the project plan: descending U,
scalar below threshold → least-loaded isolated Ω core; scalar at or above threshold
→ worst-fit non-isolated NΩ core. The same policy consumes `caas-ca` or `ca-csrd`;
`ca-line` and explicitly selected precomputed CLS are also accepted by the selector.
The split and finite threshold are required inputs. No experimental split or
threshold is selected implicitly; finite thresholds outside [0, 1] can represent
all-low/all-high calibration endpoints.

The paper's partial policy is completed with explicit rules: capacity 1 per core
in both branches, no spill between groups, and failed tasks recorded while remaining
tasks continue. U > 1 is infeasible, not an invalid measurement. Task ties use
ascending task ID; core ties use ascending core ID. Empty groups are allowed and
cannot receive tasks; groups must be disjoint with distinct nonnegative IDs and
at least one core overall. Empty workloads return the unused cores. Missing or
undefined inputs are rejected. Residual capacity uses the sum of assigned U values.

This is a greedy placement policy, not a globally optimal feasibility solver or
a schedulability proof. It completes the stage-2 offline RF/allocator consumer
interfaces. RTEMS affinity application, topology-specific scheduling, measured
labels, measured threshold calibration and S2/S3 performance evaluation remain later work.

## Offline threshold calibration (stage 4)

`chaser.threshold.calibrate` connects threshold search to the existing allocator.
Supply `CalibrationWorkload(workload_id, family_id, split, utilization)` rows,
explicit core groups, representation, seed, analyzer/feature versions, and a
`tat(workload_id, mapping)` callback. The callback supplies TAT for that exact
mapping in a consistent unit, for example the median of repeated measurements.
Set `measurement_source='measured'` for measured inputs or `'synthetic'` for fixtures.
Missing, nonpositive or nonfinite TAT aborts selection.

Only validation payloads contribute scalars, mappings and TAT requests. Duplicate
workload IDs and families crossing train/validation/test splits are rejected.
The caller supplies the frozen family membership and the same complete-case
validation population for all representations; the function does not construct
the split or infer benchmark families.

The fixed selection protocol is:

1. Search midpoints between distinct validation scalars, plus all-high/all-low
   endpoints. With strict `scalar < threshold`, the minimum scalar is all-high
   and the next representable float above the maximum is all-low. Adjacent floats
   without a representable midpoint use the upper scalar.
2. Minimize the number of workloads with any allocation failure.
3. Among those candidates, minimize mean TAT over their common successful workload
   intersection. An empty intersection is an error; differing success populations
   are not directly compared. Other candidates have no TAT score.
4. Break TAT ties by the smallest threshold. Reuse each workload/mapping's TAT
   within the call so duplicate mappings are requested only once.

Call separately for `caas-ca`, `ca-csrd` and `cls`, and again for each CLS alpha.
The seed records the experiment protocol; the search itself is exhaustive.
The result records the selected threshold, all candidates and placements,
failures, common workload IDs, consumed TAT values, core groups, versions, source,
seed, split hash and validation-input hash. Persist the result before test use:

```python
from dataclasses import asdict

# result = calibrate(...), using validation measurements supplied by the caller.
Path('threshold.json').write_text(
    json.dumps(asdict(result), indent=2, sort_keys=True, allow_nan=False) + '\n')
test_placement = allocate(cases, test_workload, result.cores, kind=result.kind,
                          alpha=result.alpha, threshold=result.threshold)
```

Keep this threshold fixed for test workloads. The API cannot verify the origin
of callback measurements; the measurement pipeline must ensure they match the
workload, mapping, binary and execution configuration. This stage implements
calibration logic and synthetic regression tests, including real locality-export
integration. No experimental threshold has been selected; measured TAT, frozen
research splits and S3/S4 calibration experiments remain pending.

## PLAN 5: analyzer and dataset bridge

`chaser.analyzer.analyze_task` accepts a prepared single-function APE, matching
ELF, cache YAML, source file, C++ analyzer executable, a new output directory,
and explicit analysis limits. It runs **three** C++ paths: element Global RD,
cache-line Global RD (control), and hierarchy CSRD. Global CA uses the program
histogram so reuse across blocks is retained. Python performs only scalar and
feature arithmetic. Each successful `analysis.json` contains `task_id`, `case`
and `provenance`; raw exports and logs remain alongside it. Provenance includes
input/output and analyzer binary hashes, the reported revision (including a
`-dirty` suffix), commands, UTC timestamps and elapsed seconds. The source hash
identifies the supplied source; compilation and source-to-ELF correspondence
remain the caller's responsibility.

```python
from pathlib import Path
from chaser.analyzer import analyze_task

record = analyze_task(
    'chaser_packed', ape=Path('rtems/baseline/build/packed.ape.json'),
    elf=Path('rtems/baseline/build/packed.exe'), cache=Path('rtems/baseline/cache.yaml'),
    source=Path('rtems/baseline/workload.c'),
    executable=Path('rtems/baseline/build/yarda/backend/yarda_cpp'),
    output_dir=Path('/tmp/chaser-packed-analysis'),
    max_cumulative_loop_iterations=2000000, max_source_accesses=1100000,
)
```

The dataset builder consumes one JSON input containing:

- `cases`: task ID → locality record, as returned in `record['case']`.
- `provenance`: task ID → `record['provenance']`. Required fields are
  `source_hash`, `elf_hash`, `analyzer_commit`, `cache_model_id`,
  `cache_config_hash`, and `model_hash` (null before RF training).
- `workloads`: records with `workload_id`, `family_id`, `utilization` (task ID → U),
  and `utilization_source` (`measured-mean` or `wcet`). U is never defaulted to zero.
- `measurements`: `Measurement` records with `workload_id`, numeric `architecture`
  (0=Global, 1=Clustered, 2=Partitioned), `topology_id`, `allocator_id`,
  `mapping_hash`, string `run_id`, `tet`, `tat`, `execution_status`, and explicit
  `measurement_source` (`measured` or `synthetic`). `time_unit` defaults to `ns`.
  The lowercase `tet`/`tat` fields store the plan's TET/TAT metrics. Failed runs
  may have null times; only `execution_status='ok'` is eligible for labeling.

```sh
python3 -m tools.build_dataset input.json --split split.json --seed 42 \
  --expected-runs 10 --output dataset-v1
```

`freeze_split` assigns approximately 70/20/10 **by family**, with at least one
family per split and at least three families required. The experiment designer
supplies family IDs: repeated runs, layout/parameter variants and period changes
must retain their family. Existing split membership and seed are reused;
changed workload/family membership is rejected. This checks declared membership,
not whether two source programs are semantically related. Exclusion never causes
resplitting. Small pilots do not establish generalization performance.

`label_measurements` requires all planned runs of all three architectures.
It selects median TAT, then median TET, then the smallest label, and records
exact ties. Failed, missing or duplicate runs prevent a label. One dataset has
one allocator, consistent units/source, and fixed topology per architecture.
Mappings may vary by workload, but must stay fixed across repeats. Different
allocator configurations require separate measurement/label datasets.

The new output directory contains `raw_measurements.jsonl`,
`task_characterization.jsonl`, `rf_samples.jsonl`, `provenance.jsonl`, and
`metadata.json`. It cannot overwrite an existing artifact. Characterization uses
`(workload_id, task_id)` because U may vary with period. RF rows contain the
unchanged 11 features, family/split, representation/alpha, label and label
evidence. TET/TAT and labels never enter the feature vector. Metadata records
the frozen split/hash, feature version/order, required repeat count and excluded
workloads with reasons. Missing schema, provenance or U is an error; unavailable
locality/CLP or incomplete measurements exclude a workload from **all eight**
variants (three CA representations and five CLS alphas). Raw evidence remains.

For S2 select `caas-ca`, `ca-csrd`, and `cls` with `alpha=0.5`; the line control
and other alphas support the separate comparisons. Feed only training workload
IDs and their labels to the existing `fit_rf` API using the original cases and
U mappings; train a new model/scaler per representation. Validation workload
records can be passed to `CalibrationWorkload` with the frozen family split and
`utilization`; calibration TAT must correspond to its requested exact mapping,
not merely the architecture-level RF label measurements. No scaler or model is
fitted by the exporter.

This implements PLAN 5's data construction path. Tests use explicitly synthetic
measurement fixtures and actual baseline C++ analysis. New scheduling C
workloads, RTEMS mapping/repeated measurements, measured labels/thresholds, and
external PolyBench evaluation are not completed by this bridge. PolyBench is
reserved as a proposed external test population after model/threshold selection;
it is not added to training or calibration by this change.

## PLAN 6/7: RTEMS placement and measurement wiring check

`tools.rtems_smoke` connects the offline allocator to real RTEMS singleton
affinity for the three existing packed/spread/conflict jobs. The supplied
configuration uses **synthetic U and an uncalibrated threshold** for integration
verification. It is not a periodic scheduling taskset or a training dataset.

```sh
python3 -m tools.rtems_smoke prepare configs/rtems-smoke.json --output rtems/smoke/build/check-v1
python3 -m tools.rtems_smoke editor rtems/smoke/build/check-v1
python3 -m tools.rtems_smoke run rtems/smoke/build/check-v1 --runs 10 --timeout 60
```

Preparation rejects incomplete placements, snapshots the source/configuration
and locality inputs, and builds a SPARC ELF using `waf configure build` and
`rtems/smoke/wscript`. It copies the installed `/opt/src/rtems/waf` launcher
into the snapshot and explicitly selects the `/opt/rtems/6` compiler, even if
the shell defines a different `CC` or `RTEMS_ROOT`. Inputs, the waf launcher,
wscript, compilation database, compiler and ELF are hashed in `manifest.json`.
Both the preparation directory and its `runs` directory
must be new. Use a new directory for subsequent batches. Generated artifacts
under `rtems/smoke/build/` are ignored by Git.

The `editor` command publishes `rtems/smoke/compile_commands.json` for the
workspace's `init.c`, using the actual waf compilation command and that
snapshot's generated `config.h`. Run it again to select a new prepared build.
The local `.clangd` supplies RTEMS target/newlib settings and removes GCC's
`-mfpu`, which clangd does not accept. No placeholder headers are used.
If VS Code retains old diagnostics, run **clangd: Restart language server**.
The generated editor database is ignored by Git; keep its referenced build
directory while editing. It can be checked without the editor using:

```sh
clangd-14 --check="$PWD/rtems/smoke/init.c" --log=error
```

The target checks the four-core configuration and requested affinity, waits
until all workers are ready, and releases one job per worker from a common
uptime epoch. It records the observed start/end cores and checks each job's
result. Logging occurs after all measured jobs complete. The common epoch
includes sequential event-dispatch skew; it is not a simultaneous hardware
release. Each repetition starts a fresh simulator process through `script`;
`timeout` bounds each process group. This requires the RTEMS toolchain, laysim,
GNU coreutils and util-linux. In the managed workspace, laysim runs outside the
sandbox.

`runs/measurements.jsonl` records successful and failed attempts alongside raw
logs, return codes, UTC start times, host wall time, and log hashes.
`runs/protocol.json` records the simulator hash, exact command and repeat count.
Prepared inputs are checked before and after execution. Success requires the
target's completion marker, complete task records, valid timing, correct
affinity and successful workload checks; simulator exit code alone is not enough.

Measured fields have deliberately explicit names:

- `cpu_ns`: per-job difference of RTEMS rate-monotonic CPU accounting samples,
  including sampling overhead but excluding time the worker is preempted.
  The ten-second active period only enables accounting; expiry fails the run.
- `start_ns` / `completion_ns`: uptime timestamps bracketing work and accounting.
- `response_ns`: completion minus the common release epoch, including queueing.
- `sum_job_cpu_ns`, `sum_response_ns`, `makespan_ns`: respectively CPU-time sum,
  response-time sum and last completion minus common release.

These are **not** automatically exported as PLAN 5 `Measurement` TET/TAT or RF
labels. Their aggregation has not been accepted as the research metric contract.
The baseline locality input describes different linked ELFs from this combined
executable, so the wiring check cannot establish cache-model accuracy or a
locality-driven performance improvement. Real experiment collection still needs
workload families, measured U, analysis of the executed ELF, periodic releases,
fixed G/C/P topology, and the agreed TET/TAT definitions. Clustered EDF SMP needs
separate scheduler instances; a partial multi-core affinity mask is insufficient.

## PLAN 7/8: S1 estimator and independent cache reference

`tools.compare_s1` compares one caller-prepared, single-task APE/linked ELF using
the actual cache geometry and an independent Python resident-cache LRU replay.
The source-derived workload sweep below uses this comparison foundation. Target
cache-counter/trace validation remains subsequent work.

```sh
python3 -m tools.compare_s1 TASK_ID \
  --ape /path/to/task.ape.json --elf /path/to/task.exe \
  --source /path/to/source.c --cache rtems/baseline/cache.yaml \
  --executable rtems/baseline/build/yarda/backend/yarda_cpp \
  --max-source-accesses 100000 --max-line-references 100000 \
  --max-cumulative-loop-iterations 2000000 --timeout 60 \
  --output /tmp/chaser-s1-task-v1
```

The output directory must be new. Limits apply to the supplied task; the
original baseline has 1,048,592 accesses and exceeds the illustrative 100,000
limit. Complete event exports require memory and disk proportional to reference
count. This is a bounded correctness-validation path, not an analyzer scalability
benchmark. Source/APE/ELF correspondence belongs to the caller; the source hash
does not establish that correspondence.

The Global RD control is `full-linked-stream-capacity-bins-v1`: for equal line
sizes and L1 capacity no larger than LLC, full-stream cache-line RD below the L1
line capacity counts as L1 first-hit; RD between the L1 and LLC line capacities
counts as LLC first-hit; larger RD and cold count as memory. Cold accesses remain
in the denominator. This is an experimental extension, not a legacy CAAS output
or a simulation of the demand hierarchy's LLC request stream.

All RD/CSRD computation stays in `yarda_cpp`. The runner analyzes the same APE
and ELF twice: actual geometry, then a derived config with a single fully
associative L1 set. That second L1's full-exact CSRD histogram is full-stream
Global RD, including finite distances exceeding L1 capacity. Its LLC counts
are not used by the control. This preserves linked line identities, including
shared lines across objects; the existing object-relative Global RD exports
used by the dataset path are unchanged.

The reference consumes only ordered linked addresses from complete YARDA events,
using integer division to form line IDs and independent per-set LRU residency.
It ignores YARDA's set/tag/RD/outcome fields. Both reference and actual CSRD use
cold state, allocation on every demand miss, L1 misses only at LLC, and no back
invalidation, victim insertion, prefetch, or writeback traffic. Events already
expand cross-line accesses and are not expanded again. The Global RD threshold
control uses full-stream recency at both capacity boundaries, which can differ
from demand-only LLC recency even without a set-conflict effect.

`comparison.json` records L1/LLC/memory counts and ratios, component absolute
errors, per-task MAE/RMSE/maximum error, input/stream/output/implementation hashes,
cache model, exact commands, tool version, and host wall times. MAE/RMSE weight
the three ratio components equally; empty input has null ratios/errors and
status `empty`. CSRD/reference disagreement is preserved with status `mismatch`.
The CLI exits 0 for `ok`/`empty`, 1 for a model mismatch, and 2 for a failed run
or invalid input. Input snapshots, both raw result/event pairs, derived config,
logs, and `failure.json` (on failure) retain the evidence. Truncated events,
incomplete coverage, malformed counts, mismatched hashes/streams, unsupported
models, and timeouts cannot produce a successful comparison.

This validates cache decisions on a **shared YARDA-emitted address stream**.
APE expansion and ELF address resolution are not independently validated here;
target cache counters or execution traces are not collected. Reports explicitly
record `execution_validation=not-performed`. Under S1-D, claims remain at the
abstract-model level until separate execution evidence is available. The current
smoke timings and host cache results cannot be substituted for GR740 counters.

## S1 load-only workload sweep

After `sh scripts/verify` builds the analyzer/plugin and verifies the toolchain,
run the full 25-case cold-model suite into a new directory:

```sh
python3 -m tools.run_s1_suite --output rtems/s1/build/evaluation-v1 \
  --sweeps 3 --max-references 250000 --timeout 60
python3 -m tools.plot_s1 rtems/s1/build/evaluation-v1/suite.json \
  --output rtems/s1/build/evaluation-v1/plots
```

The plotting command uses the environment's Matplotlib installation. For a small
probe, select `--cases packed_8 spread_8 conflict_4 conflict_5 mean_uniform mean_mixed`.
The default three sweeps expose cold plus two repeated cycles; they are not three
independent target runs. The suite rejects existing output directories, records
partial selections explicitly, and preserves each failure while attempting later
cases. Exit codes are 0 for all selected cases passing, 1 for any failed case or
CSRD/reference mismatch, and 2 for invalid input/setup. Global RD prediction error
is an experimental result and does not fail the suite.

`chaser.s1_workloads` generates a self-contained C source per case. The snapshotted
`rtems/s1/Makefile` builds that exact source into LLVM/APE and a SPARC RTEMS ELF;
APE bounds are never edited after extraction. The analyzed function returns an
accumulator and accesses one aligned volatile byte array using loads only.
Preparation and checksum checking are outside that function. The suite checks
the emitted address sequence against each case's logical offsets, load operation,
alignment, total access count and complete analysis coverage. All RD/CSRD remains
in C++; line Global RD uses the linked fully associative control described above.

The catalog preserves the original RMW baseline and adds:

- Packed 8 elements; spread/conflict pairs for 3, 4, 5 and 8 distinct lines.
- Contiguous 32-byte-stride cycles of 256, 448, 511, 512, 513, 576, 1024, 32768,
  61440, 65535, 65536, 65537, 69632 and 73728 lines.
- Two distributions with finite mean RD 511, the same 1024 cold lines and the
  same total references/footprint. `mean_uniform` revisits a 512-line cycle and
  then reads 512 new lines once. `mean_mixed` revisits a singleton and a disjoint
  1023-line cycle equally often. At three sweeps their finite histograms are
  `{511:4092}` and `{0:2046,1022:2046}`, respectively. The `sweeps` parameter controls
  reuse population here, rather than repeating the entire mixed pattern.

Each case retains source, LLVM, extracted APE, executable, build commands/logs,
element RD, both linked hierarchy analyses/events and the comparison report.
`inputs.json` records compiler versions, support/tool hashes and limits;
`suite.json` adds CA values, cold fractions, histograms, counts, ratios, source
coverage and per-level error aggregates. `results.csv` is the workload error
table. Aggregate MAE/RMSE weights evaluated workloads equally, including model
mismatches; failed cases remain listed and are excluded from numerical errors.
`resources.json` records operational wall time, disk use and Linux process RSS.
Full event export and reference replay make these costs unsuitable as analyzer-only
scalability measurements. Generated raw runs under `rtems/s1/build/` are ignored.

The suite validates modeled array accesses. Matching C/APE/ELF and logical offset
checks do not establish actual CPU trace equality: target stack/instruction
accesses, warm state after preparation, and compiler effects remain outside this
cold model. The checksum-capable ELF does not provide cache counters, TET/TAT or
scheduling labels. S1 conclusions remain within abstract-model validation.

The first completed 25-case model sweep, error table, scatter and evidence hashes
are summarized in [S1 model evaluation](artifacts/s1/model-v1/README.md).
