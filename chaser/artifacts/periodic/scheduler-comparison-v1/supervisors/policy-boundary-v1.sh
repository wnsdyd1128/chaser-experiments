#!/bin/sh
# Period spread x memory mix: 24 cells (period CV {0, 0.1, 0.2, 0.3} x low-CLS 32 KiB tasks
# {0, 4, 8} x 768 KiB tasks {0, 2}) x 10 sets at per-core U 0.4; P on wfd, balanced CLS
# grouping (cgb), release-aware (ra) and release-aware within balanced CLS grouping
# (ra-cgb). Job budgets (0.97-8.65 ms) lie inside policy-mix-v1's model check (0.21-43 ms
# over the same shape families), which is copied; the isolated gate checks set 0 of every cell.
W=/workspace/experiments/chaser
CODE=$W/.cache/period-distribution-code-4d03b93-c3
S=$W/artifacts/periodic/scheduler-comparison-v1/policy-mix
O=$W/.cache/policy-boundary-v1
L=$W/.cache/policy-boundary-v1-supervisor
cd "$CODE" || exit 1
export PYTHONPATH="$CODE" DISPLAY=165.246.44.80:90.0 PYTHONUNBUFFERED=1
mkdir -p "$O" && cp "$W/.cache/policy-mix-v1/model-check.json" "$O/model-check.json" || exit 1
status=0
# Resume after a stopped stage with e.g. STAGES="pilot full stats".
for stage in ${STAGES:-prepare isolated pilot full stats}; do
    printf "%s stage=%s started\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage"
    python3 -u "$S/pm_run.py" "$stage" --design policy-boundary --output "$O"
    status=$?
    printf "%s stage=%s exit=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" "$status"
    [ "$status" -ne 0 ] && break
done
printf "%s\n" "$status" > "$L/supervisor.exit"
printf "%s finished status=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status"
exit "$status"
