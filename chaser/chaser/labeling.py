"""Architecture labels from comparable, complete repeated measurements."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Literal

LABEL_RULE_ID = 'median-tat/median-tet/min-label-v1'


@dataclass(frozen=True)
class Measurement:
    workload_id: str
    architecture: int
    topology_id: str
    allocator_id: str
    mapping_hash: str
    run_id: str
    tet: float | None
    tat: float | None
    execution_status: str
    measurement_source: Literal['measured', 'synthetic']
    time_unit: str = 'ns'


@dataclass(frozen=True)
class LabelResult:
    label: int
    medians: dict[int, tuple[float, float]]  # TAT, TET
    tat_ties: tuple[int, ...]
    final_ties: tuple[int, ...]
    label_rule_id: str = LABEL_RULE_ID


def label_measurements(rows: Iterable[Measurement], *, expected_runs: int) -> LabelResult:
    """Require all planned runs; do not label partial or failed comparisons.

    Topology and mapping must stay fixed within each architecture, while the
    allocator, measurement units and source must match across architectures.
    """
    rows = list(rows)
    if type(expected_runs) is not int or expected_runs < 1 or not rows:
        raise ValueError('Positive expected_runs and measurements are required')
    if len({(r.workload_id, r.allocator_id, r.time_unit, r.measurement_source)
            for r in rows}) != 1:
        raise ValueError('Mixed workload, allocator, time unit or measurement source')
    for r in rows:
        if (type(r.architecture) is not int or r.architecture not in (0, 1, 2)
                or not all((r.workload_id, r.topology_id, r.allocator_id,
                            r.mapping_hash, r.run_id, r.time_unit))
                or r.measurement_source not in ('measured', 'synthetic')):
            raise ValueError('Invalid measurement identity or provenance')
        if r.execution_status != 'ok':
            raise ValueError('Failed execution prevents labeling')
        if any(v is None or not isfinite(v) or v <= 0 for v in (r.tat, r.tet)):
            raise ValueError('Positive finite TAT and TET are required')
    medians = {}
    for a in (0, 1, 2):
        group = [r for r in rows if r.architecture == a]
        if len(group) != expected_runs or len({r.run_id for r in group}) != expected_runs:
            raise ValueError('Missing or duplicate architecture runs')
        if len({(r.topology_id, r.mapping_hash) for r in group}) != 1:
            raise ValueError('Topology and mapping must be fixed per architecture')
        medians[a] = (median(r.tat for r in group), median(r.tet for r in group))
    best_tat = min(v[0] for v in medians.values())
    tat_ties = tuple(a for a in medians if medians[a][0] == best_tat)
    best_tet = min(medians[a][1] for a in tat_ties)
    final_ties = tuple(a for a in tat_ties if medians[a][1] == best_tet)
    return LabelResult(final_ties[0], medians, tat_ties, final_ties)
