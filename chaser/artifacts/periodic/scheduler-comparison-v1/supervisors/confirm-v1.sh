#!/bin/sh
# Experiment 44 (pre-registered, EXPERIMENTS.md 44): the frozen pre-run check on fresh sets of three types.
# Per design: prepare, isolated U gate, the pre-run decisions (confirm_decide.py, before any measured run),
# pilot, full, stats, rt_metrics; then the pre-registered analysis over the three designs.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
P=$W/artifacts/periodic/scheduler-comparison-v1/period-distribution
L=$W/.cache/confirm-v1-supervisor
POLICY=$W/.cache/rf-model-v1
cd "$CODE" || exit 1
export DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$L" || exit 1
status=0
for design in ${DESIGNS:-confirm-small confirm-big confirm-mem}; do
    O=$W/.cache/$design-v1
    mkdir -p "$O" && cp "$W/artifacts/periodic/scheduler-comparison-v1/results/deadline-small/model-check.json" "$O/model-check.json" || { status=1; break; }
    for stage in ${STAGES:-prepare isolated decide pilot full stats}; do
        printf "%s design=%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$design" "$stage"
        if [ "$stage" = decide ]; then
            PYTHONPATH="$W:$S:$P" python3 -u "$S/confirm_decide.py" --output "$O" --policy "$POLICY"
        else
            PYTHONPATH="$CODE" python3 -u "$S/pm_run.py" "$stage" --design "$design" --output "$O"
        fi
        status=$?
        printf "%s design=%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$design" "$stage" "$status"
        [ "$status" -ne 0 ] && break
    done
    [ "$status" -ne 0 ] && break
    PYTHONPATH="$CODE" python3 -u "$S/rt_metrics.py" --output "$O" --builds ra-cgb
done
if [ "$status" -eq 0 ]; then
    PYTHONPATH="$W:$S:$P" python3 -u "$S/confirm_analysis.py" --cache "$W/.cache" --dest "$W/.cache/confirm-analysis-v1"
    status=$?
    printf "%s analysis exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
fi
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
