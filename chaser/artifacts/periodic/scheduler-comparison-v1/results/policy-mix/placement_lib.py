"""Partitioned placement policies shared by the studies, for any task count and periods.

A policy sees each task only through static values (Item: planned U, period in
ms, traffic = L1 misses per microsecond of the task's own execution) and returns
one core index per task. Policies:

  wfd    largest U first onto the least-loaded core (U balance)
  tg     traffic grouping + U balance: high-traffic tasks go by WFD onto the
         fewest cores that keep every core under CORE_CAP, then the other tasks by
         WFD over all cores on top of those loads
  ra     release-aware: local search from wfd minimizing cohort_cost (the sum, over
         the release instants of one hyperperiod, of the busiest core's released
         work), every core under CORE_CAP; experiment 9's `informed` for 16 tasks
         with periods in {20, 40, 80} ms (experiment 2's P' for unequal U)
  ra-tg  release-aware within traffic grouping: the same search started from tg,
         with high-traffic tasks kept on the cores tg gave them
High traffic means more than a core's share of the shared L2 request rate: the
L2 serves one request every 48 ns (footprint/l2_probe.py), so above
TRAFFIC_HIGH per microsecond on every core the L2 saturates.
"""

from dataclasses import dataclass
from functools import reduce
from math import gcd, lcm
import random

CORES = 4
CORE_CAP = 0.95  # margin below 1 for scheduling overhead, as in experiment 9
RESTARTS = 20
L2_REQUESTS_PER_US = 1000 / 48
TRAFFIC_HIGH = L2_REQUESTS_PER_US / CORES
POLICIES = ('wfd', 'tg', 'ra', 'ra-tg')


@dataclass(frozen=True)
class Item:
    u: float
    period: int
    traffic: float


def is_high_traffic(item: Item) -> bool:
    return item.traffic > TRAFFIC_HIGH


def _wfd_into(tasks, indices, cores, load, assign):
    for i in sorted(indices, key=lambda i: (-tasks[i].u, i)):
        core = min(cores, key=lambda c: (load[c], c))
        assign[i] = core
        load[core] += tasks[i].u


def wfd(tasks, cores=CORES) -> list[int]:
    load, assign = [0.0] * cores, {}
    _wfd_into(tasks, range(len(tasks)), range(cores), load, assign)
    return [assign[i] for i in range(len(tasks))]


def traffic_grouped(tasks, cores=CORES, cap=CORE_CAP) -> list[int]:
    high = [i for i, t in enumerate(tasks) if is_high_traffic(t)]
    if not high or len(high) == len(tasks):
        return wfd(tasks, cores)
    for used in range(1, cores + 1):
        load, assign = [0.0] * cores, {}
        _wfd_into(tasks, high, range(used), load, assign)
        if max(load) <= cap:
            break
    _wfd_into(tasks, [i for i in range(len(tasks)) if i not in assign], range(cores), load, assign)
    return [assign[i] for i in range(len(tasks))]


def cohort_cost(assign, tasks, cores=CORES, cap=CORE_CAP) -> float:
    periods = [t.period for t in tasks]
    hyperperiod, step = reduce(lcm, periods), reduce(gcd, periods)
    cost = 0.0
    for instant in range(0, hyperperiod, step):
        work = [0.0] * cores
        for core, t in zip(assign, tasks):
            if instant % t.period == 0:
                work[core] += t.u * t.period
        cost += max(work)
    over = [sum(t.u for c, t in zip(assign, tasks) if c == core) - cap for core in range(cores)]
    return cost + 1e6 * sum(max(0.0, x) for x in over)


def _descend(assign, tasks, cores, cap, allowed):
    best = cohort_cost(assign, tasks, cores, cap)
    improved = True
    while improved:
        improved = False
        for i in range(len(tasks)):
            for c in allowed[i]:
                if c == assign[i]:
                    continue
                trial = list(assign)
                trial[i] = c
                cost = cohort_cost(trial, tasks, cores, cap)
                if cost < best - 1e-9:
                    assign, best, improved = trial, cost, True
        for i in range(len(tasks)):
            for j in range(i + 1, len(tasks)):
                if assign[i] == assign[j] or assign[j] not in allowed[i] or assign[i] not in allowed[j]:
                    continue
                trial = list(assign)
                trial[i], trial[j] = trial[j], trial[i]
                cost = cohort_cost(trial, tasks, cores, cap)
                if cost < best - 1e-9:
                    assign, best, improved = trial, cost, True
    return assign, best


def _search(start, tasks, cores, cap, seed, restarts, allowed):
    best, cost = _descend(start, tasks, cores, cap, allowed)
    rng = random.Random(seed)
    for _ in range(restarts - 1):
        trial, trial_cost = _descend([rng.choice(allowed[i]) for i in range(len(tasks))], tasks, cores, cap,
                                     allowed)
        if trial_cost < cost - 1e-9:
            best, cost = trial, trial_cost
    return best


def release_aware(tasks, cores=CORES, cap=CORE_CAP, seed=0, restarts=RESTARTS) -> list[int]:
    allowed = [range(cores)] * len(tasks)
    return _search(wfd(tasks, cores), tasks, cores, cap, seed, restarts, allowed)


def release_aware_grouped(tasks, cores=CORES, cap=CORE_CAP, seed=0, restarts=RESTARTS) -> list[int]:
    start = traffic_grouped(tasks, cores, cap)
    high = {i for i, t in enumerate(tasks) if is_high_traffic(t)}
    group = sorted({start[i] for i in high}) if high and len(high) < len(tasks) else list(range(cores))
    allowed = [group if i in high else range(cores) for i in range(len(tasks))]
    return _search(start, tasks, cores, cap, seed, restarts, allowed)


def place(policy: str, tasks, seed: int, cores=CORES, cap=CORE_CAP) -> list[int]:
    if policy == 'wfd':
        return wfd(tasks, cores)
    if policy == 'tg':
        return traffic_grouped(tasks, cores, cap)
    if policy == 'ra':
        return release_aware(tasks, cores, cap, seed)
    if policy == 'ra-tg':
        return release_aware_grouped(tasks, cores, cap, seed)
    raise ValueError(f'Unknown placement policy: {policy}')
