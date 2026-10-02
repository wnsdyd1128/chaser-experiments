"""Bimodal per-task CLS task sets: a high and a low mode with CV around each center.

Sixteen hot-cold tasks (hot H lines repeated R times, then a 32 KiB cold region,
per sweep; S sweeps per job) share a 40 ms period and U = 0.0625 (2.5 ms jobs);
the workload is built with -O2. A fraction p of the tasks is low mode. Near a bound the CV
applies to the distance from that bound: high CLS = 1 - 0.10 (1 + CV z) and
low CLS = 0.08 + 0.05 (1 + CV z), z ~ N(0, 1) truncated at 3 sigma.

Common random numbers: set k draws one task-order permutation and one z per
slot, shared by every p, CV and traffic level; the first round(16 p) slots are
low mode, so low slots are nested across p and CV only scales the same draws.

Traffic 'as-is' fills each job with sweeps. Traffic 'matched' gives every
low-mode task the L1 misses per job of the high-center level and fills the
rest of its job with register-only padding after each load, so low and high
tasks request L2 at the same average rate.

U comes from a linear job-time model fitted to isolated O2 runs (calibrate.py).
The level's free integer is rounded down and a per-sweep padding tail (at most
TAIL_SHARE of the job) absorbs the remainder, so CLS levels stay dense.
CLS is the yarda_cpp cold-job value (alpha 0.5); `cls_model` is its closed form
for this kernel and prepare checks every task against yarda_cpp.
"""

import math
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cls-distribution'))

from chaser.periodic.measurement import CONTRACT
from clsset import grouped, zigzag

# v1 used a 20 ms period (U = 0.125): co-run L2 contention stretched as-is
# low-mode jobs up to 2.75x, so sets with many low tasks missed deadlines. The
# same 2.5 ms jobs at 40 ms keep a per-core demand of at most 27.5 ms.
PERIOD = 40
TASKS = 16
CORES = 4
TASK_U = 0.0625
# Every level fills a 2.5 ms job; the period sets the task U (= JOB_NS / period).
JOB_NS = 2_500_000
COLD_LINES = 1024
STRIDE = 32
WARMUP_JOBS = 10
MEASURED_JOBS = 10
SETS = 20
LOW_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
CVS = (0.0, 0.1, 0.2, 0.3)
HIGH_CENTER, HIGH_BOUND = 0.90, 1.0
LOW_CENTER, LOW_BOUND = 0.13, 0.08
TRUNCATION_SIGMA = 3.0
SEED_BASE = 20261001
# (L1 / LLC capacity) ** 0.5 for the 16 KiB L1 and 2 MiB L2.
LLC_WEIGHT = (16384 / 2097152) ** 0.5
U_PLAN_TOLERANCE = 0.005
TAIL_SHARE = 0.08
# GCC -O2 straight-lines constant loops of one or two trips even under
# `#pragma GCC unroll 1`, so padding and tails use at least three rounds.
MIN_LOOP_ROUNDS = 3
TRAFFIC_TOLERANCE = 0.05
HIGH_HOT = range(16, 257)
HIGH_SWEEPS = range(1, 65)
LOW_HOT = range(1, 256)
# Low mode keeps one kernel shape (hot lines read twice) under both traffic levels.
LOW_REPEATS = (2,)
FEATURES = ('base', 'sweeps', 'region_loops', 'l1_hits', 'l2_hits', 'pad_loops', 'pad_rounds',
            'tail_loops', 'tail_rounds')
# Level table columns.
HOT, REPEATS, SWEEPS, PAD, TAIL, U_ERROR, CLS = range(7)


# 'main' is the v2 design; 'matched-extension' adds traffic-matched cells at the
# other mixed fractions and pairs with the main as-is cells through set ids;
# 'load-level' keeps one CLS condition and its 2.5 ms jobs and varies only the
# period (per-core nominal U 0.125-0.5).
DESIGNS = ('main', 'matched-extension', 'load-level', 'u-imbalance')
LOAD_PERIODS = (80, 40, 30, 20)
# Task-U imbalance (EXPERIMENTS.md 7): the load-level CLS condition at the
# default period, total U 1.0, task U log-normal from a set-specific draw per
# task position that is independent of the CLS draws.
U_CVS = (0.0, 0.25, 0.5, 0.75)
U_TOTAL = 1.0
U_TRUNCATION_SIGMA = 2.0
U_SEED_BASE = 20261201
BUDGET_STEP_NS = 10_000
IMBALANCE_CLS = (0.5, 0.1)
IMBALANCE_PLACEMENTS = ('balanced', 'mixed', 'grouped', 'grouped-balanced')


def cells(design: str = 'main') -> list[tuple[float, float, str]]:
    if design == 'matched-extension':
        return [(p, cv, 'matched') for p in (0.25, 0.75) for cv in CVS]
    if design in ('load-level', 'u-imbalance'):
        return [(0.5, 0.1, 'as-is')]
    return ([(p, cv, 'as-is') for p in LOW_FRACTIONS for cv in CVS]
            + [(0.5, cv, 'matched') for cv in CVS])


def periods(design: str = 'main') -> tuple[int, ...]:
    return LOAD_PERIODS if design == 'load-level' else (PERIOD,)


def u_cvs(design: str = 'main') -> tuple[float, ...]:
    return U_CVS if design == 'u-imbalance' else (0.0,)


def set_ids(low_fraction: float, cv: float) -> list[int]:
    """Single-mode sets without dispersion are identical, so only set 0 runs."""
    return [0] if cv == 0 and low_fraction in (0.0, 1.0) else list(range(SETS))


def placements(low_fraction: float) -> tuple[str, ...]:
    return ('mixed', 'grouped') if 0 < low_fraction < 1 else ('mixed',)


def draws(set_id: int) -> tuple[list[int], list[float]]:
    """Return the slot -> task-position permutation and one truncated z per slot."""
    rng = random.Random(SEED_BASE + set_id)
    order = list(range(TASKS))
    rng.shuffle(order)
    z = []
    while len(z) < TASKS:
        value = rng.gauss(0.0, 1.0)
        if abs(value) <= TRUNCATION_SIGMA:
            z.append(value)
    return order, z


def targets(low_fraction: float, cv: float, set_id: int) -> list[tuple[str, float]]:
    """Return (mode, CLS target) per task position."""
    order, z = draws(set_id)
    low = round(TASKS * low_fraction)
    result = [None] * TASKS
    for slot, (position, value) in enumerate(zip(order, z)):
        if slot < low:
            result[position] = ('low', LOW_BOUND + (LOW_CENTER - LOW_BOUND) * (1 + cv * value))
        else:
            result[position] = ('high', HIGH_BOUND - (HIGH_BOUND - HIGH_CENTER) * (1 + cv * value))
    return result


def cls_model(hot, repeats, sweeps, cold=COLD_LINES):
    """yarda_cpp CLS of one cold job: hot lines hit L1 after their first pass in a
    sweep, the cold region evicts them, and only the first sweep misses L2."""
    l1 = sweeps * (repeats - 1) * hot
    llc = (sweeps - 1) * (hot + cold)
    return (l1 + LLC_WEIGHT * llc) / (sweeps * (repeats * hot + cold))


def features(hot, repeats, sweeps, pad, tail, cold=COLD_LINES):
    """Steady-state isolated job counts: every sweep refills hot and cold lines from L2."""
    hot, repeats, sweeps, pad, tail = (np.asarray(v, dtype=float)
                                       for v in (hot, repeats, sweeps, pad, tail))
    accesses = sweeps * (repeats * hot + cold)
    return np.stack(np.broadcast_arrays(
        np.ones_like(accesses), sweeps, sweeps * (repeats + 1), sweeps * (repeats - 1) * hot,
        sweeps * (hot + cold), accesses * (pad > 0), accesses * pad, sweeps * (tail > 0),
        sweeps * tail), axis=-1)


def job_ns(model: dict, hot, repeats, sweeps, pad, tail=0, cold=COLD_LINES):
    return features(hot, repeats, sweeps, pad, tail, cold) @ np.array([model[name] for name in FEATURES])


def _levels(model, free, budget, **values):
    """Largest free integer keeping the job within budget, then a tail for the rest.

    Job time is linear in the free variable. Returns rows of the level table
    without CLS; rows whose tail would exceed TAIL_SHARE are dropped.
    """
    values = dict(values, tail=0)
    low = job_ns(model, **{**values, free: 1})
    slope = job_ns(model, **{**values, free: 2}) - low
    grid = {**values, free: np.floor(1 + (budget - low) / slope)}
    rest = budget - job_ns(model, **grid)
    sweeps = np.asarray(grid['sweeps'], dtype=float)
    tail = np.maximum(0, np.floor((rest - sweeps * model['tail_loops']) / (sweeps * model['tail_rounds'])))
    tail[tail < MIN_LOOP_ROUNDS] = 0
    job = job_ns(model, **{**grid, 'tail': tail})
    rows = np.stack(np.broadcast_arrays(grid['hot'], grid['repeats'], grid['sweeps'], grid['pad'],
                                        tail, job / budget - 1), axis=-1).reshape(-1, 6)
    share = (job - job_ns(model, **grid)) / budget
    return rows[(np.abs(rows[:, U_ERROR]) <= U_PLAN_TOLERANCE) & (share.reshape(-1) <= TAIL_SHARE)]


def _with_cls(rows):
    return np.column_stack([rows, cls_model(rows[:, HOT], rows[:, REPEATS], rows[:, SWEEPS])])


def solve_tables(model: dict, budget: float = JOB_NS) -> dict:
    """Level tables (hot, repeats, sweeps, pad, tail, U error, CLS) per mode for one job budget (ns)."""
    h, s = np.meshgrid(np.array(HIGH_HOT), np.array(HIGH_SWEEPS), indexing='ij')
    high = _levels(model, 'repeats', budget, hot=h, repeats=None, sweeps=s, pad=0)
    h, r = np.meshgrid(np.array(LOW_HOT), np.array(LOW_REPEATS), indexing='ij')
    low = _levels(model, 'sweeps', budget, hot=h, repeats=r, sweeps=None, pad=0)
    tables = {'high': _with_cls(high[high[:, REPEATS] >= 2]), 'as-is': _with_cls(low[low[:, SWEEPS] >= 1])}
    center = tables['high'][_nearest(tables['high'], HIGH_CENTER)]
    misses = center[SWEEPS] * (center[HOT] + COLD_LINES)
    rows = [_levels(model, 'pad', budget, hot=h, repeats=r, pad=None,
                    sweeps=np.maximum(1, np.round(misses / (h + COLD_LINES)) + offset))
            for offset in (-1, 0, 1)]
    matched = np.concatenate(rows)
    traffic = matched[:, SWEEPS] * (matched[:, HOT] + COLD_LINES) / misses - 1
    tables['matched'] = _with_cls(matched[(matched[:, PAD] >= MIN_LOOP_ROUNDS)
                                          & (np.abs(traffic) <= TRAFFIC_TOLERANCE)])
    tables['center_l1_misses'] = misses
    return tables


def _nearest(table, target):
    """Closest CLS; ties choose the smaller U error."""
    return int(np.lexsort((np.abs(table[:, U_ERROR]), np.abs(table[:, CLS] - target)))[0])


def level(tables: dict, mode: str, traffic: str, target: float) -> dict:
    table = tables['high' if mode == 'high' else traffic]
    row = table[_nearest(table, target)]
    return dict(hot=int(row[HOT]), repeats=int(row[REPEATS]), sweeps=int(row[SWEEPS]),
                pad=int(row[PAD]), tail=int(row[TAIL]), u_error=float(row[U_ERROR]), cls=float(row[CLS]))


def _tasks(wanted, levels, cores, period, task_us):
    tasks = []
    for i, ((mode, target), lv, core, task_u) in enumerate(zip(wanted, levels, cores, task_us)):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + COLD_LINES,
                    hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=STRIDE,
                    sweeps=lv['sweeps'], core=core, period_ticks=period, mode=mode, cls_target=target,
                    cls_planned=lv['cls'], u_planned=task_u * (1 + lv['u_error']),
                    l1_misses_planned=lv['sweeps'] * (lv['hot'] + COLD_LINES))
        if lv['pad']:
            task['pad_rounds'] = lv['pad']
        if lv['tail']:
            task['pad_tail'] = lv['tail']
        tasks.append(task)
    return tasks


def configuration(low_fraction: float, cv: float, traffic: str, set_id: int,
                  tables: dict, placement: str, period: int = PERIOD) -> dict:
    """At the default period the configuration is byte-identical to the v2 design."""
    task_u = JOB_NS / (period * 1e6)
    wanted = targets(low_fraction, cv, set_id)
    levels = [level(tables, mode, traffic, target) for mode, target in wanted]
    values = [lv['cls'] for lv in levels]
    cores = zigzag(values) if placement == 'mixed' else grouped(values)
    tasks = _tasks(wanted, levels, cores, period, [task_u] * TASKS)
    period_tag = '' if period == PERIOD else f'-t{period:03d}'
    return dict(workload_id=f'cls-bimodal-p{round(low_fraction * 100):03d}-cv{round(cv * 100):02d}'
                            f'-{traffic}{period_tag}-s{set_id:02d}-{placement}-v2',
                family_id='cls-bimodal-hot-cold-v1', policy_id=f'cls-bimodal-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32,
                workload_optimization='O2', horizon_ticks=(WARMUP_JOBS + MEASURED_JOBS) * period,
                warmup_ticks=WARMUP_JOBS * period, u_repeats=1, diagnostic_only=True, tasks=tasks,
                cls_bimodal=dict(low_fraction=low_fraction, cv=cv, traffic=traffic, set_id=set_id,
                                 seed=SEED_BASE + set_id, placement=placement,
                                 high_center=HIGH_CENTER, low_center=LOW_CENTER,
                                 truncation_sigma=TRUNCATION_SIGMA, task_u=task_u,
                                 center_l1_misses=float(tables['center_l1_misses'])))


def task_utilizations(u_cv: float, set_id: int) -> list[float]:
    """Log-normal task U with coefficient of variation u_cv, scaled to U_TOTAL.

    One standard draw per task position (truncated at U_TRUNCATION_SIGMA) is
    shared by every u_cv, so only the spread changes between CV levels.
    """
    rng = random.Random(U_SEED_BASE + set_id)
    z = []
    while len(z) < TASKS:
        value = rng.gauss(0.0, 1.0)
        if abs(value) <= U_TRUNCATION_SIGMA:
            z.append(value)
    sigma = math.sqrt(math.log(1 + u_cv ** 2))
    weights = [math.exp(sigma * value) for value in z]
    return [U_TOTAL * w / sum(weights) for w in weights]


def imbalance_budgets(u_cv: float, set_id: int) -> list[int]:
    """Job budgets (ns) of a task set, rounded to BUDGET_STEP_NS."""
    return [max(BUDGET_STEP_NS, round(u * PERIOD * 1e6 / BUDGET_STEP_NS) * BUDGET_STEP_NS)
            for u in task_utilizations(u_cv, set_id)]


def balanced_cores(utilizations, indices, core_ids) -> dict[int, int]:
    """Largest U first onto the least-loaded core that still holds fewer than its share."""
    share = len(indices) // len(core_ids)
    load, count, cores = dict.fromkeys(core_ids, 0.0), dict.fromkeys(core_ids, 0), {}
    for i in sorted(indices, key=lambda i: (-utilizations[i], i)):
        core = min((c for c in core_ids if count[c] < share), key=lambda c: (load[c], c))
        cores[i] = core
        load[core] += utilizations[i]
        count[core] += 1
    return cores


def imbalance_cores(placement: str, values, modes, utilizations) -> list[int]:
    if placement == 'mixed':
        return zigzag(values)
    if placement == 'grouped':
        return grouped(values)
    if placement == 'balanced':
        cores = balanced_cores(utilizations, range(TASKS), range(CORES))
    elif placement == 'grouped-balanced':
        low = [i for i, m in enumerate(modes) if m == 'low']
        high = [i for i, m in enumerate(modes) if m == 'high']
        cores = {**balanced_cores(utilizations, low, range(0, CORES // 2)),
                 **balanced_cores(utilizations, high, range(CORES // 2, CORES))}
    else:
        raise ValueError(f'Unknown placement: {placement}')
    return [cores[i] for i in range(TASKS)]


def imbalance_configuration(u_cv: float, set_id: int, tables_for, placement: str) -> dict:
    """Task-U imbalance set: per-task job budgets, CLS levels from each budget's table."""
    low_fraction, cv = IMBALANCE_CLS
    wanted = targets(low_fraction, cv, set_id)
    budgets = imbalance_budgets(u_cv, set_id)
    levels = [level(tables_for(b), mode, 'as-is', target) for (mode, target), b in zip(wanted, budgets)]
    task_us = [b / (PERIOD * 1e6) for b in budgets]
    cores = imbalance_cores(placement, [lv['cls'] for lv in levels], [m for m, _ in wanted], task_us)
    tasks = _tasks(wanted, levels, cores, PERIOD, task_us)
    for task, task_u in zip(tasks, task_us):
        task['u_target'] = task_u
    return dict(workload_id=f'u-imbalance-ucv{round(u_cv * 100):03d}-s{set_id:02d}-{placement}-v1',
                family_id='u-imbalance-hot-cold-v1', policy_id=f'u-imbalance-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32,
                workload_optimization='O2', horizon_ticks=(WARMUP_JOBS + MEASURED_JOBS) * PERIOD,
                warmup_ticks=WARMUP_JOBS * PERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                u_imbalance=dict(u_cv=u_cv, set_id=set_id, u_seed=U_SEED_BASE + set_id,
                                 cls_seed=SEED_BASE + set_id, low_fraction=low_fraction, cls_cv=cv,
                                 placement=placement, total_u=U_TOTAL, truncation_sigma=U_TRUNCATION_SIGMA,
                                 budget_step_ns=BUDGET_STEP_NS))
