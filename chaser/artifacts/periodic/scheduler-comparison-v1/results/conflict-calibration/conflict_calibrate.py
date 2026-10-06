"""Calibrate the O2 job-time model for conflict-miss shapes (conflictcls_set) before running them.

Experiment 25's isolated gate found the conflict tasks 4.2-5.3 % faster than the cls-bimodal
model predicts, by about the same time per sweep; the high-CLS tasks of the same sets matched.
This measures conflict levels alone (P, bimodal.PERIOD period), fits a correction of the
per-job, per-sweep, per-L1-hit and per-L2-hit coefficients on a grid of levels and checks it on
seeded random levels (every job within bi_calibrate.MAX_VALIDATION_ERROR).
Stages:
  measure   run the FIT grid and VALIDATION levels, write <output>/measured.json
  fit       least squares on the fit rows, check the validation rows, write
            <output>/conflict-model.json (the corrected coefficients); exits 1 above the limit
Usage: python3 conflict_calibrate.py measure|fit --output <dir> [--workers N]
Run with PYTHONPATH set to the c3 code copy.
"""

import argparse
import json
from pathlib import Path
import random
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'high-load'))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))
sys.path.insert(0, str(HERE.parent / 'period-distribution'))

from tools.rtems_smoke import file_hash, write_json

import bi_calibrate
import bimodal
from conflictcls_set import COLD_LINES, CONFLICT_STRIDE, HOT_LINES, REPEATS
import mem_set
import run as design

FIT_HOT = (1, 2, 3, 4)
FIT_COLD = (28, 38, 49, 60)
FIT_SWEEPS = (150, 600, 1500, 3500)
VALIDATION_LEVELS, VALIDATION_SEED = 24, 20262501
CHUNK = 16
# Features whose coefficients the fit corrects; with REPEATS = 2 region_loops is 3 x sweeps.
CORRECTED = ('base', 'sweeps', 'l1_hits', 'l2_hits')


def levels() -> list[dict]:
    fit = [dict(group='fit', hot=h, cold=c, sweeps=s) for h in FIT_HOT for c in FIT_COLD for s in FIT_SWEEPS]
    rng = random.Random(VALIDATION_SEED)
    validation = [dict(group='validation', hot=rng.choice(HOT_LINES), cold=rng.choice(COLD_LINES),
                       sweeps=rng.randint(100, 4000)) for _ in range(VALIDATION_LEVELS)]
    return fit + validation


def task(i: int, level: dict) -> dict:
    return dict(task_id=f'k{i:03d}', pattern='hot-cold', distinct=level['hot'] + level['cold'],
                hot_distinct=level['hot'], hot_repeats=REPEATS, cold_repeats=1, stride=CONFLICT_STRIDE,
                sweeps=level['sweeps'], core=i % 4, period_ticks=bimodal.PERIOD)


def features(rows) -> np.ndarray:
    f = bimodal.features([r['hot'] for r in rows], REPEATS, [r['sweeps'] for r in rows], 0, 0,
                         np.array([r['cold'] for r in rows]))
    return f[:, [bimodal.FEATURES.index(name) for name in CORRECTED]]


def measure(output: Path, workers: int) -> None:
    rows, all_levels = [], levels()
    for start in range(0, len(all_levels), CHUNK):
        chunk = all_levels[start:start + CHUNK]
        tasks = [task(start + i, level) for i, level in enumerate(chunk)]
        cpu = bi_calibrate.isolated(output / f'chunk-{start // CHUNK:02d}', tasks, workers)
        rows += [dict(level, task_id=t['task_id'], job_ns=cpu[t['task_id']]) for level, t in zip(chunk, tasks)]
    write_json(output / 'measured.json', dict(stride=CONFLICT_STRIDE, repeats=REPEATS, rows=rows))


def fit(output: Path) -> None:
    rows = json.loads((output / 'measured.json').read_text())['rows']
    model = mem_set.model()
    base = lambda rs: np.array([float(bimodal.job_ns(model, r['hot'], REPEATS, r['sweeps'], 0, 0, r['cold']))
                                for r in rs])
    train = [r for r in rows if r['group'] == 'fit']
    check = [r for r in rows if r['group'] == 'validation']
    delta, *_ = np.linalg.lstsq(features(train), np.array([r['job_ns'] for r in train]) - base(train), rcond=None)
    corrected = dict(model, **{name: model[name] + float(d) for name, d in zip(CORRECTED, delta)})
    predict = lambda rs: np.array([float(bimodal.job_ns(corrected, r['hot'], REPEATS, r['sweeps'], 0, 0, r['cold']))
                                   for r in rs])
    errors = {group: (predict(rs) / np.array([r['job_ns'] for r in rs]) - 1).tolist()
              for group, rs in (('fit', train), ('validation', check))}
    before = (base(check) / np.array([r['job_ns'] for r in check]) - 1).tolist()
    worst = max(abs(e) for e in errors['validation'])
    write_json(output / 'conflict-model.json', dict(
        base_model_path=str(mem_set.MODEL_PATH.relative_to(HERE.parents[3])),
        base_model_hash=file_hash(mem_set.MODEL_PATH),
        corrected_features=CORRECTED, delta=dict(zip(CORRECTED, map(float, delta))), model=corrected,
        validation_error_before=dict(min=min(before), max=max(before)),
        fit_max_error=max(abs(e) for e in errors['fit']), validation_max_error=worst, errors=errors))
    design.announce(f'conflict model: validation max error {worst:.2%} '
                    f'(uncorrected {min(before):+.2%}..{max(before):+.2%})')
    if worst > bi_calibrate.MAX_VALIDATION_ERROR:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('measure', 'fit'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=16)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == 'measure':
        output.mkdir(parents=True, exist_ok=True)
        measure(output, args.workers)
    else:
        fit(output)


if __name__ == '__main__':
    main()
