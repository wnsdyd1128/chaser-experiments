"""The frozen pre-run check: CHASER placement (P), Global/Clustered fallback, rejected or deferred.

A frozen policy is a directory holding model.joblib and model-spec.json (rf_freeze.py, experiment 43); loading
checks the model's SHA-256 against the spec. For one task set the decision
  1. checks the nominal Partitioned capacity (placement.nominal); unknown -> deferred,
  2. builds the candidates: CHASER's placement (ra-cgb) when feasible and valid, and G4, C1+3, C1+1+2 on the
     U-balanced mapping when every domain stays within its capacity,
  3. predicts each candidate's probability of meeting every deadline and takes P if its probability reaches
     tau, else the most likely Global/Clustered candidate at or above tau, else rejects.
The static rule (D + M below STATIC_THRESHOLD accepts CHASER's placement, else rejects) is reported alongside
for comparison; it never recommends Global or Clustered, since D + M is the same for every configuration.
"""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np

from . import features, placement

STATIC_THRESHOLD = 0.975  # experiment 42: accepted development P rows miss at most 1 %
CHASER = 'ra-cgb'


class Policy:
    def __init__(self, directory: Path):
        self.spec = json.loads((directory / 'model-spec.json').read_text())
        path = directory / 'model.joblib'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != self.spec['model_sha256']:
            raise ValueError(f'{path}: SHA-256 {digest} differs from the frozen {self.spec["model_sha256"]}')
        self.model = joblib.load(path)
        self.tau = self.spec['tau']
        self.names = self.spec['features']

    def probabilities(self, tasks, candidates: dict) -> dict:
        names = list(candidates)
        x = np.array([features.row(tasks, candidates[c], c, self.names) for c in names])
        return dict(zip(names, map(float, self.model.predict_proba(x)[:, 1])))


def choose(probs: dict, tau: float):
    """P when its probability reaches tau, else the most likely Global/Clustered candidate at or above tau."""
    if probs.get(CHASER, 0.0) >= tau:
        return 'P', CHASER
    gc = max(((p, c) for c, p in probs.items() if c in features.GC_CANDIDATES and p >= tau), default=None)
    return ('fallback_gc', gc[1]) if gc else ('rejected', None)


def candidates(tasks, seed=0) -> tuple[dict, dict, list]:
    """(nominal check, candidate -> mapping, reasons for left-out candidates)."""
    check = placement.nominal(tasks)
    out, reasons = {}, []
    if check['status'] == 'feasible':
        mapping = placement.release_aware_grouped(tasks, seed)
        if placement.valid(tasks, mapping):
            out[CHASER] = mapping
        else:
            reasons.append('CHASER placement exceeds the nominal capacity')
    base = placement.wfd(tasks)
    loads = placement.core_loads(tasks, base)
    for c in features.GC_CANDIDATES:
        if all(sum(loads[k] for k in d) <= len(d) * placement.CORE_CAP + 1e-12 for d in features.DOMAINS[c]):
            out[c] = base
        else:
            reasons.append(f'{c}: a domain exceeds its capacity')
    return check, out, reasons


def decide(tasks, policy: Policy, seed=0) -> dict:
    """Decision record for one task set (tasks from inputs.task_values)."""
    check, cands, reasons = candidates(tasks, seed)
    occupancy = features.set_features(tasks)['occupancy']
    static = 'P' if CHASER in cands and occupancy < STATIC_THRESHOLD else 'rejected'
    record = dict(nominal=check['status'], occupancy=occupancy, static_rule=static, reasons=reasons,
                  mappings=cands, probabilities={}, status=None, choice=None, tau=policy.tau)
    if check['status'] == 'unknown':
        record.update(status='deferred', reasons=reasons + ['nominal Partitioned check unknown'])
        return record
    if not cands:
        record.update(status='rejected')
        return record
    record['probabilities'] = policy.probabilities(tasks, cands)
    record['status'], record['choice'] = choose(record['probabilities'], policy.tau)
    return record
