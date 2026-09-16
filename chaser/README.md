# CHASER RTEMS / GR740 baseline test

`rtems/baseline/` contains purpose-built C workloads and an RTEMS init task.
The same `workload.c` is compiled into three separate SPARC RTEMS 6 / GR740 executables and
into LLVM IR for LAT extraction. All RD analysis uses **yarda_cpp**.
Python is used only for pytest assertions, not for YARDA analysis.

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

Requires the existing RTEMS toolchain, LLVM 14, CMake, YARDA dependencies, and
pytest. Set `YARDA_DIR` to relocate the source checkout. The script builds a
fresh C++ analyzer inside `rtems/baseline/build/yarda`, builds the three RTEMS ELFs,
extracts LAT from C, analyzes element and cache-line RD, and runs assertions.
The LAT frontend plugin defaults to YARDA's `build-release/libLoopAnnotatedTrace.so`.

Verified with YARDA `6059896` containing `8b12a00` (unroll loop-limit fix):
**12 pytest tests passed**, including SPARC ELF validation and checks that each
ELF contains only its selected job and checker. The workload exceeds
the default cumulative limit, and succeeds with an explicit limit of 2,000,000.
The old YARDA `build-release/backend/yarda_cpp` was stale; rebuilding was necessary.

YARDA exports are saved to `exports/element.rdh.json` and `exports/line.rdh.json`.
Generated ELF, LAT, and build logs live under `rtems/baseline/build/`.
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
preserved file. The snapshot includes C sources, Makefile, cache YAML, LAT,
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
source and the prebuilt LAT plugin are still required for the build/analysis checks.
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

The hierarchy target selects each job and its object from the generated LAT v2,
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
CLS calculation itself remains stage 3 work; missing alpha results are rejected.

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
working build directory or simulator logs. The Makefile preserves per-case LAT
inputs for provenance checks. No new simulator measurements were taken.
