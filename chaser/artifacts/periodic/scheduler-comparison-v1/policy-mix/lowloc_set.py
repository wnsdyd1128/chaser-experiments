"""Experiment 47 (pre-registered): CHASER's placement on task sets whose low-CLS tasks are real low-locality kernels.

Cells: period CV in PERIOD_CVS (labels 'cv00-lowloc50', 'cv20-lowloc50'); per-core loads LOADS; SETS sets per cell and
load. Common random numbers: set k keeps its task count, U shares, period z-scores, roles, kernels and sweeps in every
cell and load; the cell sets the period CV (period_i = menu(MU (1 + CV z_i)), all 40 ms at CV 0) and the load scales
the budgets.
Roles (experiment 27's rule): tasks in set order are low until their U share comes nearest LOW_SHARE; the rest are high.
Low tasks draw a kernel uniformly from kernel_tasks.LOW_LOCALITY (naive transpose, planar complex corner turn of a
256-row block), high tasks from kernel_tasks.KERNELS (experiment 45's PolyBench kernels); sweeps uniformly from SWEEPS.
Sizes (kernel_set's rule): budget = share x load x 4 x period; n is the one whose calibrated isolated job time is nearest
the budget within kernel_calibrate.bounds (the low kernels between kernel_tasks.MIN_N and MAX_N, where HARA's CLS is
0.475-0.481); a budget below the range uses fewer sweeps, then the smallest n (clamped and recorded). The models are
experiment 45's (high) and results/kernel-calibration-lowloc (low); the planned U of every task is the measured isolated
job time of the chosen (kernel, sweeps, n) in results/kernel-calibration-lowloc/task-times.json. A draw exceeding the
workload data or array limit at the highest load is redrawn with the next attempt index (deterministic).
Designs (DESIGNS, select): 'lowloc-kernels' is experiment 47 (the default). The capped designs (experiment 48 and its
pilot) fix every task's data at most DATA_CAP, like PolyBench's small datasets: n is at most the largest size within
the cap, and the job fills its budget with more sweeps (any count; the job time of s > 4 sweeps is estimated as s / 4
times the calibrated 4-sweep time, and the planned U is still the measured time). The drawn sweeps are then unused.
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
ROOT = HERE.parents[3]
HIGH_MODEL = HERE.parent / 'results/kernel-calibration/kernel-model.json'
LOW_MODEL = HERE.parent / 'results/kernel-calibration-lowloc/kernel-model.json'
DESIGNS = {
    'lowloc-kernels': dict(seed_base=20264701, sets=24, period_cvs=(0.0, 0.2), loads=(0.40, 0.45, 0.50, 0.55, 0.60),
                           data_cap=None, prefix='lowloc', times=HERE.parent / 'results/kernel-calibration-lowloc/task-times.json'),
    # Pilot of the capped design, its own seeds; chooses experiment 48's loads, not part of any judgment.
    'lowloc-small-pilot': dict(seed_base=20264881, sets=3, period_cvs=(0.0, 0.2), loads=(0.30, 0.40, 0.50, 0.60),
                               data_cap=64 * 1024, prefix='lowloc-small-pilot',
                               times=ROOT / '.cache/kernel-calibration-lowloc-small-pilot-v1/task-times.json'),
    # Experiment 48 (pre-registered 2026-10-13): loads from the two pilots (EXPERIMENTS.md 48).
    'lowloc-small': dict(seed_base=20264801, sets=24, period_cvs=(0.0, 0.2), loads=(0.60, 0.65, 0.70, 0.75, 0.80),
                         data_cap=64 * 1024, prefix='lowloc-small',
                         times=HERE.parent / 'results/kernel-calibration-lowloc-small/task-times.json'),
    # Second pilot (2026-10-13): the first met every deadline up to 0.60; this one covers the loads above it.
    'lowloc-small-pilot2': dict(seed_base=20264882, sets=3, period_cvs=(0.0, 0.2), loads=(0.65, 0.70, 0.75, 0.80),
                                data_cap=64 * 1024, prefix='lowloc-small-pilot2',
                                times=ROOT / '.cache/kernel-calibration-lowloc-small-pilot2-v1/task-times.json'),
}
LOW_SHARE = 0.5
TASK_RANGE = (12, 20)
ALPHA, LIGHT_CAP, U_MIN = 8.0, 0.35, 0.0125
PERIOD_MENU, MU, HYPERPERIOD = (20, 24, 30, 40, 48, 60, 80, 120), 40, 240
WARMUP_HYPERPERIODS, MEASURED_HYPERPERIODS = 1, 3
SWEEPS = kc.SWEEPS
DATA_LIMIT, ARRAY_LIMIT = 16 * 1024 ** 2, 96  # the workload limits of chaser.periodic
CORES = 4


def select(name: str) -> None:
    """Make `name` the design every function of this module uses."""
    global DESIGN, SEED_BASE, SETS, PERIOD_CVS, LOADS, DATA_CAP, PREFIX, FAMILY, TIMES_PATH
    d = DESIGNS[name]
    DESIGN, SEED_BASE, SETS, PERIOD_CVS, LOADS = name, d['seed_base'], d['sets'], d['period_cvs'], d['loads']
    DATA_CAP, PREFIX, FAMILY, TIMES_PATH = d['data_cap'], d['prefix'], f'{name}-v1', d['times']
    for f in (times, _counts, draw_attempt, capped_range):
        f.cache_clear()


@cache
def model() -> dict:
    return dict(json.loads(HIGH_MODEL.read_text())['tables'], **json.loads(LOW_MODEL.read_text())['tables'])


@cache
def times() -> dict:
    return json.loads(TIMES_PATH.read_text())['times']


def job_ns(kernel: str, sweeps: int, n: int) -> float:
    if f'{kernel} {sweeps}' not in model():
        return sweeps / 4 * job_ns(kernel, 4, n)
    return kc.interpolate([tuple(r) for r in model()[f'{kernel} {sweeps}']], n)


@cache
def capped_range(kernel: str) -> tuple[int, int]:
    """(smallest calibrated n, largest n whose data fits DATA_CAP) at one sweep."""
    lo, hi = kc.bounds(kernel, 1)
    return lo, max(n for n in range(lo, hi + 1) if kt.data_bytes(kernel, n) <= DATA_CAP)


def nearest_n(kernel: str, sweeps: int, lo: int, hi: int, budget_ns: float) -> int:
    if budget_ns <= job_ns(kernel, sweeps, lo):
        return lo
    if budget_ns >= job_ns(kernel, sweeps, hi):
        return hi
    a, b = lo, hi
    while b - a > 1:
        mid = (a + b) // 2
        a, b = (mid, b) if job_ns(kernel, sweeps, mid) <= budget_ns else (a, mid)
    return min((a, b), key=lambda x: abs(job_ns(kernel, sweeps, x) - budget_ns))


def size_capped(kernel: str, budget_ns: float) -> tuple[int, int, bool]:
    """(sweeps, n, clamped) for a capped design: the fewest sweeps whose capped size reaches the budget, n nearest the
    budget at those sweeps (or the cap at one sweep fewer, whichever is nearer); clamped when below one sweep of the
    smallest n."""
    lo, cap = capped_range(kernel)
    s = 1
    while job_ns(kernel, s, cap) < budget_ns:
        s += 1
    options = [(s, nearest_n(kernel, s, lo, cap, budget_ns))] + ([(s - 1, cap)] if s > 1 else [])
    s, n = min(options, key=lambda o: abs(job_ns(kernel, *o) - budget_ns))
    return s, n, budget_ns < job_ns(kernel, 1, lo)


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
    return s, min((a, b), key=lambda x: abs(job_ns(kernel, s, x) - budget_ns)), False


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


def roles(shares) -> list[str]:
    """Experiment 27's rule: a prefix in set order is low, ending where the U share comes nearest LOW_SHARE."""
    held, low = 0.0, 0
    for s in shares:
        if held + s / 2 > LOW_SHARE:
            break
        held += s
        low += 1
    low = min(max(low, 1), len(shares) - 1)
    return ['low'] * low + ['high'] * (len(shares) - low)


def _draw(set_id: int, attempt: int):
    n = _counts()[set_id]
    rng = np.random.default_rng([SEED_BASE, set_id, attempt])
    z = _normals(rng, n)
    while True:
        w = rng.dirichlet(np.full(n, ALPHA))
        if w.max() * max(LOADS) * CORES <= LIGHT_CAP and w.min() * min(LOADS) * CORES >= U_MIN:
            break
    shares = [float(x) for x in w]
    role = roles(shares)
    picks = rng.integers(0, 1 << 30, n)
    kernels = [kt.LOW_LOCALITY[int(p) % len(kt.LOW_LOCALITY)] if r == 'low' else kt.KERNELS[int(p) % len(kt.KERNELS)]
               for p, r in zip(picks, role)]
    sweeps = [SWEEPS[int(i)] for i in rng.integers(0, len(SWEEPS), n)]
    return z, shares, role, kernels, sweeps


def tasks(cv: float, load: float, set_id: int, attempt: int | None = None, measured: bool = True) -> list[dict]:
    """Planned tasks: task_id, role, kernel, sweeps, n, period, budget_ns, u (planned), clamped, data_bytes.
    measured=False uses the model's job time for u (only to enumerate the sizes to measure)."""
    attempt = draw_attempt(set_id) if attempt is None else attempt
    z, shares, role, kernels, sweeps = _draw(set_id, attempt)
    out = []
    for i, (zi, w, r, k, s) in enumerate(zip(z, shares, role, kernels, sweeps)):
        p = _menu(MU * (1 + cv * zi))
        budget = w * load * CORES * p * 1e6
        s2, n, clamped = size(k, s, budget) if DATA_CAP is None else size_capped(k, budget)
        job = times()[f'{k} {s2} {n}'] if measured else job_ns(k, s2, n)
        out.append(dict(task_id=f't{i:02d}', role=r, kernel=k, sweeps=s2, n=n, period=p, budget_ns=budget,
                        u=job / (p * 1e6), clamped=clamped, data_bytes=kt.data_bytes(k, n)))
    return out


@cache
def draw_attempt(set_id: int) -> int:
    attempt = 0
    while True:
        ok = True
        for cv in PERIOD_CVS:
            planned = tasks(cv, max(LOADS), set_id, attempt, measured=False)
            if sum(t['data_bytes'] for t in planned) > DATA_LIMIT * 0.9 or \
                    sum(len(kt.ROLES[t['kernel']]) for t in planned) > ARRAY_LIMIT:
                ok = False
        if ok:
            return attempt
        attempt += 1


def needed() -> set[tuple[str, int, int]]:
    """Every (kernel, sweeps, n) of every cell, load and set, to measure before generating the configurations."""
    return {(t['kernel'], t['sweeps'], t['n']) for cv in PERIOD_CVS for load in LOADS for k in range(SETS)
            for t in tasks(cv, load, k, measured=False)}


def heaviness(cv: float) -> str:
    return f'cv{round(cv * 100):02d}-lowloc{round(LOW_SHARE * 100):02d}'


def cases() -> list[tuple[float, float, int]]:
    return [(cv, load, k) for cv in PERIOD_CVS for load in LOADS for k in range(SETS)]


def label(case) -> str:
    cv, load, k = case
    return f'{heaviness(cv)}/u{round(load * 100):03d}/s{k:02d}'


def configuration(case, cores: list[int]) -> dict:
    cv, load, k = case
    planned = tasks(cv, load, k)
    pairs = [kt.task(t['kernel'], t['task_id'], t['n'], t['sweeps'], c, t['period']) for t, c in zip(planned, cores)]
    return kt.configuration(f'{PREFIX}-{heaviness(cv)}-u{round(load * 1000):04d}-s{k:02d}', pairs,
                            (WARMUP_HYPERPERIODS + MEASURED_HYPERPERIODS) * HYPERPERIOD, WARMUP_HYPERPERIODS * HYPERPERIOD,
                            family=FAMILY)


def realized(case) -> dict:
    planned = tasks(*case)
    periods = [t['period'] for t in planned]
    total = sum(t['u'] for t in planned)
    return dict(total_u=total, low_share=sum(t['u'] for t in planned if t['role'] == 'low') / total,
                low_tasks=sum(t['role'] == 'low' for t in planned), clamped=sum(t['clamped'] for t in planned),
                period_cv=statistics.pstdev(periods) / statistics.mean(periods),
                data_mib=sum(t['data_bytes'] for t in planned) / 1024 ** 2)


select('lowloc-kernels')
