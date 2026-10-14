#!/bin/sh
# Experiment 48 and its pilot (EXPERIMENTS.md 48): experiment 47's placement comparison with every task's data capped
# like PolyBench's small datasets (lowloc_set capped designs). DESIGN selects the lowloc_set design (a pilot, whose task
# times stay in .cache, or lowloc-small). Stages: tasks (measure every size the sets need; the models are experiments
# 45 and 47's), prepare, isolated, full, summarize, analyze. laysim runs through the date-override preload, as in lowloc-kernels-v1.sh.
# Resume after a stopped stage with e.g. STAGES="full summarize analyze".
DESIGN=${DESIGN:-lowloc-small}
W=/workspace/experiments/chaser
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
P=$W/artifacts/periodic/scheduler-comparison-v1/period-distribution
R=$W/artifacts/periodic/scheduler-comparison-v1/results
C=$W/.cache/kernel-calibration-$DESIGN-v1
O=$W/.cache/$DESIGN-v1
L=$W/.cache/$DESIGN-v1-supervisor
C3=$W/.cache/period-distribution-code-4d03b93-c3
cd "$W" || exit 1
export PYTHONPATH="$W:$S:$P" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1 LD_PRELOAD=/workspace/date_override.so
mkdir -p "$L" "$C" "$O" || exit 1
status=0
for stage in ${STAGES:-tasks prepare isolated full summarize analyze}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    case $stage in
        tasks) python3 -u "$S/kernel_calibrate.py" tasks --design "$DESIGN" --output "$C" &&
               case $DESIGN in
                   *pilot*) ;;
                   *) mkdir -p "$R/kernel-calibration-$DESIGN" && cp "$C/task-times.json" "$R/kernel-calibration-$DESIGN/" ;;
               esac ;;
        analyze) env -u LD_PRELOAD PYTHONPATH="$C3:$S:$P" python3 -u "$S/lowloc_analysis.py" --output "$O" \
                     --dest "$W/.cache/$DESIGN-analysis-v1" --title "${TITLE:-$DESIGN: CHASER placement on capped low-locality kernels}" ;;
        *) python3 -u "$S/lowloc_run.py" "$stage" --design "$DESIGN" --output "$O" ;;
    esac
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
