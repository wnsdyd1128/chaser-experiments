# RTEMS periodic measurement harness

설정 JSON으로 실험을 생성하고 환경을 수정·재현하는 절차는
[실험 가이드](EXPERIMENT-GUIDE.md)를 참고한다. 실제 보드의 준비·실행·계측 검증은
[HW 검증 가이드](HARDWARE-VALIDATION.md)를 따른다.

This checkout uses the [current measurement contract](../../system-prompt-extraction/plan/MEASUREMENT-CONTRACT-V3.md) and [dataset rebuild plan](../../system-prompt-extraction/plan/DATASET-REBUILD-PLAN.md). The serialized contract ID remains `chaser-periodic-measurement-v3` so stored plans and raw measurements keep their identity. Python modules use their ordinary names.

`tools.rtems_periodic` is the supported build, analysis, and single-batch runner. The old candidate pool, characterization collector, calibration CLI, G/C/P collector, and dataset-relocation scripts have been removed. `chaser.periodic.calibration` contains the current P-only threshold planner, selector, and batch classifier; it does not yet provide an end-to-end collection CLI. The archived `datasets/periodic-v2` and `datasets/periodic-final-v1` describe an earlier experiment and are not measurements under the current contract. S1's PolyBench experiment has a separate runner.

## Prepare and inspect a small run

Run from the workspace root with the installed GR740 RTEMS SDK, laysim, Clang/opt 14, waf, and YARDA build targets. Use fresh output directories:

```sh
python3 -m tools.rtems_periodic prepare configs/periodic-example.json --output .cache/periodic-example
python3 -m tools.rtems_periodic analyze .cache/periodic-example
python3 -m tools.rtems_periodic run .cache/periodic-example \
  --architecture p --runs 1 --output .cache/periodic-example-p
```

The example has a short horizon for a smoke run. A paper measurement must use the warm-up and measurement lengths, repeat counts, and frozen inputs in the active plan. The configuration specifies `warmup_ticks`, `u_repeats`, `horizon_ticks`, task periods, literal access patterns, and explicit core placement. The warm-up boundary must align with every task period. G, C, and P use the same workload source with different EDF SMP scheduler domains; analysis checks the linked ELF streams and array layout for each architecture.

## Explicit arrays and integer GEMM

Set `schema_version: 2` to define storage in top-level `arrays` and bind task roles
through `tasks[].arrays`. Array `length` and binding `offset_elements` count elements;
read-kernel `stride_bytes` counts bytes. Supported kernels are typed `cyclic`,
`paired-read`, and `gemm-u32`. Each array has its own 32/4096-byte alignment, type,
and constant initial value. Immutable inputs may be shared, while output arrays
must be exclusive to one task. Unsupported fields, aliases, and bounds are rejected.
The measurement contract remains v3; schema-less inputs keep the legacy recipes.

| Configuration | Workload |
|---|---|
| [gemm-u32-smoke.json](../../configs/periodic-multi-array/gemm-u32-smoke.json) | One task, A × B → C, two sweeps per job |
| [gemm-u32-shared-smoke.json](../../configs/periodic-multi-array/gemm-u32-shared-smoke.json) | Two tasks sharing A/B with separate C arrays |
| [shared-reads-smoke.json](../../configs/periodic-multi-array/shared-reads-smoke.json) | Cyclic and paired-read tasks sharing an input |

Use the same `prepare`, `analyze`, and `run` commands with one of these inputs and
fresh output directories. The [walkthrough](experiment-guide/INPUTS.md#multi-array) includes
G/C/P and independent P commands. GEMM overwrites C each sweep and hashes logical
output once at the end of the job; its hash reads are included in timing and analysis.
Arrays are initialized once before workers start, not between jobs.

Analysis validates every object's linked address, access width, and load/store order.
It records clang O0 analysis separately from workload O0/O2 compilation, and treats
stores as demand residency accesses without modeling write traffic or delays.
Sharing does not turn this cold task-local analysis into an interference/coherence model.
See the [input contract](experiment-guide/INPUTS.md#multi-array) and
[verification record](experiment-guide/INPUTS.md#multi-array-verification) for bounds and completed checks.
Python callers pass `arrays=plan['arrays']` to `workload_source` and `check_layout`
for v2; the existing positional arguments and legacy results remain supported.

## Accounting and validation

Every job, including warm-up jobs, must pass completeness, checksum, release, status, deadline, and domain checks. Metrics use only measured jobs. TET sums per-job CPU-accounting differences. TAT sums, for each nominal-release cohort, the time from its first job start to its last job completion. `response_sum_ns` separately records the sum of job release-to-completion intervals. Independent U is the median of per-run mean CPU time over measured jobs, divided by task period. A failed or incomplete run cannot yield a successful architecture label.

The runner writes `protocol.json`, `measurements.jsonl`, and one numbered `.log` per run. Use `tail -f <output>/0.log` while an execution is running. `chaser.periodic.dataset.load_batch` checks the stored hashes and reparses raw logs; `feature_record` joins the independently measured U with locality features. Diagnostic `--trace` and `--empty` runs stay outside timing labels. Schema v2 protocols also preserve the kernel contract, workload optimization, and new array/kernel module snapshots. Multi-array results remain diagnostic: locality reports set `dataset_eligible=false`, and `to_measurement` rejects their automatic conversion into RF labels pending separate qualification.

Legacy workload patterns are documented in [RECIPES.md](RECIPES.md) and [STAGED-RECIPES.md](STAGED-RECIPES.md). Their `matrix-reuse` pattern models reads; `gemm-u32` performs actual integer multiplication and stores.
