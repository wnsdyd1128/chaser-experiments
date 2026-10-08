"""Nominal Partitioned check and CHASER's placement: U-balanced WFD, balanced CLS grouping, release-aware search.

A task is a dict with u (planned utilization), period (ms) and cls. Placements return one core per task and
reproduce placement_lib (scheduler-comparison-v1) for wfd, cgb and ra-cgb, including its tie rules and the
seeded random restarts of the release search.
"""

from functools import reduce
from math import gcd, lcm
import random

CORES = 4
CORE_CAP = 0.95  # nominal per-core capacity: a margin below 1 for scheduling overhead
CLS_LOW = 0.5  # tasks at or below form the low-affinity group
BALANCE_SLACK = 0.05  # a group core may hold the mean core load x 1.05 (or the group's largest task)
RESTARTS = 20


def _wfd_into(tasks, indices, cores, load, assign):
    for i in sorted(indices, key=lambda i: (-tasks[i]['u'], i)):
        core = min(cores, key=lambda c: (load[c], c))
        assign[i] = core
        load[core] += tasks[i]['u']


def wfd(tasks, cores=CORES) -> list[int]:
    load, assign = [0.0] * cores, {}
    _wfd_into(tasks, range(len(tasks)), range(cores), load, assign)
    return [assign[i] for i in range(len(tasks))]


def core_loads(tasks, mapping, cores=CORES) -> list[float]:
    return [sum(t['u'] for t, c in zip(tasks, mapping) if c == core) for core in range(cores)]


def valid(tasks, mapping, cores=CORES, cap=CORE_CAP) -> bool:
    """Every task on exactly one existing core and no core above the nominal capacity."""
    return len(mapping) == len(tasks) and all(c in range(cores) for c in mapping) and \
        max(core_loads(tasks, mapping, cores)) <= cap + 1e-12


def nominal(tasks, cores=CORES, cap=CORE_CAP) -> dict:
    """feasible (with a WFD witness), proven_infeasible (a task or the total exceeds the capacity) or unknown."""
    if any(t['u'] > cap for t in tasks) or sum(t['u'] for t in tasks) > cores * cap:
        return dict(status='proven_infeasible', witness=None)
    witness = wfd(tasks, cores)
    if valid(tasks, witness, cores, cap):
        return dict(status='feasible', witness=witness)
    return dict(status='unknown', witness=None)


def _low(task) -> bool:
    return task['cls'] <= CLS_LOW


def grouped_balanced(tasks, cores=CORES, cap=CORE_CAP) -> list[int]:
    """Low-CLS tasks by WFD onto the fewest cores under the balanced limit, the rest by WFD over all cores."""
    group = [i for i, t in enumerate(tasks) if _low(t)]
    if not group or len(group) == len(tasks):
        return wfd(tasks, cores)
    mean = sum(t['u'] for t in tasks) / cores
    limit = min(cap, max(mean * (1 + BALANCE_SLACK), max(tasks[i]['u'] for i in group)))
    for used in range(1, cores + 1):
        load, assign = [0.0] * cores, {}
        _wfd_into(tasks, group, range(used), load, assign)
        if max(load) <= limit:
            break
    _wfd_into(tasks, [i for i in range(len(tasks)) if i not in assign], range(cores), load, assign)
    return [assign[i] for i in range(len(tasks))]


def _release_table(tasks):
    """(task, released work) per release instant of one hyperperiod; instants without a release add 0."""
    periods = [t['period'] for t in tasks]
    hyperperiod, step = reduce(lcm, periods), reduce(gcd, periods)
    table = []
    for instant in range(0, hyperperiod, step):
        released = [(i, t['u'] * t['period']) for i, t in enumerate(tasks) if instant % t['period'] == 0]
        if released:
            table.append(released)
    return table


def _cost(assign, tasks, cores, cap, table) -> float:
    """Sum over release instants of the busiest core's released work, plus a large penalty above capacity."""
    cost = 0.0
    for released in table:
        work = [0.0] * cores
        for i, w in released:
            work[assign[i]] += w
        cost += max(work)
    over = [sum(t['u'] for c, t in zip(assign, tasks) if c == core) - cap for core in range(cores)]
    return cost + 1e6 * sum(max(0.0, x) for x in over)


def _descend(assign, tasks, cores, cap, allowed, table):
    best = _cost(assign, tasks, cores, cap, table)
    improved = True
    while improved:
        improved = False
        for i in range(len(tasks)):
            for c in allowed[i]:
                if c == assign[i]:
                    continue
                trial = list(assign)
                trial[i] = c
                cost = _cost(trial, tasks, cores, cap, table)
                if cost < best - 1e-9:
                    assign, best, improved = trial, cost, True
        for i in range(len(tasks)):
            for j in range(i + 1, len(tasks)):
                if assign[i] == assign[j] or assign[j] not in allowed[i] or assign[i] not in allowed[j]:
                    continue
                trial = list(assign)
                trial[i], trial[j] = trial[j], trial[i]
                cost = _cost(trial, tasks, cores, cap, table)
                if cost < best - 1e-9:
                    assign, best, improved = trial, cost, True
    return assign, best


def release_aware_grouped(tasks, seed=0, cores=CORES, cap=CORE_CAP, restarts=RESTARTS) -> list[int]:
    """CHASER's placement (ra-cgb): local search from the balanced CLS grouping that lowers the release cost,
    low-CLS tasks kept on the group's cores; restarts from seeded random starts within the same constraint."""
    start = grouped_balanced(tasks, cores, cap)
    group = {i for i, t in enumerate(tasks) if _low(t)}
    used = sorted({start[i] for i in group}) if group and len(group) < len(tasks) else list(range(cores))
    allowed = [used if i in group else range(cores) for i in range(len(tasks))]
    table = _release_table(tasks)
    best, cost = _descend(start, tasks, cores, cap, allowed, table)
    rng = random.Random(seed)
    for _ in range(restarts - 1):
        trial, trial_cost = _descend([rng.choice(allowed[i]) for i in range(len(tasks))], tasks, cores, cap,
                                     allowed, table)
        if trial_cost < cost - 1e-9:
            best, cost = trial, trial_cost
    return best
