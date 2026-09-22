# Final ELF / independent U characterization v1

2026-09-21. Collection is **incomplete**, not a completed dataset. Inputs remain
[the frozen 207 tasksets](../input-freeze-v1/README.md), with the same 126/41/40 split.
No theta calibration, architecture labels, or RF training are performed here.

The working evidence is `.cache/characterization-v1/`; the independently extracted
and revalidated input is `.cache/characterization-v1-inputs/frozen/`.
The user deleted the previous working cache. The candidate-v3-0120 example was
subsequently rebuilt and reanalyzed; previous full-pool progress and raw preflight
logs are not present in this regenerated cache. Historical preflight summaries
below do not establish current raw-evidence availability.

Preparation checks G/C/P final ELF layouts and complete linked access streams.
With `compress_events=True` (used by the frozen-input collector), each validated
event document is stored as **events.json.xz, preset 9 extreme**. Every original
byte, field, and event is retained. The archive is decompressed and its SHA-256
and byte count checked before removing the uncompressed working file. The analysis
manifest records compressed-file hashes plus original hashes/sizes and codec.
Uncompressed analysis remains the default for the individual analyze API/CLI.

The regenerated candidate-v3-0120 example has also been converted to XZ.
For viewing without restoring a persistent file:

```sh
xz -dc .cache/characterization-v1/prepared/candidate-v3-0120/analysis/g/v3w0120_t00/events.json.xz | less
```

## Storage and execution budget

There are 2,168 tasks, 19,512 backend analysis calls, and 156,774,432 event records
across G/C/P. The previous estimate of approximately 73 GB referred to the **sum of
uncompressed event JSON**, not one file or the final feature data.

Measured comparison for candidate-v3-0120 G task 0 (4,832,652 original bytes):

| Encoding | Bytes | Compression seconds |
|---|---:|---:|
| gzip level 9 | 66,616 | 0.08 |
| XZ preset 6 | 37,056 | 0.33 |
| **XZ preset 9 extreme** | **20,320** | **5.41** |

XZ extreme is selected to favor size over compression time. It uses a 64 MiB
compression dictionary; encoder working memory is larger. This is the smallest
of the measured configurations, not a claim of a universal optimum. The full
pool's XZ storage/time remains unmeasured; do not extrapolate one small case as a
final budget. ELF/build snapshots and measurement logs are additional.
Analysis and compression remain serial. A full raw event file exists temporarily
while validation and compression run. See [compression.json](compression.json)
for the converted example's per-file original hashes, byte counts, and sizes.

One-task preflight simulator runs succeeded for both input sizes (roughly 5 and
11 seconds respectively). These samples do not establish a full-population time
budget or concurrent throughput. Independent U requires **21,680 fresh runs**;
use at most eight simulator workers and preserve each planned failure. Full U
collection and its final wall-time budget remain pending.

## Commands and interpretation

From the workspace root:

```sh
python3 -m tools.rtems_periodic_characterize prepare \
  .cache/characterization-v1-inputs/frozen \
  --output .cache/characterization-v1 --workers 8 --timeout 120
python3 -m tools.rtems_periodic_characterize run \
  .cache/characterization-v1-inputs/frozen \
  --output .cache/characterization-v1 --workers 8 --timeout 120
```

The timeout option applies to each simulator run; each analyzer command retains
its existing 120-second timeout. Complete outputs are revalidated on resume;
incomplete directories and failed batches are retained, never overwritten or
silently rerun. The same frozen configuration and collection protocol are required.
Characterization implementation snapshots are fixed when the run phase starts.

Each task runs alone using mode i+1 of the same final P ELF, ten times. Raw logs
are reloaded and checked before all jobs contribute to mean CPU/period U.
Features join exact task IDs; they contain no label. The tool records measured
`max(u_i) <= 0.25` and `sum(u_i) <= 2.0` separately from collection success.
Undefined representations remain explicit. A successful collection record does
not establish all-feature availability, final G/C/P eligibility, or dataset readiness.

The first sandbox parallel preflight could not connect to DISPLAY and preserved
40 failed attempts under `preflight-display-failure/` (moved from the initial diagnostic output path
`runs/candidate-v3-0120/`). These must not be treated as
valid U evidence. A separate escalated diagnostic retry succeeded; the separate
`preflight-independent/` batch exercises complete characterization. Preflight
results and failures remain separate from the not-yet-started full U collection.

## Preflight and verification

The separate independent-U preflight completed **40/40 runs** for candidate-v3-0120.
Raw-log reload and characterization passed; summed U is approximately 0.237 and
all four default representations have 11 features. See [preflight.json](preflight.json).
This is not the 207-input collection result.

The earlier 540-test verification and preflight logs were in the deleted cache.
Current XZ verification was rerun on 2026-09-22; see [verification.txt](verification.txt).
All 12 example archives were also decompressed and checked against their original
SHA-256 and byte counts, and the analysis manifest passed verification.
Finalize was not invoked.
