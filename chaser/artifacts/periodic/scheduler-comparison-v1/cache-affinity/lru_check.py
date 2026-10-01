"""Test the LRU explanation of the cache-affinity result, and cold-burst overlap.

For every measured job, the task-level reuse distance on its start core is the
byte footprint of the other tasks that started on that core after this task's
latest earlier job that ended there ('cold' if it never ran there before).
Every job reads its whole array, so a distinct task counts once. Per-load cost
is (job CPU - empty-job CPU of the architecture) / (lines x sweeps).

Prediction: Partitioned repeats one order per core, so at a per-core working
set >= 100% of L1 its distance always equals the other three tasks (>= L1) and
every job starts cold; Global/Clustered mix in shorter distances. If distance
explains cost, a distance bin costs about the same under every architecture.

Alternative (cold-burst overlap): a job's first sweep, taken as the first 1/S of
its execution, is the one that misses L1. Overlap is the mean number of other
cores inside their own first sweep, sampled at five points of this job's first
sweep. Per cohort, start spread is the gap between the first job starts of the
four cores. If overlap explains cost, an overlap bin costs about the same under
every architecture.
Usage: python3 lru_check.py <run dir> [<run dir> ...]  -> <run dir>/lru-check.json
"""

import json
from pathlib import Path
import sys

import numpy as np

L1_BYTES, LINE = 16384, 32
ARCHS = ('g', 'c', 'c2', 'p')
BINS = (('same core, no other task', 0, 0), ('< 8 KiB', 1, 8192), ('8-16 KiB', 8193, 16384),
        ('> 16 KiB', 16385, float('inf')), ('never on this core', None, None))
OVERLAP_BINS = (('0-0.5', 0, 0.5), ('0.5-1.5', 0.5, 1.5), ('1.5-2.5', 1.5, 2.5), ('2.5-3', 2.5, 3.01))


def distance_bin(distance):
    if distance is None:
        return BINS[-1][0]
    return next(name for name, low, high in BINS[:-1] if low <= distance <= high)


def first_sweeps(jobs, config):
    """(start, end of first sweep, core) per job."""
    tasks = config['tasks']
    return [(j['start_ns'], j['start_ns'] + (j['completion_ns'] - j['start_ns']) / tasks[j['task']]['sweeps'],
             j['start_core']) for j in jobs]


def overlap(window, windows):
    start, end, core = window
    return float(np.mean([sum(1 for s, e, c in windows if c != core and s <= t <= e)
                          for t in np.linspace(start, end, 5)]))


def start_spreads(jobs):
    """Per cohort, max - min of each core's first job start (ns)."""
    cohorts = {}
    for job in jobs:
        first = cohorts.setdefault(job['release_ns'], {})
        first[job['start_core']] = min(first.get(job['start_core'], job['start_ns']), job['start_ns'])
    return [max(f.values()) - min(f.values()) for f in cohorts.values() if len(f) == 4]


def jobs_with_distance(record, config, empty_ns):
    tasks = config['tasks']
    size = [t['distinct'] * LINE for t in tasks]
    jobs = sorted(record['jobs'], key=lambda j: j['start_ns'])
    measured = [j for j in jobs if j['job'] >= config['warmup_ticks'] // tasks[j['task']]['period_ticks']]
    windows = first_sweeps(measured, config)
    out = []
    for i, job in enumerate(jobs):
        t, core = job['task'], job['start_core']
        previous = [j for j in jobs[:i] if j['task'] == t and j['end_core'] == core
                    and j['completion_ns'] <= job['start_ns']]
        if previous:
            since = previous[-1]['completion_ns']
            others = {j['task'] for j in jobs[:i]
                      if j['start_core'] == core and j['task'] != t and j['start_ns'] >= since}
            distance = sum(size[u] for u in others)
        else:
            distance = None
        if job['job'] < config['warmup_ticks'] // tasks[t]['period_ticks']:
            continue
        loads = tasks[t]['distinct'] * tasks[t]['sweeps']
        out.append(dict(bin=distance_bin(distance), distance=distance, migrated=job['start_core'] != job['end_core'],
                        overlap=overlap(windows[measured.index(job)], windows),
                        per_load_ns=(job['cpu_after_ns'] - job['cpu_before_ns'] - empty_ns) / loads))
    return out, start_spreads(measured)


def analyze(run: Path) -> dict:
    empty = json.loads((run / 'empty.json').read_text())
    rows = [json.loads(line) for line in (run / 'results.jsonl').read_text().splitlines()]
    report = {}
    for row in rows:
        target = run / f"ws{row['mean']:03d}/s{row['cv']:02d}/set{row['set_id']:02d}"
        config = json.loads((target / 'configuration.json').read_text())
        period = config['tasks'][0]['period_ticks']
        for arch in ARCHS:
            if row[arch]['status'] != 'ok':
                continue
            record = json.loads((target / arch / 'measurements.jsonl').read_text().splitlines()[0])
            empty_ns = empty[f'p{period:02d}'][arch]['tet_ns'] / 160
            cell = report.setdefault(f"ws{row['mean']:03d}/s{row['cv']:02d}", {}).setdefault(arch, ([], []))
            jobs, spreads = jobs_with_distance(record, config, empty_ns)
            cell[0].extend(jobs)
            cell[1].extend(spreads)
    summary = {}
    for cell, archs in sorted(report.items()):
        for arch, (jobs, spreads) in archs.items():
            cost = np.array([j['per_load_ns'] for j in jobs])
            entry = dict(jobs=len(jobs), per_load_ns_mean=float(cost.mean()),
                         migrated_share=float(np.mean([j['migrated'] for j in jobs])),
                         start_spread_us_median=float(np.median(spreads)) / 1e3,
                         overlap_mean=float(np.mean([j['overlap'] for j in jobs])), bins={}, overlap_bins={})
            for name, *_ in BINS:
                picked = [j['per_load_ns'] for j in jobs if j['bin'] == name]
                if picked:
                    entry['bins'][name] = dict(share=len(picked) / len(jobs),
                                               per_load_ns_mean=float(np.mean(picked)))
            for name, low, high in OVERLAP_BINS:
                picked = [j['per_load_ns'] for j in jobs if low <= j['overlap'] < high]
                if picked:
                    entry['overlap_bins'][name] = dict(share=len(picked) / len(jobs),
                                                       per_load_ns_mean=float(np.mean(picked)))
            summary.setdefault(cell, {})[arch] = entry
    (run / 'lru-check.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    for path in sys.argv[1:]:
        analyze(Path(path).resolve())
        print('wrote', Path(path) / 'lru-check.json')
