"""Real-time metrics per Partitioned run of an hl_run output: deadlines, worst response, worst execution.

For every case and P build of <output> (hl_run layout <cell>/u<load>/s<set>/<build>/p) this
reads the run's decoded record (the first line of measurements.jsonl, which carries the jobs, so
builds pruned by prepared_builds.py need no restore) and writes <output>/rt-metrics.json:
  state                 hl_run's run state (ok, deadline, startup, other)
  max_response_ratio    largest measured (completion - release) / period
  worst_inflation       largest measured job CPU / planned job budget (U x period) over all tasks
  worst_memory_inflation  the same over the low-CLS and 768 KiB tasks (role low or big), or null
  expected_jobs         jobs released in the measured window, sum over tasks of (horizon - warm-up) / period
  late_jobs             measured jobs whose response exceeded the period (or that never completed)
  lost_jobs             expected jobs missing from the record: a late job postpones the task's next
                        release (RTEMS rate monotonic), so some releases never happen before the horizon
  missed_jobs           late_jobs + lost_jobs, the deadline violations of the run
  late_jobs_all         late jobs of the whole run, warm-up included (2026-10-06: the misses of the
                        deadline runs start at the synchronous release of the first hyperperiod, so
                        missed_jobs is mostly releases postponed after them; see the measurement contract)
  late_jobs_warmup      the late jobs among them released in the warm-up
  first_late_ms         release time (ms) of the earliest late job, or null
Inflations come from runs that met every deadline; a missed deadline leaves them null.
Usage: python3 rt_metrics.py --output <run output dir> --builds wfd,cgb,ra,ra-cgb [--jobs N]
Run with PYTHONPATH set to the c3 code copy.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'cls-bimodal'))

import bi_run


def late_summary(tasks, jobs, warmup_ticks) -> dict:
    late = [j for j in jobs if j.get('completion_ns') is None
            or j['completion_ns'] - j['release_ns'] > tasks[j['task']]['period_ticks'] * 1e6]
    return dict(late_jobs_all=len(late),
                late_jobs_warmup=sum(j['job'] < warmup_ticks // tasks[j['task']]['period_ticks'] for j in late),
                first_late_ms=min(j['release_ns'] for j in late) / 1e6 if late else None)


def metrics(job):
    case, build = job
    config = json.loads((case / build / 'configuration.json').read_text())
    run = case / build / 'p'
    if not (run / 'measurements.jsonl').exists():
        return None
    with (run / 'measurements.jsonl').open() as stream:
        result = json.loads(stream.readline())
    tasks, warm, horizon = config['tasks'], config['warmup_ticks'], config['horizon_ticks']
    measured = [j for j in result['jobs'] if j['job'] >= warm // tasks[j['task']]['period_ticks']]
    expected = sum((horizon - warm) // t['period_ticks'] for t in tasks)
    late = sum(j.get('completion_ns') is None
               or j['completion_ns'] - j['release_ns'] > tasks[j['task']]['period_ticks'] * 1e6 for j in measured)
    entry = dict(state=bi_run.run_state(result), max_response_ratio=bi_run.max_response_ratio(result, config),
                 worst_inflation=None, worst_memory_inflation=None, expected_jobs=expected, late_jobs=late,
                 lost_jobs=max(0, expected - len(measured)), missed_jobs=late + max(0, expected - len(measured)),
                 **late_summary(tasks, result['jobs'], warm))
    if entry['state'] != 'ok':
        return entry
    worst = {}
    for j in measured:
        t = tasks[j['task']]
        ratio = (j['cpu_after_ns'] - j['cpu_before_ns']) / (t['u_planned'] * t['period_ticks'] * 1e6)
        worst[j['task']] = max(worst.get(j['task'], 0.0), ratio)
    memory = [v for i, v in worst.items() if tasks[i].get('role') in ('low', 'big')]
    entry.update(worst_inflation=max(worst.values()), worst_memory_inflation=max(memory) if memory else None)
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--builds', required=True)
    parser.add_argument('--jobs', type=int, default=32)
    args = parser.parse_args()
    output, builds = args.output.resolve(), args.builds.split(',')
    cases = sorted(p for p in output.glob('*/u0*/s*') if p.is_dir())
    jobs = [(case, build) for case in cases for build in builds]
    with ProcessPoolExecutor(args.jobs) as pool:
        values = list(pool.map(metrics, jobs, chunksize=4))
    table = {}
    for (case, build), value in zip(jobs, values):
        table.setdefault(str(case.relative_to(output)), {})[build] = value
    (output / 'rt-metrics.json').write_text(json.dumps(dict(builds=builds, cases=table), indent=1) + '\n')
    print('wrote', output / 'rt-metrics.json', len(jobs), 'runs')


if __name__ == '__main__':
    main()
