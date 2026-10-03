#!/bin/sh
# G vs C without a feasible partition on fresh sets: 5 or 6 heavy tasks with at
# most 2 (stagger) or 3 (sync) sharing a period, per-core U 0.85, 40 sets per cell;
# G on WFD and capacity-balanced C (1+3) and C2 (1+1+2). Primary tests pre-registered.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/high-load
O=$W/.cache/g-vs-c-sync-v1
L=$W/.cache/g-vs-c-sync-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
status=0
# Resume after a stopped stage with e.g. STAGES="isolated pilot full stats".
for stage in ${STAGES:-prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/hl_run.py" "$stage" --design g-vs-c-sync --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
