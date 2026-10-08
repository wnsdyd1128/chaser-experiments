"""Fixed-length rows of the pre-run RF: set, cache, memory and candidate features (feature set f35m).

A row describes one (task set, candidate configuration). Tasks are inputs.task_values dicts; a candidate is one of
CANDIDATES with its core mapping (Global and Clustered candidates use the U-balanced mapping, as in the experiments).
Values reproduce rf_devcheck, rf_candidates and rf_occupancy (scheduler-comparison-v1) value for value.
"""

from functools import reduce
from math import gcd, lcm
from statistics import mean, pstdev

from .placement import CLS_LOW, CORES

L2_REQUESTS_PER_US = 1000 / 48  # the shared L2 serves one request every 48 ns (laysim, experiment 8)
MEMORY_REQUESTS_PER_US = 1000 / 220  # memory serves one access every 220 ns
L2_KIB = 2048
DOMAINS = {'p': [[0], [1], [2], [3]], 'g': [[0, 1, 2, 3]], 'c13': [[0], [1, 2, 3]], 'c112': [[0], [1], [2, 3]]}
CANDIDATES = ('wfd', 'cgb', 'ra-cgb', 'ra-cgk', 'g', 'c13', 'c112')
GC_CANDIDATES = ('g', 'c13', 'c112')


def set_features(tasks) -> dict:
    us = [t['u'] for t in tasks]
    periods = [t['period'] for t in tasks]
    cache_demand = sum(t['u'] * t['rate'] for t in tasks) / L2_REQUESTS_PER_US
    memory_demand = sum(t['u'] * t['rate'] * t['p_mem'] / (1 - t['p_l1']) for t in tasks) / MEMORY_REQUESTS_PER_US
    return dict(tasks=len(tasks), total_u=sum(us), max_u=max(us), u_cv=pstdev(us) / mean(us),
                heavy_tasks=sum(u > 0.5 for u in us), period_cv=pstdev(periods) / mean(periods),
                distinct_periods=len(set(periods)), cache_demand=cache_demand,
                low_affinity_u=sum(t['u'] for t in tasks if t['cls'] <= CLS_LOW),
                weighted_one_minus_cls=sum(t['u'] * (1 - t['cls']) for t in tasks),
                working_set_over_l2=sum(t['working_set_kib'] for t in tasks) / L2_KIB,
                max_working_set_kib=max(t['working_set_kib'] for t in tasks),
                memory_demand=memory_demand, occupancy=cache_demand + memory_demand)


def _release_features(tasks, mapping, domains) -> dict:
    periods = [t['period'] for t in tasks]
    hyperperiod, step = reduce(lcm, periods), reduce(gcd, periods)
    where = {core: i for i, d in enumerate(domains) for core in d}
    crowded = even = peak0 = 0.0
    for instant in range(0, hyperperiod, step):
        work = [0.0] * len(domains)
        for t, core in zip(tasks, mapping):
            if instant % t['period'] == 0:
                work[where[core]] += t['u'] * t['period']
        busiest = max(w / len(d) for w, d in zip(work, domains))
        crowded += busiest
        even += sum(work) / CORES
        if instant == 0:
            peak0 = busiest
    return dict(release_crowding=crowded / even, t0_peak=peak0 / min(periods))


def _group_features(tasks, mapping) -> dict:
    low = [(t, c) for t, c in zip(tasks, mapping) if t['cls'] <= CLS_LOW]
    if not low:
        return dict(effective_group_core_u=0.0, other_u_on_group_cores=0.0)
    others = [(t, c) for t, c in zip(tasks, mapping) if t['cls'] > CLS_LOW]
    cores = {c for _, c in low}
    rate = lambda ts: sum(t['rate'] for t, _ in ts) / len(ts) if ts else 0.0
    kappa = max(1.0, (len(cores) * rate(low) + (CORES - len(cores)) * rate(others)) / L2_REQUESTS_PER_US)
    core_u = max(sum(t['u'] for t, k in zip(tasks, mapping) if k == c) for c in cores)
    return dict(effective_group_core_u=core_u * kappa, other_u_on_group_cores=sum(t['u'] for t, c in others if c in cores))


def candidate_features(tasks, mapping, candidate) -> dict:
    config = candidate if candidate in GC_CANDIDATES else 'p'
    core_u = [sum(t['u'] for t, k in zip(tasks, mapping) if k == c) for c in range(CORES)]
    groups = sorted({c for t, c in zip(tasks, mapping) if t['cls'] <= CLS_LOW}) if config == 'p' else []
    out = {f'is_{c}': int(c == candidate) for c in CANDIDATES}
    out.update(max_domain_u=max(sum(core_u[c] for c in d) / len(d) for d in DOMAINS[config]),
               group_cores=len(groups), max_group_core_u=max((core_u[c] for c in groups), default=0.0))
    out.update(_release_features(tasks, mapping, DOMAINS[config]))
    out.update(_group_features(tasks, mapping) if config == 'p' else dict(effective_group_core_u=0.0,
                                                                          other_u_on_group_cores=0.0))
    return out


def row(tasks, mapping, candidate, names) -> list[float]:
    """The feature vector in the frozen model's order."""
    values = dict(set_features(tasks), **candidate_features(tasks, mapping, candidate))
    return [float(values[n]) for n in names]
