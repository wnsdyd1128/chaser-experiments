#!/bin/sh
# CLS x footprint: 4 special kinds (SL/BL/SH/BH) + 12 high-CLS background tasks, 5.5 ms
# jobs at a 200 ms period, 20 sets per kind. Reuses the v2 calibration model.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/footprint
O=$W/.cache/footprint-v1
L=$W/.cache/footprint-v1-supervisor
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
    python3 -u "$S/fp_run.py" "$stage" --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
