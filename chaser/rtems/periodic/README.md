# RTEMS periodic measurement harness

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

## Accounting and validation

Every job, including warm-up jobs, must pass completeness, checksum, release, status, deadline, and domain checks. Metrics use only measured jobs. TET sums per-job CPU-accounting differences. TAT sums, for each nominal-release cohort, the time from its first job start to its last job completion. `response_sum_ns` separately records the sum of job release-to-completion intervals. Independent U is the median of per-run mean CPU time over measured jobs, divided by task period. A failed or incomplete run cannot yield a successful architecture label.

The runner writes `protocol.json`, `measurements.jsonl`, and one numbered `.log` per run. Use `tail -f <output>/0.log` while an execution is running. `chaser.periodic.dataset.load_batch` checks the stored hashes and reparses raw logs; `feature_record` joins the independently measured U with locality features. Diagnostic `--trace` and `--empty` runs stay outside timing labels.

Workload patterns are documented in [RECIPES.md](RECIPES.md) and [STAGED-RECIPES.md](STAGED-RECIPES.md).
