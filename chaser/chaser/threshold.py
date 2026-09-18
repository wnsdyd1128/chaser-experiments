"""Validation-only threshold calibration over the existing offline allocator."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite, nextafter
from statistics import mean
from typing import Literal

from chaser.allocator import CoreGroups, Placement, allocate
from chaser.features import LocalityRecord, Representation, locality_scalar


@dataclass(frozen=True)
class CalibrationWorkload:
    workload_id: str
    family_id: str
    split: Literal['train', 'validation', 'test']
    utilization: Mapping[str, float | None]


@dataclass(frozen=True)
class CandidateResult:
    threshold: float
    failed_workloads: tuple[str, ...]
    placements: dict[str, Placement]
    mean_tat: float | None


@dataclass(frozen=True)
class MappingMeasurement:
    workload_id: str
    mapping: dict[str, int]
    tat: float


@dataclass(frozen=True)
class CalibrationResult:
    """Serialize with dataclasses.asdict and JSON sort_keys=True, allow_nan=False.

    The seed records the caller's experiment protocol; calibration is exhaustive
    and does not sample. A synthetic measurement source is never a measured θ.
    """

    schema_version: int
    protocol: str
    kind: Representation
    alpha: float | None
    threshold: float
    candidates: tuple[CandidateResult, ...]
    common_workloads: tuple[str, ...]
    measurements: tuple[MappingMeasurement, ...]
    cores: CoreGroups
    seed: int
    split_hash: str
    validation_hash: str
    analyzer_version: str
    feature_version: str
    measurement_source: Literal['measured', 'synthetic']


def threshold_candidates(scalars: Iterable[float | None]) -> tuple[float, ...]:
    """Cover each scalar < θ partition, including all-high and all-low.

    Use interval midpoints; if adjacent floats have no representable midpoint,
    the upper value gives the same partition under the allocator's strict <.
    """
    values = list(scalars)
    if not values or any(value is None or not isfinite(value) or not 0 <= value <= 1
                         for value in values):
        raise ValueError('Candidate scalars must be nonempty, finite and within [0, 1]')
    ordered = sorted({value for value in values if value is not None})
    middle = [low + (high - low) / 2 for low, high in zip(ordered, ordered[1:])]
    middle = [high if point <= low else point
              for low, high, point in zip(ordered, ordered[1:], middle)]
    return (ordered[0], *middle, nextafter(ordered[-1], float('inf')))


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                             separators=(',', ':')).encode()).hexdigest()


def calibrate(cases: Mapping[str, LocalityRecord],
              workloads: Iterable[CalibrationWorkload], cores: CoreGroups, *,
              kind: Representation,
              tat: Callable[[str, Mapping[str, int]], float | None],
              seed: int, analyzer_version: str, feature_version: str,
              measurement_source: Literal['measured', 'synthetic'],
              alpha: float | None = None) -> CalibrationResult:
    """Minimize failed workloads, then common-success mean TAT, then θ.

    Family membership must be disjoint across splits. Only validation payloads
    produce candidates, placements or TAT requests. Among minimum-failure
    candidates, compare the intersection of successful workload IDs. An empty
    intersection or missing/nonpositive/nonfinite TAT prevents calibration.

    The callback supplies one TAT summary in a consistent unit per workload and
    exact mapping (e.g. median of repeated measurements). It is called once per
    distinct compared mapping, never for partial placements. Measurement and
    frozen family split construction remain the caller's responsibility.
    Reuse the returned θ unchanged for test allocation; call separately for each
    representation/CLS alpha, using the same validation workload population.
    """
    if measurement_source not in ('measured', 'synthetic'):
        raise ValueError('Specify measured or synthetic TAT provenance')
    if not analyzer_version or not feature_version:
        raise ValueError('Analyzer and feature versions are required')
    if kind == 'cls':
        if alpha is None or not isfinite(alpha) or alpha < 0:
            raise ValueError('CLS requires a finite nonnegative alpha')
    elif alpha is not None:
        raise ValueError('Alpha applies only to CLS')

    rows = sorted(workloads, key=lambda row: row.workload_id)
    ids: set[str] = set()
    families: dict[str, str] = {}
    for row in rows:
        if not row.workload_id or row.workload_id in ids or not row.family_id:
            raise ValueError('Workload IDs must be unique and family IDs nonempty')
        if row.split not in ('train', 'validation', 'test'):
            raise ValueError('Unknown dataset split')
        if row.family_id in families and families[row.family_id] != row.split:
            raise ValueError('A family must not cross dataset splits')
        ids.add(row.workload_id)
        families[row.family_id] = row.split
    validation = [row for row in rows if row.split == 'validation']
    if not validation or any(not row.utilization for row in validation):
        raise ValueError('Nonempty validation workloads are required')

    task_ids = sorted({task for row in validation for task in row.utilization})
    scalars: dict[str, float | None] = {}
    for task in task_ids:
        if task not in cases:
            raise ValueError(f'Missing locality for task: {task}')
        scalars[task] = locality_scalar(kind, cases[task], alpha=alpha)
    thresholds = threshold_candidates(scalars.values())
    placements = [{row.workload_id: allocate(cases, row.utilization, cores,
                                           kind=kind, threshold=theta, alpha=alpha)
                   for row in validation} for theta in thresholds]
    failures = [tuple(key for key, placement in candidate.items() if placement.infeasible)
                for candidate in placements]
    minimum = min(map(len, failures))
    finalists = [i for i, failed in enumerate(failures) if len(failed) == minimum]
    common = tuple(sorted(set(row.workload_id for row in validation).difference(
        *(set(failures[i]) for i in finalists))))
    if not common:
        raise ValueError('No common successful validation workloads among finalists')

    measurements: list[MappingMeasurement] = []
    cache: dict[tuple[str, tuple[tuple[str, int], ...]], float] = {}
    scores: dict[int, float] = {}
    for i in finalists:
        values: list[float] = []
        for workload_id in common:
            mapping = placements[i][workload_id].mapping
            key = (workload_id, tuple(sorted(mapping.items())))
            if key not in cache:
                value = tat(workload_id, dict(mapping))
                if value is None or not isfinite(value) or value <= 0:
                    raise ValueError(f'Missing or invalid TAT for workload: {workload_id}')
                cache[key] = value
                measurements.append(MappingMeasurement(workload_id, dict(mapping), value))
            values.append(cache[key])
        scores[i] = mean(values)
    winner = min(finalists, key=lambda i: (scores[i], thresholds[i]))
    candidates = tuple(CandidateResult(theta, failures[i], placements[i], scores.get(i))
                       for i, theta in enumerate(thresholds))
    return CalibrationResult(
        schema_version=1, protocol='failed-workloads/common-mean-tat/min-theta-v1',
        kind=kind, alpha=alpha, threshold=thresholds[winner], candidates=candidates,
        common_workloads=common, measurements=tuple(measurements),
        cores=CoreGroups(tuple(sorted(cores.isolated)), tuple(sorted(cores.non_isolated))),
        seed=seed,
        split_hash=_digest([(row.workload_id, row.family_id, row.split) for row in rows]),
        validation_hash=_digest({'scalars': scalars, 'workloads': {
            row.workload_id: dict(row.utilization) for row in validation}}),
        analyzer_version=analyzer_version, feature_version=feature_version,
        measurement_source=measurement_source,
    )
