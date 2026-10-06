"""Experiment 1's normal-period design with 12-20 tasks instead of 16.

Set k has task_count(k) = 12 + k mod 9 tasks, so every count appears SETS / 9 times
and sets 0-8 hold one of each. Every task has U = PER_CORE_U * CORES / n, so the
per-core nominal U stays experiment 1's 0.5. Means, CVs, grid, truncation, the O0
cyclic 64-line job and its CPU model, the snake P placement and the array layout are
experiment 1's (taskset.py). A zero CV leaves one task set per count (sets 0-8). Set k
draws n truncated standard normals from seed SEED_BASE + k, shared by every mean and
CV (common random numbers). The run.py and control.py stages use this module in
place of taskset (tc_run.py).
"""

import random

from chaser.periodic.measurement import CONTRACT
import taskset
from taskset import (CORES, CVS, GRID, JOB_BASE_NS, MEANS, REFERENCE_MEAN, SWEEP_NS, TRUNCATION_SIGMA,
                     assign_cores, periods, unit)

TASK_RANGE = (12, 20)
TASKS = TASK_RANGE  # per set: task_count(set_id)
SETS = 18
PER_CORE_U = taskset.TASK_U * taskset.TASKS / CORES
SEED_BASE = 20262201


def task_count(set_id: int) -> int:
    return TASK_RANGE[0] + set_id % (TASK_RANGE[1] - TASK_RANGE[0] + 1)


def task_u(set_id: int) -> float:
    return PER_CORE_U * CORES / task_count(set_id)


# run.py's u-check measures set 0 (12 tasks: the highest per-task U, so the most
# sweeps per job) against TASK_U.
TASK_U = task_u(0)


def standard_draws(seed: int, count: int) -> list[float]:
    rng = random.Random(seed)
    draws = []
    while len(draws) < count:
        z = rng.gauss(0.0, 1.0)
        if abs(z) <= TRUNCATION_SIGMA:
            draws.append(z)
    return draws


def sweeps(period_ticks: int, u: float) -> int:
    target_ns = u * period_ticks * 1_000_000
    return max(1, round((target_ns - JOB_BASE_NS) / SWEEP_NS))


def set_ids(cv: float) -> list[int]:
    """A zero CV has exactly one possible task set per task count."""
    return list(range(TASK_RANGE[1] - TASK_RANGE[0] + 1)) if cv == 0 else list(range(SETS))


def configuration(mean: int, cv: float, set_id: int) -> dict:
    u = task_u(set_id)
    draws = standard_draws(SEED_BASE + set_id, task_count(set_id))
    task_periods = periods(mean, cv, draws)
    cores = assign_cores(task_periods)
    # Contiguous arrays follow task order: grouped by core, then period.
    rows = sorted((core, period, i) for i, (core, period) in enumerate(zip(cores, task_periods)))
    tasks = [dict(task_id=f't{i:02d}', pattern='cyclic', distinct=64, stride=32,
                  sweeps=sweeps(period, u), core=core, period_ticks=period)
             for i, (core, period, _) in enumerate(rows)]
    horizon = 2 * GRID * unit(mean)
    return dict(workload_id=f'period-tc-m{mean}-cv{round(cv * 100):02d}-s{set_id:02d}-v1',
                family_id='period-distribution-cyclic64-v1',
                policy_id='period-snake-equal-u-v1',
                measurement_contract_id=CONTRACT,
                array_alignment_bytes=32, workload_optimization='O0',
                horizon_ticks=horizon, warmup_ticks=horizon // 2,
                u_repeats=1, diagnostic_only=True, tasks=tasks,
                period_distribution=dict(mean_ticks=mean, cv=cv, set_id=set_id,
                                         seed=SEED_BASE + set_id, draws=draws,
                                         truncation_sigma=TRUNCATION_SIGMA, grid=GRID,
                                         task_u=u, task_count=task_count(set_id)))
