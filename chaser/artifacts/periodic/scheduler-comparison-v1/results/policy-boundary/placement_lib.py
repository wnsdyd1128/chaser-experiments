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
  cg     CLS grouping + U balance: tg with low-CLS tasks (cls <= CLS_LOW) as the group
  ra-cg  release-aware within CLS grouping
  cgb    balanced CLS grouping: cg, but a group core may hold only the mean core load
         plus BALANCE_SLACK (or the group's largest task, if larger), so grouping does not
         pile load onto one core
  ra-cgb release-aware within balanced CLS grouping
High traffic means more than a core's share of the shared L2 request rate: the
L2 serves one request every 48 ns (footprint/l2_probe.py), so above
TRAFFIC_HIGH per microsecond on every core the L2 saturates. CLS_LOW splits the
CLS scale in half; the policy-mix modes (about 0.9 and 0.13 or less) fall on
either side for any cut between 0.17 and 0.87.
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
CLS_LOW = 0.5
BALANCE_SLACK = 0.05
POLICIES = ('wfd', 'tg', 'ra', 'ra-tg')  # the policy-mix study (experiment 17)
CLS_POLICIES = ('cg', 'ra-cg')  # its CLS-keyed counterparts (experiment 18)
BOUNDARY_POLICIES = ('wfd', 'cgb', 'ra', 'ra-cgb')  # the period x memory boundary study (experiment 19)


@dataclass(frozen=True)
class Item:
    u: float
    period: int
    traffic: float
    cls: float = 1.0


def is_high_traffic(item: Item) -> bool:
    return item.traffic > TRAFFIC_HIGH


def is_low_cls(item: Item) -> bool:
    return item.cls <= CLS_LOW


def _wfd_into(tasks, indices, cores, load, assign):
    for i in sorted(indices, key=lambda i: (-tasks[i].u, i)):
        core = min(cores, key=lambda c: (load[c], c))
        assign[i] = core
        load[core] += tasks[i].u


def wfd(tasks, cores=CORES) -> list[int]:
    load, assign = [0.0] * cores, {}
    _wfd_into(tasks, range(len(tasks)), range(cores), load, assign)
    return [assign[i] for i in range(len(tasks))]


def _grouped(tasks, member, cores, cap, balanced=False) -> list[int]:
    """Group members by WFD onto the fewest cores under a per-core limit, the rest by WFD
    over all cores. The limit is cap, or for a balanced grouping the mean core load plus
    BALANCE_SLACK (at least the largest member's U, at most cap)."""
    group = [i for i, t in enumerate(tasks) if member(t)]
    if not group or len(group) == len(tasks):
        return wfd(tasks, cores)
    limit = cap
    if balanced:
        mean = sum(t.u for t in tasks) / cores
        limit = min(cap, max(mean * (1 + BALANCE_SLACK), max(tasks[i].u for i in group)))
    for used in range(1, cores + 1):
        load, assign = [0.0] * cores, {}
        _wfd_into(tasks, group, range(used), load, assign)
        if max(load) <= limit:
            break
    _wfd_into(tasks, [i for i in range(len(tasks)) if i not in assign], range(cores), load, assign)
    return [assign[i] for i in range(len(tasks))]


def traffic_grouped(tasks, cores=CORES, cap=CORE_CAP) -> list[int]:
    return _grouped(tasks, is_high_traffic, cores, cap)


def cls_grouped(tasks, cores=CORES, cap=CORE_CAP) -> list[int]:
    return _grouped(tasks, is_low_cls, cores, cap)


def cls_grouped_balanced(tasks, cores=CORES, cap=CORE_CAP) -> list[int]:
    return _grouped(tasks, is_low_cls, cores, cap, balanced=True)


def _release_table(tasks):
    """(task, released work) per release instant of one hyperperiod; instants without a release add 0."""
    periods = [t.period for t in tasks]
    hyperperiod, step = reduce(lcm, periods), reduce(gcd, periods)
    table = []
    for instant in range(0, hyperperiod, step):
        released = [(i, t.u * t.period) for i, t in enumerate(tasks) if instant % t.period == 0]
        if released:
            table.append(released)
    return table


def _cost(assign, tasks, cores, cap, table) -> float:
    cost = 0.0
    for released in table:
        work = [0.0] * cores
        for i, w in released:
            work[assign[i]] += w
        cost += max(work)
    over = [sum(t.u for c, t in zip(assign, tasks) if c == core) - cap for core in range(cores)]
    return cost + 1e6 * sum(max(0.0, x) for x in over)


def cohort_cost(assign, tasks, cores=CORES, cap=CORE_CAP) -> float:
    return _cost(assign, tasks, cores, cap, _release_table(tasks))


def _descend(assign, tasks, cores, cap, allowed, table):
    cohort_cost = lambda trial, tasks, cores, cap: _cost(trial, tasks, cores, cap, table)
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
    table = _release_table(tasks)
    best, cost = _descend(start, tasks, cores, cap, allowed, table)
    rng = random.Random(seed)
    for _ in range(restarts - 1):
        trial, trial_cost = _descend([rng.choice(allowed[i]) for i in range(len(tasks))], tasks, cores, cap,
                                     allowed, table)
        if trial_cost < cost - 1e-9:
            best, cost = trial, trial_cost
    return best


def release_aware(tasks, cores=CORES, cap=CORE_CAP, seed=0, restarts=RESTARTS) -> list[int]:
    allowed = [range(cores)] * len(tasks)
    return _search(wfd(tasks, cores), tasks, cores, cap, seed, restarts, allowed)


def _release_aware_within(tasks, member, cores, cap, seed, restarts, balanced=False) -> list[int]:
    start = _grouped(tasks, member, cores, cap, balanced)
    group = {i for i, t in enumerate(tasks) if member(t)}
    used = sorted({start[i] for i in group}) if group and len(group) < len(tasks) else list(range(cores))
    allowed = [used if i in group else range(cores) for i in range(len(tasks))]
    return _search(start, tasks, cores, cap, seed, restarts, allowed)


def release_aware_grouped(tasks, cores=CORES, cap=CORE_CAP, seed=0, restarts=RESTARTS) -> list[int]:
    return _release_aware_within(tasks, is_high_traffic, cores, cap, seed, restarts)


def place(policy: str, tasks, seed: int, cores=CORES, cap=CORE_CAP) -> list[int]:
    if policy == 'wfd':
        return wfd(tasks, cores)
    if policy == 'tg':
        return traffic_grouped(tasks, cores, cap)
    if policy == 'ra':
        return release_aware(tasks, cores, cap, seed)
    if policy == 'ra-tg':
        return release_aware_grouped(tasks, cores, cap, seed)
    if policy == 'cg':
        return cls_grouped(tasks, cores, cap)
    if policy == 'ra-cg':
        return _release_aware_within(tasks, is_low_cls, cores, cap, seed, RESTARTS)
    if policy == 'cgb':
        return cls_grouped_balanced(tasks, cores, cap)
    if policy == 'ra-cgb':
        return _release_aware_within(tasks, is_low_cls, cores, cap, seed, RESTARTS, balanced=True)
    raise ValueError(f'Unknown placement policy: {policy}')
