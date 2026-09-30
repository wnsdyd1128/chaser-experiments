"""Sample normal-period task sets with equal per-task utilization.

Periods are drawn from N(mean, (cv * mean)^2), truncated at +/-3 sigma, and
rounded in log space to ``unit * d`` where ``d`` divides ``GRID``. The unit is
``mean / REFERENCE_MEAN`` ticks, so every mean uses the same relative grid and
the same standard draws (common random numbers across means and CVs). The
horizon is two grid spans: warm-up and measurement each cover every period.
"""

import math
import random

from chaser.periodic.measurement import CONTRACT

GRID = 180
REFERENCE_MEAN = 10
MEANS = (20, 50, 80, 100, 500)
CVS = (0.0, 0.1, 0.2, 0.3)
SETS = 20
TASKS = 16
CORES = 4
TASK_U = 0.125
TRUNCATION_SIGMA = 3.0
SEED_BASE = 20260929
# Isolated P job CPU of the 64-line O0 cyclic job, 32-byte aligned
# (l1-optimization-sweeps-v1/independent-u-v1): 29.75 us at 4 sweeps and
# 295.7 us at 48 sweeps. The linear fit sets the planned U; the pilot
# re-measures isolated U before the full design runs.
JOB_BASE_NS = 5_580
SWEEP_NS = 6_044
DIVISORS = tuple(d for d in range(1, GRID + 1) if GRID % d == 0)


def unit(mean: int) -> int:
    if type(mean) is not int or mean <= 0 or mean % REFERENCE_MEAN:
        raise ValueError(f'Mean period must be a positive multiple of {REFERENCE_MEAN}')
    return mean // REFERENCE_MEAN


def standard_draws(seed: int) -> list[float]:
    rng = random.Random(seed)
    draws = []
    while len(draws) < TASKS:
        z = rng.gauss(0.0, 1.0)
        if abs(z) <= TRUNCATION_SIGMA:
            draws.append(z)
    return draws


def quantize(value: float, mean: int) -> int:
    """Return the log-nearest grid period in ticks; ties choose the shorter."""
    scale = unit(mean)
    relative = value / scale
    return scale * min(DIVISORS, key=lambda d: (abs(math.log(d / relative)), d))


def periods(mean: int, cv: float, draws: list[float]) -> list[int]:
    if not 0 <= cv * TRUNCATION_SIGMA < 1:
        raise ValueError('Truncated periods must stay positive')
    return [quantize(mean * (1 + cv * z), mean) for z in draws]


def sweeps(period_ticks: int) -> int:
    target_ns = TASK_U * period_ticks * 1_000_000
    return max(1, round((target_ns - JOB_BASE_NS) / SWEEP_NS))


def assign_cores(task_periods: list[int]) -> list[int]:
    """Snake over period-sorted tasks so every core gets one of each rank group."""
    order = sorted(range(len(task_periods)), key=lambda i: (task_periods[i], i))
    cores = [0] * len(task_periods)
    for rank, index in enumerate(order):
        lap, position = divmod(rank, CORES)
        cores[index] = position if lap % 2 == 0 else CORES - 1 - position
    return cores


def set_ids(cv: float) -> list[int]:
    """A zero CV has exactly one possible task set."""
    return [0] if cv == 0 else list(range(SETS))


def configuration(mean: int, cv: float, set_id: int) -> dict:
    draws = standard_draws(SEED_BASE + set_id)
    task_periods = periods(mean, cv, draws)
    cores = assign_cores(task_periods)
    # Contiguous arrays follow task order: grouped by core, then period.
    rows = sorted((core, period, i) for i, (core, period) in
                  enumerate(zip(cores, task_periods)))
    tasks = [dict(task_id=f't{i:02d}', pattern='cyclic', distinct=64, stride=32,
                  sweeps=sweeps(period), core=core, period_ticks=period)
             for i, (core, period, _) in enumerate(rows)]
    horizon = 2 * GRID * unit(mean)
    return dict(workload_id=f'period-dist-m{mean}-cv{round(cv * 100):02d}-s{set_id:02d}-v2',
                family_id='period-distribution-cyclic64-v1',
                policy_id='period-snake-equal-u-v1',
                measurement_contract_id=CONTRACT,
                array_alignment_bytes=32, workload_optimization='O0',
                horizon_ticks=horizon, warmup_ticks=horizon // 2,
                u_repeats=1, diagnostic_only=True, tasks=tasks,
                period_distribution=dict(mean_ticks=mean, cv=cv, set_id=set_id,
                                         seed=SEED_BASE + set_id, draws=draws,
                                         truncation_sigma=TRUNCATION_SIGMA, grid=GRID,
                                         task_u=TASK_U))
