"""Calibrate hot-cold levels: (hot repeats, sweeps) pairs at U = 0.125, then yarda_cpp CLS.

Stages (one output directory):
  measure  per-sweep CPU of every hot-repeat grid value (isolated P, 2 sweeps, 100 ms)
  verify   per period, every integer (repeats, sweeps) pair whose linear cost model
           predicts U within 1.5%; isolated runs keep pairs measured within 2%
  analyze  yarda_cpp hierarchy analysis of the kept pairs -> calibration.json

Integer sweeps alone cannot hit U when one sweep fills most of the job, so the
hot repeats are chosen jointly with the sweeps instead of from a fixed grid.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'period-distribution'))

from chaser.periodic.analysis import analyze
from chaser.periodic.build import prepare
from chaser.periodic.dataset import characterize, load_batch
from tools.rtems_smoke import write_json

import clsset
import run as design

JOB_BASE_NS = 5_580
MEASURE_PERIOD = 100
MEASURE_SWEEPS = 2
PLAN_TOLERANCE = 0.015
U_TOLERANCE = 0.02
CHUNK = 32


def level_id(repeats: int, sweeps: int) -> str:
    return f'r{repeats:04d}s{sweeps:02d}'


def level_config(name: str, period: int, levels: list[tuple[int, int]]) -> dict:
    tasks = [dict(task_id=level_id(repeats, sweeps), pattern='hot-cold',
                  distinct=clsset.HOT_LINES + clsset.COLD_LINES, hot_distinct=clsset.HOT_LINES,
                  hot_repeats=repeats, cold_repeats=1, stride=clsset.STRIDE, sweeps=sweeps,
                  core=i % clsset.CORES, period_ticks=period)
             for i, (repeats, sweeps) in enumerate(levels)]
    return dict(workload_id=f'cls-calibration-{name}', family_id='cls-calibration-v1',
                policy_id='calibration', measurement_contract_id='chaser-periodic-measurement-v3',
                array_alignment_bytes=32, workload_optimization='O0', horizon_ticks=15 * period,
                warmup_ticks=5 * period, u_repeats=1, diagnostic_only=True, tasks=tasks)


def isolated(output: Path, config: dict, workers: int) -> dict:
    """Prepare, run every task alone on P core 0, return task_id -> mean job CPU."""
    prepared = output / 'prepared'
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', config)
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
    levels = [(r, MEASURE_SWEEPS) for r in clsset.REPEAT_GRID]
    cpu = isolated(root / 'measure', level_config('measure', MEASURE_PERIOD, levels), workers)
    cost = {r: (cpu[level_id(r, MEASURE_SWEEPS)] - JOB_BASE_NS) / MEASURE_SWEEPS
            for r in clsset.REPEAT_GRID}
    write_json(root / 'sweep-cost.json', {str(r): c for r, c in cost.items()})
    design.announce('measured per-sweep CPU: ' + ', '.join(f'R{r}={c / 1e3:.1f}us' for r, c in cost.items()))


def planned_levels(cost: dict[int, float], period: int) -> list[tuple[int, int]]:
    """Integer (repeats, sweeps) pairs whose linear cost model hits U within 1.5%."""
    slope, intercept = np.polyfit(sorted(cost), [cost[r] for r in sorted(cost)], 1)
    target = clsset.TASK_U * period * 1e6
    levels = []
    for sweeps in range(1, 100_000):
        if JOB_BASE_NS + sweeps * (intercept + slope) > target * (1 + PLAN_TOLERANCE):
            return levels
        for repeats in range(1, 1_000_000):
            error = (JOB_BASE_NS + sweeps * (intercept + slope * repeats)) / target - 1
            if error > PLAN_TOLERANCE:
                break
            if error >= -PLAN_TOLERANCE:
                levels.append((repeats, sweeps))
    raise RuntimeError('Sweep search did not terminate')


def verify(root: Path, workers: int) -> None:
    cost = {int(r): c for r, c in json.loads((root / 'sweep-cost.json').read_text()).items()}
    result = {}
    for period in clsset.PERIODS:
        levels = planned_levels(cost, period)
        kept = []
        for index in range(0, len(levels), CHUNK):
            output = root / f'verify-p{period:03d}-c{index // CHUNK:02d}'
            chunk = levels[index:index + CHUNK]
            cpu = isolated(output, level_config(output.name, period, chunk), workers)
            for repeats, sweeps in chunk:
                u = cpu[level_id(repeats, sweeps)] / (period * 1e6)
                if abs(u / clsset.TASK_U - 1) <= U_TOLERANCE:
                    kept.append(dict(hot_repeats=repeats, sweeps=sweeps, u=u, chunk=output.name))
        design.announce(f'period {period}: kept {len(kept)}/{len(levels)} levels within '
                        f'{U_TOLERANCE:.0%} of U = {clsset.TASK_U}')
        result[str(period)] = kept
    write_json(root / 'sweeps.json', result)


def analyze_levels(root: Path) -> None:
    chosen = json.loads((root / 'sweeps.json').read_text())
    tables = {}
    chunks = sorted({level['chunk'] for levels in chosen.values() for level in levels})
    with ThreadPoolExecutor(max_workers=len(chunks)) as pool:
        futures = {chunk: pool.submit(analyze, root / chunk / 'prepared', compress_events=True)
                   for chunk in chunks}
        reports = {chunk: future.result() for chunk, future in futures.items()}
    for period, levels in chosen.items():
        rows = []
        for level in levels:
            report = reports[level['chunk']]
            case = report['cases'][level_id(level['hot_repeats'], level['sweeps'])]
            rows.append(dict(level, cls=case['cls'][clsset.ALPHA], clp=case['clp'],
                             modeled_accesses=case['modeled_accesses']))
        tables[period] = rows
        design.announce(f'period {period}: CLS range {min(r["cls"] for r in rows):.3f}'
                        f'-{max(r["cls"] for r in rows):.3f} over {len(rows)} levels')
    write_json(root / 'calibration.json', dict(alpha=clsset.ALPHA, tables=tables,
               analyzer=next(iter(report['provenance'].values()))['analyzer_commit']))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('measure', 'verify', 'analyze'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=design.MAX_WORKERS)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    {'measure': lambda: measure(args.output, args.workers),
     'verify': lambda: verify(args.output, args.workers),
     'analyze': lambda: analyze_levels(args.output)}[args.stage]()


if __name__ == '__main__':
    main()
