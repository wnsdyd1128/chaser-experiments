#!/bin/sh
# High load + memory contention: 8 high- + 8 low-CLS hot-cold O2 tasks, periods
# {20,40,80} ms, per-core U {0.3,0.45,0.6} x low-CLS traffic {as-is, matched},
# 30 sets per cell; G/C/C2/P on WFD and P traffic-grouped + U-balanced. The
# model check over the design's job budgets gates the run.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/high-load
O=$W/.cache/memory-load-v1
L=$W/.cache/memory-load-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
status=0
# Resume after a stopped stage with e.g. STAGES="isolated pilot full stats".
for stage in ${STAGES:-check prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    if [ "$stage" = check ]; then
        python3 -u "$S/mem_check.py" --output "$O"
    else
        python3 -u "$S/hl_run.py" "$stage" --design memory --output "$O"
    fi
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
