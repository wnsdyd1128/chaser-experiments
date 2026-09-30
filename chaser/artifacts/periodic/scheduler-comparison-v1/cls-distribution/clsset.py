"""Sample task sets whose per-task CLS follows a truncated normal distribution.

All tasks share one period and U = 0.125. Each task runs the legacy hot-cold
kernel: a 2 KiB hot region repeated `hot_repeats` times, then a 32 KiB cold
region once, per sweep. Calibration fixes, per period, the sweeps giving the
target U and the yarda_cpp CLS (alpha 0.5) of each calibrated hot-repeat level;
targets are quantized to the nearest calibrated level. Tasks are ordered by
calibrated CLS, so both placements share task order and array layout and differ
only in the core field.
"""

import random

from chaser.periodic.measurement import CONTRACT

PERIODS = (20, 100)
MEANS = (0.3, 0.5, 0.7)
CVS = (0.0, 0.1, 0.2, 0.3)
SETS = 20
TASKS = 16
CORES = 4
TASK_U = 0.125
HOT_LINES = 64
COLD_LINES = 1024
STRIDE = 32
WARMUP_JOBS = 10
MEASURED_JOBS = 10
TRUNCATION_SIGMA = 3.0
SEED_BASE = 20260930
ALPHA = '0.5'
PLACEMENTS = ('zigzag', 'grouped')
# Hot-repeat levels for calibration: roughly geometric so CLS steps stay small.
REPEAT_GRID = (1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 18, 21, 26, 31, 37, 45, 54, 64,
               77, 92, 111, 133, 160, 192, 230, 276, 331, 397)


def set_ids(cv: float) -> list[int]:
    return [0] if cv == 0 else list(range(SETS))


def targets(mean: float, cv: float, seed: int, low: float, high: float) -> list[float]:
    """Draw per-task CLS targets within +/-3 sigma and the achievable range."""
    if cv == 0:
        return [mean] * TASKS
    rng = random.Random(seed)
    values = []
    while len(values) < TASKS:
        z = rng.gauss(0.0, 1.0)
        value = mean * (1 + cv * z)
        if abs(z) <= TRUNCATION_SIGMA and low <= value <= high:
            values.append(value)
    return values


def quantize(target: float, table: list[dict]) -> dict:
    """Return the calibrated level nearest in CLS; ties choose fewer hot repeats."""
    return min(table, key=lambda row: (abs(row['cls'] - target), row['hot_repeats']))


def zigzag(values: list[float]) -> list[int]:
    """Snake over CLS ranks: every core receives one task from each quartile."""
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    cores = [0] * len(values)
    for rank, index in enumerate(order):
        lap, position = divmod(rank, CORES)
        cores[index] = position if lap % 2 == 0 else CORES - 1 - position
    return cores


def grouped(values: list[float]) -> list[int]:
    """Consecutive CLS ranks share a core; core 0 holds the lowest CLS."""
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    per_core = len(values) // CORES
    cores = [0] * len(values)
    for rank, index in enumerate(order):
        cores[index] = rank // per_core
    return cores


def configuration(period: int, mean: float, cv: float, set_id: int,
                  tables: dict[int, list[dict]], placement: str) -> dict:
    table = tables[period]
    low, high = min(r['cls'] for r in table), max(r['cls'] for r in table)
    wanted = targets(mean, cv, SEED_BASE + set_id, low, high)
    levels = sorted(((quantize(t, table), t) for t in wanted),
                    key=lambda pair: (pair[0]['cls'], pair[1]))
    values = [level['cls'] for level, _ in levels]
    cores = zigzag(values) if placement == 'zigzag' else grouped(values)
    tasks = [dict(task_id=f't{i:02d}', pattern='hot-cold', distinct=HOT_LINES + COLD_LINES,
                  hot_distinct=HOT_LINES, hot_repeats=level['hot_repeats'], cold_repeats=1,
                  stride=STRIDE, sweeps=level['sweeps'], core=core, period_ticks=period,
                  cls_target=target, cls_calibrated=level['cls'])
             for i, ((level, target), core) in enumerate(zip(levels, cores))]
    return dict(workload_id=f'cls-dist-p{period}-m{round(mean * 100):02d}-cv{round(cv * 100):02d}'
                            f'-s{set_id:02d}-{placement}-v1',
                family_id='cls-distribution-hot-cold-v1', policy_id=f'cls-{placement}-v1',
                measurement_contract_id=CONTRACT, array_alignment_bytes=32,
                workload_optimization='O0', horizon_ticks=(WARMUP_JOBS + MEASURED_JOBS) * period,
                warmup_ticks=WARMUP_JOBS * period, u_repeats=1, diagnostic_only=True, tasks=tasks,
                cls_distribution=dict(period_ticks=period, mean=mean, cv=cv, set_id=set_id,
                                      seed=SEED_BASE + set_id, alpha=ALPHA, placement=placement,
                                      truncation_sigma=TRUNCATION_SIGMA, task_u=TASK_U))
