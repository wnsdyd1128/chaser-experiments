"""Multi-factor task sets: which Partitioned placement wins when several mechanisms co-occur?

Sixteen hot-cold O2 tasks per set. Each set draws six factors; across the SETS sets
every level appears equally often and each factor is shuffled on its own stream:
  periods  single (every task 40 ms) or mixed (each task from {20, 40, 80} ms)
  low      memory-bound low-CLS tasks with the 32 KiB cold region (center 0.13): 0, 4, 8
  traffic  those tasks' traffic: as-is (loads fill the job) or matched (the high-CLS
           center's L1 misses per job, register padding for the rest; bimodal)
  big      low-CLS tasks with a 768 KiB cold region (experiment 8's BL, as-is): 0, 2, 4
  alpha    Dirichlet concentration of the light tasks' U shares: 32 (near equal) or 4
  heavy    one high-CLS task with U ~ Uniform(0.5, 0.6), the same at both loads: 0 or 1
The other tasks are high-CLS (center 0.90); mode CV 0.1 around each center.
Per-core nominal U 0.3 or 0.45 (isolated runs). Common random numbers: set k keeps
its factors, periods, roles, CLS draws and shares at both loads; the load scales the
light tasks' U only. A big task needs a job of at least one 768 KiB sweep, so big
tasks are drawn among the tasks whose budget at the lower load allows one (they lean
toward longer periods). Each job budget (U x period, 10 us steps) gets a level from
the fitted O2 model (mem_set.tables for the 32 KiB kinds, big_level here).

Placements (placement_lib): wfd, tg, ra, ra-tg on static per-task values (planned U,
period, traffic = planned L1 misses per job / planned job time). The cluster domains
of C2 (1+1+2) follow wfd. The CLS-keyed cg and ra-cg (mix_cls_set) also read the
planned CLS.
"""

from functools import cache
import random
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'high-load'))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))

import bimodal
from hl_set import CONTRACT
import mem_set
from placement_lib import CORE_CAP, CORES, POLICIES, Item, place

TASKS = 16
PERIODS = (20, 40, 80)
SINGLE_PERIOD = 40
HYPERPERIOD = 80
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 2, 4
LOADS = (0.3, 0.45)
HEAVINESS = ('mix',)  # one stratum; hl_run's case key
SETS = 80
SEED_BASE = 20261701
FACTORS = dict(periods=('single', 'mixed'), low=(0, 4, 8), traffic=('as-is', 'matched'), big=(0, 2, 4),
               alpha=(32.0, 4.0), heavy=(0, 1))
ALPHA, HEAVY = FACTORS['alpha'], FACTORS['heavy']
HEAVY_RANGE = (0.5, 0.6)
LIGHT_CAP = 0.35
U_MIN = 0.005
CLS_CV = 0.1
BIG_LINES = 24576
BUDGET_STEP_NS = 10_000
OPTIMIZATION = 'O2'
PLACEMENTS = POLICIES


@cache
def _factor_table() -> tuple[dict, ...]:
    columns = {}
    for name, levels in FACTORS.items():
        column = [levels[i % len(levels)] for i in range(SETS)]
        random.Random(f'{SEED_BASE}-{name}').shuffle(column)
        columns[name] = column
    return tuple({name: columns[name][k] for name in FACTORS} for k in range(SETS))


def factors(set_id: int) -> dict:
    return dict(_factor_table()[set_id])


@cache
def _draws(set_id: int):
    """Per-set random structure, drawn in a fixed order so factors do not shift the streams."""
    rng = np.random.default_rng([SEED_BASE, set_id])
    order = rng.permutation(TASKS).tolist()
    z = []
    while len(z) < TASKS:
        value = float(rng.normal())
        if abs(value) <= bimodal.TRUNCATION_SIGMA:
            z.append(value)
    heavy_u = float(rng.uniform(*HEAVY_RANGE))
    mixed = [int(p) for p in rng.choice(PERIODS, TASKS)]
    f = factors(set_id)
    light = TASKS - f['heavy']
    totals = [load * CORES - heavy_u * f['heavy'] for load in LOADS]
    while True:
        w = rng.dirichlet(np.full(light, f['alpha']))
        if w.max() * max(totals) <= LIGHT_CAP and w.min() * min(totals) >= U_MIN:
            break
    return order, z, heavy_u, mixed, [float(x) for x in w]


def task_periods(set_id: int) -> list[int]:
    return [SINGLE_PERIOD] * TASKS if factors(set_id)['periods'] == 'single' else _draws(set_id)[3]


def _heavy_position(set_id: int):
    return _draws(set_id)[0][0] if factors(set_id)['heavy'] else None


def target_u(load: float, set_id: int) -> list[float]:
    order, _, heavy_u, _, shares = _draws(set_id)
    heavy = _heavy_position(set_id)
    light = iter(w * (load * CORES - (heavy_u if heavy is not None else 0.0)) for w in shares)
    return [heavy_u if i == heavy else next(light) for i in range(TASKS)]


def budgets(load: float, set_id: int) -> list[int]:
    return [max(BUDGET_STEP_NS, round(u * p * 1e6 / BUDGET_STEP_NS) * BUDGET_STEP_NS)
            for u, p in zip(target_u(load, set_id), task_periods(set_id))]


def big_min_ns() -> float:
    return float(bimodal.job_ns(mem_set.model(), 1, 2, 1, 0, 0, BIG_LINES))


@cache
def roles(set_id: int) -> tuple[str, ...]:
    f, order = factors(set_id), _draws(set_id)[0]
    heavy = _heavy_position(set_id)
    eligible = budgets(min(LOADS), set_id)
    role = {heavy: 'heavy'} if heavy is not None else {}
    big = [i for i in order if i not in role and eligible[i] >= big_min_ns()][:f['big']]
    if len(big) < f['big']:
        raise ValueError(f'set {set_id}: only {len(big)} tasks can hold a 768 KiB sweep')
    role.update({i: 'big' for i in big})
    role.update({i: 'low' for i in [i for i in order if i not in role][:f['low']]})
    return tuple(role.get(i, 'high') for i in range(TASKS))


def big_level(budget: float) -> dict:
    """1-line hot x 2 + 768 KiB cold per sweep; most sweeps that fit, a tail for the rest."""
    model = mem_set.model()
    one = big_min_ns()
    sweeps = int((budget - one) // (float(bimodal.job_ns(model, 1, 2, 2, 0, 0, BIG_LINES)) - one)) + 1
    if sweeps < 1:
        raise ValueError(f'{budget} ns cannot hold one 768 KiB sweep')
    rest = budget - float(bimodal.job_ns(model, 1, 2, sweeps, 0, 0, BIG_LINES))
    tail = int((rest - sweeps * model['tail_loops']) // (sweeps * model['tail_rounds']))
    tail = tail if tail >= bimodal.MIN_LOOP_ROUNDS else 0
    job = float(bimodal.job_ns(model, 1, 2, sweeps, 0, tail, BIG_LINES))
    return dict(hot=1, repeats=2, sweeps=sweeps, pad=0, tail=tail, cold=BIG_LINES, u_error=job / budget - 1,
                cls=float(bimodal.cls_model(1, 2, sweeps, BIG_LINES)))


def cls_target(role: str, z: float):
    if role == 'big':
        return None
    if role == 'low':
        return bimodal.LOW_BOUND + (bimodal.LOW_CENTER - bimodal.LOW_BOUND) * (1 + CLS_CV * z)
    return bimodal.HIGH_BOUND - (bimodal.HIGH_BOUND - bimodal.HIGH_CENTER) * (1 + CLS_CV * z)


def levels(load: float, set_id: int) -> list[dict]:
    traffic, z = factors(set_id)['traffic'], _draws(set_id)[1]
    out = []
    for role, budget, value in zip(roles(set_id), budgets(load, set_id), z):
        if role == 'big':
            out.append(big_level(budget))
            continue
        mode = 'low' if role == 'low' else 'high'
        lv = bimodal.level(mem_set.tables(budget), mode, traffic, cls_target(role, value))
        out.append(dict(lv, cold=bimodal.COLD_LINES))
    return out


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    if heaviness != 'mix':
        raise ValueError(f'Unknown stratum: {heaviness}')
    f, periods, task_roles = factors(set_id), task_periods(set_id), roles(set_id)
    task_budgets, task_levels, z = budgets(load, set_id), levels(load, set_id), _draws(set_id)[1]
    job = [b * (1 + lv['u_error']) for b, lv in zip(task_budgets, task_levels)]
    us = [j / (p * 1e6) for j, p in zip(job, periods)]
    misses = [lv['sweeps'] * (lv['hot'] + lv['cold']) for lv in task_levels]
    traffic = [m / (j / 1e3) for m, j in zip(misses, job)]
    cores = place(placement, [Item(u=u, period=p, traffic=r, cls=lv['cls'])
                              for u, p, r, lv in zip(us, periods, traffic, task_levels)], seed=SEED_BASE + set_id)
    tasks = []
    for i, (role, lv) in enumerate(zip(task_roles, task_levels)):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + lv['cold'],
                    hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=bimodal.STRIDE,
                    sweeps=lv['sweeps'], core=cores[i], period_ticks=periods[i], role=role,
                    mode='low' if role in ('low', 'big') else 'high', cls_target=cls_target(role, z[i]),
                    cls_planned=lv['cls'], u_target=task_budgets[i] / (periods[i] * 1e6), u_planned=us[i],
                    l1_misses_planned=misses[i], traffic_planned=traffic[i],
                    footprint_kib=(lv['hot'] + lv['cold']) * bimodal.STRIDE / 1024)
        if lv['pad']:
            task['pad_rounds'] = lv['pad']
        if lv['tail']:
            task['pad_tail'] = lv['tail']
        tasks.append(task)
    core_u = [sum(u for u, c in zip(us, cores) if c == core) for core in range(CORES)]
    return dict(workload_id=f'policy-mix-u{round(load * 100):03d}-s{set_id:02d}-{placement}-v1',
                family_id='policy-mix-hot-cold-v1', policy_id=f'policy-mix-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization=OPTIMIZATION,
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us), core_u=core_u, core_cap=CORE_CAP,
                               factors=f))
