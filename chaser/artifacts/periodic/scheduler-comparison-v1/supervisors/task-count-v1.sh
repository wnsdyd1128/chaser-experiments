#!/bin/sh
# Task count x memory pressure: 12-20 tasks (each count 4 times per cell) x 768 KiB share of
# total U {0, 25 %, 50 %} x per-core U {0.35, 0.45}, periods {20, 40, 80} ms; G and C2 (1+1+2)
# on wfd and P on wfd, cgb, ra, ra-cgb. Job budgets (0.44-20.8 ms) lie inside
# policy-mix-v1's model check (0.21-43 ms, same shape families), which is copied; the
# isolated gate checks set 0 of every cell.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
O=$W/.cache/task-count-v1
L=$W/.cache/task-count-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$O" && cp "$W/.cache/policy-mix-v1/model-check.json" "$O/model-check.json" || exit 1
status=0
# Resume after a stopped stage with e.g. STAGES="pilot full stats".
for stage in ${STAGES:-prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/pm_run.py" "$stage" --design task-count --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
