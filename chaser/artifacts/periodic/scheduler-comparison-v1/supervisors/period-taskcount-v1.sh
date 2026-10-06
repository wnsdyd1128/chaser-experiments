#!/bin/sh
# Experiments 1 and 2 with 12-20 tasks: mu 20/50/80/100/500 x CV {0, 0.1, 0.2, 0.3}, equal
# per-task U (per-core 0.5), O0 cyclic 64-line jobs; G/C (1+3)/P/C2 (1+1+2) on the period
# snake, then P'/C'/C2' on the cohort-aware placement. Uses the 4d03b93 + C2 code copy as
# experiments 1 and 2 did. Stops at the first nonzero exit.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c2
S=$W/artifacts/periodic/scheduler-comparison-v1/period-distribution
MAIN=$W/.cache/period-taskcount-v1
COHORT=$W/.cache/period-taskcount-cohort-v1
L=$W/.cache/period-taskcount-v1-supervisor
mkdir -p "$L"
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
step() {
    name=$1
    shift
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$name"
    python3 -u "$@"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$name" "$status"
    return $status
}
status=0
# Resume after a stopped stage with e.g. MAIN_STAGES="full" (and COHORT_STAGES likewise).
for stage in ${MAIN_STAGES:-prepare u-check pilot full}; do
    step "main-$stage" "$S/tc_run.py" main "$stage" --output "$MAIN" || break
done
[ "$status" -eq 0 ] && step main-stats "$S/stats.py" "$MAIN"
if [ "$status" -eq 0 ]; then
    for stage in ${COHORT_STAGES:-prepare g-check run summarize stats}; do
        step "cohort-$stage" "$S/tc_run.py" control "$stage" --main "$MAIN" --output "$COHORT" || break
    done
fi
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
