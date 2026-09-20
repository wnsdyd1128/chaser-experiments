# Periodic G/C/P measurement harness

This harness builds RF dataset measurements and supports later allocation/system
experiments. The first pilot uses explicit placements, **not calibrated theta or
a trained RF**. It does not establish a performance improvement or target cache
accuracy. The measurement backend is the installed `laysim-gr740`, not silicon.

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
arrays initialized to one. A job calls its annotated inline kernel `sweeps` times
and returns a load-count checksum. The compiler is not asked to inline helpers;
YARDA expands their `ape.inline` annotations under each `ape.analyze` job root.
The task source and sweep count stay identical across G/C/P and independent runs.

`horizon_ticks` must be a multiple of every task period. Each task executes
`horizon_ticks / period_ticks` jobs; the period tick is 1 ms. Tasks are bounded to
1–16, at most 4096 total jobs, and at most 16 MiB of aligned workload data.
The cold job locality is a feature, not a prediction of warm, concurrent periodic
cache activity. Array data and cache state are not reset between sweeps or jobs.

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

`probe.c` reads the installed RTEMS period epoch, watchdog deadline and EDF
priority node under the period lock. This is deliberately tied to that SDK ABI;
the executable embeds the probe and the build manifest identifies RTEMS libraries.
The private timecounter starts at `SBT_1S`; the probe removes that offset to match
the public zero-based uptime API.

Watchdog and EDF deadlines must match the nominal table **exactly in ticks**.
The observed epoch may be slightly early or late relative to `tick * 1 ms`;
an absolute difference of one tick or more fails. No deadline slack is added to
job completion checks. `ready_ns` is unavailable: period initiation is not a
measurement of the exact scheduler ready transition. The raw epoch is retained
separately. The release/deadline table is recoverable from the run header, task
periods and job indices.

### Planned public-API measurement path

The current `probe_period()` runs before and after every job, including normal
timing and independent-U runs. `--trace` controls dispatch tracing only; disabling
it does not disable private period inspection.

The documented next change is to use public RTEMS APIs for normal timing and U,
and move private period/EDF inspection into separate diagnostic runs. This change
is **not implemented yet**. Uptime elapsed time includes preemption after job
start; it is distinct from CPU time and from nominal-release response time.
Elapsed mean/max will be auxiliary metrics; TET and TAT retain their definitions
below. Public period status and completion deadlines must detect overruns even
on the final job, where no subsequent `period()` call can report a timeout.

Public status does not directly expose the private EDF deadline or the exact
scheduler ready transition. The transition must revise the measurement contract
ID, raw schema and validators to state what each mode actually observes, then
revalidate G/C/P, U, overhead and final-job failure handling. Existing pilot
archives retain their original measurement protocol. See the
[measurement transition plan](../../system-prompt-extraction/plan/MEASUREMENT-CONTRACT.md#22-공개-rtems-api-중심-측정으로-전환하는-방침--구현-예정).

## Metrics and failure handling

Per job, `executed_since_last_period` from the public rate-monotonic status API is
sampled immediately before and after workload execution. Locked period snapshots
bracket this interval to check that the epoch/deadline did not change. All records
are buffered in RAM; printing happens after every worker finishes.

- `TET = sum(cpu_after_ns - cpu_before_ns)` over all measured jobs.
- `TAT = sum(completion_ns - nominal_release_ns)` over all measured jobs.
- `makespan_ns = max(completion_ns) - t0_ns` is retained separately.
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
