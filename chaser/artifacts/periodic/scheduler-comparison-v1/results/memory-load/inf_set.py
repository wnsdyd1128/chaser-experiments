"""Partition-infeasible task sets: which of Global and Clustered wins when no partition fits?

Same tasks, periods and placements as hl_set, but with H heavy tasks whose U is
drawn from (0.51, 0.55]: any two heavy tasks on one core exceed U 1, so with
H >= 5 heavy tasks on 4 cores no partition keeps every core at U <= 1 (H = 4
is the feasible control). Per-core load 0.85 or 0.95. Light tasks share the
rest like hl_set (Dirichlet(ALPHA), U <= LIGHT_CAP at the highest load, >= U_MIN
at the lowest). Common random numbers: set k fixes the periods, the six heavy
draws and positions (the first H are used) and, per H, the light shares; the
load only scales the light shares.

Placements, besides hl_set's wfd and informed:
  c-cap   C (1+3): tasks in decreasing U go to the cluster whose per-core load
          after adding them is lowest (single core 0 vs cores 1-3)
  c2-cap  C2 (1+1+2): the same rule over core 0, core 1 and cores 2-3
Inside a multi-core cluster the core field only marks membership.
"""

from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hl_set
from hl_set import (ALPHA, CORE_CAP, CORES, HYPERPERIOD, LIGHT_CAP, LINES, MEASURED_HYPERPERIODS, PERIODS,
                    STRIDE, TASKS, WARMUP_HYPERPERIODS, CONTRACT, periods, planned_u, sweeps)

LOADS = (0.85, 0.95)
HEAVINESS = ('h4', 'h5', 'h6')
SETS = 30
SEED_BASE = 20261401
U_MIN = 0.002
HEAVY = 6
HEAVY_RANGE = (0.51, 0.55)
PLACEMENTS = ('wfd', 'informed', 'c-cap', 'c2-cap')
CLUSTERS = {'c-cap': ((0,), (1, 2, 3)), 'c2-cap': ((0,), (1,), (2, 3))}


def heavy_count(heaviness: str) -> int:
    return int(heaviness[1:])


def utilizations(load: float, heaviness: str, set_id: int) -> list[float]:
    count = heavy_count(heaviness)
    base = np.random.default_rng([SEED_BASE, set_id])
    heavy = base.uniform(*HEAVY_RANGE, HEAVY)[:count]
    positions = base.permutation(TASKS)[:count]
    rng = np.random.default_rng([SEED_BASE, set_id, count])
    high, low = max(LOADS) * CORES - heavy.sum(), min(LOADS) * CORES - heavy.sum()
    while True:
        w = rng.dirichlet(np.full(TASKS - count, ALPHA))
        if w.max() * high <= LIGHT_CAP and w.min() * low >= U_MIN:
            break
    light = iter(w * (load * CORES - heavy.sum()))
    heavy_at = dict(zip(positions.tolist(), heavy.tolist()))
    return [float(heavy_at[i]) if i in heavy_at else float(next(light)) for i in range(TASKS)]


def cluster_cores(us, clusters) -> list[int]:
    """Decreasing U onto the cluster with the lowest per-core load after the addition."""
    load = [0.0] * len(clusters)
    cores = {}
    for i in sorted(range(len(us)), key=lambda i: (-us[i], i)):
        k = min(range(len(clusters)), key=lambda k: ((load[k] + us[i]) / len(clusters[k]), k))
        load[k] += us[i]
        cores[i] = k
    # Membership only: spread a multi-core cluster's tasks over its cores by WFD.
    out = {}
    for k, members in enumerate(clusters):
        assigned = [i for i in cores if cores[i] == k]
        out.update(hl_set.wfd(us, cores=members, tasks=assigned))
    return [out[i] for i in range(len(us))]


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    task_periods = periods(set_id)
    targets = utilizations(load, heaviness, set_id)
    task_sweeps = [sweeps(u, p) for u, p in zip(targets, task_periods)]
    us = [planned_u(s, p) for s, p in zip(task_sweeps, task_periods)]
    if placement in CLUSTERS:
        cores = cluster_cores(us, CLUSTERS[placement])
    else:
        cores = hl_set.placement_cores(placement, us, task_periods, set_id)
    tasks = [dict(task_id=f't{i:02d}', pattern='cyclic', distinct=LINES, stride=STRIDE, sweeps=task_sweeps[i],
                  core=cores[i], period_ticks=task_periods[i], u_target=targets[i], u_planned=us[i],
                  heavy=targets[i] > 0.5) for i in range(TASKS)]
    core_u = [sum(u for u, c in zip(us, cores) if c == core) for core in range(CORES)]
    return dict(workload_id=f'infeasible-u{round(load * 100):03d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id='infeasible-cyclic-v1', policy_id=f'infeasible-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization='O0',
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us), core_u=core_u, alpha=ALPHA,
                               light_cap=LIGHT_CAP, heavy=heavy_count(heaviness), heavy_range=HEAVY_RANGE,
                               partition_feasible=heavy_count(heaviness) <= CORES))
