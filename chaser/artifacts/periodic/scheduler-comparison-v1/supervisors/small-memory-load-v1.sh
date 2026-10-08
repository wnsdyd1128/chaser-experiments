#!/bin/sh
# Small-memory low-CLS tasks under load: 12-20 tasks (each count twice) x period CV {0, 0.2}
# x share of total U held by 32 KiB low-CLS as-is tasks {25 %, 50 %} x per-core U {0.45-0.6},
# periods from {20, ..., 120} ms around 40 ms; G and C2 (1+1+2) on wfd and P on wfd, cgb, ra,
# ra-cgb. Job budgets (0.65-18.14 ms) lie inside policy-mix-v1's model check per family
# (high 0.24-43.17 ms, low as-is 0.23-18.12 ms), which is copied; the isolated gate checks
# set 0 of every cell.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
O=$W/.cache/small-memory-load-v1
L=$W/.cache/small-memory-load-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$O" "$L" && cp "$W/artifacts/periodic/scheduler-comparison-v1/results/deadline-small/model-check.json" "$O/model-check.json" || exit 1
status=0
# Resume after a stopped stage with e.g. STAGES="pilot full stats".
for stage in ${STAGES:-prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/pm_run.py" "$stage" --design small-memory-load --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
