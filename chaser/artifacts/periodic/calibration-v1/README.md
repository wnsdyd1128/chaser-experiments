# Validation calibration v1: preparation complete, timing blocked

## Latest: full error survey completed

At the user's request, the remaining 171 mappings were measured without changing
the harness or retrying existing failed runs. All **197 mappings / 1,970 runs**
are now complete: **196 mappings / 1,960 runs succeeded**, and the original
mapping of `candidate-v3-0112` failed all ten runs. No additional failing mapping
or taskset was found. That taskset's other four mappings passed all 40 runs.
The only observed parser errors were `arm_phase` and `release_mismatch` in those
same ten failed runs. This survey did not select theta or exclude any workload.

The independent [raw-log audit](../../../.cache/calibration-v1/survey-v1/raw-audit.json)
reparsed failures as well as successful runs and verified that all historical
evidence was unchanged. The original stopped-collection records below remain
historical snapshots; current coverage is in
[survey summary](../../../.cache/calibration-v1/survey-v1/summary.json).
The completed collection log is available at
`.cache/calibration-v1/survey-v1/collection.log` (`tail -f` can view it, but this
survey has finished and will not append further measurements).

## Initial stopped attempt

Recorded 2026-09-22. **No theta or allocation policy was frozen.**
The measured calibration path is implemented, but one validation mapping fails
the existing release-phase contract. Its evidence is retained; the remaining
measurements were not admitted after the collector observed that batch failure.

## Frozen scope and budget

- Source: `.cache/characterization-v1-inputs/frozen` and
  `.cache/characterization-v1`; existing input/split membership is unchanged.
- Validation only: 41 tasksets, 448 tasks. Original independent-U raw logs and
  locality were revalidated. Train/test feature payloads are not loaded.
- Core groups: Ω={0}, NΩ={1,2,3}; CLS alpha=0.5.
- CAAS-CA / CA-CSRD / CLS threshold candidates: **31 / 33 / 42**.
- Comparable exact mappings per representation: **140 / 146 / 166**.
  All candidates have zero allocation failures on the 41 validation workloads.
- Sharing the same identified workload/mapping snapshot across representations
  reduces this to **197 distinct P batches, 1,970 planned fresh-process runs**.
- Prepare workers=8; simulator limit=16; timeout=1,800 seconds per process.

The plan contains the full frozen split hash, validation-subset hashes, original
U identities, mapping configurations, implementation hashes and tool identities.
The original U ELF identity is never rewritten to refer to a mapping ELF.
See [plan](../../../.cache/calibration-v1/plan.json) and
[budget](../../../.cache/calibration-v1/budget.json). Historical preparation times
in the budget are not a wall-time forecast.

## Completed preparation and preserved measurements

Preparation completed with exit 0: **197/197 snapshots, 591 G/C/P ELFs**.
Each final ELF was analyzed; source, harness, build tools, layout, locality and
linked streams were checked against the original characterization conditions.
The 6,576 event archives contain 89,971,260,981 original bytes compressed to
975,737,836 bytes. Restoration hashes were checked during compression; a second
full decompression pass was not performed.

Timing stopped with exit 1 after draining admitted work:

| Result | Batches | Runs |
|---|---:|---:|
| Successful | 25 | 250 |
| Failed | 1 | 10 |
| Not attempted | 171 | 1,710 |

One initial batch was measured separately while preparation continued; its ten
runs were revalidated and reused by the collector, and are included above.
All 26 completed batches were subsequently revalidated from raw logs. The failed
batch was also checked against the calibration TAT gate and correctly rejected.

Evidence: [prepare summary](../../../.cache/calibration-v1/prepare-completion-summary.json),
[run progress](../../../.cache/calibration-v1/run-progress.json),
[raw-evidence audit](../../../.cache/calibration-v1/collection-failure-audit.json).
Raw data and implementation snapshots remain in `.cache/calibration-v1/`;
committing this README does not back up those files.

## Blocking release-phase failure

Workload `candidate-v3-0112`, mapping
`36f078e344977a79e8bc30bfd2e7f5b2b1d9af54347286518ae256ecf6831037`,
fails all ten repetitions with `arm_phase` and `release_mismatch`.
The header declares `t0_tick=42`, but every one of the 16 tasks records both
arm tick brackets as 43. The simulator exits normally; this is a measurement
contract failure, not a timeout or evidence of allocator infeasibility.

The relative sleep in `rtems/periodic/init.c` computes a delay from a tick read
before RTEMS inserts its timeout. A tick boundary between those operations could
explain waking at t0+1. This remains a hypothesis: a separate diagnostic ELF that
records the tick immediately after waking moved the nominal epoch to 43 and
passed both diagnostic runs, so it did not reproduce the original failure.
See [diagnostic summary](../../../.cache/calibration-startup-diagnostic-v1/summary.json).
Those two runs are excluded from U, calibration and architecture labels.

The production harness and parser were not changed. Do not replace the failed
runs, relax the arm/release checks, shift t0 after the fact, or select theta from
this incomplete comparison. The next step is to establish and correct startup
synchronization, then establish whether original U remains equivalent under the
corrected harness. New harness snapshots and calibration provenance are required;
the current source/tool guards must not simply be removed to permit reuse.

## Implementation verification

`sh scripts/verify`: **608 passed, 1 optional cold-Cachegrind test skipped**.
With `CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install`, the cold-test file was
rerun: **3 passed**, including the skipped test. No related test remains failing.
The new calibration/threshold tests cover validation-only input access, exact
mapping deduplication, original U provenance, strict timing acceptance,
simulator identity, incomplete/failed evidence preservation and policy freezing.

See [verification record](../../../.cache/calibration-v1/implementation-verification.json).
`finalize` was not invoked; Git staging/commit operations were not performed.
