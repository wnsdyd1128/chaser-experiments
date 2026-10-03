"""Period spread x memory mix: where does release-aware placement give way to CLS grouping?

Full factorial over 24 cells (the cell is hl_run's 'heaviness' stratum), SETS sets each:
  period CV  0, 0.1, 0.2, 0.3: period_i = MU (1 + CV z_i), z ~ N(0, 1) truncated at 3,
             rounded in log space to PERIOD_MENU (lcm 240 ms = one hyperperiod)
  low        memory-bound low-CLS tasks, 32 KiB cold region, traffic as-is: 0, 4, 8
  big        low-CLS tasks with a 768 KiB cold region (experiment 8's BL): 0, 2
Every low-CLS task here also has high traffic, so CLS grouping and traffic grouping pick
the same group. The other tasks are high-CLS (center 0.90); mode CV 0.1 (mix_set).
Per-core nominal U LOADS; U shares from Dirichlet(ALPHA), largest task <= LIGHT_CAP,
smallest >= U_MIN. Common random numbers: set k keeps its shares, CLS draws, period
z-scores and task order in every cell. The CV only scales the period z-scores; the low
tasks nest (the four of low 4 are among the eight of low 8) and the two big tasks are the
same tasks wherever there are big tasks, chosen among the tasks whose budget holds one
768 KiB sweep in every period-CV cell; the low tasks never take those two positions.
Placements (placement_lib BOUNDARY_POLICIES): wfd, cgb, ra, ra-cgb.
"""

from functools import cache
import math
from pathlib import Path
import statistics
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'high-load'))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))

import bimodal
from hl_set import CONTRACT
import mem_set
import mix_set
from placement_lib import BOUNDARY_POLICIES, CORE_CAP, CORES, Item, place

TASKS = 16
MU = 40
PERIOD_MENU = (20, 24, 30, 40, 48, 60, 80, 120)
PERIODS = PERIOD_MENU
HYPERPERIOD = 240
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 1, 2
PERIOD_CVS = (0.0, 0.1, 0.2, 0.3)
LOWS = (0, 4, 8)
BIGS = (0, 2)
HEAVINESS = tuple(f'cv{round(cv * 100):02d}-low{low}-big{big}' for cv in PERIOD_CVS for low in LOWS for big in BIGS)
LOADS = (0.4,)
SETS = 10
SEED_BASE = 20261901
ALPHA = 8.0
LIGHT_CAP = 0.35
U_MIN = 0.005
HEAVY, HEAVY_RANGE = 0, None
TRENDS = False  # the 24 cells have no order for hl_run's trend tests
OPTIMIZATION = 'O2'
PLACEMENTS = BOUNDARY_POLICIES


def cell(heaviness: str) -> dict:
    cv, low, big = heaviness.split('-')
    return dict(period_cv=int(cv[2:]) / 100, low=int(low[3:]), big=int(big[3:]))


def _truncated(rng, count):
    out = []
    while len(out) < count:
        value = float(rng.normal())
        if abs(value) <= bimodal.TRUNCATION_SIGMA:
            out.append(value)
    return out


@cache
def _draws(set_id: int):
    rng = np.random.default_rng([SEED_BASE, set_id])
    order = rng.permutation(TASKS).tolist()
    z_cls, z_period = _truncated(rng, TASKS), _truncated(rng, TASKS)
    total = LOADS[0] * CORES
    while True:
        w = rng.dirichlet(np.full(TASKS, ALPHA))
        if w.max() * total <= LIGHT_CAP and w.min() * total >= U_MIN:
            return order, z_cls, z_period, [float(x) for x in w]


def _menu(raw: float) -> int:
    return min(PERIOD_MENU, key=lambda p: (abs(math.log(p / raw)), p))


def periods(cv: float, set_id: int) -> list[int]:
    return [_menu(MU * (1 + cv * z)) for z in _draws(set_id)[2]]


def budgets(load: float, cv: float, set_id: int) -> list[int]:
    step = mix_set.BUDGET_STEP_NS
    return [max(step, round(w * load * CORES * p * 1e6 / step) * step)
            for w, p in zip(_draws(set_id)[3], periods(cv, set_id))]


@cache
def big_positions(set_id: int) -> tuple[int, ...]:
    """The first two tasks in set order whose budget holds one 768 KiB sweep in every cell."""
    room = [min(budgets(load, cv, set_id)[i] for load in LOADS for cv in PERIOD_CVS) for i in range(TASKS)]
    chosen = [i for i in _draws(set_id)[0] if room[i] >= mix_set.big_min_ns()][:max(BIGS)]
    if len(chosen) < max(BIGS):
        raise ValueError(f'set {set_id}: only {len(chosen)} tasks can hold a 768 KiB sweep in every cell')
    return tuple(chosen)


def roles(heaviness: str, set_id: int) -> list[str]:
    c, candidates = cell(heaviness), big_positions(set_id)
    role = {i: 'big' for i in candidates[:c['big']]}
    low = [i for i in _draws(set_id)[0] if i not in candidates][:c['low']]
    role.update({i: 'low' for i in low})
    return [role.get(i, 'high') for i in range(TASKS)]


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    c = cell(heaviness)
    task_periods, task_roles = periods(c['period_cv'], set_id), roles(heaviness, set_id)
    task_budgets, z = budgets(load, c['period_cv'], set_id), _draws(set_id)[1]
    levels = []
    for role, budget, value in zip(task_roles, task_budgets, z):
        if role == 'big':
            levels.append(mix_set.big_level(budget))
        else:
            lv = bimodal.level(mem_set.tables(budget), 'low' if role == 'low' else 'high', 'as-is',
                               mix_set.cls_target(role, value))
            levels.append(dict(lv, cold=bimodal.COLD_LINES))
    job = [b * (1 + lv['u_error']) for b, lv in zip(task_budgets, levels)]
    us = [j / (p * 1e6) for j, p in zip(job, task_periods)]
    misses = [lv['sweeps'] * (lv['hot'] + lv['cold']) for lv in levels]
    traffic = [m / (j / 1e3) for m, j in zip(misses, job)]
    cores = place(placement, [Item(u=u, period=p, traffic=r, cls=lv['cls'])
                              for u, p, r, lv in zip(us, task_periods, traffic, levels)], seed=SEED_BASE + set_id)
    tasks = []
    for i, (role, lv) in enumerate(zip(task_roles, levels)):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + lv['cold'],
                    hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=bimodal.STRIDE,
                    sweeps=lv['sweeps'], core=cores[i], period_ticks=task_periods[i], role=role,
                    mode='low' if role in ('low', 'big') else 'high', cls_target=mix_set.cls_target(role, z[i]),
                    cls_planned=lv['cls'], u_target=task_budgets[i] / (task_periods[i] * 1e6), u_planned=us[i],
                    l1_misses_planned=misses[i], traffic_planned=traffic[i],
                    footprint_kib=(lv['hot'] + lv['cold']) * bimodal.STRIDE / 1024)
        if lv['pad']:
            task['pad_rounds'] = lv['pad']
        if lv['tail']:
            task['pad_tail'] = lv['tail']
        tasks.append(task)
    core_u = [sum(u for u, k in zip(us, cores) if k == core) for core in range(CORES)]
    return dict(workload_id=f'policy-boundary-u{round(load * 100):03d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id='policy-boundary-hot-cold-v1', policy_id=f'policy-boundary-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization=OPTIMIZATION,
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us), core_u=core_u, core_cap=CORE_CAP,
                               realized_period_cv=statistics.pstdev(task_periods) / statistics.mean(task_periods),
                               **c))


def protocol_extra() -> dict:
    return dict(cells={h: cell(h) for h in HEAVINESS}, period_menu=PERIOD_MENU, mu=MU, seed_base=SEED_BASE,
                big_positions={k: big_positions(k) for k in range(SETS)})
