"""Plan and select P-only thresholds from the current measurement contract."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from statistics import mean, median
from typing import Literal

from chaser.policy.allocator import CoreGroups, allocate
from chaser.locality.features import LocalityRecord, Representation, locality_scalar
from chaser.periodic.measurement import CONTRACT
from chaser.periodic.dataset import load_batch


MappingKey = tuple[str, tuple[tuple[str, int], ...]]
POLICIES = (('caas-ca', None), ('ca-csrd', None),
            ('cls', 0.0), ('cls', 0.3), ('cls', 0.5), ('cls', 0.7), ('cls', 1.0))


@dataclass(frozen=True)
class CalibrationWorkload:
    workload_id: str
    split_group_id: str
    utilization: Mapping[str, float]
    split: Literal['calibration'] = 'calibration'


@dataclass(frozen=True)
class Candidate:
    threshold: float
    mappings: dict[str, dict[str, int]]
    allocation_failures: tuple[str, ...]


@dataclass(frozen=True)
class CalibrationPlan:
    workload_ids: tuple[str, ...]
    candidates: tuple[Candidate, ...]
    measurement_requests: tuple[MappingKey, ...]


@dataclass(frozen=True)
class MeasurementOutcome:
    status: Literal['ok', 'workload_failure', 'infrastructure_error']
    median_tat_ns: float | None
    reason: str | None = None


@dataclass(frozen=True)
class CandidateScore:
    threshold: float
    failed_workloads: tuple[str, ...]
    mean_tat_ns: float | None


@dataclass(frozen=True)
class CalibrationSelection:
    status: Literal['complete', 'partial_coverage', 'calibration_unresolved']
    threshold: float | None
    common_workloads: tuple[str, ...]
    candidates: tuple[CandidateScore, ...]


def threshold_candidates(scalars: Sequence[float | None]) -> tuple[float, ...]:
    """Return exactly the allowed endpoints and observed D_theta scalar values."""
    if (not scalars or any(value is None or not isfinite(value) or not 0 <= value <= 1
                           for value in scalars)):
        raise ValueError('Calibration scalars must be finite and within [0, 1]')
    return tuple(sorted({0.0, 1.0, *scalars}))


def mapping_key(workload_id: str, mapping: Mapping[str, int]) -> MappingKey:
    """Identify a P mapping inside one workload; runtime identity is pinned separately."""
    return workload_id, tuple(sorted(mapping.items()))


def plan_calibration(cases: Mapping[str, LocalityRecord],
                     workloads: Sequence[CalibrationWorkload], cores: CoreGroups, *,
                     kind: Representation, alpha: float | None = None) -> CalibrationPlan:
    """Request every feasible candidate P mapping before execution failures are known."""
    if kind == 'cls':
        if alpha not in (0, 0.3, 0.5, 0.7, 1):
            raise ValueError('CLS alpha must be one of the five frozen values')
    elif kind not in ('caas-ca', 'ca-csrd') or alpha is not None:
        raise ValueError('Calibrate CAAS-CA, CA-CSRD and five CLS alphas')
    rows = sorted(workloads, key=lambda row: row.workload_id)
    if (not rows or any(row.split != 'calibration' or not row.workload_id
                        or not row.split_group_id or not row.utilization for row in rows)
            or len({row.workload_id for row in rows}) != len(rows)):
        raise ValueError('Only distinct nonempty D_theta workloads are allowed')
    task_ids = sorted({task for row in rows for task in row.utilization})
    if len(task_ids) != sum(len(row.utilization) for row in rows):
        raise ValueError('Calibration task IDs must be unique across workloads')
    if any(task not in cases for task in task_ids):
        raise ValueError('Missing calibration task locality')
    scalars = [locality_scalar(kind, cases[task], alpha=alpha) for task in task_ids]
    thresholds = threshold_candidates(scalars)
    requests: dict[MappingKey, None] = {}
    candidates = []
    for theta in thresholds:
        mappings, failures = {}, []
        for row in rows:
            placement = allocate(cases, row.utilization, cores, kind=kind,
                                 alpha=alpha, threshold=theta)
            if placement.infeasible:
                failures.append(row.workload_id)
            else:
                mappings[row.workload_id] = placement.mapping
                requests[mapping_key(row.workload_id, placement.mapping)] = None
        candidates.append(Candidate(theta, mappings, tuple(failures)))
    return CalibrationPlan(tuple(row.workload_id for row in rows), tuple(candidates),
                           tuple(requests))


def plan_all_policies(cases: Mapping[str, LocalityRecord],
                      workloads: Sequence[CalibrationWorkload], cores: CoreGroups) -> dict[str, CalibrationPlan]:
    """Plan the two CA and five CLS thresholds on one D_theta population."""
    return {kind if alpha is None else f'cls-{alpha:g}':
            plan_calibration(cases, workloads, cores, kind=kind, alpha=alpha)
            for kind, alpha in POLICIES}


def select_threshold(plan: CalibrationPlan,
                     outcomes: Mapping[MappingKey, MeasurementOutcome]) -> CalibrationSelection:
    """Minimize all failures, compare common-success mean TAT, then smaller theta."""
    if set(outcomes) != set(plan.measurement_requests):
        raise ValueError('Every exact P mapping needs one measurement outcome')
    for outcome in outcomes.values():
        if outcome.status == 'infrastructure_error':
            raise ValueError('Unresolved infrastructure error in calibration evidence')
        if outcome.status == 'ok':
            if (outcome.median_tat_ns is None or not isfinite(outcome.median_tat_ns)
                    or outcome.median_tat_ns <= 0):
                raise ValueError('Successful P mapping needs a positive finite median TAT')
        elif outcome.status != 'workload_failure' or outcome.median_tat_ns is not None:
            raise ValueError('Invalid P mapping measurement outcome')
    failures = []
    for candidate in plan.candidates:
        failed = set(candidate.allocation_failures)
        failed.update(name for name, mapping in candidate.mappings.items()
                      if outcomes[mapping_key(name, mapping)].status == 'workload_failure')
        failures.append(tuple(sorted(failed)))
    minimum = min(map(len, failures))
    finalists = [i for i, failed in enumerate(failures) if len(failed) == minimum]
    common = tuple(name for name in plan.workload_ids
                   if all(name not in failures[i] for i in finalists))
    scores: dict[int, float] = {}
    if common:
        for i in finalists:
            scores[i] = mean(outcomes[mapping_key(name, plan.candidates[i].mappings[name])]
                             .median_tat_ns for name in common)
        winner = min(finalists, key=lambda i: (scores[i], plan.candidates[i].threshold))
        status = 'complete' if minimum == 0 else 'partial_coverage'
        theta = plan.candidates[winner].threshold
    else:
        status, theta = 'calibration_unresolved', None
    candidates = tuple(CandidateScore(candidate.threshold, failures[i], scores.get(i))
                       for i, candidate in enumerate(plan.candidates))
    return CalibrationSelection(status, theta, common, candidates)


_WORKLOAD_FAILURES = {'deadline_miss', 'postponed_job', 'period_status',
                      'job_completeness'}


def classify_p_batch(snapshot: Path, directory: Path, *, expected_runs: int,
                     timeout: float, simulator_hash: str) -> MeasurementOutcome:
    """Require all repeats; only target scheduling failures count against theta."""
    try:
        plan = json.loads((snapshot / 'p/plan.json').read_text())
        protocol = json.loads((directory / 'protocol.json').read_text())
        expected = dict(runs=expected_runs, timeout_seconds=timeout, mode=0,
                        trace=False, empty=False, simulator_hash=simulator_hash,
                        contract_id=CONTRACT, plan_hash=plan['plan_hash'])
        if (plan['contract_id'] != CONTRACT
                or any(protocol.get(key) != value for key, value in expected.items())):
            raise ValueError('P batch protocol differs')
        rows = load_batch(snapshot, directory)
        if (len(rows) != expected_runs or {row['run_id'] for row in rows} != {
                str(i) for i in range(expected_runs)}
                or any(row['architecture'] != 2 or row['mode'] or row['trace']
                       or row['empty'] for row in rows)):
            raise ValueError('Incomplete P batch identity')
        failed = [row for row in rows if row['execution_status'] != 'ok']
        if failed:
            reasons = set().union(*(set(row.get('errors', ())) for row in failed))
            if (not reasons.intersection(_WORKLOAD_FAILURES - {'job_completeness'})
                    or not reasons <= _WORKLOAD_FAILURES
                    or any(row.get('returncode') != 0 for row in failed)):
                raise ValueError('P batch has unresolved execution evidence')
            return MeasurementOutcome('workload_failure', None, ','.join(sorted(reasons)))
        if any(row.get('returncode') != 0 for row in rows):
            raise ValueError('Successful P batch has nonzero process exit')
        return MeasurementOutcome('ok', median(row['tat_ns'] for row in rows))
    except (OSError, KeyError, TypeError, ValueError) as error:
        return MeasurementOutcome('infrastructure_error', None,
                                  f'{type(error).__name__}: {error}')
