"""Cache-affinity task sets: per-core reusable working set vs L1, and job length.

Sixteen cyclic tasks, four per core under P with each core's arrays contiguous.
Factor A sets the mean per-core working set as a share of the 16 KiB L1; factor B
sets the sweeps per job. Each task's working set is jittered by +/-25% with a
per-set seed shared across conditions. All tasks share the shortest whole-tick
period that keeps the planned task U at most U_CAP.
"""

from math import ceil
import random

from chaser.periodic.measurement import CONTRACT

WS_LEVELS = (25, 50, 100, 150)
SWEEPS = (2, 8, 32)
SETS = 20
TASKS = 16
CORES = 4
L1_BYTES = 16384
LINE = 32
JITTER = 0.25
SEED_BASE = 20261001
# L1-hit cost of one cyclic load and the per-job base from the CLS calibration.
ACCESS_NS = 93.66
JOB_BASE_NS = 5_580
U_CAP = 0.125
# One-tick periods release all 16 jobs every tick; pilot G/C runs missed
# deadlines at a planned per-core U of 0.40 there, so one tick is used only up
# to a per-core U of 0.25.
U_CAP_ONE_TICK = 0.0625
WARMUP_JOBS = 10
MEASURED_JOBS = 10


def mean_lines(level: int) -> int:
    return L1_BYTES * level // 100 // (TASKS // CORES) // LINE


def planned_job_ns(lines: int, sweeps: int) -> float:
    return JOB_BASE_NS + sweeps * lines * ACCESS_NS


def period_ticks(level: int, sweeps: int) -> int:
    job = planned_job_ns(mean_lines(level), sweeps)
    if job <= U_CAP_ONE_TICK * 1e6:
        return 1
    return max(2, ceil(job / (U_CAP * 1e6)))


def task_lines(level: int, set_id: int) -> list[int]:
    rng = random.Random(SEED_BASE + set_id)
    base = mean_lines(level)
    return [max(1, round(base * (1 + JITTER * rng.uniform(-1, 1)))) for _ in range(TASKS)]


def configuration(level: int, sweeps: int, set_id: int, optimization: str = 'O0') -> dict:
    """O2 keeps the O0 tasks and periods; only the workload object is optimized."""
    if optimization not in ('O0', 'O2'):
        raise ValueError('Workload optimization must be O0 or O2')
    period = period_ticks(level, sweeps)
    per_core = TASKS // CORES
    tasks = [dict(task_id=f't{i:02d}', pattern='cyclic', distinct=lines, stride=LINE,
                  sweeps=sweeps, core=i // per_core, period_ticks=period)
             for i, lines in enumerate(task_lines(level, set_id))]
    suffix = '' if optimization == 'O0' else f'-{optimization.lower()}'
    return dict(workload_id=f'cache-affinity-ws{level:03d}-s{sweeps:02d}-set{set_id:02d}{suffix}-v1',
                family_id='cache-affinity-cyclic-v1', policy_id='contiguous-core-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32,
                workload_optimization=optimization, horizon_ticks=(WARMUP_JOBS + MEASURED_JOBS) * period,
                warmup_ticks=WARMUP_JOBS * period, u_repeats=1, diagnostic_only=True, tasks=tasks,
                cache_affinity=dict(ws_level_pct=level, sweeps=sweeps, set_id=set_id,
                                    seed=SEED_BASE + set_id, jitter=JITTER, u_cap=U_CAP,
                                    per_core_bytes=[sum(t['distinct'] * LINE for t in tasks
                                                        if t['core'] == c) for c in range(CORES)]))
