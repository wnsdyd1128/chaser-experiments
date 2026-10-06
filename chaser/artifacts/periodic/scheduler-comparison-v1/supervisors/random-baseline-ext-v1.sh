#!/bin/sh
# Random baseline, earlier studies: P on three random placements per set
# (each task on a uniformly drawn core, redrawn until every core is under U 0.95), on the sets of
# experiments 24 (every cell and load), 25 (every cell), 19 (cells with low-CLS or 768 KiB tasks)
# and 17 (the policy-mix sets, paired with 17 and 18), to pair with their results. Same task shapes as
# those runs; the isolated gate checks set 0 of every cell. Runs the four designs in turn.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
L=$W/.cache/random-baseline-ext-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$L" || exit 1
status=0
for design in ${DESIGNS:-random-small-memory-load random-conflict-cls random-policy-boundary random-policy-mix}; do
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
