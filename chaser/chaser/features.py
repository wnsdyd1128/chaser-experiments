"""Build scalar or cache-level profile features for architecture selection."""

from collections.abc import Iterable, Mapping, Sequence
from math import fsum, isclose, isfinite
from statistics import mean, median, pstdev
from typing import Literal, TypeAlias, TypedDict

Representation: TypeAlias = Literal['caas-ca', 'ca-line', 'ca-csrd', 'cls', 'clp']
ScalarField: TypeAlias = Literal['ca_caas_element', 'ca_global_line', 'ca_csrd_l1']


class LocalityRecord(TypedDict, total=False):
    """Fields consumed from an export; missing or null inputs are checked at use."""

    ca_caas_element: float | None
    ca_global_line: float | None
    ca_csrd_l1: float | None
    cls: Mapping[str, float | None]
    clp: Sequence[float] | None
    utilization: float | None


FEATURE_NAMES: tuple[str, ...] = (
    'ca_mean', 'ca_std', 'ca_min', 'ca_max', 'ca_median',
    'u_mean', 'u_std', 'u_min', 'u_max', 'u_median', 'u_sum',
)
CLP_FEATURE_NAMES: tuple[str, ...] = tuple(
    f'{component}_{stat}'
    for component in ('p_l1_hit', 'p_llc_hit', 'p_miss')
    for stat in ('mean', 'std', 'min', 'max', 'median')
) + FEATURE_NAMES[5:]
CLP_FEATURE_VERSION = 'clp-21/population-std/task-id-join-v1'


def _stats(values: Sequence[float]) -> list[float]:
    return [mean(values), pstdev(values), min(values), max(values), median(values)]


def locality_scalar(kind: Representation, task_result: LocalityRecord, *,
                    alpha: float | None = None) -> float | None:
    """Read a locality.json case; CLS requires a precomputed string-keyed alpha map."""
    fields: dict[str, ScalarField] = {
        'caas-ca': 'ca_caas_element', 'ca-line': 'ca_global_line',
        'ca-csrd': 'ca_csrd_l1',
    }
    if kind == 'cls':
        if alpha is None:
            raise ValueError('CLS requires an explicit alpha')
        values = task_result.get('cls', {})
        key = str(float(alpha))
        if key not in values:
            raise ValueError(f'Missing CLS for alpha={key}')
        return values[key]
    if kind not in fields:
        raise ValueError(f'Unknown representation: {kind}')
    if fields[kind] not in task_result:
        raise ValueError(f'Missing scalar: {fields[kind]}')
    return task_result[fields[kind]]


def build_features(tasks: Iterable[LocalityRecord], kind: Representation, *,
                   alpha: float | None = None) -> list[float]:
    """Reject incomplete samples; use population std (ddof=0), without scaling.

    Each case record must include utilization joined by task ID by the caller.
    Legacy ca_* names refer to the selected scalar for every representation.
    CLP uses L1/LLC/miss components in that order and never uses alpha.
    """
    locality: list[float] = []
    profiles: list[list[float]] = [[], [], []]
    utilization: list[float] = []
    if kind == 'clp' and alpha is not None:
        raise ValueError('CLP features do not use alpha')
    for task in tasks:
        u = task.get('utilization')
        if u is None or not isfinite(u) or u < 0:
            raise ValueError('Utilization must be finite and nonnegative')
        if kind == 'clp':
            profile = task.get('clp')
            if (not isinstance(profile, (list, tuple)) or len(profile) != 3
                    or any(not isfinite(p) or not 0 <= p <= 1 for p in profile)
                    or not isclose(fsum(profile), 1, rel_tol=0, abs_tol=1e-12)):
                raise ValueError('CLP must be a finite three-component probability profile')
            for values, p in zip(profiles, profile):
                values.append(p)
        else:
            scalar = locality_scalar(kind, task, alpha=alpha)
            if scalar is None or not isfinite(scalar) or not 0 <= scalar <= 1:
                raise ValueError('Locality scalar must be finite and within [0, 1]')
            locality.append(scalar)
        utilization.append(u)
    if not utilization:
        raise ValueError('A workload must contain at least one task')
    local_features = ([stat for values in profiles for stat in _stats(values)]
                      if kind == 'clp' else _stats(locality))
    return local_features + _stats(utilization) + [fsum(utilization)]
