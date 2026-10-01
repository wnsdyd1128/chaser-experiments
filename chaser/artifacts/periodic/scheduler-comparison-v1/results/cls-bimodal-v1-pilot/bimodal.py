"""Bimodal per-task CLS task sets: a high and a low mode with CV around each center.

Sixteen hot-cold tasks (hot H lines repeated R times, then a 32 KiB cold region,
per sweep; S sweeps per job) share a 20 ms period and U = 0.125; the workload
is built with -O2. A fraction p of the tasks is low mode. Near a bound the CV
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

import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cls-distribution'))

from chaser.periodic.measurement import CONTRACT
from clsset import grouped, zigzag

PERIOD = 20
TASKS = 16
CORES = 4
TASK_U = 0.125
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


def cells() -> list[tuple[float, float, str]]:
    return ([(p, cv, 'as-is') for p in LOW_FRACTIONS for cv in CVS]
            + [(0.5, cv, 'matched') for cv in CVS])


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


def job_ns(model: dict, hot, repeats, sweeps, pad, tail=0):
    return features(hot, repeats, sweeps, pad, tail) @ np.array([model[name] for name in FEATURES])


def _levels(model, free, **values):
    """Largest free integer keeping the job within budget, then a tail for the rest.

    Job time is linear in the free variable. Returns rows of the level table
    without CLS; rows whose tail would exceed TAIL_SHARE are dropped.
    """
    budget = TASK_U * PERIOD * 1e6
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


def solve_tables(model: dict) -> dict:
    """Level tables (hot, repeats, sweeps, pad, tail, U error, CLS) per mode."""
    h, s = np.meshgrid(np.array(HIGH_HOT), np.array(HIGH_SWEEPS), indexing='ij')
    high = _levels(model, 'repeats', hot=h, repeats=None, sweeps=s, pad=0)
    h, r = np.meshgrid(np.array(LOW_HOT), np.array(LOW_REPEATS), indexing='ij')
    low = _levels(model, 'sweeps', hot=h, repeats=r, sweeps=None, pad=0)
    tables = {'high': _with_cls(high[high[:, REPEATS] >= 2]), 'as-is': _with_cls(low[low[:, SWEEPS] >= 1])}
    center = tables['high'][_nearest(tables['high'], HIGH_CENTER)]
    misses = center[SWEEPS] * (center[HOT] + COLD_LINES)
    rows = [_levels(model, 'pad', hot=h, repeats=r, pad=None,
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


def configuration(low_fraction: float, cv: float, traffic: str, set_id: int,
                  tables: dict, placement: str) -> dict:
    wanted = targets(low_fraction, cv, set_id)
    levels = [level(tables, mode, traffic, target) for mode, target in wanted]
    values = [lv['cls'] for lv in levels]
    cores = zigzag(values) if placement == 'mixed' else grouped(values)
    tasks = []
    for i, ((mode, target), lv, core) in enumerate(zip(wanted, levels, cores)):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + COLD_LINES,
                    hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=STRIDE,
                    sweeps=lv['sweeps'], core=core, period_ticks=PERIOD, mode=mode, cls_target=target,
                    cls_planned=lv['cls'], u_planned=TASK_U * (1 + lv['u_error']),
                    l1_misses_planned=lv['sweeps'] * (lv['hot'] + COLD_LINES))
        if lv['pad']:
            task['pad_rounds'] = lv['pad']
        if lv['tail']:
            task['pad_tail'] = lv['tail']
        tasks.append(task)
    return dict(workload_id=f'cls-bimodal-p{round(low_fraction * 100):03d}-cv{round(cv * 100):02d}'
                            f'-{traffic}-s{set_id:02d}-{placement}-v1',
                family_id='cls-bimodal-hot-cold-v1', policy_id=f'cls-bimodal-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32,
                workload_optimization='O2', horizon_ticks=(WARMUP_JOBS + MEASURED_JOBS) * PERIOD,
                warmup_ticks=WARMUP_JOBS * PERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                cls_bimodal=dict(low_fraction=low_fraction, cv=cv, traffic=traffic, set_id=set_id,
                                 seed=SEED_BASE + set_id, placement=placement,
                                 high_center=HIGH_CENTER, low_center=LOW_CENTER,
                                 truncation_sigma=TRUNCATION_SIGMA, task_u=TASK_U,
                                 center_l1_misses=float(tables['center_l1_misses'])))
