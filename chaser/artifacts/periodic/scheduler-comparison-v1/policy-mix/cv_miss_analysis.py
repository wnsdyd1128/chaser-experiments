"""Exploratory: why the CLS grouping's deadline gain fades when periods spread (period CV 0.2).

Experiments 24 and 27 (32 KiB low-CLS tasks at 50 % of U) found the CLS placements meeting more
deadlines than release-aware at period CV 0 but not at CV 0.2. For every case of a deadline run near
the boundary (--loads) and every Partitioned build (wfd, cgb, ra, ra-cgb), this reads the run's
decoded record (first line of measurements.jsonl) and its configuration, and reports per period cell
and placement:
  missed jobs      late jobs (response > period or never completed) and lost releases, split by the
                   missing task's role (memory 'low' / 'high') and by whether its core holds memory tasks
  late-job causes  median start delay (start - release) and execution span (completion - start) of
                   the late jobs, each over the period
  concurrency      share of the measured window with memory-task jobs active on two or more cores
                   (a job is active from start to completion, preemptions included)
  release cost     placement_lib.cohort_cost of the planned mapping (the release-aware objective)
  inflation        worst memory-task job CPU / planned budget (runs that met every deadline)
  core loads       effective U (measured job CPU over the measured window) and planned U, averaged over the
                   cores holding memory tasks and over the others; planned U of other tasks on memory cores
Exploratory: these runs' results were read before. Writes <dest>/cv-miss.json and .md.
Usage: python3 cv_miss_analysis.py --output <run> [--loads 0.5,0.525,0.55] --dest <dir>
"""

import argparse
import json
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from placement_lib import Item, cohort_cost

BUILDS = ('wfd', 'cgb', 'ra', 'ra-cgb')


def group_cores(tasks) -> set:
    return {t['core'] for t in tasks if t['role'] in ('low', 'big')}


def concurrency(tasks, jobs, start, end) -> dict:
    """Over [start, end): time-average number of cores with an active memory-task job, and the shares
    of time with at least two and at least three such cores."""
    events = []
    for j in jobs:
        t = tasks[j['task']]
        if t['role'] not in ('low', 'big') or j.get('completion_ns') is None:
            continue
        a, b = max(j['start_ns'], start), min(j['completion_ns'], end)
        if a < b:
            events += [(a, 1, t['core']), (b, -1, t['core'])]
    active, busy, last, weighted, two, three = {}, 0, start, 0.0, 0.0, 0.0
    for time, step, core in sorted(events):
        weighted += busy * (time - last)
        two += (time - last) if busy >= 2 else 0.0
        three += (time - last) if busy >= 3 else 0.0
        last = time
        active[core] = active.get(core, 0) + step
        busy = sum(1 for v in active.values() if v > 0)
    span = end - start
    return dict(mean_cores=weighted / span, at_least_two=two / span, at_least_three=three / span)


def effective_load(tasks, jobs, warmup_ticks, horizon_ticks) -> dict:
    """Per core: measured jobs' CPU time over the measured window (the core's effective utilization)."""
    load = {}
    for j in jobs:
        t = tasks[j['task']]
        if j['job'] >= warmup_ticks // t['period_ticks']:
            load[t['core']] = load.get(t['core'], 0.0) + j['cpu_after_ns'] - j['cpu_before_ns']
    return {core: v / ((horizon_ticks - warmup_ticks) * 1e6) for core, v in load.items()}


def missed_by_task(tasks, jobs, warmup_ticks, horizon_ticks):
    late = {i: 0 for i in range(len(tasks))}
    seen = {i: 0 for i in range(len(tasks))}
    for j in jobs:
        t = tasks[j['task']]
        if j['job'] < warmup_ticks // t['period_ticks']:
            continue
        seen[j['task']] += 1
        if j.get('completion_ns') is None or j['completion_ns'] - j['release_ns'] > t['period_ticks'] * 1e6:
            late[j['task']] += 1
    lost = {i: max(0, (horizon_ticks - warmup_ticks) // t['period_ticks'] - seen[i]) for i, t in enumerate(tasks)}
    return late, lost


def run_entry(case: Path, build: str):
    config = json.loads((case / build / 'configuration.json').read_text())
    path = case / build / 'p' / 'measurements.jsonl'
    if not path.exists():
        return None
    with path.open() as stream:
        record = json.loads(stream.readline())
    if record['execution_status'] != 'ok' and 'deadline_miss' not in record.get('errors', []):
        return None  # startup or other failure: missing
    tasks, warm, horizon = config['tasks'], config['warmup_ticks'], config['horizon_ticks']
    late, lost = missed_by_task(tasks, record['jobs'], warm, horizon)
    groups = group_cores(tasks)
    split = {}
    for i, t in enumerate(tasks):
        key = f"{'memory' if t['role'] in ('low', 'big') else 'other'}-{'group' if t['core'] in groups else 'nongroup'}"
        split[key] = split.get(key, 0) + late[i] + lost[i]
    # Every late job, warm-up included: the misses of these runs start in the first hyperperiod.
    late_jobs = [j for j in record['jobs'] if j.get('completion_ns') is not None
                 and j['completion_ns'] - j['release_ns'] > tasks[j['task']]['period_ticks'] * 1e6]
    causes = [((j['start_ns'] - j['release_ns']) / (tasks[j['task']]['period_ticks'] * 1e6),
               (j['completion_ns'] - j['start_ns']) / (tasks[j['task']]['period_ticks'] * 1e6)) for j in late_jobs]
    late_warm = sum(j['job'] < warm // tasks[j['task']]['period_ticks'] for j in late_jobs)
    load = effective_load(tasks, record['jobs'], warm, horizon)
    items = [Item(u=t['u_planned'], period=t['period_ticks'], traffic=t['traffic_planned'], cls=t['cls_planned'])
             for t in tasks]
    inflation = None
    if record['execution_status'] == 'ok':
        worst = [max(((j['cpu_after_ns'] - j['cpu_before_ns']) / (tasks[i]['u_planned'] * tasks[i]['period_ticks'] * 1e6)
                      for j in record['jobs'] if j['task'] == i and j['job'] >= warm // tasks[i]['period_ticks']), default=0)
                 for i, t in enumerate(tasks) if t['role'] in ('low', 'big')]
        inflation = max(worst) if worst else None
    planned = {c: sum(t['u_planned'] for t in tasks if t['core'] == c) for c in range(len(config['high_load']['core_u']))}
    planned_group = [v for c, v in planned.items() if c in groups]
    planned_other = [v for c, v in planned.items() if c not in groups]
    group_load = [v for c, v in load.items() if c in groups]
    other_load = [v for c, v in load.items() if c not in groups]
    return dict(met=record['execution_status'] == 'ok', missed=sum(late.values()) + sum(lost.values()), split=split,
                causes=causes, late_warm=late_warm, concurrency=concurrency(tasks, record['jobs'], warm * 1e6, horizon * 1e6),
                max_load=max(load.values(), default=None), group_load=sum(group_load) / len(group_load) if group_load else None,
                other_load=sum(other_load) / len(other_load) if other_load else None,
                planned_group=sum(planned_group) / len(planned_group) if planned_group else None,
                planned_other=sum(planned_other) / len(planned_other) if planned_other else None,
                other_u_on_group=sum(t['u_planned'] for t in tasks if t['core'] in groups and t['role'] not in ('low', 'big')),
                release_cost=cohort_cost([t['core'] for t in tasks], items), inflation=inflation,
                group_cores=len(groups))


def summarize(entries: dict) -> dict:
    out = {}
    for (cell, build), runs in sorted(entries.items()):
        runs = [r for r in runs if r]
        split = {}
        for r in runs:
            for k, v in r['split'].items():
                split[k] = split.get(k, 0) + v
        causes = [c for r in runs for c in r['causes']]
        infl = [r['inflation'] for r in runs if r['inflation']]
        med = lambda key: median(r[key] for r in runs if r[key] is not None) if any(r[key] is not None for r in runs) else None
        out.setdefault(cell, {})[build] = dict(
            runs=len(runs), met=sum(r['met'] for r in runs), missed=sum(r['missed'] for r in runs), split=split,
            late_jobs=len(causes), late_in_warmup=sum(r['late_warm'] for r in runs),
            start_delay=median(c[0] for c in causes) if causes else None,
            execution_span=median(c[1] for c in causes) if causes else None,
            memory_cores=median(r['concurrency']['mean_cores'] for r in runs) if runs else None,
            memory_three=median(r['concurrency']['at_least_three'] for r in runs) if runs else None,
            max_load=med('max_load'), group_load=med('group_load'), other_load=med('other_load'),
            planned_group=med('planned_group'), planned_other=med('planned_other'), other_u_on_group=med('other_u_on_group'),
            release_cost=median(r['release_cost'] for r in runs) if runs else None,
            inflation=median(infl) if infl else None, group_cores=median(r['group_cores'] for r in runs) if runs else None)
    return out


def release_cost_ratios(entries: dict, builds=BUILDS) -> dict:
    """Per cell: median over cases of each build's release cost / ra's on the same case (empty without ra)."""
    out = {}
    for cell in sorted({cell for cell, _ in entries}):
        ra = entries.get((cell, 'ra'))
        out[cell] = {b: median(x['release_cost'] / y['release_cost'] for x, y in zip(entries[(cell, b)], ra) if x and y)
                     for b in builds} if ra else {}
    return out


def markdown(result: dict) -> str:
    lines = [f"# Period-spread miss analysis (exploratory): {result['run']}, loads {result['loads']}", '',
             '| cell | placement | met / runs | missed jobs | memory-group / memory-nongroup / other-group / other-nongroup '
             '| late jobs (in warm-up) | late: start delay / execution (x period) | memory cores active (mean, share >= 3) '
             '| effective core U: max / group / other | release cost / ra | worst inflation | group cores |',
             '|---|---|---|---:|---|---|---|---|---|---:|---:|---:|']
    for cell, by in result['summary'].items():
        for b, e in by.items():
            s = e['split']
            f = lambda v, spec: '-' if v is None else format(v, spec)
            lines.append(f"| {cell} | {b} | {e['met']} / {e['runs']} | {e['missed']} | {s.get('memory-group', 0)} / "
                         f"{s.get('memory-nongroup', 0)} / {s.get('other-group', 0)} / {s.get('other-nongroup', 0)} | "
                         f"{e['late_jobs']} ({e['late_in_warmup']}) | {f(e['start_delay'], '.2f')} / {f(e['execution_span'], '.2f')} | "
                         f"{f(e['memory_cores'], '.2f')}, {f(e['memory_three'], '.2f')} | "
                         f"{f(e['max_load'], '.2f')} / {f(e['group_load'], '.2f')} / {f(e['other_load'], '.2f')} | "
                         f"{f(result['release_cost_ratio'][cell].get(b), '.3f')} | {f(e['inflation'], '.2f')} | {f(e['group_cores'], '.0f')} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--loads', default='0.5,0.525,0.55')
    parser.add_argument('--builds', default=','.join(BUILDS))
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    loads = [round(float(x) * 100) for x in args.loads.split(',')]
    output = args.output.resolve()
    entries = {}
    for case in sorted(p for p in output.glob('*/u0*/s*') if p.is_dir() and int(p.parent.name[1:]) in loads):
        cell = case.parent.parent.name
        for build in args.builds.split(','):
            entries.setdefault((cell, build), []).append(run_entry(case, build))
    result = dict(run=output.name, loads=args.loads, summary=summarize(entries),
                  release_cost_ratio=release_cost_ratios(entries, args.builds.split(',')))
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / f'cv-miss-{output.name}.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / f'cv-miss-{output.name}.md').write_text(markdown(result))
    print(markdown(result))


if __name__ == '__main__':
    main()
