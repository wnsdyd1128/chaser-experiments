"""Experiment 44 (pre-registered): fresh sets for confirming the pre-run check, three task types.

One design per type (hl_run cases need one load grid per design):
  confirm-small  32 KiB low-CLS tasks (experiment 27's low shape, traffic as-is) hold MEMORY_SHARE 0.5 of the U
  confirm-big    768 KiB tasks (mix_set.big_level, experiment 27's big shape) hold 0.25
  confirm-mem    memory-bound tasks (memcost_set.mem_level, experiment 41's shape) hold 0.25, at most 4 per set
The rest are high-CLS tasks (center 0.90). Task counts, Dirichlet(8) shares, period CV 0.2 on deadline_set's
menu, the common random numbers across loads and the memory-task prefix rule follow deadline_set; seeds are new.
Placements: CHASER's ra-cgb and the U-balanced wfd (the base of G4, C1+3 and C1+1+2), both by placement_lib on
the planned U, period, traffic and CLS with seed SEED_BASE + set id, which chaser.policy.pfirst reproduces.
"""

from functools import cache
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
import deadline_set as ds
from hl_set import CONTRACT
import mem_set
import memcost_set
import mix_set
from placement_lib import CORE_CAP, CORES, Item, place

PERIOD_CV = 0.2
KINDS = {
    'small': dict(role='low', share=0.5, max_memory=None, seed=20264401, loads=(0.45, 0.4875, 0.525, 0.5625, 0.6),
                  checks=(ds.MODEL_CHECK_NS['low'],)),
    'big': dict(role='big', share=0.25, max_memory=None, seed=20264431, loads=(0.30, 0.3375, 0.375, 0.4125, 0.45),
                checks=((1_700_000, 15_150_000),)),
    'mem': dict(role='low', share=0.25, max_memory=4, seed=20264461, loads=(0.45, 0.4875, 0.525, 0.5625, 0.6),
                checks=(ds.MODEL_CHECK_NS['low'], memcost_set.MODEL_CHECK_NS['mem'])),
}


class Design:
    """An hl_run design module for one task type."""

    TASKS = ds.TASK_RANGE
    PERIODS = ds.PERIOD_MENU
    HYPERPERIOD = ds.HYPERPERIOD
    WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 1, 3
    SETS = 24
    ALPHA, LIGHT_CAP, U_MIN = ds.ALPHA, ds.LIGHT_CAP, ds.U_MIN
    HEAVY, HEAVY_RANGE = 0, None
    CORE_CAP = CORE_CAP
    TRENDS = True
    OPTIMIZATION = 'O2'
    PLACEMENTS = ('wfd', 'ra-cgb')
    MODEL_CHECK_NS = dict(ds.MODEL_CHECK_NS, big=(1_700_000, 15_150_000), mem=memcost_set.MODEL_CHECK_NS['mem'])

    def __init__(self, kind: str):
        k = KINDS[kind]
        self.kind, self.role, self.share, self.max_memory = kind, k['role'], k['share'], k['max_memory']
        self.SEED_BASE, self.LOADS, self.checks = k['seed'], k['loads'], k['checks']
        self.STUDY = f'confirm-{kind}'
        self.HEAVINESS = (f"cv20-{kind}{round(self.share * 100):02d}",)
        self._counts = cache(self._counts)
        self._draws = cache(self._draws)
        self.memory_tasks = cache(self.memory_tasks)

    def _counts(self) -> tuple[int, ...]:
        values = list(range(self.TASKS[0], self.TASKS[1] + 1))
        column = [values[i % len(values)] for i in range(self.SETS)]
        random.Random(f'{self.SEED_BASE}-tasks').shuffle(column)
        return tuple(column)

    def task_count(self, set_id: int) -> int:
        return self._counts()[set_id]

    def _draws(self, set_id: int):
        n = self.task_count(set_id)
        rng = np.random.default_rng([self.SEED_BASE, set_id])
        order = rng.permutation(n).tolist()
        z_cls, z_period = ds.truncated_normals(rng, n), ds.truncated_normals(rng, n)
        while True:
            w = rng.dirichlet(np.full(n, self.ALPHA))
            if w.max() * max(self.LOADS) * CORES <= self.LIGHT_CAP and w.min() * min(self.LOADS) * CORES >= self.U_MIN:
                return order, z_cls, z_period, [float(x) for x in w]

    def periods(self, set_id: int) -> list[int]:
        return [ds.menu_period(ds.MU * (1 + PERIOD_CV * z)) for z in self._draws(set_id)[2]]

    def budgets(self, load: float, set_id: int) -> list[int]:
        step = mix_set.BUDGET_STEP_NS
        return [max(step, round(w * load * CORES * p * 1e6 / step) * step)
                for w, p in zip(self._draws(set_id)[3], self.periods(set_id))]

    def memory_tasks(self, set_id: int) -> tuple[int, ...]:
        """A prefix of the eligible tasks in set order, ending nearest the share (and at most max_memory)."""
        order, _, _, shares = self._draws(set_id)
        room = [[self.budgets(load, set_id)[i] for load in self.LOADS] for i in range(len(order))]
        chosen, held = [], 0.0
        for i in (i for i in order if all(low <= min(room[i]) and max(room[i]) <= high for low, high in self.checks)):
            if held + shares[i] / 2 > self.share or len(chosen) == (self.max_memory or len(order)):
                break
            chosen.append(i)
            held += shares[i]
        return tuple(chosen)

    def roles(self, set_id: int) -> list[str]:
        memory = set(self.memory_tasks(set_id))
        return [self.role if i in memory else 'high' for i in range(self.task_count(set_id))]

    def level(self, role: str, budget: int, z: float) -> dict:
        tables = mem_set.tables(budget)
        if role == 'high':
            return dict(bimodal.level(tables, 'high', 'as-is', mix_set.cls_target('high', z)), cold=bimodal.COLD_LINES,
                        stride=bimodal.STRIDE)
        if role == 'big':
            return dict(mix_set.big_level(budget), stride=bimodal.STRIDE)
        small = dict(bimodal.level(tables, 'low', 'as-is', mix_set.cls_target('low', z)), cold=bimodal.COLD_LINES,
                     stride=bimodal.STRIDE)
        return small if self.kind == 'small' else memcost_set.mem_level(budget, small['cls'])

    def configuration(self, load: float, heaviness: str, set_id: int, placement: str) -> dict:
        task_periods, task_roles = self.periods(set_id), self.roles(set_id)
        task_budgets, z = self.budgets(load, set_id), self._draws(set_id)[1]
        levels = [self.level(r, b, v) for r, b, v in zip(task_roles, task_budgets, z)]
        job = [b * (1 + lv['u_error']) for b, lv in zip(task_budgets, levels)]
        us = [j / (p * 1e6) for j, p in zip(job, task_periods)]
        misses = [lv['sweeps'] * (lv['hot'] + lv['cold']) for lv in levels]
        traffic = [m / (j / 1e3) for m, j in zip(misses, job)]
        cores = place(placement, [Item(u=u, period=p, traffic=r, cls=lv['cls'])
                                  for u, p, r, lv in zip(us, task_periods, traffic, levels)], seed=self.SEED_BASE + set_id)
        tasks = []
        for i, (role, lv) in enumerate(zip(task_roles, levels)):
            task = dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=lv['hot'] + lv['cold'],
                        hot_distinct=lv['hot'], hot_repeats=lv['repeats'], cold_repeats=1, stride=lv['stride'],
                        sweeps=lv['sweeps'], core=cores[i], period_ticks=task_periods[i], role=role,
                        mode='high' if role == 'high' else 'low', cls_target=mix_set.cls_target(role, z[i]),
                        cls_planned=lv['cls'], u_target=task_budgets[i] / (task_periods[i] * 1e6), u_planned=us[i],
                        l1_misses_planned=misses[i], traffic_planned=traffic[i],
                        footprint_kib=(lv['hot'] + lv['cold']) * bimodal.STRIDE / 1024,
                        data_kib=(lv['hot'] + lv['cold']) * lv['stride'] / 1024)
            if lv['pad']:
                task['pad_rounds'] = lv['pad']
            if lv['tail']:
                task['pad_tail'] = lv['tail']
            tasks.append(task)
        memory_u = sum(u for u, r in zip(us, task_roles) if r != 'high')
        return dict(workload_id=f'{self.STUDY}-u{round(load * 10000):05d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                    family_id=f'{self.STUDY}-hot-cold-v1', policy_id=f'{self.STUDY}-{placement}-v1',
                    measurement_contract_id=CONTRACT, array_alignment_bytes=32, workload_optimization=self.OPTIMIZATION,
                    horizon_ticks=(self.WARMUP_HYPERPERIODS + self.MEASURED_HYPERPERIODS) * self.HYPERPERIOD,
                    warmup_ticks=self.WARMUP_HYPERPERIODS * self.HYPERPERIOD, u_repeats=1, diagnostic_only=True,
                    tasks=tasks,
                    high_load=dict(load=load, heaviness=heaviness, kind=self.kind, set_id=set_id,
                                   seed=self.SEED_BASE + set_id, placement=placement, total_u=sum(us),
                                   core_u=[sum(u for u, k in zip(us, cores) if k == core) for core in range(CORES)],
                                   core_cap=CORE_CAP, tasks=len(tasks), memory_share=memory_u / sum(us),
                                   realized_period_cv=statistics.pstdev(task_periods) / statistics.mean(task_periods),
                                   period_cv=PERIOD_CV, memory_share_target=self.share))

    def protocol_extra(self) -> dict:
        return dict(kind=self.kind, role=self.role, share=self.share, max_memory=self.max_memory, period_cv=PERIOD_CV,
                    seed_base=self.SEED_BASE, loads=self.LOADS, task_counts=[self.task_count(k) for k in range(self.SETS)],
                    memory_tasks={f'{k}': self.memory_tasks(k) for k in range(self.SETS)})


DESIGNS = {f'confirm-{kind}': Design(kind) for kind in KINDS}
