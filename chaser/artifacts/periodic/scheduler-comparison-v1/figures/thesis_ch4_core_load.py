"""Per-run core loads behind thesis figure 4.3, extracted once from the raw experiment 24 runs.

For the 32 KiB low-CLS tasks at 50 % of U (cv00-low50, cv20-low50), loads 0.5 and 0.55, and the two CLS grouping
placements, writes one row per started run: whether it met every deadline, and the planned and effective U averaged
over the cores holding the grouped low-CLS tasks and over the other cores. Planned U sums the tasks' isolated U;
effective U is the measured jobs' CPU time over the measured window (cv_miss_analysis.effective_load). A core with no
measured job counts as 0. A task stops at its first deadline miss (rtems/periodic/init.c), so only runs that met
every deadline show the load with every task running; figure 4.3 uses those at load 0.5 (at 0.55 only 2-7 of
18 runs per bar met every deadline).
The raw runs (.cache/small-memory-load-v1) are on the cleanup list; the CSV keeps the values.
Usage: python3 thesis_ch4_core_load.py <raw run dir> <output csv>
"""
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'policy-mix'))

from cv_miss_analysis import effective_load, group_cores

CELLS = ('cv00-low50', 'cv20-low50')
LOADS = (50, 55)
BUILDS = ('cgb', 'ra-cgb')


def row(case: Path, build: str):
    config = json.loads((case / build / 'configuration.json').read_text())
    path = case / build / 'p' / 'measurements.jsonl'
    if not path.exists():
        return None
    with path.open() as stream:
        record = json.loads(stream.readline())
    if record['execution_status'] != 'ok' and 'deadline_miss' not in record.get('errors', []):
        return None  # failed to start
    tasks = config['tasks']
    groups = group_cores(tasks)
    cores = range(len(config['high_load']['core_u']))
    load = effective_load(tasks, record['jobs'], config['warmup_ticks'], config['horizon_ticks'])
    planned = {c: sum(t['u_planned'] for t in tasks if t['core'] == c) for c in cores}
    mean = lambda values: sum(values) / len(values)
    return dict(cell=case.parent.parent.name, load=f'{int(case.parent.name[1:]) / 100:g}', set=case.name, placement=build,
                met=int(record['execution_status'] == 'ok'), group_cores=len(groups),
                planned_group=mean([planned[c] for c in cores if c in groups]),
                planned_other=mean([planned[c] for c in cores if c not in groups]),
                effective_group=mean([load.get(c, 0.0) for c in cores if c in groups]),
                effective_other=mean([load.get(c, 0.0) for c in cores if c not in groups]))


def main():
    raw, dest = Path(sys.argv[1]), Path(sys.argv[2])
    rows = [r for cell in CELLS for load in LOADS for case in sorted((raw / cell / f'u{load:03d}').glob('s*'))
            for build in BUILDS if (r := row(case, build))]
    with dest.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: f'{v:.6f}' if isinstance(v, float) else v for k, v in r.items()} for r in rows)
    print('wrote', dest, len(rows), 'runs')


if __name__ == '__main__':
    main()
