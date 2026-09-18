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
