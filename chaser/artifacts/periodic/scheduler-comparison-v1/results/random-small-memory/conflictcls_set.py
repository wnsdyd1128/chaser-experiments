"""Low CLS from the access pattern, not the working set: conflict-miss tasks in experiment 21's sets.

Experiment 21's low-CLS tasks stream a 32 KiB cold region (twice the L1), so they flush the whole
L1 of their core every sweep. Here the same tasks (same sets, seeds, budgets, periods, roles and
high-CLS tasks as smallmem_set) instead walk 32-64 lines (1-2 KiB of data) CONFLICT_STRIDE apart:
every line of a task falls into one L1 set, so with more lines than the 4 ways each sweep misses
the L1 on every access but the hot repeats and hits the L2 (the lines spread over distinct L2
sets). The L2 request rate matches the streaming tasks; only one L1 set is polluted. yarda's
hierarchy-rd uses set-aware reuse distance, so it sees these misses; the closed-form CLS is
bimodal.cls_model with the cold region of C lines (the cold lines in the same set evict the hot
ones every sweep). Cells: period CV {0, 0.2} x low-CLS share {25 %, 50 %} of experiment 21 (its
low-0 cells have no low-CLS task, so they are not repeated).
Placements (placement_lib BOUNDARY_POLICIES): wfd, cgb, ra, ra-cgb; G and C2 (1+1+2) follow wfd.
"""

from functools import cache
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
from placement_lib import CORE_CAP, CORES, Item, place
import smallmem_set as sm
from smallmem_set import (ALPHA, HEAVY, HEAVY_RANGE, HYPERPERIOD, LIGHT_CAP, LOADS, MEASURED_HYPERPERIODS,
                          OPTIMIZATION, PERIODS, PLACEMENTS, SEED_BASE, SETS, TASKS, U_MIN, WARMUP_HYPERPERIODS,
                          cell, task_count)

HEAVINESS = ('cv00-low25', 'cv00-low50', 'cv20-low25', 'cv20-low50')
TRENDS = False
CONFLICT_STRIDE = 4096  # the L1 way size (16 KiB / 4 ways)
HOT_LINES = range(1, 5)  # at most the associativity, so the repeats hit
COLD_LINES = range(28, 61)
REPEATS = 2


@cache
def conflict_level(budget: int, target: float) -> dict:
    """Nearest-CLS conflict level for one job budget; ties choose the smaller U error."""
    model, rows = mem_set.model(), []
    for cold in COLD_LINES:
        levels = bimodal._levels(model, 'sweeps', budget, hot=np.array(HOT_LINES), repeats=REPEATS, sweeps=None,
                                 pad=0, cold=cold)
        levels = levels[levels[:, bimodal.SWEEPS] >= 1]
        cls = bimodal.cls_model(levels[:, bimodal.HOT], levels[:, bimodal.REPEATS], levels[:, bimodal.SWEEPS], cold)
        rows += [(abs(c - target), abs(row[bimodal.U_ERROR]), cold, row, c) for row, c in zip(levels, cls)]
    _, _, cold, row, cls = min(rows, key=lambda r: r[:2])
    return dict(hot=int(row[bimodal.HOT]), repeats=int(row[bimodal.REPEATS]), sweeps=int(row[bimodal.SWEEPS]),
                pad=0, tail=int(row[bimodal.TAIL]), u_error=float(row[bimodal.U_ERROR]), cls=float(cls), cold=cold)


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    c = cell(heaviness)
    task_periods, task_roles = sm.periods(c['period_cv'], set_id), sm.roles(heaviness, set_id)
    task_budgets, z = sm.budgets(load, c['period_cv'], set_id), sm._draws(set_id)[1]
    levels = []
    for role, budget, value in zip(task_roles, task_budgets, z):
        if role == 'low':
            levels.append(dict(conflict_level(budget, mix_set.cls_target('low', value)), stride=CONFLICT_STRIDE))
        else:
            lv = bimodal.level(mem_set.tables(budget), 'high', 'as-is', mix_set.cls_target('high', value))
            levels.append(dict(lv, cold=bimodal.COLD_LINES, stride=bimodal.STRIDE))
    job = [b * (1 + lv['u_error']) for b, lv in zip(task_budgets, levels)]
    us = [j / (p * 1e6) for j, p in zip(job, task_periods)]
    misses = [lv['sweeps'] * (lv['hot'] + lv['cold']) for lv in levels]
    traffic = [m / (j / 1e3) for m, j in zip(misses, job)]
    cores = place(placement, [Item(u=u, period=p, traffic=r, cls=lv['cls'])
                              for u, p, r, lv in zip(us, task_periods, traffic, levels)], seed=SEED_BASE + set_id)
    tasks = []
    for i, (role, lv) in enumerate(zip(task_roles, levels)):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + lv['cold'],
                    hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=lv['stride'],
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
    return dict(workload_id=f'conflict-cls-u{round(load * 100):03d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id='conflict-cls-hot-cold-v1', policy_id=f'conflict-cls-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization=OPTIMIZATION,
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us), core_u=core_u, core_cap=CORE_CAP,
                               tasks=len(tasks), low_share=low_u / sum(us),
                               realized_period_cv=statistics.pstdev(task_periods) / statistics.mean(task_periods),
                               period_cv=c['period_cv'], low_share_target=c['low_share']))


def protocol_extra() -> dict:
    return dict(cells={h: cell(h) for h in HEAVINESS}, period_menu=sm.PERIOD_MENU, mu=sm.MU, seed_base=SEED_BASE,
                paired_with='small-memory-v1 (same sets; low-CLS tasks stream 32 KiB there)',
                conflict_stride=CONFLICT_STRIDE, hot_lines=list(HOT_LINES), cold_lines=list(COLD_LINES),
                task_range=sm.TASK_RANGE, task_counts=[task_count(k) for k in range(SETS)],
                low_tasks={f'{k}': {f'{s}': sm.low_tasks(k, s) for s in (0.25, 0.5)} for k in range(SETS)})
