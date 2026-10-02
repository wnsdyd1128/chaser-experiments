"""Fit and validate the O2 job-time model of bimodal levels; check CLS against yarda_cpp.

Stages (one output directory):
  measure  isolated P runs of seeded random levels from the three level families
           (high, low as-is, low matched) at 40-110% of the U budget, in a fit
           and a held-out validation group
  fit      least-squares job-time model on the fit group -> model.json; fails
           when any validation level misses its measured job CPU by more than 2%
           or when a yarda_cpp CLS differs from bimodal.cls_model
  extend   check the fitted model on the levels the task-U imbalance design uses:
           40 job budgets spread evenly over its budget range, alternating the
           high- and low-mode centers -> extend.json; when any misses by more
           than 2%, refit on the fit group plus these levels (old model kept as
           model-before-extend.json) and require the validation group and the
           new levels within 2%

Run with PYTHONPATH set to the 4d03b93 + C2 + padding code copy.
"""

import argparse
import json
from pathlib import Path
import random
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'period-distribution'))

from chaser.periodic.build import prepare
from chaser.periodic.dataset import characterize, load_batch
from chaser.periodic.measurement import CONTRACT
from tools.rtems_smoke import file_hash, write_json

import bimodal
import run as design
import yarda_counts

# Approximate O2 costs from the pad-check runs; only used to size the grid.
PRIOR = dict(base=6000.0, sweeps=200.0, region_loops=50.0, l1_hits=20.7, l2_hits=67.0,
             pad_loops=20.3, pad_rounds=16.1, tail_loops=30.0, tail_rounds=16.1)
GROUPS = (('fit', 72, 20261101), ('validation', 36, 20261102))
EXTEND_LEVELS = 40
# Family -> (free integer solved from the sampled job time, its minimum).
FREE = {'high': ('repeats', 2), 'as-is': ('sweeps', 1), 'matched': ('pad', bimodal.MIN_LOOP_ROUNDS)}
CHUNK = 32
HORIZON_PERIODS, WARMUP_PERIODS = 15, 5
MAX_VALIDATION_ERROR = 0.02
SNAPSHOT = ('bi_calibrate.py', 'bimodal.py', 'yarda_counts.py')


def solve(free, **values):
    """Integer value of `free` putting the prior job time nearest to values['job']."""
    job = values.pop('job')
    low = bimodal.job_ns(PRIOR, **{**values, free: 1})
    slope = bimodal.job_ns(PRIOR, **{**values, free: 2}) - low
    return int(round(1 + (job - low) / slope))


def sample_levels(count: int, seed: int, job_ns=None, families=tuple(FREE)) -> list[dict]:
    """Seeded levels cycling over families; job time uniform in job_ns (default 40-110% of 2.5 ms)."""
    rng = random.Random(seed)
    budget = bimodal.TASK_U * bimodal.PERIOD * 1e6
    low, high = job_ns or (0.4 * budget, 1.1 * budget)
    levels = []
    while len(levels) < count:
        family = families[len(levels) % len(families)]
        tail = rng.choice((0, rng.randint(bimodal.MIN_LOOP_ROUNDS, 2000)))
        if family == 'high':
            level = dict(hot=rng.randint(16, 256), sweeps=rng.randint(1, 40), pad=0, tail=tail)
        elif family == 'as-is':
            level = dict(hot=rng.randint(1, 255), repeats=2, pad=0, tail=tail)
        else:
            level = dict(hot=rng.randint(1, 255), repeats=2, sweeps=rng.randint(5, 15), tail=tail)
        free, minimum = FREE[family]
        level[free] = solve(free, **level, **{free: None}, job=rng.uniform(low, high))
        if level[free] >= minimum:
            levels.append(dict(level, family=family))
    return levels


def level_task(i: int, level: dict) -> dict:
    task = dict(task_id=f'l{i:03d}', pattern='hot-cold', distinct=level['hot'] + bimodal.COLD_LINES,
                hot_distinct=level['hot'], hot_repeats=level['repeats'], cold_repeats=1,
                stride=bimodal.STRIDE, sweeps=level['sweeps'], core=i % bimodal.CORES,
                period_ticks=bimodal.PERIOD)
    for key, field in (('pad', 'pad_rounds'), ('tail', 'pad_tail')):
        if level[key]:
            task[field] = level[key]
    return task


def isolated(output: Path, tasks: list[dict], workers: int) -> dict:
    """Prepare one chunk, run every task alone under P, return task_id -> mean job CPU (ns)."""
    config = dict(workload_id=f'cls-bimodal-calibration-{output.name}', family_id='cls-bimodal-calibration-v1',
                  policy_id='calibration', measurement_contract_id=CONTRACT, array_alignment_bytes=32,
                  workload_optimization='O2', horizon_ticks=HORIZON_PERIODS * bimodal.PERIOD,
                  warmup_ticks=WARMUP_PERIODS * bimodal.PERIOD, u_repeats=1, diagnostic_only=True,
                  tasks=tasks)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', config)
    prepared = output / 'prepared'
    prepare(config, prepared)
    plan = json.loads((prepared / 'p/plan.json').read_text())
    specs = [(f'{output.name}/{t["task_id"]}', prepared, output / 'isolated' / t['task_id'], 'p', i + 1)
             for i, t in enumerate(plan['tasks'])]
    failed, infra = design.run_specs(specs, workers)
    if failed or infra:
        raise RuntimeError(f'Isolated calibration runs failed: {failed}, infrastructure={infra}')
    batches = [load_batch(prepared, output / 'isolated' / t['task_id']) for t in plan['tasks']]
    u = characterize(plan, batches)['utilization']
    return {t['task_id']: u[t['task_id']] * t['period_ticks'] * 1e6 for t in plan['tasks']}


def measure(root: Path, workers: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in SNAPSHOT:
        (root / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    rows = []
    for group, count, seed in GROUPS:
        levels = sample_levels(count, seed)
        for start in range(0, count, CHUNK):
            chunk = levels[start:start + CHUNK]
            tasks = [level_task(start + i, level) for i, level in enumerate(chunk)]
            cpu = isolated(root / f'{group}-c{start // CHUNK:02d}', tasks, workers)
            rows += [dict(level, group=group, chunk=f'{group}-c{start // CHUNK:02d}', task_id=t['task_id'],
                          job_ns=cpu[t['task_id']]) for level, t in zip(chunk, tasks)]
    write_json(root / 'measured.json', rows)
    design.announce(f'measured {len(rows)} isolated levels')


def shape(r):
    return dict(hot=r['hot'], repeats=r['repeats'], sweeps=r['sweeps'], pad=r['pad'], tail=r['tail'])


def least_squares(train) -> dict:
    x = np.array([bimodal.features(**shape(r)) for r in train])
    coefficients, *_ = np.linalg.lstsq(x, np.array([r['job_ns'] for r in train]), rcond=None)
    return dict(zip(bimodal.FEATURES, map(float, coefficients)))


def predict(model, rows):
    for r in rows:
        r['predicted_ns'] = float(bimodal.job_ns(model, **shape(r)))
        r['relative_error'] = r['predicted_ns'] / r['job_ns'] - 1


def cls_mismatches(root, rows) -> list[str]:
    """Compare yarda_cpp CLS with bimodal.cls_model for every measured level."""
    mismatches = []
    for chunk in sorted({r['chunk'] for r in rows}):
        counts = yarda_counts.analyze(root / chunk / 'prepared', root / chunk / 'yarda')
        for r in (r for r in rows if r['chunk'] == chunk):
            r['cls_yarda'] = counts[r['task_id']]['cls']
            r['cls_model'] = float(bimodal.cls_model(r['hot'], r['repeats'], r['sweeps']))
            if abs(r['cls_yarda'] - r['cls_model']) > 1e-9:
                mismatches.append(r['task_id'])
    return mismatches


def fit(root: Path) -> None:
    rows = json.loads((root / 'measured.json').read_text())
    model = least_squares([r for r in rows if r['group'] == 'fit'])
    predict(model, rows)
    errors = {g: max(abs(r['relative_error']) for r in rows if r['group'] == g) for g, _, _ in GROUPS}
    mismatches = cls_mismatches(root, rows)
    write_json(root / 'measured.json', rows)
    write_json(root / 'model.json', dict(features=bimodal.FEATURES, coefficients=model,
                                         max_relative_error=errors, cls_mismatches=mismatches,
                                         measured_hash=file_hash(root / 'measured.json')))
    design.announce('model ' + ', '.join(f'{k}={v:.2f}' for k, v in model.items())
                    + f'; max error fit {errors["fit"]:.2%}, validation {errors["validation"]:.2%}')
    if errors['validation'] > MAX_VALIDATION_ERROR or mismatches:
        raise RuntimeError(f'Calibration gate failed: validation {errors["validation"]:.2%}, '
                           f'CLS mismatches {mismatches}')


def design_levels(model: dict) -> list[dict]:
    """Levels of the task-U imbalance design at evenly spaced budgets of its range."""
    budgets = sorted({b for cv in bimodal.U_CVS for k in range(bimodal.SETS)
                      for b in bimodal.imbalance_budgets(cv, k)})
    picks = [budgets[round(i * (len(budgets) - 1) / (EXTEND_LEVELS - 1))] for i in range(EXTEND_LEVELS)]
    levels = []
    for i, budget in enumerate(picks):
        mode, center = (('high', bimodal.HIGH_CENTER), ('low', bimodal.LOW_CENTER))[i % 2]
        lv = bimodal.level(bimodal.solve_tables(model, budget), mode, 'as-is', center)
        levels.append(dict(hot=lv['hot'], repeats=lv['repeats'], sweeps=lv['sweeps'], pad=lv['pad'],
                           tail=lv['tail'], family='high' if mode == 'high' else 'as-is', budget_ns=budget))
    return levels


def extend(root: Path, workers: int) -> None:
    current = json.loads((root / 'model.json').read_text())
    levels = design_levels(current['coefficients'])
    rows = []
    for start in range(0, len(levels), CHUNK):
        chunk, name = levels[start:start + CHUNK], f'extend-c{start // CHUNK:02d}'
        tasks = [level_task(start + i, level) for i, level in enumerate(chunk)]
        cpu = isolated(root / name, tasks, workers)
        rows += [dict(level, group='extend', chunk=name, task_id=t['task_id'], job_ns=cpu[t['task_id']])
                 for level, t in zip(chunk, tasks)]
    mismatches = cls_mismatches(root, rows)
    predict(current['coefficients'], rows)
    budget_range = (min(r['budget_ns'] for r in rows), max(r['budget_ns'] for r in rows))
    report = dict(budget_ns_range=budget_range, levels=len(rows), cls_mismatches=mismatches,
                  model_hash=file_hash(root / 'model.json'),
                  max_relative_error=max(abs(r['relative_error']) for r in rows), refit=False)
    if report['max_relative_error'] > MAX_VALIDATION_ERROR:
        measured = json.loads((root / 'measured.json').read_text())
        model = least_squares([r for r in measured if r['group'] == 'fit'] + rows)
        predict(model, measured + rows)
        errors = {g: max(abs(r['relative_error']) for r in measured + rows if r['group'] == g)
                  for g in ('fit', 'validation', 'extend')}
        (root / 'model-before-extend.json').write_text((root / 'model.json').read_text())
        write_json(root / 'model.json', dict(current, coefficients=model, max_relative_error=errors,
                                             extended=dict(levels=len(rows), budget_ns_range=budget_range)))
        report.update(refit=True, refit_max_relative_error=errors, model_hash=file_hash(root / 'model.json'))
    write_json(root / 'extend.json', dict(report, rows=rows))
    design.announce(f'extend: max error {report["max_relative_error"]:.2%} with the fitted model, '
                    f'refit={report["refit"]}')
    final = report.get('refit_max_relative_error', {}).values() if report['refit'] else []
    if mismatches or any(e > MAX_VALIDATION_ERROR for e in final):
        raise RuntimeError(f'Extend gate failed: {report}')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('measure', 'fit', 'extend'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=design.MAX_WORKERS)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.stage == 'measure':
        measure(output, args.workers)
    elif args.stage == 'extend':
        extend(output, args.workers)
    else:
        fit(output)


if __name__ == '__main__':
    main()
