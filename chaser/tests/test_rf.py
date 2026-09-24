import json
from pathlib import Path

import numpy as np
import pytest

from chaser.features import build_features
from chaser.rf import fit_rf, fit_rf_vectors


@pytest.fixture
def cases():
    return json.loads(Path('exports/locality.json').read_text())['cases']


@pytest.mark.parametrize('kind', ['caas-ca', 'ca-csrd'])
def test_exported_features_reach_a_new_rf_and_predict_deterministically(cases, kind):
    # Labels are synthetic wiring fixtures, not measured architecture winners.
    workloads = [{'packed': 0.1}, {'spread': 0.5}, {'conflict': 0.9}]
    labels = [0, 1, 2]
    model = fit_rf(cases, workloads, labels, kind, seed=42)
    repeated = fit_rf(cases, workloads, labels, kind, seed=42)
    assert model.predict(cases, workloads).tolist() == labels
    np.testing.assert_array_equal(model.predict(cases, workloads),
                                  repeated.predict(cases, workloads))
    assert model.pipeline['rf'].n_features_in_ == 11
    expected = [build_features([{**cases[task_id], 'utilization': u}], kind)
                for workload in workloads for task_id, u in workload.items()]
    np.testing.assert_allclose(model.pipeline['scale'].data_min_,
                               np.min(expected, axis=0))
    np.testing.assert_allclose(model.pipeline['scale'].data_max_,
                               np.max(expected, axis=0))
    np.testing.assert_array_equal(model.predict(cases, workloads),
                                  model.pipeline.predict(expected))


def test_representation_changes_only_locality_and_keeps_training_scaler(cases):
    workloads = [{'spread': 0.2, 'conflict': 0.6}, {'packed': 0.4}]
    caas = fit_rf(cases, workloads, [0, 1], 'caas-ca', seed=42)
    csrd = fit_rf(cases, workloads, [0, 1], 'ca-csrd', seed=42)
    caas_max = caas.pipeline['scale'].data_max_
    csrd_max = csrd.pipeline['scale'].data_max_
    assert caas_max[0] != csrd_max[0]
    np.testing.assert_array_equal(caas_max[5:], csrd_max[5:])
    before = csrd_max.copy()
    csrd.predict(cases, [{'packed': 2.0}])
    np.testing.assert_array_equal(csrd.pipeline['scale'].data_max_, before)
    np.testing.assert_array_equal(
        csrd.predict(cases, workloads),
        csrd.predict(dict(reversed(list(cases.items()))),
                     [dict(reversed(list(row.items()))) for row in workloads]))


@pytest.mark.parametrize('workloads, labels', [
    ([], []), ([{}], [0]), ([{'missing': 0.2}], [0]),
    ([{'packed': None}], [0]), ([{'packed': 0.2}], []),
    ([{'packed': 0.2}], [3]),
])
def test_invalid_training_inputs_are_rejected(cases, workloads, labels):
    with pytest.raises(ValueError):
        fit_rf(cases, workloads, labels, 'ca-csrd', seed=42)


def test_undefined_scalar_is_rejected_in_training_and_prediction(cases):
    workloads = [{'packed': 0.2}]
    model = fit_rf(cases, workloads, [0], 'ca-csrd', seed=42)
    cases['packed']['ca_csrd_l1'] = None
    with pytest.raises(ValueError):
        fit_rf(cases, workloads, [0], 'ca-csrd', seed=42)
    with pytest.raises(ValueError):
        model.predict(cases, workloads)


def test_clp_21_features_reach_the_same_rf_and_scaler(cases):
    workloads = [{'packed': 0.1}, {'spread': 0.5}, {'conflict': 0.9}]
    model = fit_rf(cases, workloads, [0, 1, 2], 'clp', seed=42)
    expected = [build_features([{**cases[t], 'utilization': u}], 'clp')
                for workload in workloads for t, u in workload.items()]
    assert model.pipeline['rf'].n_features_in_ == 21
    np.testing.assert_allclose(model.pipeline['scale'].data_min_, np.min(expected, axis=0))
    np.testing.assert_array_equal(model.predict(cases, workloads),
                                  model.pipeline.predict(expected))
    exported = fit_rf_vectors(expected, [0, 1, 2], 'clp', seed=42)
    np.testing.assert_array_equal(exported.predict_vectors(expected),
                                  model.predict(cases, workloads))


def test_rf_rejects_exported_vectors_with_wrong_dimension_or_nonfinite_values():
    with pytest.raises(ValueError):
        fit_rf_vectors([[0.0] * 11], [0], 'clp', seed=42)
    with pytest.raises(ValueError):
        fit_rf_vectors([[float('nan')] * 21], [0], 'clp', seed=42)
