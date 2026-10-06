#!/bin/sh
# CLS spread: 12-20 tasks (each count twice) x CLS mean {0.3, 0.6, 0.9} x CLS SD {0, 0.1, 0.2}
# x period CV {0, 0.2} at per-core U 0.4; G and C2 (1+1+2) on wfd and P on wfd, cgb, ra, ra-cgb
# (absolute cut CLS <= 0.5) and cgr, ra-cgr (relative cut: lower-CLS half of the U). Mid-range
# CLS uses high-mode shapes with up to 1024 sweeps, outside policy-mix-v1's model check, so no
# model check is copied: the isolated gate (every task of set 0 of each cell, 3 %) checks the
# job-time model on this design's shapes before the pilot.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
O=$W/.cache/cls-spread-v1
L=$W/.cache/cls-spread-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$O" "$L" || exit 1
status=0
# Resume after a stopped stage with e.g. STAGES="pilot full stats".
for stage in ${STAGES:-prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/pm_run.py" "$stage" --design cls-spread --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
