"""Capacity-weighted locality from unconditional two-level first-hit ratios."""

from math import fsum, isclose, isfinite
from typing import TypedDict

DEFAULT_ALPHAS: tuple[float, ...] = (0.0, 0.3, 0.5, 0.7, 1.0)


class CacheSpec(TypedDict):
    l1_capacity: int
    llc_capacity: int


class ClpProfile(TypedDict):
    modeled_accesses: int
    l1_first_hit_ratio: float | None
    llc_first_hit_ratio: float | None
    all_cache_miss_ratio: float | None


def level_weights(cache: CacheSpec, alpha: float) -> dict[str, float]:
    """Use byte capacities with L1 as the smallest level; alpha must be nonnegative."""
    if not isfinite(alpha) or alpha < 0:
        raise ValueError('Alpha must be finite and nonnegative')
    l1, llc = cache['l1_capacity'], cache['llc_capacity']
    if not isfinite(l1) or not isfinite(llc) or not 0 < l1 <= llc:
        raise ValueError('Capacities must be finite and satisfy 0 < L1 <= LLC')
    return {'L1': 1.0, 'LLC': (l1 / llc) ** alpha}


def cls(profile: ClpProfile, cache: CacheSpec, alpha: float) -> float | None:
    """Return None for no accesses; ratios share the modeled-access population."""
    weights = level_weights(cache, alpha)
    if profile['modeled_accesses'] < 0:
        raise ValueError('Modeled accesses must be nonnegative')
    if profile['modeled_accesses'] == 0:
        return None
    ratios = [profile[key] for key in ('l1_first_hit_ratio', 'llc_first_hit_ratio',
                                       'all_cache_miss_ratio')]
    if any(p is None or not isfinite(p) or not 0 <= p <= 1 for p in ratios):
        raise ValueError('First-hit and miss ratios must be finite and within [0, 1]')
    l1, llc, miss = ratios
    if not isclose(fsum((l1, llc, miss)), 1.0, rel_tol=0, abs_tol=1e-12):
        raise ValueError('First-hit and miss ratios must sum to one')
    # Bound only floating-point roundoff accepted by the conservation check.
    return min(1.0, l1 + weights['LLC'] * llc)
