"""Cohort-aware P placement for equal-U task sets.

P serializes the jobs of one release cohort that share a core. With equal
per-task U, job CPU is proportional to the period, so the busiest core's summed
periods bound that cohort's P span from below. The placement keeps an equal
task count per core and minimizes the bound summed over every release instant
of one window, over which the release pattern repeats.
"""

import random

import numpy as np

from taskset import CORES, assign_cores

RESTARTS = 20
SEED = 0


def _releases(periods, window):
    """Weighted release rows with multiplicities for identical instants."""
    rows = {}
    for t in range(window):
        key = tuple(p if t % p == 0 else 0 for p in periods)
        if any(key):
            rows[key] = rows.get(key, 0) + 1
    return np.array(list(rows), dtype=float), np.array(list(rows.values()), dtype=float)


def _cost(releases, counts, cores):
    onehot = np.zeros((len(cores), CORES))
    onehot[np.arange(len(cores)), cores] = 1
    return float(counts @ (releases @ onehot).max(axis=1))


def cohort_cost(periods: list[int], cores: list[int], window: int) -> float:
    return _cost(*_releases(periods, window), cores)


def _descend(releases, counts, cores):
    """Apply the best improving swap between cores until none improves."""
    best = _cost(releases, counts, cores)
    while True:
        move = None
        for i in range(len(cores)):
            for j in range(i + 1, len(cores)):
                if cores[i] == cores[j]:
                    continue
                cores[i], cores[j] = cores[j], cores[i]
                cost = _cost(releases, counts, cores)
                cores[i], cores[j] = cores[j], cores[i]
                if cost < best:
                    best, move = cost, (i, j)
        if move is None:
            return best, cores
        i, j = move
        cores[i], cores[j] = cores[j], cores[i]


def cohort_cores(periods: list[int], window: int) -> list[int]:
    """Best of a snake start and seeded random balanced starts."""
    releases, counts = _releases(periods, window)
    rng = random.Random(SEED)
    starts = [assign_cores(periods)]
    for _ in range(RESTARTS - 1):
        cores = [c for c in range(CORES) for _ in range(len(periods) // CORES)]
        rng.shuffle(cores)
        starts.append(cores)
    best = None
    for start in starts:
        cost, cores = _descend(releases, counts, list(start))
        if best is None or cost < best[0]:
            best = (cost, cores)
    return best[1]
