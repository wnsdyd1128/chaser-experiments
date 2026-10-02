#!/bin/sh
# Task-U imbalance: checks the job-time model on the design's own levels (12
# workers, alongside the load-level run), waits for the load-level run, then
# runs the design. Starts from a copy of the v2 calibration.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/cls-bimodal
O=$W/.cache/u-imbalance-v1
L=$W/.cache/u-imbalance-v1-supervisor
PREV=$W/.cache/load-level-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
status=0
# Resume after a stopped stage with e.g. STAGES="isolated pilot full stats".
for stage in ${STAGES:-extend prepare isolated pilot full stats}; do
    if [ "$stage" = prepare ]; then
        while [ ! -f "$PREV/supervisor.exit" ] && kill -0 "$(cat $PREV/supervisor.pid)" 2>/dev/null; do sleep 30; done
    fi
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    if [ "$stage" = extend ]; then
        python3 -u "$S/bi_calibrate.py" extend --workers 12 --output "$O/calibration"
    else
        python3 -u "$S/bi_run.py" "$stage" --design u-imbalance --output "$O"
    fi
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
