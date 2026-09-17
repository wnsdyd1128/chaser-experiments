"""Train and consume locality features with the CAAS sklearn RF implementation."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler

from chaser.features import LocalityRecord, Representation, build_features


Cases: TypeAlias = Mapping[str, LocalityRecord]
Workload: TypeAlias = Mapping[str, float | None]
LABEL_NAMES: dict[int, str] = {0: 'Global', 1: 'Clustered', 2: 'Partitioned'}


def _feature_matrix(cases: Cases, workloads: Iterable[Workload],
                    kind: Representation, alpha: float | None) -> list[list[float]]:
    """Join export case IDs to explicit utilization; never infer missing U."""
    rows: list[list[float]] = []
    for workload in workloads:
        tasks: list[LocalityRecord] = []
        for task_id in sorted(workload):
            if task_id not in cases:
                raise ValueError(f'Missing locality for task: {task_id}')
            tasks.append({**cases[task_id], 'utilization': workload[task_id]})
        rows.append(build_features(tasks, kind, alpha=alpha))
    if not rows:
        raise ValueError('At least one workload is required')
    return rows


@dataclass(frozen=True)
class ArchitectureRF:
    """Keep the training representation and fitted scaler for all predictions."""

    kind: Representation
    alpha: float | None
    pipeline: Pipeline

    def predict(self, cases: Cases, workloads: Iterable[Workload]) -> NDArray[np.int64]:
        """Return 0/1/2 labels for task-ID-to-utilization workload mappings."""
        rows = _feature_matrix(cases, workloads, self.kind, self.alpha)
        return self.pipeline.predict(rows)


def fit_rf(cases: Cases, workloads: Iterable[Workload], labels: Iterable[int],
           kind: Representation, *, seed: int,
           alpha: float | None = None) -> ArchitectureRF:
    """Fit a fresh model on training workloads and caller-supplied labels only.

    Cases use locality.json's cases mapping. Each workload maps its task IDs to
    utilization. The caller owns measured labels and the family-level split;
    this function neither generates labels nor splits or evaluates the dataset.
    RF parameters match the existing CAAS wrapper; preprocessing follows the
    CHASER plan and is fitted only here, then reused by ArchitectureRF.predict.
    """
    rows = _feature_matrix(cases, workloads, kind, alpha)
    labels = list(labels)
    if len(labels) != len(rows) or any(label not in LABEL_NAMES for label in labels):
        raise ValueError('Supply one architecture label (0, 1, 2) per workload')
    pipeline = Pipeline([
        ('scale', MinMaxScaler()),
        ('rf', RandomForestClassifier(n_estimators=100, max_depth=None,
                                      random_state=seed)),
    ])
    pipeline.fit(rows, labels)
    return ArchitectureRF(kind, alpha, pipeline)
