"""Confirmatory deadline study, 32 KiB type (experiment 27a): fresh sets near the L2 bandwidth boundary.

Pre-registered (experiment 27, EXPERIMENTS.md) before any run: the design of experiment 24's
50 % cells on new sets (SEED_BASE), a finer load grid and a longer measured window. Cells
(hl_run's 'heaviness' stratum) x loads, SETS sets each:
  period CV  0, 0.2: period_i = MU (1 + CV z_i), z ~ N(0, 1) truncated at 3, rounded in log
             space to PERIOD_MENU (lcm 240 ms = one hyperperiod)
  load       per-core nominal U 0.45 to 0.6 in steps of 0.025
Memory-bound low-CLS tasks (32 KiB cold region, traffic as-is; experiment 5's low mode) hold
MEMORY_SHARE of the total U; the other tasks are high-CLS (center 0.90, mode CV 0.1; mix_set).
Every low-CLS task also has high traffic, so CLS grouping and traffic grouping pick the same
group. Task counts range over TASK_RANGE and appear equally often across the sets. U shares
from Dirichlet(ALPHA), largest <= LIGHT_CAP at the highest load, smallest >= U_MIN at the
lowest (U_MIN x 20 ms keeps every budget above the model check's smallest). Common random
numbers: set k keeps its task count, shares, CLS draws, period z-scores, order and low tasks in
every cell and load; the load scales only the budgets. Low tasks are a prefix, in set order, of
the tasks whose budget stays inside the low-as-is model check at every load and CV, ending where
the U share comes nearest the target. Warm-up 1 hyperperiod, measured 3 (experiment 24: 2).
Placements: placement_lib BOUNDARY_POLICIES (wfd, cgb, ra, ra-cgb) and RANDOM_POLICIES (three
random draws from the set's seed); G and C2 (1+1+2) follow wfd. hl_run labels a case by
round(load x 100), so 0.475, 0.525 and 0.575 show as u048, u052 and u057; workload ids carry
the load in thousandths.
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
from placement_lib import BOUNDARY_POLICIES, CORE_CAP, CORES, RANDOM_POLICIES, Item, place

STUDY = 'deadline-small'
TASK_RANGE = (12, 20)
TASKS = TASK_RANGE  # per set: task_count(set_id)
MU = 40
PERIOD_MENU = (20, 24, 30, 40, 48, 60, 80, 120)
PERIODS = PERIOD_MENU
HYPERPERIOD = 240
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 1, 3
PERIOD_CVS = (0.0, 0.2)
MEMORY_ROLE, MEMORY_SHARE = 'low', 0.5
HEAVINESS = tuple(f'cv{round(cv * 100):02d}-low{round(MEMORY_SHARE * 100):02d}' for cv in PERIOD_CVS)
LOADS = (0.45, 0.475, 0.5, 0.525, 0.55, 0.575, 0.6)
SETS = 18
SEED_BASE = 20262701
ALPHA = 8.0
LIGHT_CAP = 0.35
U_MIN = 0.0125
HEAVY, HEAVY_RANGE = 0, None
TRENDS = True  # hl_run's load trend tests per cell
OPTIMIZATION = 'O2'
PLACEMENTS = BOUNDARY_POLICIES + RANDOM_POLICIES
# Budgets the copied policy-mix-v1 model check measured, per shape family (ns).
MODEL_CHECK_NS = {'high': (240_000, 43_170_000), 'low': (230_000, 18_120_000)}


def cell(heaviness: str) -> dict:
    cv, memory = heaviness.split('-')
    return dict(period_cv=int(cv[2:]) / 100, memory_share=int(memory[3:]) / 100)


@cache
def _counts() -> tuple[int, ...]:
    values = list(range(TASK_RANGE[0], TASK_RANGE[1] + 1))
    column = [values[i % len(values)] for i in range(SETS)]
    random.Random(f'{SEED_BASE}-tasks').shuffle(column)
    return tuple(column)


def task_count(set_id: int) -> int:
    return _counts()[set_id]


def truncated_normals(rng, count):
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
    z_cls, z_period = truncated_normals(rng, n), truncated_normals(rng, n)
    while True:
        w = rng.dirichlet(np.full(n, ALPHA))
        if w.max() * max(LOADS) * CORES <= LIGHT_CAP and w.min() * min(LOADS) * CORES >= U_MIN:
            return order, z_cls, z_period, [float(x) for x in w]


def menu_period(raw: float) -> int:
    return min(PERIOD_MENU, key=lambda p: (abs(math.log(p / raw)), p))


def periods(cv: float, set_id: int) -> list[int]:
    return [menu_period(MU * (1 + cv * z)) for z in _draws(set_id)[2]]


def budgets(load: float, cv: float, set_id: int) -> list[int]:
    step = mix_set.BUDGET_STEP_NS
    return [max(step, round(w * load * CORES * p * 1e6 / step) * step)
            for w, p in zip(_draws(set_id)[3], periods(cv, set_id))]


@cache
def memory_tasks(set_id: int) -> tuple[int, ...]:
    """A prefix of the eligible tasks in set order, ending nearest MEMORY_SHARE of the U."""
    order, _, _, shares = _draws(set_id)
    low, high = MODEL_CHECK_NS[MEMORY_ROLE]
    room = [[budgets(load, cv, set_id)[i] for load in LOADS for cv in PERIOD_CVS] for i in range(len(order))]
    chosen, held = [], 0.0
    for i in (i for i in order if low <= min(room[i]) and max(room[i]) <= high):
        if held + shares[i] / 2 > MEMORY_SHARE:
            break
        chosen.append(i)
        held += shares[i]
    return tuple(chosen)


def roles(heaviness: str, set_id: int) -> list[str]:
    memory = set(memory_tasks(set_id))
    return [MEMORY_ROLE if i in memory else 'high' for i in range(task_count(set_id))]


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
    memory_u = sum(u for u, r in zip(us, task_roles) if r == MEMORY_ROLE)
    return dict(workload_id=f'{STUDY}-u{round(load * 1000):04d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id=f'{STUDY}-hot-cold-v1', policy_id=f'{STUDY}-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization=OPTIMIZATION,
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us),
                               core_u=[sum(u for u, k in zip(us, cores) if k == core) for core in range(CORES)],
                               core_cap=CORE_CAP, tasks=len(tasks), memory_share=memory_u / sum(us),
                               realized_period_cv=statistics.pstdev(task_periods) / statistics.mean(task_periods),
                               period_cv=c['period_cv'], memory_share_target=c['memory_share']))


def protocol_extra() -> dict:
    return dict(cells={h: cell(h) for h in HEAVINESS}, period_menu=PERIOD_MENU, mu=MU, seed_base=SEED_BASE,
                task_range=TASK_RANGE, task_counts=[task_count(k) for k in range(SETS)],
                model_check_ns=MODEL_CHECK_NS, memory_role=MEMORY_ROLE,
                memory_tasks={f'{k}': memory_tasks(k) for k in range(SETS)})
