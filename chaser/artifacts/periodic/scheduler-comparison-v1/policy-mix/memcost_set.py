"""Experiment 41 (pre-registered): same CLS and U, memory tasks hitting L2 or going to memory.

Fresh sets with experiment 27's rules (task counts 12-20, Dirichlet(8) shares, high-CLS tasks centered at 0.90,
period CV 0.2 on deadline_set's menu, one hyperperiod of warm-up and three measured). The memory tasks are a
prefix, in set order, of the tasks whose budget fits both memory shapes at every load, ending nearest
MEMORY_SHARE of the U and at most MAX_MEMORY tasks (each memory-bound task holds about 2.6-2.9 MiB of the
16 MiB workload data). The two cells ('heaviness' in hl_run) differ only in the memory tasks' shape:
  l2   experiment 27's 32 KiB low-CLS shape (traffic as-is): L1 misses hit L2 after the first sweep
  mem  the memory-bound shape of mem_calibrate.py (4096 B stride, MEM_COLD lines overflow every touched L2
       set): every L1 miss goes to memory; hot lines, repeats and cold lines are chosen so its CLS is the
       nearest to the l2 task's CLS for the same budget, and its sweeps fill the same budget
Every task keeps its target U and period in both cells, and placements use the target U and CLS, so both
cells place every task on the same core. At the same U the mem tasks issue fewer L1 misses (about 215 ns
each instead of about 68 ns), so their L2 request demand D is lower while their memory demand is higher.
"""

from functools import cache
import json
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
import deadline_set
from hl_set import CONTRACT
from mem_calibrate import MEM_COLD, MEM_HOT, MEM_REPEATS, MEM_STRIDE
import mem_set
import mix_set
from placement_lib import CORE_CAP, CORES, Item, place

STUDY = 'memory-cost'
TASK_RANGE = deadline_set.TASK_RANGE
TASKS = TASK_RANGE
MU = deadline_set.MU
PERIOD_CV = 0.2
PERIOD_MENU = deadline_set.PERIOD_MENU
PERIODS = PERIOD_MENU
HYPERPERIOD = deadline_set.HYPERPERIOD
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 1, 3
MEMORY_ROLE, MEMORY_SHARE, MAX_MEMORY = 'low', 0.25, 4
SHAPES = ('l2', 'mem')
HEAVINESS = tuple(f'{shape}-low{round(MEMORY_SHARE * 100):02d}' for shape in SHAPES)
LOADS = (0.45, 0.5, 0.55, 0.6)
SETS = 24
SEED_BASE = 20264101
ALPHA = 8.0
LIGHT_CAP = 0.35
U_MIN = 0.0125
HEAVY, HEAVY_RANGE = 0, None
TRENDS = True
OPTIMIZATION = 'O2'
PLACEMENTS = ('wfd', 'cgb')
MEM_MODEL_PATH = HERE.parent / 'results/mem-calibration/mem-model.json'
# Budgets the model checks cover (ns): high and low as deadline_set; mem the calibration's sweep range.
MODEL_CHECK_NS = dict(deadline_set.MODEL_CHECK_NS, mem=(500_000, 17_000_000))
DATA_LIMIT = 16 * 1024 ** 2


def shape(heaviness: str) -> str:
    return heaviness.split('-')[0]


@cache
def mem_model() -> dict:
    return json.loads(MEM_MODEL_PATH.read_text())['model']


def mem_cls(hot, repeats, cold):
    """yarda_cpp CLS of the memory-bound shape: only the hot repeats hit (L1); every other access misses L2."""
    return (repeats - 1) * hot / (repeats * hot + cold)


@cache
def mem_level(budget: int, target: float) -> dict:
    """The memory-bound level nearest the target CLS for one job budget; ties choose the smaller U error."""
    model, rows = mem_model(), []
    for hot in MEM_HOT:
        for cold in MEM_COLD:
            exact = (target * cold + hot) / (hot * (1 - target))  # repeats giving the target CLS
            for repeats in {r for r in (math.floor(exact), math.ceil(exact)) if r in MEM_REPEATS}:
                levels = bimodal._levels(model, 'sweeps', budget, hot=np.array([hot]), repeats=repeats, sweeps=None,
                                         pad=0, cold=cold)
                for row in levels[levels[:, bimodal.SWEEPS] >= 1]:
                    c = mem_cls(hot, repeats, cold)
                    rows.append((abs(c - target), abs(row[bimodal.U_ERROR]), hot, cold, repeats, row, c))
    _, _, hot, cold, repeats, row, c = min(rows, key=lambda r: r[:2])
    return dict(hot=hot, repeats=repeats, sweeps=int(row[bimodal.SWEEPS]), pad=0, tail=int(row[bimodal.TAIL]),
                u_error=float(row[bimodal.U_ERROR]), cls=float(c), cold=cold, stride=MEM_STRIDE)


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
    z_cls, z_period = deadline_set.truncated_normals(rng, n), deadline_set.truncated_normals(rng, n)
    while True:
        w = rng.dirichlet(np.full(n, ALPHA))
        if w.max() * max(LOADS) * CORES <= LIGHT_CAP and w.min() * min(LOADS) * CORES >= U_MIN:
            return order, z_cls, z_period, [float(x) for x in w]


def periods(set_id: int) -> list[int]:
    return [deadline_set.menu_period(MU * (1 + PERIOD_CV * z)) for z in _draws(set_id)[2]]


def budgets(load: float, set_id: int) -> list[int]:
    step = mix_set.BUDGET_STEP_NS
    return [max(step, round(w * load * CORES * p * 1e6 / step) * step) for w, p in zip(_draws(set_id)[3], periods(set_id))]


@cache
def memory_tasks(set_id: int) -> tuple[int, ...]:
    order, _, _, shares = _draws(set_id)
    lows = [MODEL_CHECK_NS[MEMORY_ROLE], MODEL_CHECK_NS['mem']]
    room = [[budgets(load, set_id)[i] for load in LOADS] for i in range(task_count(set_id))]
    chosen, held = [], 0.0
    for i in (i for i in order if all(low <= min(room[i]) and max(room[i]) <= high for low, high in lows)):
        if held + shares[i] / 2 > MEMORY_SHARE or len(chosen) == MAX_MEMORY:
            break
        chosen.append(i)
        held += shares[i]
    return tuple(chosen)


def roles(set_id: int) -> list[str]:
    memory = set(memory_tasks(set_id))
    return [MEMORY_ROLE if i in memory else 'high' for i in range(task_count(set_id))]


def levels(load: float, heaviness: str, set_id: int) -> list[dict]:
    z, out = _draws(set_id)[1], []
    for role, budget, value in zip(roles(set_id), budgets(load, set_id), z):
        tables = mem_set.tables(budget)
        if role == MEMORY_ROLE:
            l2 = dict(bimodal.level(tables, 'low', 'as-is', mix_set.cls_target('low', value)), cold=bimodal.COLD_LINES,
                      stride=bimodal.STRIDE)
            out.append(l2 if shape(heaviness) == 'l2' else mem_level(budget, l2['cls']))
        else:
            out.append(dict(bimodal.level(tables, 'high', 'as-is', mix_set.cls_target('high', value)),
                            cold=bimodal.COLD_LINES, stride=bimodal.STRIDE))
    return out


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    task_periods, task_roles, task_budgets = periods(set_id), roles(set_id), budgets(load, set_id)
    lvs, z = levels(load, heaviness, set_id), _draws(set_id)[1]
    targets = [b / (p * 1e6) for b, p in zip(task_budgets, task_periods)]
    job = [b * (1 + lv['u_error']) for b, lv in zip(task_budgets, lvs)]
    us = [j / (p * 1e6) for j, p in zip(job, task_periods)]
    misses = [lv['sweeps'] * (lv['hot'] + lv['cold']) for lv in lvs]
    traffic = [m / (j / 1e3) for m, j in zip(misses, job)]
    # Placement on the target U and the l2 cell's CLS, so both cells put every task on the same core.
    reference = levels(load, HEAVINESS[0], set_id)
    cores = place(placement, [Item(u=u, period=p, traffic=0.0, cls=lv['cls'])
                              for u, p, lv in zip(targets, task_periods, reference)], seed=SEED_BASE + set_id)
    tasks = []
    for i, (role, lv) in enumerate(zip(task_roles, lvs)):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + lv['cold'],
                    hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=lv['stride'],
                    sweeps=lv['sweeps'], core=cores[i], period_ticks=task_periods[i], role=role, mode=role,
                    shape='mem' if lv['stride'] == MEM_STRIDE else 'cache',
                    cls_target=mix_set.cls_target(role, z[i]), cls_planned=lv['cls'], u_target=targets[i],
                    u_planned=us[i], l1_misses_planned=misses[i], traffic_planned=traffic[i],
                    footprint_kib=(lv['hot'] + lv['cold']) * bimodal.STRIDE / 1024,
                    data_kib=(lv['hot'] + lv['cold']) * lv['stride'] / 1024)
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
                high_load=dict(load=load, heaviness=heaviness, shape=shape(heaviness), set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us),
                               core_u=[sum(u for u, k in zip(us, cores) if k == core) for core in range(CORES)],
                               core_cap=CORE_CAP, tasks=len(tasks), memory_share=memory_u / sum(us),
                               realized_period_cv=statistics.pstdev(task_periods) / statistics.mean(task_periods)))


def protocol_extra() -> dict:
    return dict(shapes=SHAPES, period_menu=PERIOD_MENU, mu=MU, period_cv=PERIOD_CV, seed_base=SEED_BASE,
                task_counts=[task_count(k) for k in range(SETS)], model_check_ns=MODEL_CHECK_NS,
                memory_role=MEMORY_ROLE, max_memory=MAX_MEMORY, mem_stride=MEM_STRIDE,
                mem_model_path=str(MEM_MODEL_PATH.relative_to(HERE.parent)),
                memory_tasks={f'{k}': memory_tasks(k) for k in range(SETS)})
