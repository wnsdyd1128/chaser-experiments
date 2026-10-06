"""Confirmatory deadline study, 768 KiB type (experiment 27b): fresh sets under L2 capacity contention.

Pre-registered with deadline_set (experiment 27). Experiment 20's 25 % cell (768 KiB low-CLS
tasks, experiment 8's BL shape, as-is) on new sets (SEED_BASE), with deadline_set's period
model and measured window instead of experiment 20's {20, 40, 80} ms. Cells x loads, SETS sets each:
  period CV  0, 0.2 (deadline_set's PERIOD_MENU around MU, lcm 240 ms = one hyperperiod)
  load       per-core nominal U 0.30, 0.35, 0.40, 0.45
768 KiB tasks hold MEMORY_SHARE of the total U; the other tasks are high-CLS (center 0.90,
mode CV 0.1). Task counts, Dirichlet shares and common random numbers as in deadline_set
(largest share <= LIGHT_CAP at 0.45, smallest >= U_MIN at 0.30). 768 KiB tasks are a prefix,
in set order, of the tasks whose budget stays inside the model check's 'big' range at every
load and CV (experiment 20 required only one sweep at the lower load), ending where the U
share comes nearest the target. Warm-up 1 hyperperiod, measured 3. Placements as deadline_set.
"""

from functools import cache
from pathlib import Path
import random
import statistics
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'high-load'))
sys.path.insert(0, str(HERE.parent / 'cls-bimodal'))

import bimodal
from deadline_set import (ALPHA, HEAVY, HEAVY_RANGE, HYPERPERIOD, LIGHT_CAP, MEASURED_HYPERPERIODS, MU,
                          OPTIMIZATION, PERIOD_CVS, PERIOD_MENU, PERIODS, PLACEMENTS, TASK_RANGE, TASKS, TRENDS,
                          U_MIN, WARMUP_HYPERPERIODS, menu_period, truncated_normals)
from hl_set import CONTRACT
import mem_set
import mix_set
from placement_lib import CORE_CAP, CORES, Item, place

STUDY = 'deadline-big'
MEMORY_ROLE, MEMORY_SHARE = 'big', 0.25
HEAVINESS = tuple(f'cv{round(cv * 100):02d}-big{round(MEMORY_SHARE * 100):02d}' for cv in PERIOD_CVS)
LOADS = (0.3, 0.35, 0.4, 0.45)
SETS = 18
SEED_BASE = 20262751
# Budgets the copied policy-mix-v1 model check measured, per shape family (ns).
MODEL_CHECK_NS = {'high': (240_000, 43_170_000), 'big': (1_700_000, 15_150_000)}


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
    levels = []
    for role, budget, value in zip(task_roles, task_budgets, z):
        if role == 'big':
            levels.append(mix_set.big_level(budget))
        else:
            lv = bimodal.level(mem_set.tables(budget), 'high', 'as-is', mix_set.cls_target('high', value))
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
                    mode='low' if role == 'big' else 'high', cls_target=mix_set.cls_target(role, z[i]),
                    cls_planned=lv['cls'], u_target=task_budgets[i] / (task_periods[i] * 1e6), u_planned=us[i],
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
