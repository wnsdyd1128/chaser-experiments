"""High-load task sets: does Partitioned stay best when packing gets tight?

Sixteen compute-bound tasks (experiment 1's 2 KiB cyclic O0 kernel, L1-resident,
so co-run memory contention stays negligible) with periods drawn from
{20, 40, 80} ms. The per-core nominal U is 0.5, 0.7 or 0.85 (total 2.0-3.4).
Task U shares:
  light  all 16 tasks from a symmetric Dirichlet(ALPHA) share, every task
         U <= LIGHT_CAP at the highest load and >= U_MIN at the lowest
  heavy  HEAVY tasks with U ~ Uniform(0.5, 0.8) (same at every load), the
         other 14 split the remaining U like the light set
Plain UUniFast cannot keep 16 tasks under 0.3 at a total U of 3.4 (its
largest task is typically ~0.7), hence the bounded Dirichlet share.
Common random numbers: set k fixes the periods, task order and shares; the load
level only scales them.

Placements (task order and sources are shared, only the core field differs):
  wfd         largest U first onto the least-loaded core (cluster domains of
              C (1+3) and C2 (1+1+2) follow it)
  informed    local search from wfd minimizing, over one hyperperiod, the sum of
              each release instant's busiest-core released work, with per-core
              U <= CORE_CAP enforced (the release-aware P' of experiment 2 for
              unequal U; the margin below 1 absorbs scheduling overhead)
  c-informed  core 0 (the single-core cluster of C (1+3)) takes the smallest
              tasks up to the per-core mean U; the rest (heavy tasks included)
              share the 3-core cluster
"""

from pathlib import Path
import random
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'period-distribution'))

from chaser.periodic.measurement import CONTRACT
import taskset

TASKS = 16
CORES = 4
PERIODS = (20, 40, 80)
HYPERPERIOD = 80
LOADS = (0.5, 0.7, 0.85)
HEAVINESS = ('light', 'heavy')
SETS = 20
SEED_BASE = 20261301
ALPHA = 8.0
LIGHT_CAP = 0.35
U_MIN = 0.005
HEAVY = 2
HEAVY_RANGE = (0.5, 0.8)
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 2, 4
LINES, STRIDE = 64, 32
PLACEMENTS = ('wfd', 'informed', 'c-informed')
RESTARTS = 20
CORE_CAP = 0.95


def periods(set_id: int) -> list[int]:
    rng = random.Random(SEED_BASE + set_id)
    return [rng.choice(PERIODS) for _ in range(TASKS)]


def _shares(rng, count, high_total, low_total):
    """Dirichlet shares whose largest task fits LIGHT_CAP at high_total and smallest U_MIN at low_total."""
    while True:
        w = rng.dirichlet(np.full(count, ALPHA))
        if w.max() * high_total <= LIGHT_CAP and w.min() * low_total >= U_MIN:
            return w


def utilizations(load: float, heaviness: str, set_id: int) -> list[float]:
    rng = np.random.default_rng([SEED_BASE, set_id, HEAVINESS.index(heaviness)])
    totals = [level * CORES for level in LOADS]
    if heaviness == 'light':
        return [float(u) for u in _shares(rng, TASKS, max(totals), min(totals)) * load * CORES]
    heavy = rng.uniform(*HEAVY_RANGE, HEAVY)
    positions = rng.permutation(TASKS)[:HEAVY]
    w = _shares(rng, TASKS - HEAVY, max(totals) - heavy.sum(), min(totals) - heavy.sum())
    light = iter(w * (load * CORES - heavy.sum()))
    heavy_at = dict(zip(positions.tolist(), heavy.tolist()))
    return [float(heavy_at[i]) if i in heavy_at else float(next(light)) for i in range(TASKS)]


def sweeps(u: float, period: int) -> int:
    return max(1, round((u * period * 1e6 - taskset.JOB_BASE_NS) / taskset.SWEEP_NS))


def planned_u(task_sweeps: int, period: int) -> float:
    return (taskset.JOB_BASE_NS + taskset.SWEEP_NS * task_sweeps) / (period * 1e6)


def wfd(us, cores=range(CORES), tasks=None) -> dict[int, int]:
    load, out = {c: 0.0 for c in cores}, {}
    for i in sorted(range(len(us)) if tasks is None else tasks, key=lambda i: (-us[i], i)):
        core = min(load, key=lambda c: (load[c], c))
        out[i] = core
        load[core] += us[i]
    return out


def cohort_cost(cores, us, task_periods) -> float:
    """Sum over the release instants of one hyperperiod of the busiest core's released work,
    plus a large penalty for any core above CORE_CAP."""
    cost = 0.0
    for t in range(0, HYPERPERIOD, min(PERIODS)):
        work = [0.0] * CORES
        for i, (u, p) in enumerate(zip(us, task_periods)):
            if t % p == 0:
                work[cores[i]] += u * p
        cost += max(work)
    over = [sum(u for i, u in enumerate(us) if cores[i] == c) - CORE_CAP for c in range(CORES)]
    return cost + 1e6 * sum(max(0.0, x) for x in over)


def _descend(cores, us, task_periods):
    best = cohort_cost(cores, us, task_periods)
    improved = True
    while improved:
        improved = False
        for i in range(TASKS):
            for c in range(CORES):
                if c == cores[i]:
                    continue
                trial = list(cores)
                trial[i] = c
                cost = cohort_cost(trial, us, task_periods)
                if cost < best - 1e-9:
                    cores, best, improved = trial, cost, True
        for i in range(TASKS):
            for j in range(i + 1, TASKS):
                if cores[i] == cores[j]:
                    continue
                trial = list(cores)
                trial[i], trial[j] = trial[j], trial[i]
                cost = cohort_cost(trial, us, task_periods)
                if cost < best - 1e-9:
                    cores, best, improved = trial, cost, True
    return cores, best


def informed(us, task_periods, seed) -> list[int]:
    start = wfd(us)
    best, cost = _descend([start[i] for i in range(TASKS)], us, task_periods)
    rng = random.Random(seed)
    for _ in range(RESTARTS - 1):
        trial, trial_cost = _descend([rng.randrange(CORES) for _ in range(TASKS)], us, task_periods)
        if trial_cost < cost - 1e-9:
            best, cost = trial, trial_cost
    return best


def c_informed(us) -> list[int]:
    target = sum(us) / CORES
    cores, load = {}, 0.0
    for i in sorted(range(TASKS), key=lambda i: (us[i], i)):
        if load + us[i] <= target:
            cores[i], load = 0, load + us[i]
    rest = [i for i in range(TASKS) if i not in cores]
    cores.update(wfd(us, cores=(1, 2, 3), tasks=rest))
    return [cores[i] for i in range(TASKS)]


def placement_cores(placement, us, task_periods, set_id) -> list[int]:
    if placement == 'wfd':
        assignment = wfd(us)
        return [assignment[i] for i in range(TASKS)]
    if placement == 'informed':
        return informed(us, task_periods, SEED_BASE + set_id)
    if placement == 'c-informed':
        return c_informed(us)
    raise ValueError(f'Unknown placement: {placement}')


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    task_periods = periods(set_id)
    targets = utilizations(load, heaviness, set_id)
    task_sweeps = [sweeps(u, p) for u, p in zip(targets, task_periods)]
    us = [planned_u(s, p) for s, p in zip(task_sweeps, task_periods)]
    cores = placement_cores(placement, us, task_periods, set_id)
    tasks = [dict(task_id=f't{i:02d}', pattern='cyclic', distinct=LINES, stride=STRIDE, sweeps=task_sweeps[i],
                  core=cores[i], period_ticks=task_periods[i], u_target=targets[i], u_planned=us[i],
                  heavy=targets[i] >= HEAVY_RANGE[0])
             for i in range(TASKS)]
    core_u = [sum(u for u, c in zip(us, cores) if c == core) for core in range(CORES)]
    return dict(workload_id=f'high-load-u{round(load * 100):03d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id='high-load-cyclic-v1', policy_id=f'high-load-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization='O0',
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us), core_u=core_u, alpha=ALPHA,
                               light_cap=LIGHT_CAP, heavy=HEAVY, heavy_range=HEAVY_RANGE))
