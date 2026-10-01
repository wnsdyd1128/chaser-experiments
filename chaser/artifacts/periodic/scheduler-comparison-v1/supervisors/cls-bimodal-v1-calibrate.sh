#!/bin/sh
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/cls-bimodal
O=$W/.cache/cls-bimodal-v1/calibration
L=$W/.cache/cls-bimodal-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
status=0
for stage in measure fit; do
    printf "%s calibrate stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/bi_calibrate.py" "$stage" --output "$O"
    status=$?
    printf "%s calibrate stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/calibrate.exit"
exit "$status"
