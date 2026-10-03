"""High load with memory contention: does traffic grouping keep deadlines as load rises?

Sixteen hot-cold O2 tasks (the bimodal study's level tables), 8 high-CLS
(center 0.90) and 8 low-CLS (center 0.13), mode CV 0.1, at random positions
(bimodal.targets(0.5, 0.1, k)). Periods from {20, 40, 80} ms (hl_set.periods).
Per-core nominal U 0.3 / 0.45 / 0.6 from Dirichlet(ALPHA) shares (largest task
<= LIGHT_CAP at the highest load, smallest >= U_MIN at the lowest). The traffic
factor sets the low-CLS tasks' level: as-is (memory-bound, the most L1 misses)
or matched (the high-center L1 misses per job, the rest register padding),
which is the no-contention control. Each task's job budget (U x period, 10 us
steps) gets its own level table from the fitted O2 model in the exported
bimodal calibration. Common random numbers: set k fixes periods, task modes,
CLS draws and U shares; the load scales the shares, the traffic factor only
swaps the low-CLS level shape.

Placements: wfd (largest U first onto the least-loaded core, CLS-blind; the
cluster domains of C (1+3) and C2 (1+1+2) follow it) and grouped-balanced
(low-CLS tasks on cores 0-1 and high-CLS tasks on cores 2-3, WFD inside each
group).
"""

from functools import cache
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))

import bimodal
from hl_set import (CONTRACT, CORE_CAP, CORES, HYPERPERIOD, MEASURED_HYPERPERIODS, PERIODS, TASKS,
                    WARMUP_HYPERPERIODS, periods, wfd)

LOADS = (0.3, 0.45, 0.6)
HEAVINESS = ('as-is', 'matched')  # traffic of the low-CLS tasks
SETS = 30
SEED_BASE = 20261501
ALPHA = 8.0
LIGHT_CAP = 0.35
U_MIN = 0.005
HEAVY, HEAVY_RANGE = 0, None
OPTIMIZATION = 'O2'
LOW_FRACTION, CLS_CV = 0.5, 0.1
BUDGET_STEP_NS = 10_000
PLACEMENTS = ('wfd', 'grouped-balanced')
MODEL_PATH = HERE.parent / 'results/cls-bimodal/calibration/model.json'


@cache
def model() -> dict:
    return json.loads(MODEL_PATH.read_text())['coefficients']


@cache
def tables(budget: int) -> dict:
    return bimodal.solve_tables(model(), budget)


@cache
def shares(set_id: int) -> tuple[float, ...]:
    rng = np.random.default_rng([SEED_BASE, set_id])
    while True:
        w = rng.dirichlet(np.full(TASKS, ALPHA))
        if w.max() * max(LOADS) * CORES <= LIGHT_CAP and w.min() * min(LOADS) * CORES >= U_MIN:
            return tuple(float(x) for x in w)


def budgets(load: float, set_id: int) -> list[int]:
    return [max(BUDGET_STEP_NS, round(w * load * CORES * p * 1e6 / BUDGET_STEP_NS) * BUDGET_STEP_NS)
            for w, p in zip(shares(set_id), periods(set_id))]


def grouped_balanced(us, modes) -> list[int]:
    low = [i for i, m in enumerate(modes) if m == 'low']
    high = [i for i, m in enumerate(modes) if m == 'high']
    cores = {**wfd(us, cores=(0, 1), tasks=low), **wfd(us, cores=(2, 3), tasks=high)}
    return [cores[i] for i in range(TASKS)]


def configuration(load: float, traffic: str, set_id: int, placement: str) -> dict:
    task_periods = periods(set_id)
    wanted = bimodal.targets(LOW_FRACTION, CLS_CV, set_id)
    task_budgets = budgets(load, set_id)
    levels = [bimodal.level(tables(b), mode, traffic, target) for (mode, target), b in zip(wanted, task_budgets)]
    us = [b * (1 + lv['u_error']) / (p * 1e6) for b, lv, p in zip(task_budgets, levels, task_periods)]
    modes = [mode for mode, _ in wanted]
    if placement == 'wfd':
        assignment = wfd(us)
        cores = [assignment[i] for i in range(TASKS)]
    elif placement == 'grouped-balanced':
        cores = grouped_balanced(us, modes)
    else:
        raise ValueError(f'Unknown placement: {placement}')
    tasks = []
    for i, ((mode, target), lv) in enumerate(zip(wanted, levels)):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + bimodal.COLD_LINES,
                    hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=bimodal.STRIDE,
                    sweeps=lv['sweeps'], core=cores[i], period_ticks=task_periods[i], mode=mode,
                    cls_target=target, cls_planned=lv['cls'], u_target=task_budgets[i] / (task_periods[i] * 1e6),
                    u_planned=us[i], l1_misses_planned=lv['sweeps'] * (lv['hot'] + bimodal.COLD_LINES))
        if lv['pad']:
            task['pad_rounds'] = lv['pad']
        if lv['tail']:
            task['pad_tail'] = lv['tail']
        tasks.append(task)
    core_u = [sum(u for u, c in zip(us, cores) if c == core) for core in range(CORES)]
    return dict(workload_id=f'memory-load-u{round(load * 100):03d}-{traffic}-s{set_id:02d}-{placement}-v1',
                family_id='memory-load-hot-cold-v1', policy_id=f'memory-load-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization=OPTIMIZATION,
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=traffic, traffic=traffic, set_id=set_id,
                               seed=SEED_BASE + set_id, placement=placement, total_u=sum(us), core_u=core_u,
                               alpha=ALPHA, light_cap=LIGHT_CAP, low_fraction=LOW_FRACTION, cls_cv=CLS_CV))
