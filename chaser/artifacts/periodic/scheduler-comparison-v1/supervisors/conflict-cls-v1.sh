#!/bin/sh
# Conflict-miss low-CLS tasks: experiment 21's sets (12-20 tasks, per-core U 0.4) in the cells
# period CV {0, 0.2} x low-CLS share {25 %, 50 %}, with each low-CLS task walking 43-61 lines
# (1.4-1.9 KiB) 4 KiB apart so every access but the hot repeats misses one L1 set and hits the L2.
# G and C2 (1+1+2) on wfd and P on wfd, cgb, ra, ra-cgb. The conflict shapes are outside
# policy-mix-v1's model check, so none is copied: the isolated gate (every task of set 0 of each
# cell, 3 %) checks the job-time model on them before the pilot.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
O=$W/.cache/conflict-cls-v1
L=$W/.cache/conflict-cls-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$O" "$L" || exit 1
status=0
# Resume after a stopped stage with e.g. STAGES="pilot full stats".
for stage in ${STAGES:-prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/pm_run.py" "$stage" --design conflict-cls --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
