# Validation calibration v1: historical evidence; active loader connected in v2

## Current status (2026-09-23)

The authoritative [V2 active membership](../validation-supplement-v2/active-population.json)
contains **207 active tasksets (train/validation/test = 126/41/40)** out of
**212 archived inputs**. The original family counts and train/test membership are
preserved. Original failed tasksets candidate-v3-0112, candidate-v3-0135,
candidate-v3-0136 and candidate-v3-0207 are excluded in their entirety, including
successful mappings. V1-0001 (window-coefficient) is also excluded for family
balance, not measurement failure. All original inputs and evidence remain archived.
Validation now consists of 37 retained originals plus V1-0002/0003/0004 and V2-0001.

V2 validation **completed and passed at 2026-09-22 20:31:30 UTC**: independent U
100/100 and G/C/P 10/10 each, with raw revalidation, no raw errors or undefined
features, U within bounds and unchanged U evidence. See the
[completion record](../validation-supplement-v2/README.md),
[summary](../validation-supplement-v2/validation-evidence/summary.json),
[exit result](../validation-supplement-v2/validation-evidence/exit.json) and
[collection-time source hashes](../validation-supplement-v2/validation-evidence/source-hashes.json).
These three JSON files are byte-for-byte copies of the completed run's cache records;
raw logs and detailed build/U/feature evidence still require separate cache preservation.
Generation-time pending fields in the V2 manifest and membership are retained as
provenance; they do not describe the completed run's current status.

**The current membership and existing U/features are now connected through the
[v2 loader binding](../calibration-v2/README.md). Theta/policy remains unfrozen.**
Loader validation passed for 41 validation workloads, 448 tasks and 4,480 independent-U
runs. Next: recompute validation threshold candidates and mappings, establish execution-equivalent measurement reuse
and the additional budget, then measure required mappings before freezing theta/policy.
Final labels and RF evaluation follow that freeze. Supplement validation covers the
measured basic mappings, not all future calibration mappings.

The census, budgets and stopped-attempt records below are historical. Their original
197 mappings and threshold counts must not be treated as the recalculated budget for
the current membership. Startup repair remains a separate unresolved issue; the
current experimental path uses the validated supplements without relaxing the parser.

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
this incomplete comparison. The recovery path proposed at that time was to establish and correct startup
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


## 2026-09-22 completed G/C/P error census and follow-up decision

The earlier 26-batch stop above is historical. The P census subsequently completed
197 batches: 1,960 successful runs and 10 failures. G/C measurements then added
3,940 runs using the same prepared snapshots, without changing the harness/parser.
The combined census completed at 2026-09-22T17:45:42Z:

| Architecture | Successful | Failed | Total |
|---|---:|---:|---:|
| G | 1,970 | 0 | 1,970 |
| C (EDF SMP {1,3}) | 1,940 | 30 | 1,970 |
| P (preserved measurements) | 1,960 | 10 | 1,970 |

C failures are one mapping each of candidate-v3-0135, candidate-v3-0136 and
candidate-v3-0207; P failures remain candidate-v3-0112. All ten repetitions of each
failed combination report arm_phase and release_mismatch. These are four tasksets,
not forty distinct inputs. Other C topologies were not measured.

[Combined summary](../../../.cache/calibration-v1/gcp-survey-v1/summary.json) records
raw-evidence revalidation and unchanged historical evidence; exit.json records exit 0.
This means the census completed, not that all timing measurements passed.
The collector, protocol, raw G/C runs and collection.log remain in that directory.
Theta/policy remains unfrozen.

The user authorized preserving all original inputs and evidence, adding four new
tasksets separately with generation rules fixed before measurement, and reusing
identical successful measurements. See the authoritative
[supplement plan](../../../system-prompt-extraction/plan/VALIDATION-SUPPLEMENT-V1.md).
This is the next experimental path; startup repair is a separate unresolved issue.
The [supplement generation rules](../validation-supplement-v1/README.md) are now frozen:
seed 20260922 selects four families, each with ten tasks and the existing L1-boundary
profile. An in-memory preview verified unique input identities and twelve static
G/C/P plans. The four runnable input configs and a separate validation extension
have now been prepared; see the supplement record for ELF analysis and independent-U
collection status. The existing calibration has not been rerun or frozen.
Additional successes do not replace failed rows or automatically satisfy the existing
freeze gate.

The implementation verification paragraph above describes the initial attempt.
The later finalize at 2026-09-22T14:01:33Z passed with 609 tests and no skips using
CHASER_COLD_PREFIX=/tmp/chaser-cg-cold-install. That result predates this documentation
update. The census wrapper also passed two targeted checks against preserved successful
and failed P evidence; no full verifier or finalize was rerun for that census documentation.
The subsequent supplement-rule work passed static replay and the full verifier:
609 tests, no skips, 79.62 seconds. See its [verification record](../validation-supplement-v1/verification.json).
Finalize was not invoked for the supplement-rule work.
