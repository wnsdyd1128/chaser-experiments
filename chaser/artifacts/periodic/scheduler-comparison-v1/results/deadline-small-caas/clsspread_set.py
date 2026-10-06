"""CLS mean x CLS spread x period spread x task count: does CLS-aware placement help when CLS is continuous?

Experiment 3's question (CLS mean and spread) in the current setting: O2 hot-cold jobs, unequal
U, periods around 40 ms, 12-20 tasks. Cells (hl_run's 'heaviness' stratum), SETS sets each,
per-core nominal U LOADS:
  CLS mean   0.3, 0.6, 0.9 (not 0.5: that is the absolute grouping's cut, so a set without
             spread would split on rounding noise)
  CLS SD     0, 0.1, 0.2: target CLS_i = mean + SD z_i, z ~ N(0, 1) truncated at 3; the level
             is the nearest the job budget allows (about 0.10-0.99), so wide spreads clip
  period CV  0, 0.2: period_i = MU (1 + CV z_i), rounded in log space to PERIOD_MENU
Every task has the high mode's hot-cold shape (hot H lines x R repeats + a 32 KiB cold region
per sweep, traffic as-is), with up to MAX_SWEEPS sweeps so long jobs reach mid-range CLS; a
lower CLS means more L1 misses per microsecond. Task counts range over TASK_RANGE and appear
equally often. U shares from Dirichlet(ALPHA), largest <= LIGHT_CAP, smallest >= U_MIN. Common
random numbers: set k keeps its task count, shares, CLS and period z-scores and order in every
cell. Placements: wfd, cgb, ra, ra-cgb (absolute cut CLS <= 0.5) and cgr, ra-cgr (relative
cut: the lower-CLS half of the U); G and C2 (1+1+2) follow wfd.
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
from placement_lib import BOUNDARY_POLICIES, CLS_LOW, CORE_CAP, CORES, RELATIVE_POLICIES, Item, place

TASK_RANGE = (12, 20)
TASKS = TASK_RANGE  # per set: task_count(set_id)
MU = 40
PERIOD_MENU = (20, 24, 30, 40, 48, 60, 80, 120)
PERIODS = PERIOD_MENU
HYPERPERIOD = 240
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 1, 2
CLS_MEANS = (0.3, 0.6, 0.9)
CLS_SDS = (0.0, 0.1, 0.2)
PERIOD_CVS = (0.0, 0.2)
HEAVINESS = tuple(f'cls{round(m * 100):02d}-sd{round(s * 100):02d}-cv{round(cv * 100):02d}'
                  for m in CLS_MEANS for s in CLS_SDS for cv in PERIOD_CVS)
LOADS = (0.4,)
SETS = 18
SEED_BASE = 20262301
ALPHA = 8.0
LIGHT_CAP = 0.35
U_MIN = 0.011
MAX_SWEEPS = 1024
HEAVY, HEAVY_RANGE = 0, None
TRENDS = False  # the 18 cells have no single order for hl_run's trend tests
OPTIMIZATION = 'O2'
PLACEMENTS = BOUNDARY_POLICIES + RELATIVE_POLICIES


def cell(heaviness: str) -> dict:
    m, s, cv = heaviness.split('-')
    return dict(cls_mean=int(m[3:]) / 100, cls_sd=int(s[2:]) / 100, period_cv=int(cv[2:]) / 100)


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
    total = LOADS[0] * CORES
    while True:
        w = rng.dirichlet(np.full(n, ALPHA))
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
def _table(budget: int) -> dict:
    """bimodal's high-mode level table with up to MAX_SWEEPS sweeps (bimodal stops at 64,
    which keeps jobs longer than a few ms above CLS 0.8)."""
    h, s = np.meshgrid(np.array(bimodal.HIGH_HOT), np.arange(1, MAX_SWEEPS + 1), indexing='ij')
    rows = bimodal._levels(mem_set.model(), 'repeats', budget, hot=h, repeats=None, sweeps=s, pad=0)
    return {'high': bimodal._with_cls(rows[rows[:, bimodal.REPEATS] >= 2])}


@cache
def level(budget: int, target: float) -> dict:
    return bimodal.level(_table(budget), 'high', 'as-is', target)


def targets(heaviness: str, set_id: int) -> list[float]:
    c = cell(heaviness)
    return [c['cls_mean'] + c['cls_sd'] * z for z in _draws(set_id)[1]]


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    c = cell(heaviness)
    task_periods, task_budgets = periods(c['period_cv'], set_id), budgets(load, c['period_cv'], set_id)
    task_targets = targets(heaviness, set_id)
    levels = [dict(level(b, t), cold=bimodal.COLD_LINES) for b, t in zip(task_budgets, task_targets)]
    job = [b * (1 + lv['u_error']) for b, lv in zip(task_budgets, levels)]
    us = [j / (p * 1e6) for j, p in zip(job, task_periods)]
    misses = [lv['sweeps'] * (lv['hot'] + lv['cold']) for lv in levels]
    traffic = [m / (j / 1e3) for m, j in zip(misses, job)]
    cores = place(placement, [Item(u=u, period=p, traffic=r, cls=lv['cls'])
                              for u, p, r, lv in zip(us, task_periods, traffic, levels)], seed=SEED_BASE + set_id)
    tasks = []
    for i, lv in enumerate(levels):
        task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + lv['cold'],
                    hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=bimodal.STRIDE,
                    sweeps=lv['sweeps'], core=cores[i], period_ticks=task_periods[i],
                    role='low' if lv['cls'] <= CLS_LOW else 'high', mode='spread', cls_target=task_targets[i],
                    cls_planned=lv['cls'], u_target=task_budgets[i] / (task_periods[i] * 1e6), u_planned=us[i],
                    l1_misses_planned=misses[i], traffic_planned=traffic[i],
                    footprint_kib=(lv['hot'] + lv['cold']) * bimodal.STRIDE / 1024)
        if lv['tail']:
            task['pad_tail'] = lv['tail']
        tasks.append(task)
    core_u = [sum(u for u, k in zip(us, cores) if k == core) for core in range(CORES)]
    cls = [lv['cls'] for lv in levels]
    return dict(workload_id=f'cls-spread-u{round(load * 100):03d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id='cls-spread-hot-cold-v1', policy_id=f'cls-spread-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization=OPTIMIZATION,
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, set_id=set_id, seed=SEED_BASE + set_id,
                               placement=placement, total_u=sum(us), core_u=core_u, core_cap=CORE_CAP,
                               tasks=len(tasks), realized_cls_mean=statistics.mean(cls),
                               realized_cls_sd=statistics.pstdev(cls),
                               realized_period_cv=statistics.pstdev(task_periods) / statistics.mean(task_periods),
                               **c))


def protocol_extra() -> dict:
    return dict(cells={h: cell(h) for h in HEAVINESS}, period_menu=PERIOD_MENU, mu=MU, seed_base=SEED_BASE,
                task_range=TASK_RANGE, task_counts=[task_count(k) for k in range(SETS)], max_sweeps=MAX_SWEEPS)
