#!/bin/sh
# Experiment 46 (EXPERIMENTS.md 46): the frozen pre-run check v1 on task sets of held-out kernels (2MM, SYRK, TRMM,
# DOITGEN). Calibration of the job times (measure, fit, tasks), export of the calibration, then prepare, isolated U
# gate, the pre-run decisions (before any measured run), full runs, summarize, the analysis and the technical report.
# The recorded run (2026-10-08) decided with the dropped policy v2 (--policy rf-model-v2) and recorded v1 with
# --compare-policy; the runs do not depend on the decisions, so this script with v1 reproduces the runs and v1's decisions.
W=/workspace/experiments/chaser
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
P=$W/artifacts/periodic/scheduler-comparison-v1/period-distribution
R=$W/artifacts/periodic/scheduler-comparison-v1/results
L=$W/.cache/heldout-kernels-v1-supervisor
K=$W/.cache/kernel-calibration-heldout-v2
O=$W/.cache/heldout-kernels-v1
cd "$W" || exit 1
export PYTHONPATH="$W:$S:$P" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$L" "$K" "$O" || exit 1
step() {
    name=$1
    shift
    printf "%s %s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$name"
    "$@"
    code=$?
    printf "%s %s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$name" "$code"
    return "$code"
}
status=0
for stage in ${CALIBRATE:-measure fit}; do
    step "calibrate=$stage" python3 -u "$S/kernel_calibrate.py" "$stage" --design heldout-kernels --output "$K" || { status=1; break; }
done
if [ "$status" -eq 0 ] && [ -n "${CALIBRATE-measure fit}" ]; then
    mkdir -p "$R/kernel-calibration-heldout" && cp "$K/kernel-model.json" "$K/measured.json" "$R/kernel-calibration-heldout/" || status=1
fi
if [ "$status" -eq 0 ] && [ -n "${CALIBRATE-measure fit}" ]; then
    step "calibrate=tasks" python3 -u "$S/kernel_calibrate.py" tasks --design heldout-kernels --output "$K" && \
        cp "$K/task-times.json" "$R/kernel-calibration-heldout/" || status=1
fi
if [ "$status" -eq 0 ]; then
    for stage in ${STAGES:-prepare isolated decide full summarize}; do
        step "stage=$stage" python3 -u "$S/kernel_run.py" "$stage" --design heldout-kernels --output "$O" \
            --policy "$W/.cache/rf-model-v1"
        status=$?
        [ "$status" -ne 0 ] && break
    done
fi
if [ "$status" -eq 0 ]; then
    step analysis python3 -u "$S/heldout_analysis.py" --cache "$W/.cache" --output heldout-kernels-v1 \
        --dest "$W/.cache/heldout-kernels-analysis-v1" && \
    step report python3 -u "$S/kernel_report.py" --cache "$W/.cache" --output heldout-kernels-v1 --design heldout-kernels \
        --dest "$W/.cache/heldout-kernels-analysis-v1"
    status=$?
fi
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
