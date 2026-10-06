"""Check the fitted O2 job-time model on the policy-mix design's own task shapes before running it.

The design's budgets (0.2-43 ms) and its 768 KiB tasks with long padding tails lie
outside the earlier model checks, so this picks PER_FAMILY levels of each family
(high-CLS, low as-is, low matched, big) evenly over that family's budgets in the
design, runs each alone (P, 100 ms period, the first two jobs as warm-up) and
requires every measured job within 2% of the model and every yarda_cpp CLS equal to
the closed form. Writes <output>/model-check.json; exits 1 on failure.
Run with PYTHONPATH set to the c3 code copy.
"""

import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'high-load'))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))
sys.path.insert(0, str(HERE.parent / 'period-distribution'))

from tools.rtems_smoke import file_hash, write_json

import bi_calibrate
import bimodal
import mem_set
import mix_set
import run as design
import yarda_counts

PER_FAMILY = 12
CHUNK = 16
CHECK_PERIOD = 100


def family(task: dict, traffic: str) -> str:
    return 'low-' + traffic if task['role'] == 'low' else 'big' if task['role'] == 'big' else 'high'


def check_levels() -> list[dict]:
    """Distinct (family, shape) of the design, then PER_FAMILY spread over each family's budgets."""
    shapes = {}
    for load in mix_set.LOADS:
        for k in range(mix_set.SETS):
            traffic = mix_set.factors(k)['traffic']
            for t, b in zip(mix_set.configuration(load, 'mix', k, 'wfd')['tasks'], mix_set.budgets(load, k)):
                key = (family(t, traffic), t['hot_distinct'], t['hot_repeats'], t['sweeps'],
                       t.get('pad_rounds', 0), t.get('pad_tail', 0), t['distinct'] - t['hot_distinct'])
                shapes.setdefault(key, dict(family=key[0], hot=key[1], repeats=key[2], sweeps=key[3], pad=key[4],
                                            tail=key[5], cold=key[6], budget_ns=b, cls_planned=t['cls_planned']))
    picks = []
    for name in ('high', 'low-as-is', 'low-matched', 'big'):
        rows = sorted((s for s in shapes.values() if s['family'] == name), key=lambda s: s['budget_ns'])
        picks += [rows[round(i * (len(rows) - 1) / (PER_FAMILY - 1))] for i in range(PER_FAMILY)]
    return picks


def level_task(i: int, level: dict) -> dict:
    task = dict(task_id=f'l{i:03d}', pattern='hot-cold', distinct=level['hot'] + level['cold'],
                hot_distinct=level['hot'], hot_repeats=level['repeats'], cold_repeats=1, stride=bimodal.STRIDE,
                sweeps=level['sweeps'], core=i % mix_set.CORES, period_ticks=CHECK_PERIOD)
    for key, name in (('pad', 'pad_rounds'), ('tail', 'pad_tail')):
        if level[key]:
            task[name] = level[key]
    return task


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=design.MAX_WORKERS)
    args = parser.parse_args()
    root = args.output.resolve() / 'model-check'
    levels = check_levels()
    # Interleave families so no chunk carries more than a few 768 KiB arrays.
    order = [levels[f * PER_FAMILY + i] for i in range(PER_FAMILY) for f in range(4)]
    model, rows = mem_set.model(), []
    for start in range(0, len(order), CHUNK):
        chunk, name = order[start:start + CHUNK], f'check-c{start // CHUNK:02d}'
        tasks = [level_task(start + i, level) for i, level in enumerate(chunk)]
        cpu = bi_calibrate.isolated(root / name, tasks, args.workers)
        counts = yarda_counts.analyze(root / name / 'prepared', root / name / 'yarda')
        for level, task in zip(chunk, tasks):
            predicted = float(bimodal.job_ns(model, level['hot'], level['repeats'], level['sweeps'], level['pad'],
                                             level['tail'], level['cold']))
            rows.append(dict(level, chunk=name, task_id=task['task_id'], job_ns=cpu[task['task_id']],
                             predicted_ns=predicted, relative_error=predicted / cpu[task['task_id']] - 1,
                             cls_yarda=counts[task['task_id']]['cls']))
    mismatches = [r['task_id'] for r in rows if abs(r['cls_yarda'] - r['cls_planned']) > 1e-9]
    worst = max(abs(r['relative_error']) for r in rows)
    write_json(args.output.resolve() / 'model-check.json', dict(
        model_path=str(mem_set.MODEL_PATH.relative_to(HERE.parents[3])), model_hash=file_hash(mem_set.MODEL_PATH),
        levels=len(rows), max_relative_error=worst, cls_mismatches=mismatches, rows=rows))
    design.announce(f'model check over {len(rows)} levels: max error {worst:.2%}, CLS mismatches {mismatches}')
    if worst > bi_calibrate.MAX_VALIDATION_ERROR or mismatches:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
