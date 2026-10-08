"""Calibrate the O2 job-time model for the memory-bound shape of experiment 41 (memcost_set) before running it.

The shape is hot-cold with a 4096 B stride: the hot lines (at most the L1 associativity) hit L1 on their
repeats, and the cold region, MEM_COLD lines of which every touched L2 set gets at least five, misses L1
and L2 on every access (a probe on 2026-10-07 measured about 215 ns per access, against about 68 ns for
the cls-bimodal shapes whose misses hit L2). The cls-bimodal model is fitted on L2 hits, so this measures
memory levels alone (P, bimodal.PERIOD period), fits a correction of the per-job, per-sweep, per-region-loop,
per-L1-hit and per-miss coefficients on a grid and checks it on seeded random levels (every job within
bi_calibrate.MAX_VALIDATION_ERROR). A chunk holds at most CHUNK tasks so its data stays under 16 MiB.
Stages:
  measure   run the FIT grid and VALIDATION levels, write <output>/measured.json
  fit       least squares on the fit rows, check the validation rows, write <output>/mem-model.json
            (the corrected coefficients); exits 1 above the limit
Usage: python3 mem_calibrate.py measure|fit --output <dir> [--workers N]
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
import mem_set
import run as design

MEM_STRIDE = 4096  # the L1 way size; 128 lines apart, so the cold lines spread over 128 L2 sets
MEM_HOT = range(1, 5)  # at most the L1 associativity, so the repeats hit
MEM_COLD = range(640, 705, 16)  # at least five lines in every touched L2 set (4 ways): every access misses
MEM_REPEATS = range(2, 61)
FIT_HOT, FIT_REPEATS, FIT_COLD, FIT_SWEEPS = (2, 4), (10, 25, 40), (640, 704), (5, 30, 100)
VALIDATION_LEVELS, VALIDATION_SEED = 24, 20264101
CHUNK = 5
CORRECTED = ('base', 'sweeps', 'region_loops', 'l1_hits', 'l2_hits')


def levels() -> list[dict]:
    fit = [dict(group='fit', hot=h, repeats=r, cold=c, sweeps=s)
           for h in FIT_HOT for r in FIT_REPEATS for c in FIT_COLD for s in FIT_SWEEPS]
    rng = random.Random(VALIDATION_SEED)
    validation = [dict(group='validation', hot=rng.choice(MEM_HOT), repeats=rng.choice(MEM_REPEATS),
                       cold=rng.choice(MEM_COLD), sweeps=rng.randint(3, 110)) for _ in range(VALIDATION_LEVELS)]
    return fit + validation


def task(i: int, level: dict) -> dict:
    return dict(task_id=f'k{i:03d}', pattern='hot-cold', distinct=level['hot'] + level['cold'],
                hot_distinct=level['hot'], hot_repeats=level['repeats'], cold_repeats=1, stride=MEM_STRIDE,
                sweeps=level['sweeps'], core=i % 4, period_ticks=bimodal.PERIOD)


def features(rows) -> np.ndarray:
    f = bimodal.features(np.array([r['hot'] for r in rows]), np.array([r['repeats'] for r in rows]),
                         np.array([r['sweeps'] for r in rows]), 0, 0, np.array([r['cold'] for r in rows]))
    return f[:, [bimodal.FEATURES.index(name) for name in CORRECTED]]


def measure(output: Path, workers: int) -> None:
    rows, all_levels = [], levels()
    for start in range(0, len(all_levels), CHUNK):
        chunk = all_levels[start:start + CHUNK]
        tasks = [task(start + i, level) for i, level in enumerate(chunk)]
        cpu = bi_calibrate.isolated(output / f'chunk-{start // CHUNK:02d}', tasks, workers)
        rows += [dict(level, task_id=t['task_id'], job_ns=cpu[t['task_id']]) for level, t in zip(chunk, tasks)]
    write_json(output / 'measured.json', dict(stride=MEM_STRIDE, rows=rows))


def fit(output: Path) -> None:
    rows = json.loads((output / 'measured.json').read_text())['rows']
    model = mem_set.model()
    job = lambda m, rs: np.array([float(bimodal.job_ns(m, r['hot'], r['repeats'], r['sweeps'], 0, 0, r['cold'])) for r in rs])
    train = [r for r in rows if r['group'] == 'fit']
    check = [r for r in rows if r['group'] == 'validation']
    delta, *_ = np.linalg.lstsq(features(train), np.array([r['job_ns'] for r in train]) - job(model, train), rcond=None)
    corrected = dict(model, **{name: model[name] + float(d) for name, d in zip(CORRECTED, delta)})
    errors = {group: (job(corrected, rs) / np.array([r['job_ns'] for r in rs]) - 1).tolist()
              for group, rs in (('fit', train), ('validation', check))}
    before = (job(model, check) / np.array([r['job_ns'] for r in check]) - 1).tolist()
    worst = max(abs(e) for e in errors['validation'])
    write_json(output / 'mem-model.json', dict(
        base_model_path=str(mem_set.MODEL_PATH.relative_to(HERE.parents[3])), base_model_hash=file_hash(mem_set.MODEL_PATH),
        stride=MEM_STRIDE, corrected_features=CORRECTED, delta=dict(zip(CORRECTED, map(float, delta))), model=corrected,
        validation_error_before=dict(min=min(before), max=max(before)),
        fit_max_error=max(abs(e) for e in errors['fit']), validation_max_error=worst, errors=errors))
    design.announce(f'memory model: validation max error {worst:.2%} (uncorrected {min(before):+.2%}..{max(before):+.2%})')
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
