"""Check the fitted O2 job-time model over the memory design's job budgets before running it.

Picks CHECK_LEVELS budgets evenly over the design's budget range, cycling the
high-CLS, low as-is and low matched centers, runs each level alone (P) and
requires every measured job within 2% of the model and every yarda_cpp CLS
equal to bimodal.cls_model. Writes <output>/model-check.json.
Run with PYTHONPATH set to the c3 code copy.
"""

import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))
sys.path.insert(0, str(HERE.parent / 'period-distribution'))

from tools.rtems_smoke import file_hash, write_json

import bi_calibrate
import bimodal
import mem_set
import run as design

CHECK_LEVELS = 45
FAMILIES = (('high', 'as-is', bimodal.HIGH_CENTER), ('low', 'as-is', bimodal.LOW_CENTER),
            ('low', 'matched', bimodal.LOW_CENTER))


def check_levels() -> list[dict]:
    budgets = sorted({b for load in mem_set.LOADS for k in range(mem_set.SETS) for b in mem_set.budgets(load, k)})
    picks = [budgets[round(i * (len(budgets) - 1) / (CHECK_LEVELS - 1))] for i in range(CHECK_LEVELS)]
    levels = []
    for i, budget in enumerate(picks):
        mode, traffic, center = FAMILIES[i % len(FAMILIES)]
        lv = bimodal.level(mem_set.tables(budget), mode, traffic, center)
        levels.append(dict(hot=lv['hot'], repeats=lv['repeats'], sweeps=lv['sweeps'], pad=lv['pad'], tail=lv['tail'],
                           family='high' if mode == 'high' else traffic, budget_ns=budget))
    return levels


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=design.MAX_WORKERS)
    args = parser.parse_args()
    root = args.output.resolve() / 'model-check'
    levels = check_levels()
    rows = []
    for start in range(0, len(levels), bi_calibrate.CHUNK):
        chunk, name = levels[start:start + bi_calibrate.CHUNK], f'check-c{start // bi_calibrate.CHUNK:02d}'
        tasks = [bi_calibrate.level_task(start + i, level) for i, level in enumerate(chunk)]
        cpu = bi_calibrate.isolated(root / name, tasks, args.workers)
        rows += [dict(level, chunk=name, task_id=t['task_id'], job_ns=cpu[t['task_id']]) for level, t in zip(chunk, tasks)]
    mismatches = bi_calibrate.cls_mismatches(root, rows)
    bi_calibrate.predict(mem_set.model(), rows)
    worst = max(abs(r['relative_error']) for r in rows)
    write_json(args.output.resolve() / 'model-check.json', dict(
        model_path=str(mem_set.MODEL_PATH.relative_to(HERE.parents[3])), model_hash=file_hash(mem_set.MODEL_PATH),
        levels=len(rows), max_relative_error=worst, cls_mismatches=mismatches, rows=rows))
    design.announce(f'model check over {len(rows)} levels: max error {worst:.2%}, CLS mismatches {mismatches}')
    if worst > bi_calibrate.MAX_VALIDATION_ERROR or mismatches:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
