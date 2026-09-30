#!/bin/sh
# v2: mu 20/50/80/100/500, G/C/P/C2, then the cohort-placement control.
# Uses the 4d03b93 + C2 code copy. Stops at the first nonzero exit.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c2
S=$W/.cache/configs/period-distribution
MAIN=$W/.cache/period-distribution-v2
COHORT=$W/.cache/period-distribution-cohort-v2
L=$W/.cache/period-distribution-v2-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
step() {
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1"
    shift
    python3 -u "$@"
    status=$?
    printf "%s stage exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
    return $status
}
status=0
for stage in u-check pilot full; do
    step "main-$stage" "$S/run.py" "$stage" --output "$MAIN" || break
done
[ "$status" -eq 0 ] && step main-stats "$S/stats.py" "$MAIN"
if [ "$status" -eq 0 ]; then
    for stage in g-check run summarize stats; do
        step "cohort-$stage" "$S/control.py" "$stage" --main "$MAIN" --output "$COHORT" || break
    done
fi
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
