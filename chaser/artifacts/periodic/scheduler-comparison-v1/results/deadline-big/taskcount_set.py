"""Task count x memory pressure: does the Partitioned-first picture hold away from 16 tasks?

Every earlier study used 16 tasks on 4 cores. Here the task count ranges over TASK_RANGE
(12-20; 12, 16 and 20 are multiples of the core count, the rest are not); across the SETS
sets of a cell every count appears equally often. Cells (hl_run's 'heaviness' stratum) x
loads:
  memory   share of the total U held by 768 KiB low-CLS tasks (experiment 8's BL shape,
           as-is): 0, 25 %, 50 %; the 25 % tasks are among the 50 % tasks
  load     per-core nominal U 0.35 or 0.45
The other tasks are high-CLS (center 0.90, CV 0.1). Periods from {20, 40, 80} ms per task
(harmonic rate groups). U shares from Dirichlet(ALPHA), largest <= LIGHT_CAP at the higher
load and smallest >= U_MIN at the lower one (U_MIN keeps every budget inside the model
check's range). Common random numbers: set k keeps its task count, periods, shares, CLS
draws and order in every cell; memory tasks are a prefix, in set order, of the tasks whose
budget holds one 768 KiB sweep at the lower load, ending where the U share comes nearest
the target.
Placements (placement_lib BOUNDARY_POLICIES): wfd, cgb, ra, ra-cgb; G and C2 (1+1+2) follow wfd.
"""

from functools import cache
from pathlib import Path
import random
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
PERIODS = (20, 40, 80)
HYPERPERIOD = 80
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 2, 4
MEMORY_SHARES = (0.0, 0.25, 0.5)
HEAVINESS = tuple(f'mem{round(s * 100):02d}' for s in MEMORY_SHARES)
LOADS = (0.35, 0.45)
SETS = 36
SEED_BASE = 20262001
ALPHA = 8.0
LIGHT_CAP = 0.35
U_MIN = 0.011
HEAVY, HEAVY_RANGE = 0, None
TRENDS = False
OPTIMIZATION = 'O2'
PLACEMENTS = BOUNDARY_POLICIES


def memory_share(heaviness: str) -> float:
    return int(heaviness[3:]) / 100


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
    z = []
    while len(z) < n:
        value = float(rng.normal())
        if abs(value) <= bimodal.TRUNCATION_SIGMA:
            z.append(value)
    periods = [int(p) for p in rng.choice(PERIODS, n)]
    totals = [load * CORES for load in LOADS]
    while True:
        w = rng.dirichlet(np.full(n, ALPHA))
        if w.max() * max(totals) <= LIGHT_CAP and w.min() * min(totals) >= U_MIN:
            return order, z, periods, [float(x) for x in w]


def budgets(load: float, set_id: int) -> list[int]:
    step = mix_set.BUDGET_STEP_NS
    _, _, periods, shares = _draws(set_id)
    return [max(step, round(w * load * CORES * p * 1e6 / step) * step) for w, p in zip(shares, periods)]


@cache
def memory_tasks(set_id: int, share: float) -> tuple[int, ...]:
    """A prefix of the eligible tasks in set order, so a larger share keeps the smaller one's tasks."""
    order, _, _, shares = _draws(set_id)
    room = budgets(min(LOADS), set_id)
    chosen, held = [], 0.0
    for i in (i for i in order if room[i] >= mix_set.big_min_ns()):
        if held + shares[i] / 2 > share:
            break
        chosen.append(i)
        held += shares[i]
    return tuple(chosen)


def roles(heaviness: str, set_id: int) -> list[str]:
    big = set(memory_tasks(set_id, memory_share(heaviness)))
    return ['big' if i in big else 'high' for i in range(task_count(set_id))]


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    _, z, periods, _ = _draws(set_id)
    task_roles, task_budgets = roles(heaviness, set_id), budgets(load, set_id)
    levels = []
    for role, budget, value in zip(task_roles, task_budgets, z):
        if role == 'big':
            levels.append(mix_set.big_level(budget))
        else:
            lv = bimodal.level(mem_set.tables(budget), 'high', 'as-is', mix_set.cls_target('high', value))
            levels.append(dict(lv, cold=bimodal.COLD_LINES))
    job = [b * (1 + lv['u_error']) for b, lv in zip(task_budgets, levels)]
    us = [j / (p * 1e6) for j, p in zip(job, periods)]
    misses = [lv['sweeps'] * (lv['hot'] + lv['cold']) for lv in levels]
    traffic = [m / (j / 1e3) for m, j in zip(misses, job)]
    cores = place(placement, [Item(u=u, period=p, traffic=r, cls=lv['cls'])
                              for u, p, r, lv in zip(us, periods, traffic, levels)], seed=SEED_BASE + set_id)
    tasks = []
    for i, (role, lv) in enumerate(zip(task_roles, levels)):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + lv['cold'],
                    hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=bimodal.STRIDE,
                    sweeps=lv['sweeps'], core=cores[i], period_ticks=periods[i], role=role,
                    mode='low' if role == 'big' else 'high', cls_target=mix_set.cls_target(role, z[i]),
                    cls_planned=lv['cls'], u_target=task_budgets[i] / (periods[i] * 1e6), u_planned=us[i],
                    l1_misses_planned=misses[i], traffic_planned=traffic[i],
                    footprint_kib=(lv['hot'] + lv['cold']) * bimodal.STRIDE / 1024)
        if lv['pad']:
            task['pad_rounds'] = lv['pad']
        if lv['tail']:
            task['pad_tail'] = lv['tail']
        tasks.append(task)
    core_u = [sum(u for u, k in zip(us, cores) if k == core) for core in range(CORES)]
    big_u = sum(u for u, r in zip(us, task_roles) if r == 'big')
    return dict(workload_id=f'task-count-u{round(load * 100):03d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id='task-count-hot-cold-v1', policy_id=f'task-count-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization=OPTIMIZATION,
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us), core_u=core_u, core_cap=CORE_CAP,
                               tasks=len(tasks), memory_share_target=memory_share(heaviness),
                               memory_share=big_u / sum(us)))


def protocol_extra() -> dict:
    return dict(task_range=TASK_RANGE, task_counts=[task_count(k) for k in range(SETS)],
                memory_shares=MEMORY_SHARES, seed_base=SEED_BASE,
                memory_tasks={f'{k}': {h: memory_tasks(k, memory_share(h)) for h in HEAVINESS} for k in range(SETS)})
