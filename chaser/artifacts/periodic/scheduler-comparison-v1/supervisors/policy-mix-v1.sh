#!/bin/sh
# Multi-factor placement comparison: 80 task sets x per-core U {0.3, 0.45}. Six factors
# drawn per set (periods, low-CLS count and traffic, 768 KiB tasks, U spread, heavy
# task); P on wfd / tg / ra / ra-tg, G and C2 (1+1+2) on wfd. The model check over the
# design's own task shapes gates the run.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
O=$W/.cache/policy-mix-v1
L=$W/.cache/policy-mix-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
status=0
# Resume after a stopped stage with e.g. STAGES="isolated pilot full stats".
for stage in ${STAGES:-check prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    if [ "$stage" = check ]; then
        python3 -u "$S/pm_check.py" --output "$O"
    else
        python3 -u "$S/pm_run.py" "$stage" --output "$O"
    fi
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
