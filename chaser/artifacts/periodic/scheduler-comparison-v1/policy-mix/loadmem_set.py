"""Small-memory low-CLS tasks x per-core load: does CLS-aware placement keep deadlines longer?

Experiment 21's task sets pushed toward the schedulability boundary experiment 11 found between
per-core U 0.45 and 0.6 with half the tasks memory-bound. Cells (hl_run's 'heaviness' stratum)
x loads, SETS sets each:
  period CV  0, 0.2: period_i = MU (1 + CV z_i), z ~ N(0, 1) truncated at 3, rounded in log
             space to PERIOD_MENU (lcm 240 ms = one hyperperiod)
  low        share of the total U held by memory-bound low-CLS tasks (32 KiB cold region,
             traffic as-is; experiment 5's low mode): 25 %, 50 %
  load       per-core nominal U 0.45, 0.5, 0.55, 0.6
Every low-CLS task also has high traffic, so CLS grouping and traffic grouping pick the same
group. The other tasks are high-CLS (center 0.90, mode CV 0.1; mix_set). Task counts range over
TASK_RANGE and appear equally often across the sets. U shares from Dirichlet(ALPHA), largest
<= LIGHT_CAP at the highest load, smallest >= U_MIN at the lowest. Common random numbers: set k
keeps its task count, shares, CLS draws, period z-scores and order in every cell and load; the
load scales only the budgets. Low tasks are a prefix, in set order, of the tasks whose budget
stays inside the low-as-is model check at every load and CV (so the 25 % tasks are among the
50 % tasks), ending where the U share comes nearest the target.
Placements (placement_lib BOUNDARY_POLICIES): wfd, cgb, ra, ra-cgb; G and C2 (1+1+2) follow wfd.
"""

from functools import cache
import math
import random
import statistics
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
import mix_set
from placement_lib import BOUNDARY_POLICIES, CORE_CAP, CORES, Item, place

TASK_RANGE = (12, 20)
TASKS = TASK_RANGE  # per set: task_count(set_id)
MU = 40
PERIOD_MENU = (20, 24, 30, 40, 48, 60, 80, 120)
PERIODS = PERIOD_MENU
HYPERPERIOD = 240
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 1, 2
PERIOD_CVS = (0.0, 0.2)
LOW_SHARES = (0.25, 0.5)
HEAVINESS = tuple(f'cv{round(cv * 100):02d}-low{round(s * 100):02d}' for cv in PERIOD_CVS for s in LOW_SHARES)
LOADS = (0.45, 0.5, 0.55, 0.6)
SETS = 18
SEED_BASE = 20262401
ALPHA = 8.0
LIGHT_CAP = 0.35
U_MIN = 0.011
HEAVY, HEAVY_RANGE = 0, None
TRENDS = True  # hl_run's load trend tests per cell
OPTIMIZATION = 'O2'
PLACEMENTS = BOUNDARY_POLICIES
# Budgets the copied policy-mix-v1 model check measured, per shape family (ns).
MODEL_CHECK_NS = {'high': (240_000, 43_170_000), 'low': (230_000, 18_120_000)}


def cell(heaviness: str) -> dict:
    cv, low = heaviness.split('-')
    return dict(period_cv=int(cv[2:]) / 100, low_share=int(low[3:]) / 100)


@cache
def _counts() -> tuple[int, ...]:
    values = list(range(TASK_RANGE[0], TASK_RANGE[1] + 1))
    column = [values[i % len(values)] for i in range(SETS)]
    random.Random(f'{SEED_BASE}-tasks').shuffle(column)
    return tuple(column)


def task_count(set_id: int) -> int:
    return _counts()[set_id]


def _truncated(rng, count):
    out = []
    while len(out) < count:
        value = float(rng.normal())
        if abs(value) <= bimodal.TRUNCATION_SIGMA:
            out.append(value)
    return out


@cache
def _draws(set_id: int):
    n = task_count(set_id)
    rng = np.random.default_rng([SEED_BASE, set_id])
    order = rng.permutation(n).tolist()
    z_cls, z_period = _truncated(rng, n), _truncated(rng, n)
    while True:
        w = rng.dirichlet(np.full(n, ALPHA))
        if w.max() * max(LOADS) * CORES <= LIGHT_CAP and w.min() * min(LOADS) * CORES >= U_MIN:
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
def low_tasks(set_id: int, share: float) -> tuple[int, ...]:
    """A prefix of the eligible tasks in set order, so a larger share keeps the smaller one's tasks."""
    order, _, _, shares = _draws(set_id)
    low, high = MODEL_CHECK_NS['low']
    room = [[budgets(load, cv, set_id)[i] for load in LOADS for cv in PERIOD_CVS] for i in range(len(order))]
    chosen, held = [], 0.0
    for i in (i for i in order if low <= min(room[i]) and max(room[i]) <= high):
        if held + shares[i] / 2 > share:
            break
        chosen.append(i)
        held += shares[i]
    return tuple(chosen)


def roles(heaviness: str, set_id: int) -> list[str]:
    low = set(low_tasks(set_id, cell(heaviness)['low_share']))
    return ['low' if i in low else 'high' for i in range(task_count(set_id))]


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    c = cell(heaviness)
    task_periods, task_roles = periods(c['period_cv'], set_id), roles(heaviness, set_id)
    task_budgets, z = budgets(load, c['period_cv'], set_id), _draws(set_id)[1]
    levels = [dict(bimodal.level(mem_set.tables(budget), role, 'as-is', mix_set.cls_target(role, value)),
                   cold=bimodal.COLD_LINES) for role, budget, value in zip(task_roles, task_budgets, z)]
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
                    sweeps=lv['sweeps'], core=cores[i], period_ticks=task_periods[i], role=role, mode=role,
                    cls_target=mix_set.cls_target(role, z[i]), cls_planned=lv['cls'],
                    u_target=task_budgets[i] / (task_periods[i] * 1e6), u_planned=us[i],
                    l1_misses_planned=misses[i], traffic_planned=traffic[i],
                    footprint_kib=(lv['hot'] + lv['cold']) * bimodal.STRIDE / 1024)
        if lv['pad']:
            task['pad_rounds'] = lv['pad']
        if lv['tail']:
            task['pad_tail'] = lv['tail']
        tasks.append(task)
    core_u = [sum(u for u, k in zip(us, cores) if k == core) for core in range(CORES)]
    low_u = sum(u for u, r in zip(us, task_roles) if r == 'low')
    return dict(workload_id=f'small-memory-load-u{round(load * 100):03d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id='small-memory-load-hot-cold-v1', policy_id=f'small-memory-load-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization=OPTIMIZATION,
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us), core_u=core_u, core_cap=CORE_CAP,
                               tasks=len(tasks), low_share=low_u / sum(us),
                               realized_period_cv=statistics.pstdev(task_periods) / statistics.mean(task_periods),
                               period_cv=c['period_cv'], low_share_target=c['low_share']))


def protocol_extra() -> dict:
    return dict(cells={h: cell(h) for h in HEAVINESS}, period_menu=PERIOD_MENU, mu=MU, seed_base=SEED_BASE,
                task_range=TASK_RANGE, task_counts=[task_count(k) for k in range(SETS)],
                model_check_ns=MODEL_CHECK_NS,
                low_tasks={f'{k}': {f'{s}': low_tasks(k, s) for s in LOW_SHARES} for k in range(SETS)})
