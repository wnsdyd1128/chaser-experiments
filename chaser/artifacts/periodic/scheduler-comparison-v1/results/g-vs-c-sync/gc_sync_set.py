"""G versus C without a feasible partition: heavy-task count x heavy-period sharing (fresh sets).

Replaces gc_set, whose all-equal heavy periods released every heavy job at once
and made every configuration miss. In the infeasible run (inf_set) what
separated the outcomes was how many heavy tasks share one period: their jobs,
each needing more than half of its period, are released together. This design
fixes the sharing:
  stagger  at most two heavy tasks per period (5 heavy: 2/2/1, 6 heavy: 2/2/2)
  sync     three heavy tasks share one period (5 heavy: 3/1/1, 6 heavy: 3/2/1)
over the periods {20, 40, 80} ms, with the period receiving each count drawn
per set. Pre-registered primary hypotheses (Holm over the three McNemar tests):
  H1  5 heavy, sync: C2 (1+1+2, capacity) meets every deadline more often than G
  H2  6 heavy, stagger and sync: G more often than C2 (its 2-core cluster overflows)
Everything else (heavy U 0.51-0.55, light Dirichlet(ALPHA) shares, per-core load
0.85, 16 compute-bound tasks) follows inf_set, but with a new seed base so the
sets are independent of the run that suggested the hypotheses. Common random
numbers: set k fixes the light periods, heavy U draws and positions and the
light shares; stagger and sync of the same set differ only in heavy periods.
"""

from pathlib import Path
import random
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hl_set
import inf_set
from inf_set import (ALPHA, CORE_CAP, CORES, HYPERPERIOD, LIGHT_CAP, MEASURED_HYPERPERIODS, PERIODS, TASKS,
                     U_MIN, WARMUP_HYPERPERIODS)

LOADS = (0.85,)
HEAVINESS = ('h5-stagger', 'h5-sync', 'h6-stagger', 'h6-sync')
SETS = 40
SEED_BASE = 20261701
HEAVY = 6
HEAVY_RANGE = inf_set.HEAVY_RANGE
SHARING = {('h5', 'stagger'): (2, 2, 1), ('h5', 'sync'): (3, 1, 1),
           ('h6', 'stagger'): (2, 2, 2), ('h6', 'sync'): (3, 2, 1)}
PLACEMENTS = ('wfd', 'c-cap', 'c2-cap')
TRENDS = False
PRIMARY = (('h5-sync', 'c2_cap', 'g'), ('h6-stagger', 'g', 'c2_cap'), ('h6-sync', 'g', 'c2_cap'))


def split(heaviness: str) -> tuple[str, str]:
    count, sharing = heaviness.split('-')
    return count, sharing


def draws(set_id: int, count: str) -> tuple[list[float], list[int], list[float], list[int]]:
    """Heavy U, heavy positions, light shares and light periods of a set (stagger and sync share them)."""
    base = np.random.default_rng([SEED_BASE, set_id])
    heavy = base.uniform(*HEAVY_RANGE, HEAVY)[:inf_set.heavy_count(count)]
    positions = base.permutation(TASKS)[:len(heavy)]
    rng = random.Random(SEED_BASE + set_id)
    light_periods = [rng.choice(PERIODS) for _ in range(TASKS)]
    shares_rng = np.random.default_rng([SEED_BASE, set_id, len(heavy)])
    rest = LOADS[0] * CORES - heavy.sum()
    while True:
        w = shares_rng.dirichlet(np.full(TASKS - len(heavy), ALPHA))
        if w.max() * rest <= LIGHT_CAP and w.min() * rest >= U_MIN:
            break
    return heavy.tolist(), positions.tolist(), (w * rest).tolist(), light_periods


def heavy_periods(heaviness: str, set_id: int) -> list[int]:
    count, sharing = split(heaviness)
    counts = SHARING[(count, sharing)]
    order = random.Random(SEED_BASE * 7 + set_id).sample(PERIODS, len(PERIODS))
    return [p for p, n in zip(order, counts) for _ in range(n)]


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    count, sharing = split(heaviness)
    heavy, positions, light, light_periods = draws(set_id, count)
    heavy_at = dict(zip(positions, zip(heavy, heavy_periods(heaviness, set_id))))
    light_iter = iter(light)
    targets, task_periods = [], []
    for i in range(TASKS):
        if i in heavy_at:
            targets.append(heavy_at[i][0])
            task_periods.append(heavy_at[i][1])
        else:
            targets.append(next(light_iter))
            task_periods.append(light_periods[i])
    task_sweeps = [hl_set.sweeps(u, p) for u, p in zip(targets, task_periods)]
    us = [hl_set.planned_u(s, p) for s, p in zip(task_sweeps, task_periods)]
    if placement in inf_set.CLUSTERS:
        cores = inf_set.cluster_cores(us, inf_set.CLUSTERS[placement])
    else:
        assignment = hl_set.wfd(us)
        cores = [assignment[i] for i in range(TASKS)]
    tasks = [dict(task_id=f't{i:02d}', pattern='cyclic', distinct=hl_set.LINES, stride=hl_set.STRIDE,
                  sweeps=task_sweeps[i], core=cores[i], period_ticks=task_periods[i], u_target=targets[i],
                  u_planned=us[i], heavy=i in heavy_at) for i in range(TASKS)]
    core_u = [sum(u for u, c in zip(us, cores) if c == core) for core in range(CORES)]
    return dict(workload_id=f'g-vs-c-sync-u{round(load * 100):03d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id='g-vs-c-sync-cyclic-v1', policy_id=f'g-vs-c-sync-{placement}-v1',
                measurement_contract_id=hl_set.CONTRACT, array_alignment_bytes=32, workload_optimization='O0',
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, heavy=len(heavy), sharing=sharing,
                               heavy_period_counts=SHARING[(count, sharing)], set_id=set_id,
                               seed=SEED_BASE + set_id, placement=placement, total_u=sum(us), core_u=core_u))
