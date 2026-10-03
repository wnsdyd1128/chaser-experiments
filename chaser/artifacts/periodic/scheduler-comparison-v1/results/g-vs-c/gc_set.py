"""G versus C when no partition fits: heavy-task count x heavy-task period.

The infeasible design (inf_set) at a per-core load of 0.85 with H = 5 or 6 heavy
tasks (U 0.51-0.55), but every heavy task gets the same period: short (20 ms)
or long (80 ms). Light tasks keep hl_set's random periods. Everything else,
including the U draws and task positions, is inf_set's for the same set id, so
the four cells differ only in H and the heavy period.

Expected from the infeasible run: short heavy periods concentrate heavy work in
the synchronous 20 ms windows, which global EDF handles poorly while a heavy
task alone in a single-core cluster always fits (uniprocessor EDF, U <= 1);
with six heavy tasks the 2-core cluster of C2 (1+1+2) overflows (4 x ~0.53 > 2)
and only Global spreads them. Placements: wfd (Global runs here), c-cap and
c2-cap (inf_set's capacity-balanced cluster assignment).
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inf_set
from inf_set import (ALPHA, CORE_CAP, CORES, HYPERPERIOD, LIGHT_CAP, MEASURED_HYPERPERIODS, PERIODS, TASKS,
                     U_MIN, WARMUP_HYPERPERIODS)
import hl_set

LOADS = (0.85,)
HEAVINESS = ('h5-short', 'h5-long', 'h6-short', 'h6-long')
SETS = 30
HEAVY = 6
HEAVY_RANGE = inf_set.HEAVY_RANGE
HEAVY_PERIOD = {'short': 20, 'long': 80}
PLACEMENTS = ('wfd', 'c-cap', 'c2-cap')
TRENDS = False


def split(heaviness: str) -> tuple[str, str]:
    count, period = heaviness.split('-')
    return count, period


def periods(heaviness: str, set_id: int) -> list[int]:
    count, period = split(heaviness)
    targets = inf_set.utilizations(LOADS[0], count, set_id)
    return [HEAVY_PERIOD[period] if u > 0.5 else p for u, p in zip(targets, hl_set.periods(set_id))]


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    count, period = split(heaviness)
    task_periods = periods(heaviness, set_id)
    targets = inf_set.utilizations(load, count, set_id)
    task_sweeps = [hl_set.sweeps(u, p) for u, p in zip(targets, task_periods)]
    us = [hl_set.planned_u(s, p) for s, p in zip(task_sweeps, task_periods)]
    if placement in inf_set.CLUSTERS:
        cores = inf_set.cluster_cores(us, inf_set.CLUSTERS[placement])
    else:
        assignment = hl_set.wfd(us)
        cores = [assignment[i] for i in range(TASKS)]
    tasks = [dict(task_id=f't{i:02d}', pattern='cyclic', distinct=hl_set.LINES, stride=hl_set.STRIDE,
                  sweeps=task_sweeps[i], core=cores[i], period_ticks=task_periods[i], u_target=targets[i],
                  u_planned=us[i], heavy=targets[i] > 0.5) for i in range(TASKS)]
    core_u = [sum(u for u, c in zip(us, cores) if c == core) for core in range(CORES)]
    return dict(workload_id=f'g-vs-c-u{round(load * 100):03d}-{heaviness}-s{set_id:02d}-{placement}-v1',
                family_id='g-vs-c-cyclic-v1', policy_id=f'g-vs-c-{placement}-v1',
                measurement_contract_id=hl_set.CONTRACT, array_alignment_bytes=32, workload_optimization='O0',
                horizon_ticks=(WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD,
                warmup_ticks=WARMUP_HYPERPERIODS * HYPERPERIOD, u_repeats=1, diagnostic_only=True, tasks=tasks,
                high_load=dict(load=load, heaviness=heaviness, heavy=inf_set.heavy_count(count),
                               heavy_period=HEAVY_PERIOD[period], set_id=set_id, seed=inf_set.SEED_BASE + set_id,
                               placement=placement, total_u=sum(us), core_u=core_u))
