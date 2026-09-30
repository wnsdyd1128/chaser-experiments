#!/bin/sh
# CLS-distribution main run with the 4d03b93 + C2 code copy; stops at the first failure.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c2
S=$W/.cache/configs/cls-distribution
O=$W/.cache/cls-distribution-v1
L=$W/.cache/cls-distribution-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
status=0
for stage in prepare u-check pilot full stats; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/cls_run.py" "$stage" --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
