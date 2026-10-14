#!/bin/sh
# Experiment 47 (pre-registered, EXPERIMENTS.md 47): CHASER's placement (WFD, CGB, RA, RA-CGB) on task sets whose low-CLS
# tasks are real low-locality kernels (naive transpose, planar complex corner turn). Stages: calibrate (measure, fit and
# export the low kernels' job-time model), tasks (measure every size the sets need, export), prepare, isolated, full,
# summarize, analyze. laysim runs through the date-override preload (/workspace/date_override.so: it changes only the
# calendar date localtime() returns; 2026-10-13 check: four experiment 45 runs gave identical records).
# Resume after a stopped stage with e.g. STAGES="full summarize analyze".
W=/workspace/experiments/chaser
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
P=$W/artifacts/periodic/scheduler-comparison-v1/period-distribution
R=$W/artifacts/periodic/scheduler-comparison-v1/results
C=$W/.cache/kernel-calibration-lowloc-v1
O=$W/.cache/lowloc-kernels-v1
L=$W/.cache/lowloc-kernels-v1-supervisor
C3=$W/.cache/period-distribution-code-4d03b93-c3
cd "$W" || exit 1
export PYTHONPATH="$W:$S:$P" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1 LD_PRELOAD=/workspace/date_override.so
mkdir -p "$L" "$C" "$O" "$R/kernel-calibration-lowloc" || exit 1
status=0
for stage in ${STAGES:-calibrate tasks prepare isolated full summarize analyze}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    case $stage in
        calibrate) python3 -u "$S/kernel_calibrate.py" measure --design lowloc-kernels --output "$C" &&
                   python3 -u "$S/kernel_calibrate.py" fit --design lowloc-kernels --output "$C" &&
                   cp "$C/kernel-model.json" "$C/measured.json" "$R/kernel-calibration-lowloc/" ;;
        tasks) python3 -u "$S/kernel_calibrate.py" tasks --design lowloc-kernels --output "$C" &&
               cp "$C/task-times.json" "$R/kernel-calibration-lowloc/" ;;
        analyze) env -u LD_PRELOAD PYTHONPATH="$C3:$S:$P" python3 -u "$S/lowloc_analysis.py" --output "$O" \
                     --dest "$W/.cache/lowloc-kernels-analysis-v1" ;;
        *) python3 -u "$S/lowloc_run.py" "$stage" --output "$O" ;;
    esac
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
