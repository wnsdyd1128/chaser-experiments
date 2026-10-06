#!/bin/sh
# Random baseline (CAAS's affinity-blind placement): P on three random placements per set
# (each task on a uniformly drawn core, redrawn until every core is under U 0.95), on the sets of
# experiment 21 (low-CLS cells), 20 (25 % memory cell, both loads) and 23 (CLS mean 0.6 and 0.9
# with spread), to pair with their wfd, CLS-based and release-aware results. Same task shapes as
# those runs; the isolated gate checks set 0 of every cell. Runs the three designs in turn.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
L=$W/.cache/random-baseline-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$L" || exit 1
status=0
for design in ${DESIGNS:-random-small-memory random-task-count random-cls-spread}; do
    O=$W/.cache/$design-v1
    mkdir -p "$O" || exit 1
    for stage in ${STAGES:-prepare isolated pilot full stats}; do
        printf "%s design=%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$design" "$stage"
        python3 -u "$S/pm_run.py" "$stage" --design "$design" --output "$O"
        status=$?
        printf "%s design=%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$design" "$stage" "$status"
        [ "$status" -ne 0 ] && break
    done
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
