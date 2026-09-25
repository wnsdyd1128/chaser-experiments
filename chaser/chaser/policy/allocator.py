"""Offline task placement using the CAAS Algorithm 1 group-selection rules."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import fsum, isfinite

from chaser.locality.features import LocalityRecord, Representation, locality_scalar


@dataclass(frozen=True)
class CoreGroups:
    """Explicit isolated Ω and non-isolated NΩ core IDs; no assumed split."""

    isolated: tuple[int, ...]
    non_isolated: tuple[int, ...]


@dataclass(frozen=True)
class Placement:
    mapping: dict[str, int]
    residual: dict[int, float]
    infeasible: list[str]


def allocate(cases: Mapping[str, LocalityRecord],
             workload: Mapping[str, float | None], cores: CoreGroups, *,
             kind: Representation, threshold: float,
             alpha: float | None = None) -> Placement:
    """Join task IDs to scalars, then place by descending utilization.

    Scalars at or below the threshold use least-loaded Ω; others use worst-fit NΩ.
    Each core has capacity 1. Both branches enforce capacity, never spill into
    the other group, and record failures while continuing. These failure rules
    and ascending task/core ID tie-breaks make the paper's partial policy total.
    Threshold and core split are caller inputs, not calibrated defaults.
    This returns an offline mapping; it does not set RTEMS task affinity.
    """
    core_ids = cores.isolated + cores.non_isolated
    if (not core_ids or len(set(core_ids)) != len(core_ids)
            or any(not isinstance(core, int) or core < 0 for core in core_ids)):
        raise ValueError('Core groups must contain distinct nonnegative core IDs')
    if not isfinite(threshold):
        raise ValueError('Threshold must be finite')

    tasks: list[tuple[str, float, float]] = []
    for task_id, u in workload.items():
        if task_id not in cases:
            raise ValueError(f'Missing locality for task: {task_id}')
        scalar = locality_scalar(kind, cases[task_id], alpha=alpha)
        if scalar is None or not isfinite(scalar) or not 0 <= scalar <= 1:
            raise ValueError('Locality scalar must be finite and within [0, 1]')
        if u is None or not isfinite(u) or u < 0:
            raise ValueError('Utilization must be finite and nonnegative')
        tasks.append((task_id, u, scalar))

    loads: dict[int, list[float]] = {core: [] for core in sorted(core_ids)}
    residual = {core: 1.0 for core in loads}
    mapping: dict[str, int] = {}
    infeasible: list[str] = []
    for task_id, u, scalar in sorted(tasks, key=lambda task: (-task[1], task[0])):
        group = cores.isolated if scalar <= threshold else cores.non_isolated
        # Sum assigned U values to avoid repeated-subtraction errors at capacity.
        candidates = [core for core in group if fsum([*loads[core], u]) <= 1.0]
        if not candidates:
            infeasible.append(task_id)
            continue
        # For fixed U, least load and maximum residual-U have the same ordering.
        core = min(candidates, key=lambda core: (-residual[core], core))
        loads[core].append(u)
        residual[core] = 1.0 - fsum(loads[core])
        mapping[task_id] = core
    return Placement(mapping, residual, infeasible)
