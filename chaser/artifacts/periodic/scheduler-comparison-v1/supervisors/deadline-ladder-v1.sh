#!/bin/sh
# Experiment 28, CAAS Algorithm 1 against the CLS steps (pre-registered in EXPERIMENTS.md 28), on
# experiment 27's sets: P on caas (CA-CSRD, frozen threshold, core 0 isolated), cls-a1 (CLS 0.5) and
# cls-a1-cal (CLS, frozen calibrated threshold) for deadline-small-caas then deadline-big-caas, each
# prepare, isolated (set 0 of every cell), pilot, full, stats and rt_metrics; then the pre-registered
# ladder analysis against experiment 27's outputs. Waits for experiment 27's supervisor to finish and
# starts only if it exited 0. CA-CSRD tables (results/ca-csrd/) were made from experiment 27's
# yarda analyses by ca_table.py before this run.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
L=$W/.cache/deadline-ladder-v1-supervisor
A=$W/.cache/deadline-ladder-v1
PREVIOUS=$W/.cache/deadline-confirm-v1-supervisor/supervisor.exit
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
while [ ! -f "$PREVIOUS" ]; do sleep 60; done
if [ "$(cat "$PREVIOUS")" != 0 ]; then
    printf "%s experiment 27 exited %s; not starting\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(cat "$PREVIOUS")"
    printf "1\n" > "$L/supervisor.exit"
    exit 1
fi
status=0
# Resume after a stopped stage with e.g. DESIGNS="deadline-big-caas" STAGES="full stats rt".
for design in ${DESIGNS:-deadline-small-caas deadline-big-caas}; do
    O=$W/.cache/$design-v1
    mkdir -p "$O" && cp "$W/artifacts/periodic/scheduler-comparison-v1/results/deadline-small/model-check.json" "$O/model-check.json" || { status=1; break; }
    for stage in ${STAGES:-prepare isolated pilot full stats rt}; do
        case $stage in
            rt) step "design=$design stage=rt" python3 -u "$S/rt_metrics.py" --output "$O" --builds caas,cls-a1,cls-a1-cal ;;
            *) step "design=$design stage=$stage" python3 -u "$S/pm_run.py" "$stage" --design "$design" --output "$O" ;;
        esac
        status=$?
        [ "$status" -ne 0 ] && break
    done
    [ "$status" -ne 0 ] && break
done
if [ "$status" -eq 0 ]; then
    step analyze python3 -u "$S/ladder_analysis.py" --small "$W/.cache/deadline-small-v1" \
        --small-caas "$W/.cache/deadline-small-caas-v1" --big "$W/.cache/deadline-big-v1" \
        --big-caas "$W/.cache/deadline-big-caas-v1" --dest "$A"
    status=$?
fi
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
