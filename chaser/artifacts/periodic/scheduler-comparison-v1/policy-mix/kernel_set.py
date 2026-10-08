"""Experiment 45 (pre-registered): fresh task sets of real kernels (uint32 PolyBench/C adaptations, kernel_tasks).

Per set (common random numbers across loads, as deadline_set): task count from TASK_RANGE, Dirichlet(ALPHA) U shares,
period CV 0.2 on deadline_set's menu, and per task a kernel drawn uniformly from kernel_tasks.KERNELS and sweeps from
SWEEPS. A task's budget is share x load x 4 x period; its dimension n is the one whose calibrated isolated job time
(kernel_calibrate, results/kernel-calibration/kernel-model.json) is nearest the budget, searched over the calibrated
range of (kernel, sweeps); a budget below the range uses fewer sweeps, then the smallest n (clamped and recorded).
The planned U is the measured isolated job time of the chosen (kernel, sweeps, n) (kernel_calibrate tasks stage,
results/kernel-calibration/task-times.json) over the period; the interpolation model only chooses n (real kernels are
not smooth in n; 2026-10-08, before any run). A draw whose largest load
exceeds the workload data or array limit is redrawn with the next attempt index (deterministic).
"""

from functools import cache
import json
import math
import random
import statistics
from pathlib import Path

import numpy as np

import kernel_calibrate as kc
import kernel_tasks as kt

HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE.parent / 'results/kernel-calibration/kernel-model.json'
TIMES_PATH = HERE.parent / 'results/kernel-calibration/task-times.json'
SEED_BASE, SETS = 20264501, 24
LOADS = (0.40, 0.475, 0.55, 0.625, 0.70)
HEAVINESS = 'real'
TASK_RANGE = (12, 20)
ALPHA, LIGHT_CAP, U_MIN = 8.0, 0.35, 0.0125
PERIOD_MENU, MU, PERIOD_CV, HYPERPERIOD = (20, 24, 30, 40, 48, 60, 80, 120), 40, 0.2, 240
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 1, 3
SWEEPS = kc.SWEEPS
DATA_LIMIT, ARRAY_LIMIT = 16 * 1024 ** 2, 96  # the workload limits of chaser.periodic
CORES = 4


@cache
def model() -> dict:
    return json.loads(MODEL_PATH.read_text())['tables']


@cache
def times() -> dict:
    return json.loads(TIMES_PATH.read_text())['times']


def job_ns(kernel: str, sweeps: int, n: int) -> float:
    return kc.interpolate([tuple(r) for r in model()[f'{kernel} {sweeps}']], n)


def size(kernel: str, sweeps: int, budget_ns: float) -> tuple[int, int, bool]:
    """(sweeps, n, clamped): n with the calibrated job time nearest the budget, fewer sweeps if needed."""
    for s in [sweeps] + [x for x in SWEEPS if x < sweeps][::-1]:
        lo, hi = kc.bounds(kernel, s)
        if job_ns(kernel, s, lo) <= budget_ns or s == 1:
            break
    lo, hi = kc.bounds(kernel, s)
    if budget_ns <= job_ns(kernel, s, lo):
        return s, lo, True
    if budget_ns >= job_ns(kernel, s, hi):
        return s, hi, True
    a, b = lo, hi
    while b - a > 1:
        mid = (a + b) // 2
        a, b = (mid, b) if job_ns(kernel, s, mid) <= budget_ns else (a, mid)
    n = min((a, b), key=lambda x: abs(job_ns(kernel, s, x) - budget_ns))
    return s, n, False


def _menu(raw: float) -> int:
    return min(PERIOD_MENU, key=lambda p: (abs(math.log(p / raw)), p))


@cache
def _counts() -> tuple[int, ...]:
    values = list(range(TASK_RANGE[0], TASK_RANGE[1] + 1))
    column = [values[i % len(values)] for i in range(SETS)]
    random.Random(f'{SEED_BASE}-tasks').shuffle(column)
    return tuple(column)


def _normals(rng, count):
    out = []
    while len(out) < count:
        v = float(rng.normal())
        if abs(v) <= 3:
            out.append(v)
    return out


def _draw(set_id: int, attempt: int):
    n = _counts()[set_id]
    rng = np.random.default_rng([SEED_BASE, set_id, attempt])
    periods = [_menu(MU * (1 + PERIOD_CV * z)) for z in _normals(rng, n)]
    kernels = [kt.KERNELS[int(i)] for i in rng.integers(0, len(kt.KERNELS), n)]
    sweeps = [SWEEPS[int(i)] for i in rng.integers(0, len(SWEEPS), n)]
    while True:
        w = rng.dirichlet(np.full(n, ALPHA))
        if w.max() * max(LOADS) * CORES <= LIGHT_CAP and w.min() * min(LOADS) * CORES >= U_MIN:
            return periods, kernels, sweeps, [float(x) for x in w]


def tasks(load: float, set_id: int, attempt: int | None = None, measured: bool = True) -> list[dict]:
    """Planned tasks: task_id, kernel, sweeps, n, period, budget_ns, u (planned), clamped, data_bytes.
    measured=False uses the model's job time for u (only to enumerate the sizes to measure)."""
    attempt = draw_attempt(set_id) if attempt is None else attempt
    periods, kernels, sweeps, shares = _draw(set_id, attempt)
    out = []
    for i, (p, k, s, w) in enumerate(zip(periods, kernels, sweeps, shares)):
        budget = w * load * CORES * p * 1e6
        s2, n, clamped = size(k, s, budget)
        job = times()[f'{k} {s2} {n}'] if measured else job_ns(k, s2, n)
        out.append(dict(task_id=f't{i:02d}', kernel=k, sweeps=s2, n=n, period=p, budget_ns=budget,
                        u=job / (p * 1e6), clamped=clamped, data_bytes=kt.data_bytes(k, n)))
    return out


@cache
def draw_attempt(set_id: int) -> int:
    attempt = 0
    while True:
        planned = tasks(max(LOADS), set_id, attempt, measured=False)
        if sum(t['data_bytes'] for t in planned) <= DATA_LIMIT * 0.9 and \
                sum(len(kt.ROLES[t['kernel']]) for t in planned) <= ARRAY_LIMIT:
            return attempt
        attempt += 1


def needed() -> set[tuple[str, int, int]]:
    """Every (kernel, sweeps, n) of every set and load, to measure before generating the configurations."""
    return {(t['kernel'], t['sweeps'], t['n']) for k in range(SETS) for load in LOADS for t in tasks(load, k, measured=False)}


def configuration(load: float, set_id: int, cores: list[int]) -> dict:
    planned = tasks(load, set_id)
    pairs = [kt.task(t['kernel'], t['task_id'], t['n'], t['sweeps'], c, t['period']) for t, c in zip(planned, cores)]
    return kt.configuration(f'real-kernels-u{round(load * 1000):04d}-s{set_id:02d}', pairs,
                            (WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD, WARMUP_HYPERPERIODS * HYPERPERIOD)


def cases() -> list[tuple[float, int]]:
    return [(load, k) for load in LOADS for k in range(SETS)]


def label(case) -> str:
    load, k = case
    return f'{HEAVINESS}/u{round(load * 100):03d}/s{k:02d}'


def realized(load: float, set_id: int) -> dict:
    planned = tasks(load, set_id)
    periods = [t['period'] for t in planned]
    return dict(total_u=sum(t['u'] for t in planned), clamped=sum(t['clamped'] for t in planned),
                period_cv=statistics.pstdev(periods) / statistics.mean(periods),
                data_mib=sum(t['data_bytes'] for t in planned) / 1024 ** 2)
