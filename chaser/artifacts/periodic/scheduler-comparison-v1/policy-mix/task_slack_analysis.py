"""Per-task cache role and deadline slack of the late tasks (experiment 37, reanalysis, exploratory).

For every Partitioned run (wfd, cgb, ra-cgb; experiments 17 and 18 wfd, cg, ra-cg) of the development
experiments, reads the job record (first line of measurements.jsonl, so pruned builds need no restore)
and, per task: its class (memory task = role low or big; other task on a core with or without a memory
task), its planned first-deadline slack under EDF at the synchronous release (period minus the same-core
planned work due by then, over the period) and whether any job of the whole run, warm-up included, ended
after its period or never ended. Startup and other failures are left out.
Reading fixed beforehand (EXPERIMENTS.md 37): with at least 20 memory tasks below slack 0.3, and in every
such slack bin a higher late rate for memory tasks than for the other tasks on memory-task cores.
Usage: python3 task_slack_analysis.py --cache <.cache dir> --dest <dir> [--jobs N]
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

import numpy as np

import rf_devcheck as rd

MEMORY_ROLES = ('low', 'big')
CLASSES = ('memory', 'other-with-memory', 'other-without-memory')
BINS = ((0.1, '< 0.1'), (0.2, '0.1-0.2'), (0.3, '0.2-0.3'), (0.5, '0.3-0.5'), (float('inf'), '>= 0.5'))
TIGHT = ('< 0.1', '0.1-0.2', '0.2-0.3')
MIN_TIGHT_MEMORY = 20
# (experiment, output, P builds)
RUNS = (('17 and 18 mixed tasks', 'policy-mix-v1', ('wfd',)), ('17 and 18 mixed tasks', 'policy-mix-cls-v1', ('cg', 'ra-cg')),
        ('20 768 KiB', 'task-count-v1', ('wfd', 'cgb', 'ra-cgb')), ('21 32 KiB', 'small-memory-v1', ('wfd', 'cgb', 'ra-cgb')),
        ('23 continuous CLS', 'cls-spread-v1', ('wfd', 'cgb', 'ra-cgb')),
        ('24 32 KiB under load', 'small-memory-load-v1', ('wfd', 'cgb', 'ra-cgb')),
        ('25 conflict-miss', 'conflict-cls-v2', ('wfd', 'cgb', 'ra-cgb')),
        ('27 32 KiB', 'deadline-small-v1', ('wfd', 'cgb', 'ra-cgb')), ('27 768 KiB', 'deadline-big-v1', ('wfd', 'cgb', 'ra-cgb')))


def first_deadline_slack(tasks, i) -> float:
    t = tasks[i]
    due = sum((t['period_ticks'] // o['period_ticks']) * o['u_planned'] * o['period_ticks'] for o in tasks if o['core'] == t['core'])
    return (t['period_ticks'] - due) / t['period_ticks']


def classes(tasks) -> list[str]:
    cores = {t['core'] for t in tasks if t['role'] in MEMORY_ROLES}
    return ['memory' if t['role'] in MEMORY_ROLES else 'other-with-memory' if t['core'] in cores else 'other-without-memory'
            for t in tasks]


def late_jobs(tasks, jobs) -> list[int]:
    late = [0] * len(tasks)
    for j in jobs:
        if j.get('completion_ns') is None or j['completion_ns'] - j['release_ns'] > tasks[j['task']]['period_ticks'] * 1e6:
            late[j['task']] += 1
    return late


def slack_bin(r) -> str:
    return next(label for edge, label in BINS if r < edge)


def reading(table) -> dict:
    """table[bin][class] = dict(tasks, late); the pre-fixed reading over the tight bins."""
    rate = lambda c: c['late'] / c['tasks']
    compared = [b for b in TIGHT if b in table and table[b]['memory']['tasks'] and table[b]['other-with-memory']['tasks']]
    higher = bool(compared) and all(rate(table[b]['memory']) > rate(table[b]['other-with-memory']) for b in compared)
    tight = sum(table[b]['memory']['tasks'] for b in TIGHT if b in table)
    return dict(tight_memory_tasks=tight, higher_in_every_bin=higher, holds=tight >= MIN_TIGHT_MEMORY and higher)


def run_rows(job):
    experiment, case, build = job
    path = case / build / 'p' / 'measurements.jsonl'
    if not path.exists():
        return []
    with path.open() as stream:
        record = json.loads(stream.readline())
    if record['execution_status'] != 'ok' and 'deadline_miss' not in record.get('errors', []):
        return []
    tasks = json.loads((case / build / 'configuration.json').read_text())['tasks']
    late = late_jobs(tasks, record['jobs'])
    return [dict(experiment=experiment, case=str(case), build=build, met=record['execution_status'] == 'ok', task=i,
                 cls=classes(tasks)[i], slack=first_deadline_slack(tasks, i), u=t['u_planned'], period=t['period_ticks'],
                 late_jobs=late[i]) for i, t in enumerate(tasks)]


def summarize(rows) -> dict:
    out = dict(tasks=len(rows), runs=len({(r['case'], r['build']) for r in rows}),
               missed_runs=len({(r['case'], r['build']) for r in rows if not r['met']}), by_class={}, by_bin={}, tight_memory={})
    for c in CLASSES:
        sub = [r for r in rows if r['cls'] == c]
        out['by_class'][c] = dict(tasks=len(sub), late_tasks=sum(r['late_jobs'] > 0 for r in sub), late_jobs=sum(r['late_jobs'] for r in sub))
    for _, b in BINS:
        out['by_bin'][b] = {c: dict(tasks=sum(1 for r in rows if r['cls'] == c and slack_bin(r['slack']) == b),
                                    late=sum(1 for r in rows if r['cls'] == c and slack_bin(r['slack']) == b and r['late_jobs'] > 0))
                            for c in CLASSES}
    for e in dict.fromkeys(r['experiment'] for r in rows):
        out['tight_memory'][e] = sum(1 for r in rows if r['experiment'] == e and r['cls'] == 'memory' and r['slack'] < 0.2)
    missed = [r for r in rows if not r['met']]
    out['slack_auc_in_missed_runs'] = {c: rd.auc([int(r['late_jobs'] > 0) for r in missed if c in (None, r['cls'])],
                                                 [-r['slack'] for r in missed if c in (None, r['cls'])])
                                       for c in (None,) + CLASSES}
    out['slack_auc_in_missed_runs']['all'] = out['slack_auc_in_missed_runs'].pop(None)
    out['reading'] = reading(out['by_bin'])
    return out


def markdown(result) -> str:
    s = result['all']
    lines = ['# Late tasks: cache role and planned first-deadline slack (experiment 37, reanalysis, exploratory)', '',
             f"{s['runs']} Partitioned runs ({s['missed_runs']} missed a deadline), {s['tasks']} task rows", '',
             '## Who was late (whole run, warm-up included)', '',
             '| experiment | ' + ' | '.join(f'{c}: late tasks / tasks (late jobs)' for c in CLASSES) + ' |', '|---|---|---|---|']
    for name, v in [('all', s)] + list(result['by_experiment'].items()):
        lines.append(f'| {name} | ' + ' | '.join(f"{v['by_class'][c]['late_tasks']} / {v['by_class'][c]['tasks']} ({v['by_class'][c]['late_jobs']})"
                                               for c in CLASSES) + ' |')
    lines += ['', '## Late rate by planned slack (tasks late at least once / tasks)', '',
              '| slack | ' + ' | '.join(CLASSES) + ' |', '|---|---|---|---|']
    for _, b in BINS:
        cells = [f"{s['by_bin'][b][c]['late']} / {s['by_bin'][b][c]['tasks']}"
                 + (f" ({s['by_bin'][b][c]['late'] / s['by_bin'][b][c]['tasks']:.1%})" if s['by_bin'][b][c]['tasks'] else '')
                 for c in CLASSES]
        lines.append(f'| {b} | ' + ' | '.join(cells) + ' |')
    lines += ['', '## Memory tasks with slack below 0.2', '']
    lines += [f'- {e}: {n}' for e, n in s['tight_memory'].items()]
    lines += ['', '## Slack AUC for which task is late, within missed runs', '']
    lines += [f"- {c}: {'-' if v is None else f'{v:.3f}'}" for c, v in s['slack_auc_in_missed_runs'].items()]
    r = s['reading']
    lines += ['', f"## Reading: {'holds' if r['holds'] else 'does not hold'}", '',
              f"- memory tasks below slack 0.3: {r['tight_memory_tasks']} (needs {MIN_TIGHT_MEMORY})",
              f"- memory tasks late more often than the others on memory-task cores in every tight bin: {r['higher_in_every_bin']}"]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=32)
    args = parser.parse_args()
    cache = args.cache.resolve()
    work = [(e, case, b) for e, out, builds in RUNS for case in sorted((cache / out).glob('*/u0*/s*')) for b in builds]
    with ProcessPoolExecutor(args.jobs) as pool:
        rows = [row for chunk in pool.map(run_rows, work, chunksize=8) for row in chunk]
    result = dict(all=summarize(rows), by_experiment={e: summarize([r for r in rows if r['experiment'] == e])
                                                      for e in dict.fromkeys(r['experiment'] for r in rows)})
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'task-slack.json').write_text(json.dumps(result, indent=1) + '\n')
    with open(args.dest / 'task-rows.jsonl', 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    (args.dest / 'task-slack.md').write_text(markdown(result))
    print('wrote', args.dest / 'task-slack.md')


if __name__ == '__main__':
    main()
