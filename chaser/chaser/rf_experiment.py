"""Frozen 3x3 RF search on the periodic final analysis set."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from statistics import mean, median

import joblib
import numpy as np
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             confusion_matrix, precision_recall_fscore_support)

from chaser.features import CLP_FEATURE_VERSION
from chaser.final_clp import POLICIES
from chaser.rf import fit_rf_vectors

REPRESENTATIONS = ('caas-ca', 'ca-csrd', 'clp')
SEEDS = (42, 43, 44, 45, 46)
SPLITS = ('train', 'validation', 'test')
BASELINE = (None, 1, 'sqrt', None)
GRID = (BASELINE,) + tuple(
    candidate for candidate in product((4, 8, None), (1, 2, 4),
                                       ('sqrt', 0.5), (None, 'balanced'))
    if candidate != BASELINE)
assert len(GRID) == 36


def _read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def load_samples(source: Path) -> tuple[dict, dict]:
    """Verify frozen source and CLP hashes, then return nine aligned samples."""
    lock = json.loads((source / 'analysis-set-lock.json').read_text())
    for name, expected in lock['source_hashes'].items():
        if sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen source hash changed: {name}')
    clp_root = source / 'clp-v1'
    clp = json.loads((clp_root / 'summary.json').read_text())
    if (clp['analysis_set_id'] != lock['analysis_set_id']
            or clp['source_hashes'] != lock['source_hashes']
            or clp['feature_version'] != CLP_FEATURE_VERSION
            or clp['feature_dimension'] != 21):
        raise ValueError('CLP export does not match frozen analysis set')
    for name, expected in clp['files'].items():
        if sha256((clp_root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'CLP sample hash changed: {name}')

    eligibility = json.loads((source / 'eligibility.json').read_text())
    split = json.loads((source / 'split.json').read_text())
    common = set(eligibility['common_workloads'])
    if (len(common) != lock['common_count']
            or Counter(split['assignments'][w] for w in common) != lock['split_counts']):
        raise ValueError('Frozen cohort or split changed')
    evidence = {(row['kind'], row['workload_id']): row for row in
                eligibility['policy_workloads']}
    samples = {}
    for policy in POLICIES:
        scalar = _read_rows(source / policy / 'rf_samples.jsonl')
        profile = _read_rows(clp_root / policy / 'rf_samples.jsonl')
        for rep in REPRESENTATIONS:
            rows = [row for row in (profile if rep == 'clp' else scalar)
                    if row['representation_id'] == rep]
            ids = [row['workload_id'] for row in rows]
            if len(ids) != len(common) or set(ids) != common:
                raise ValueError(f'RF samples differ from frozen cohort: {policy}/{rep}')
            for row in rows:
                w = row['workload_id']
                if (row['split_group'] != split['assignments'][w]
                        or row['family_id'] != split['workloads'][w]
                        or not row['eligible_for_common_analysis']
                        or row['label'] != row['label_evidence']['label']
                        or row['label_evidence'] != evidence[(policy, w)]['label_evidence']
                        or len(row['features']) != (21 if rep == 'clp' else 11)):
                    raise ValueError(f'RF row metadata differs: {policy}/{rep}/{w}')
            samples[(policy, rep)] = sorted(rows, key=lambda row: row['workload_id'])
    for policy in POLICIES:
        reference = {r['workload_id']: r for r in samples[(policy, 'caas-ca')]}
        for rep in REPRESENTATIONS[1:]:
            for row in samples[(policy, rep)]:
                prior = reference[row['workload_id']]
                if (row['label'] != prior['label']
                        or row['label_evidence'] != prior['label_evidence']):
                    raise ValueError(f'Policy label changed across RF inputs: {policy}')
    for rep in REPRESENTATIONS:
        reference = {r['workload_id']: r['features']
                     for r in samples[(POLICIES[0], rep)]}
        for policy in POLICIES[1:]:
            for row in samples[(policy, rep)]:
                if row['features'] != reference[row['workload_id']]:
                    raise ValueError(f'Feature changed across policies: {rep}')
    return samples, {'lock': lock, 'clp_summary': clp}


def evaluate(rows: list[dict], predictions: list[int]) -> tuple[dict, list[dict]]:
    """Score classifications and measured TAT regret without fitting on evaluation rows."""
    if not rows or len(rows) != len(predictions):
        raise ValueError('Evaluation rows and predictions differ')
    labels = [row['label'] for row in rows]
    precision, recall, f1, support = precision_recall_fscore_support(
        labels, predictions, labels=(0, 1, 2), zero_division=0)
    decisions = []
    for row, prediction in zip(rows, predictions):
        medians = row['label_evidence']['medians']
        tat, tet = medians[str(int(prediction))]
        oracle_tat = min(value[0] for value in medians.values())
        if oracle_tat <= 0:
            raise ValueError('Oracle TAT must be positive')
        regret = (tat - oracle_tat) / oracle_tat
        decisions.append({'workload_id': row['workload_id'],
                          'label': row['label'], 'prediction': int(prediction),
                          'selected_tat': tat, 'selected_tet': tet,
                          'oracle_tat': oracle_tat, 'tat_regret': regret})
    regrets = [d['tat_regret'] for d in decisions]
    metrics = {'count': len(rows), 'accuracy': accuracy_score(labels, predictions),
               'macro_f1': float(mean(f1)),
               'balanced_accuracy': balanced_accuracy_score(labels, predictions),
               'precision': precision.tolist(), 'recall': recall.tolist(),
               'support': support.tolist(),
               'confusion_matrix': confusion_matrix(labels, predictions,
                                                    labels=(0, 1, 2)).tolist(),
               'tat_regret': {'mean': mean(regrets), 'median': median(regrets),
                              'p95': float(np.percentile(regrets, 95)),
                              'max': max(regrets)},
               'near_optimal_rate': {str(epsilon):
                                     mean(regret <= epsilon for regret in regrets)
                                     for epsilon in (0.01, 0.03, 0.05)}}
    return metrics, decisions


def _params(candidate: tuple) -> dict:
    depth, leaf, features, weight = candidate
    return {'max_depth': depth, 'min_samples_leaf': leaf,
            'max_features': features, 'class_weight': weight}


def _save_selected(directory: Path, rows: dict, models: list,
                   seed_metrics: list[dict]) -> None:
    directory.mkdir()
    for seed, model, metrics in zip(SEEDS, models, seed_metrics):
        seed_path = directory / f'seed-{seed}'
        seed_path.mkdir()
        joblib.dump(model, seed_path / 'model.joblib')
        records = {'seed': seed, 'validation': metrics}
        for split in ('validation', 'test'):
            data = rows[split]
            predictions = model.predict_vectors(row['features'] for row in data).tolist()
            summary, decisions = evaluate(data, predictions)
            records[split] = summary
            (seed_path / f'{split}-predictions.jsonl').write_text(''.join(
                json.dumps(d, sort_keys=True) + '\n' for d in decisions))
        (seed_path / 'metrics.json').write_text(json.dumps(records, sort_keys=True) + '\n')


def train_cell(policy: str, rep: str, rows: list[dict], output: Path) -> dict:
    """Choose one RF setting per cell using validation means across five seeds."""
    subsets = {split: [row for row in rows if row['split_group'] == split]
               for split in SPLITS}
    if any(not subset for subset in subsets.values()):
        raise ValueError('Missing train, validation or test split')
    expected = {'train': 120, 'validation': 41, 'test': 37}
    if {split: len(subset) for split, subset in subsets.items()} != expected:
        raise ValueError('Unexpected frozen split counts')

    cell = output / policy / rep
    cell.mkdir(parents=True)
    search = []
    best_score = None
    best_models = best_metrics = best_candidate = None
    baseline_models = baseline_metrics = None
    for candidate_id, candidate in enumerate(GRID):
        models, validation = [], []
        for seed in SEEDS:
            model = fit_rf_vectors(
                (row['features'] for row in subsets['train']),
                (row['label'] for row in subsets['train']), rep, seed=seed,
                rf_params=_params(candidate))
            predictions = model.predict_vectors(
                row['features'] for row in subsets['validation']).tolist()
            metrics, _ = evaluate(subsets['validation'], predictions)
            models.append(model)
            validation.append(metrics)
        avg_regret = mean(m['tat_regret']['mean'] for m in validation)
        avg_f1 = mean(m['macro_f1'] for m in validation)
        score = (avg_regret, -avg_f1, candidate_id)
        search.append({'candidate_id': candidate_id, 'params': _params(candidate),
                       'mean_validation_tat_regret': avg_regret,
                       'mean_validation_macro_f1': avg_f1,
                       'seed_validation': dict(zip(SEEDS, validation))})
        if candidate == BASELINE:
            baseline_models, baseline_metrics = models, validation
        if best_score is None or score < best_score:
            best_score, best_candidate = score, candidate_id
            best_models, best_metrics = models, validation
    (cell / 'search.json').write_text(json.dumps(search, sort_keys=True) + '\n')
    _save_selected(cell / 'baseline', subsets, baseline_models, baseline_metrics)
    _save_selected(cell / 'tuned', subsets, best_models, best_metrics)
    result = {'policy': policy, 'representation': rep,
              'candidate_count': len(GRID), 'fit_count': len(GRID) * len(SEEDS),
              'best_candidate_id': best_candidate,
              'best_params': _params(GRID[best_candidate]),
              'baseline_validation_tat_regret': search[0]['mean_validation_tat_regret'],
              'best_validation_tat_regret': search[best_candidate]['mean_validation_tat_regret']}
    (cell / 'selection.json').write_text(json.dumps(result, sort_keys=True) + '\n')
    return result
