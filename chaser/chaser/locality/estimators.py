"""S1 estimators consume C++ histograms; Python only thresholds and scores them."""

from math import sqrt

from chaser.locality.cache_reference import CacheLevel, FirstHits, validate_hierarchy


def _count(value) -> int:
    if type(value) is not int or value < 0:
        raise ValueError('Histogram counts must be nonnegative integers')
    return value


def _histogram(profile: dict, key: str) -> tuple[dict[int, int], int]:
    histogram = {}
    for distance, count in profile[key].items():
        if type(distance) is int:
            rd = distance
        elif isinstance(distance, str) and distance.isascii() and distance.isdecimal():
            rd = int(distance)
        else:
            raise ValueError('Histogram distances must be nonnegative integers')
        if rd < 0 or rd in histogram:
            raise ValueError('Invalid or duplicate histogram distance')
        histogram[rd] = _count(count)
    cold = _count(profile['cold_misses'])
    if 'total_reuses' in profile and _count(profile['total_reuses']) != sum(histogram.values()):
        raise ValueError('Histogram population disagrees with total_reuses')
    return histogram, cold


def global_rd(profile: dict, l1: CacheLevel, llc: CacheLevel) -> FirstHits:
    """Bin full-stream cache-line RD by capacity; cold is always memory.

    This control is not a demand-hierarchy simulation: the LLC threshold uses
    the same full-stream RD as L1, not a distance recomputed on L1 misses.
    """
    validate_hierarchy(l1, llc)
    histogram, cold = _histogram(profile, 'histogram')
    first = sum(n for rd, n in histogram.items() if rd < l1.lines)
    second = sum(n for rd, n in histogram.items() if l1.lines <= rd < llc.lines)
    return FirstHits(first, second, cold + sum(histogram.values()) - first - second)


def csrd_counts(task: dict, l1: CacheLevel, llc: CacheLevel) -> FirstHits:
    """Apply RD_set < ways independently on each level's own request stream."""
    validate_hierarchy(l1, llc)
    population = _count(task['modeled_accesses'])
    hits = []
    for key, level in (('l1', l1), ('llc', llc)):
        profile = task[key]
        histogram, cold = _histogram(profile, 'csrd_histogram')
        if _count(profile['lookups']) != population or cold + sum(histogram.values()) != population:
            raise ValueError('CSRD lookup population does not conserve requests')
        hit = sum(n for rd, n in histogram.items() if rd < level.ways)
        hits.append(hit)
        population -= hit
    return FirstHits(*hits, population)


def compare(predicted: FirstHits, reference: FirstHits) -> dict | None:
    """Return per-component ratio errors, with equal weighting across L1/LLC/miss."""
    if predicted.total != reference.total:
        raise ValueError('Prediction and reference population differ')
    if not reference.total:
        return None
    errors = [abs(p - r) for p, r in zip(predicted.ratios, reference.ratios)]
    return {'absolute_error': errors, 'mae': sum(errors) / 3,
            'rmse': sqrt(sum(e * e for e in errors) / 3),
            'max_absolute_error': max(errors)}
