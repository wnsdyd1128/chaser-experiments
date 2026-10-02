#!/bin/sh
# Load level: the v2 CLS condition (8 high + 8 low, CV 0.1, as-is) with 2.5 ms
# jobs at periods 80/40/30/20 ms. Reuses the v2 calibration model.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/cls-bimodal
O=$W/.cache/load-level-v1
L=$W/.cache/load-level-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
if [ ! -f "$O/calibration/model.json" ]; then
    printf "%s calibration model is missing\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf "1\n" > "$L/supervisor.exit"
    exit 1
fi
status=0
# Resume after a stopped stage with e.g. STAGES="isolated pilot full stats".
for stage in ${STAGES:-prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/bi_run.py" "$stage" --design load-level --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
