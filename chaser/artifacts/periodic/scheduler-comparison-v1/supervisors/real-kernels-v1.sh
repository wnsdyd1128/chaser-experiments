#!/bin/sh
# Experiment 45 (pre-registered, EXPERIMENTS.md 45): the frozen pre-run check on real-kernel task sets.
# prepare (wfd build, YARDA, pfirst CHASER placement, ra-cgb build), isolated U gate, decisions before any
# measured run, full runs (CHASER P, G4, C1+3, C1+1+2), summarize, then the pre-registered analysis.
W=/workspace/experiments/chaser
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
P=$W/artifacts/periodic/scheduler-comparison-v1/period-distribution
L=$W/.cache/real-kernels-v1-supervisor
O=$W/.cache/real-kernels-v1
cd "$W" || exit 1
export PYTHONPATH="$W:$S:$P" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$L" "$O" || exit 1
status=0
for stage in ${STAGES:-prepare isolated decide full summarize}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/kernel_run.py" "$stage" --output "$O" --policy "$W/.cache/rf-model-v1"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
if [ "$status" -eq 0 ]; then
    python3 -u "$S/confirm_analysis.py" --cache "$W/.cache" --outputs real-kernels-v1 --dest "$W/.cache/real-kernels-analysis-v1"
    status=$?
    printf "%s analysis exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
fi
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
