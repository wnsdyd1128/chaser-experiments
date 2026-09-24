import json
from pathlib import Path

import joblib
import pytest

import chaser.rf_experiment as experiment
from chaser.rf import fit_rf_vectors


def sample_rows():
    rows = []
    for i in range(198):
        split = 'train' if i < 120 else 'validation' if i < 161 else 'test'
        rows.append({'workload_id': f'w{i:03}', 'split_group': split,
                     'features': [float(i % 7)] * 11, 'label': i % 3,
                     'label_evidence': {'medians': {
                         '0': [100, 90], '1': [102, 70], '2': [150, 50]}}})
    return rows


def test_evaluation_uses_tat_and_reports_selected_tet():
    metrics, predictions = experiment.evaluate(sample_rows()[:2], [1, 2])
    assert metrics['tat_regret']['mean'] == pytest.approx(0.26)
    assert metrics['near_optimal_rate']['0.01'] == 0
    assert metrics['near_optimal_rate']['0.03'] == 0.5
    assert predictions[0]['selected_tat'] == 102
    assert predictions[0]['selected_tet'] == 70
    assert predictions[1]['tat_regret'] == pytest.approx(0.5)
    assert len(metrics['confusion_matrix']) == 3


def test_search_selection_does_not_depend_on_test_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, 'GRID', (experiment.BASELINE, (4, 2, 0.5, 'balanced')))
    monkeypatch.setattr(experiment, 'SEEDS', (42, 43))
    rows = sample_rows()
    first = experiment.train_cell('caas-ca', 'caas-ca', rows, tmp_path / 'first')
    changed = [dict(row) for row in rows]
    for row in changed:
        if row['split_group'] == 'test':
            row['label'] = (row['label'] + 1) % 3
    second = experiment.train_cell('caas-ca', 'caas-ca', changed, tmp_path / 'second')
    assert first['best_candidate_id'] == second['best_candidate_id']
    assert first['best_validation_tat_regret'] == second['best_validation_tat_regret']
    directory = tmp_path / 'first' / 'caas-ca' / 'caas-ca'
    model = joblib.load(directory / 'baseline' / 'seed-42' / 'model.joblib')
    assert model.pipeline['scale'].data_max_.tolist() == [6.0] * 11
    assert model.pipeline['rf'].n_jobs == 1
    assert len(json.loads((directory / 'search.json').read_text())) == 2
    with pytest.raises(ValueError, match='fixed'):
        fit_rf_vectors([[0.0] * 11], [0], 'caas-ca', seed=42,
                       rf_params={'random_state': 1})


def test_frozen_final_samples_are_aligned():
    root = Path(__file__).resolve().parents[1] / 'datasets/periodic-final-v1'
    if not (root / 'clp-v1/summary.json').exists():
        pytest.skip('Local CLP export is unavailable')
    samples, provenance = experiment.load_samples(root)
    assert len(samples) == 9
    assert all(len(rows) == 198 for rows in samples.values())
    assert provenance['lock']['split_counts'] == {
        'train': 120, 'validation': 41, 'test': 37}
