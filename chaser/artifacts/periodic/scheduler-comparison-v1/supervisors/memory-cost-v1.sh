#!/bin/sh
# Experiment 41 (pre-registered, EXPERIMENTS.md 41): memory tasks hitting L2 vs going to memory at the same
# CLS and U; prepare, isolated U gate, pilot, full, stats, then rt_metrics and the analysis. Needs
# results/mem-calibration/mem-model.json (mem_calibrate.py).
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
L=$W/.cache/memory-cost-v1-supervisor
O=$W/.cache/memory-cost-v1
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$L" "$O" && cp "$W/artifacts/periodic/scheduler-comparison-v1/results/deadline-small/model-check.json" "$O/model-check.json" || exit 1
status=0
for stage in ${STAGES:-prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/pm_run.py" "$stage" --design memory-cost --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
if [ "$status" -eq 0 ]; then
    python3 -u "$S/rt_metrics.py" --output "$O" --builds wfd,cgb && \
    PYTHONPATH="$CODE:$S" python3 -u "$S/memcost_analysis.py" --output "$O" --rows "$W/artifacts/periodic/scheduler-comparison-v1/results/rf-model/training-rows.jsonl.gz" --dest "$W/.cache/memory-cost-analysis-v1"
    status=$?
    printf "%s analysis exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
fi
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
