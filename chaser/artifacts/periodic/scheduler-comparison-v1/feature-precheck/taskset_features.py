"""Static task-set representations for the feature pre-check; no run result enters a feature.

Per task, from yarda (cold-job analysis) and the task specification:
  u              isolated utilization (job CPU time / period), measured before any G/C/P run
  period_ms
  cls, p_l1, p_llc, p_miss   CLS (alpha 0.5) and CLP shares of the modeled accesses
  traffic        L1 misses per microsecond of the job's own CPU time
  footprint_kib  yarda `memory` x 32 B: distinct lines a cold job touches while the set fits in L2

Representations (fixed length for any task count):
  R0      plan contract CLS+U: CLS mean/std/min/max/median + U the same + U sum (11)
  R0-CLP  plan contract CLP+U: the five statistics of each CLP share + U (21)
  R1      R0 + period statistics and period CV
  R2      R1 + traffic and footprint statistics + set-level structure
  R3      R1 + bag of task types + task count
  R4      R2 + bag of task types

The bag of task types is a bag of words whose words are hardware-defined task types:
footprint (L1-resident / within a core's L2 share / beyond) x traffic (within / above a
core's share of the L2 request rate) x utilization (light / heavy). It holds the U sum and
the task count of each type, so it keeps which properties occur together in one task.
"""

from dataclasses import dataclass
from itertools import combinations

import numpy as np

CORES = 4
LINE_BYTES = 32
L1_KIB = 16
L2_KIB = 2048
# The shared L2 serves one request at a time, 12 cycles = 48 ns at 250 MHz (footprint/l2_probe.py).
L2_REQUESTS_PER_US = 1000 / 48
# If every core issues more than its 1/CORES share of that rate, the L2 saturates.
TRAFFIC_HIGH = L2_REQUESTS_PER_US / CORES
HEAVY_U = 0.5  # the heavy-task bound used for global EDF
FOOTPRINT_LIMITS_KIB = (L1_KIB, L2_KIB / CORES)
TYPES = tuple((f, r, h) for f in range(3) for r in range(2) for h in range(2))


@dataclass(frozen=True)
class Task:
    u: float
    period_ms: float
    cls: float
    p_l1: float
    p_llc: float
    p_miss: float
    traffic: float
    footprint_kib: float


def stats(values) -> list[float]:
    """mean, population std, min, max, median: the plan's per-scalar statistics."""
    v = np.asarray(values, dtype=float)
    return [float(v.mean()), float(v.std()), float(v.min()), float(v.max()), float(np.median(v))]


def u_stats(tasks) -> list[float]:
    u = [t.u for t in tasks]
    return stats(u) + [float(sum(u))]


def r0_cls(tasks) -> list[float]:
    return stats([t.cls for t in tasks]) + u_stats(tasks)


def r0_clp(tasks) -> list[float]:
    return (stats([t.p_l1 for t in tasks]) + stats([t.p_llc for t in tasks])
            + stats([t.p_miss for t in tasks]) + u_stats(tasks))


def period_stats(tasks) -> list[float]:
    s = stats([t.period_ms for t in tasks])
    return s + [s[1] / s[0]]


def release_structure(tasks, cores=CORES) -> list[float]:
    """Synchronous release: [work released at 0 / (cores x shortest period),
    distinct periods, share of period pairs where one divides the other]."""
    periods = [t.period_ms for t in tasks]
    work = sum(t.u * t.period_ms for t in tasks)
    pairs = list(combinations(periods, 2))
    harmonic = (sum(max(a, b) % min(a, b) == 0 for a, b in pairs) / len(pairs)) if pairs else 1.0
    return [work / (cores * min(periods)), float(len(set(periods))), harmonic]


def structure(tasks, cores=CORES) -> list[float]:
    u = np.array([t.u for t in tasks])
    traffic = np.array([t.traffic for t in tasks])
    footprint = np.array([t.footprint_kib for t in tasks])
    cls = np.array([t.cls for t in tasks])
    return (stats(traffic) + stats(footprint) + [
        float(len(tasks)), len(tasks) / cores,
        float((u * cls).sum() / u.sum()),
        # u x traffic = L1 misses per microsecond of wall time, summed over the set
        float((u * traffic).sum()) / L2_REQUESTS_PER_US,
        float(np.sort(footprint)[-cores:].sum()) / L2_KIB,
        float((u > HEAVY_U).sum()),
    ] + release_structure(tasks, cores))


def task_type(task: Task) -> tuple[int, int, int]:
    """(footprint class 0-2, traffic class 0-1, utilization class 0-1); bounds are inclusive."""
    return (sum(task.footprint_kib > limit for limit in FOOTPRINT_LIMITS_KIB),
            int(task.traffic > TRAFFIC_HIGH), int(task.u > HEAVY_U))


def bow(tasks) -> list[float]:
    """U sum of each task type, then the task count of each type (TYPES order)."""
    mass, count = dict.fromkeys(TYPES, 0.0), dict.fromkeys(TYPES, 0)
    for t in tasks:
        kind = task_type(t)
        mass[kind] += t.u
        count[kind] += 1
    return [mass[k] for k in TYPES] + [float(count[k]) for k in TYPES]


REPRESENTATIONS = {
    'R0': r0_cls,
    'R0-CLP': r0_clp,
    'R1': lambda ts: r0_cls(ts) + period_stats(ts),
    'R2': lambda ts: r0_cls(ts) + period_stats(ts) + structure(ts),
    'R3': lambda ts: r0_cls(ts) + period_stats(ts) + bow(ts) + [float(len(ts))],
    'R4': lambda ts: r0_cls(ts) + period_stats(ts) + structure(ts) + bow(ts),
}


def best_choice(tat, tet) -> int:
    """Index of the option with the lowest TAT; exact ties go to lower TET, then the first option."""
    return min(range(len(tat)), key=lambda i: (tat[i], tet[i], i))


def regret(costs, choice) -> float:
    return costs[choice] / min(costs) - 1
