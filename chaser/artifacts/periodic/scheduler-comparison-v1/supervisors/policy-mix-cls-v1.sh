#!/bin/sh
# CLS-keyed placements on the policy-mix task sets: the same 160 cases (80 sets x per-core U
# {0.3, 0.45}) with P on cg (CLS grouping + U balance) and ra-cg (release-aware within CLS
# grouping), to pair case by case with policy-mix-v1's tg and ra-tg. The task shapes equal
# policy-mix-v1's, so its model check is copied instead of rerun.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
O=$W/.cache/policy-mix-cls-v1
L=$W/.cache/policy-mix-cls-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$O" && cp "$W/.cache/policy-mix-v1/model-check.json" "$O/model-check.json" || exit 1
status=0
# Resume after a stopped stage with e.g. STAGES="pilot full stats".
for stage in ${STAGES:-prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/pm_run.py" "$stage" --design policy-mix-cls --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
