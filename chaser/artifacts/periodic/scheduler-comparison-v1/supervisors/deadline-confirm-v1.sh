#!/bin/sh
# Experiment 27, confirmatory deadline study (pre-registered in EXPERIMENTS.md 27), on fresh sets:
# deadline-small (32 KiB low-CLS as-is tasks at 50 % of U, per-core U 0.45-0.6 by 0.025) then
# deadline-big (768 KiB tasks at 25 % of U, per-core U 0.30-0.45), each 12-20 tasks (each count
# twice) x period CV {0, 0.2} x 18 sets, warm-up 1 + measured 3 hyperperiods of 240 ms; G and C2
# (1+1+2) on wfd and P on wfd, cgb, ra, ra-cgb and three random draws. Per design: prepare, the
# static L2 demand prediction (deadline_analysis.py refuses once any run exists), isolated (set 0
# of every cell), pilot, full, stats and rt_metrics; then the pre-registered analysis of both.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
L=$W/.cache/deadline-confirm-v1-supervisor
A=$W/.cache/deadline-confirm-v1
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$L" || exit 1
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
# Resume after a stopped stage with e.g. DESIGNS="deadline-big" STAGES="full stats rt".
for design in ${DESIGNS:-deadline-small deadline-big}; do
    O=$W/.cache/$design-v1
    mkdir -p "$O" && cp "$W/.cache/policy-mix-v1/model-check.json" "$O/model-check.json" || { status=1; break; }
    for stage in ${STAGES:-prepare predict isolated pilot full stats rt}; do
        case $stage in
            predict) step "design=$design stage=predict" python3 -u "$S/deadline_analysis.py" predict --output "$O" ;;
            rt) step "design=$design stage=rt" python3 -u "$S/rt_metrics.py" --output "$O" \
                    --builds wfd,cgb,ra,ra-cgb,rnd0,rnd1,rnd2 ;;
            *) step "design=$design stage=$stage" python3 -u "$S/pm_run.py" "$stage" --design "$design" --output "$O" ;;
        esac
        status=$?
        [ "$status" -ne 0 ] && break
    done
    [ "$status" -ne 0 ] && break
done
if [ "$status" -eq 0 ]; then
    step analyze python3 -u "$S/deadline_analysis.py" analyze --small "$W/.cache/deadline-small-v1" \
        --big "$W/.cache/deadline-big-v1" --dest "$A"
    status=$?
fi
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
