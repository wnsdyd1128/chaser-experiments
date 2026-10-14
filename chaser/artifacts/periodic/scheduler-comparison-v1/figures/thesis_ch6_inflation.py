"""Per-task job time inflation behind thesis figure 6.12, extracted once from the raw experiment 45 and 46 runs.

For every judged set at per-core loads 0.625 and 0.70, the CHASER (P, ra-cgb) run: per task, the worst job CPU time over
the task's planned budget (planned U x period; the planned U is the measured isolated job time). The same computation as
figures/heldout_bars.py (heldout-inflation). A task stops at its first deadline miss (rtems/periodic/init.c), so a task in
a run that missed has the jobs it ran up to that point.
The raw runs (.cache/real-kernels-v1, .cache/heldout-kernels-v1) are on the cleanup list; the CSV keeps the values.
Usage: python3 thesis_ch6_inflation.py <.cache dir> <output csv>   (PYTHONPATH: workspace, policy-mix, period-distribution)
"""
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'policy-mix'))

import confirm_analysis as ca

OUTPUTS = (('real-kernels-v1', 'experiment 45'), ('heldout-kernels-v1', 'experiment 46'))


def main():
    cache, dest = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    rows = []
    for name, experiment in OUTPUTS:
        records, _ = ca.sets(cache, (name,))
        for r in records:
            if r['load'] < 0.6:
                continue
            case = cache / name / r['label']
            planned = json.loads((case / 'design.json').read_text())['tasks']
            plan = json.loads((case / 'ra-cgb/prepared/p/plan.json').read_text())
            run = json.loads((case / 'ra-cgb/p/measurements.jsonl').read_text().splitlines()[0])
            for i, (t, p) in enumerate(zip(plan['tasks'], planned)):
                cpu = [j['cpu_after_ns'] - j['cpu_before_ns'] for j in run['jobs'] if j['task'] == i and j.get('kind') == 'job']
                rows.append(dict(experiment=experiment, kernel=p['kernel'], load=r['load'], set=r['label'].split('/')[-1],
                                 task_id=p['task_id'], chaser_met=int(r['met']['ra-cgb']),
                                 worst_over_planned=f"{max(cpu) / (p['u'] * t['period_ticks'] * 1e6):.6f}"))
    with dest.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'wrote {dest}: {len(rows)} tasks')


if __name__ == '__main__':
    main()
