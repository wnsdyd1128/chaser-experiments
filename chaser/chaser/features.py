"""Select exported locality scalars and preserve the CAAS 11-feature interface."""

from collections.abc import Iterable, Mapping, Sequence
from math import fsum, isfinite
from statistics import mean, median, pstdev
from typing import Literal, TypeAlias, TypedDict

Representation: TypeAlias = Literal['caas-ca', 'ca-line', 'ca-csrd', 'cls']
ScalarField: TypeAlias = Literal['ca_caas_element', 'ca_global_line', 'ca_csrd_l1']


class LocalityRecord(TypedDict, total=False):
    """Fields consumed from an export; missing or null inputs are checked at use."""

    ca_caas_element: float | None
    ca_global_line: float | None
    ca_csrd_l1: float | None
    cls: Mapping[str, float | None]
    utilization: float | None


FEATURE_NAMES: tuple[str, ...] = (
    'ca_mean', 'ca_std', 'ca_min', 'ca_max', 'ca_median',
    'u_mean', 'u_std', 'u_min', 'u_max', 'u_median', 'u_sum',
)


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
    """Reject incomplete samples; use population std (NumPy ddof=0), without scaling.

    Each case record must include utilization joined by task ID by the caller.
    Legacy ca_* names refer to the selected scalar for every representation.
    """
    locality: list[float] = []
    utilization: list[float] = []
    for task in tasks:
        scalar = locality_scalar(kind, task, alpha=alpha)
        u = task.get('utilization')
        if scalar is None or not isfinite(scalar) or not 0 <= scalar <= 1:
            raise ValueError('Locality scalar must be finite and within [0, 1]')
        if u is None or not isfinite(u) or u < 0:
            raise ValueError('Utilization must be finite and nonnegative')
        locality.append(scalar)
        utilization.append(u)
    if not locality:
        raise ValueError('A workload must contain at least one task')

    def stats(values: Sequence[float]) -> list[float]:
        return [mean(values), pstdev(values), min(values), max(values), median(values)]

    return stats(locality) + stats(utilization) + [fsum(utilization)]
