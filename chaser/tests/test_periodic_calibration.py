"""Calibration compares P mappings after allocation and execution outcomes."""

import json

import pytest

from chaser.policy.allocator import CoreGroups, allocate
from chaser.periodic import calibration as batch_classifier
from chaser.periodic.calibration import (CalibrationWorkload, MeasurementOutcome,
    mapping_key, plan_all_policies, plan_calibration, select_threshold,
    threshold_candidates)
from chaser.periodic.measurement import CONTRACT


CORES = CoreGroups((0,), (1,))
CASES = {'a': {'ca_caas_element': 0.2}, 'b': {'ca_caas_element': 0.2}}
ROWS = (CalibrationWorkload('a', 'group-a', {'a': 0.2}),
        CalibrationWorkload('b', 'group-b', {'b': 0.2}))


def plan():
    return plan_calibration(CASES, ROWS, CORES, kind='caas-ca')


def outcomes(p):
    return {key: MeasurementOutcome('ok', 20.0) for key in p.measurement_requests}


def test_candidates_use_endpoints_observed_values_and_inclusive_equality():
    assert threshold_candidates([0, 0.2, 0.2, 1]) == (0.0, 0.2, 1.0)
    p = plan()
    assert [candidate.threshold for candidate in p.candidates] == [0.0, 0.2, 1.0]
    assert p.candidates[0].mappings['a'] == {'a': 1}
    assert p.candidates[1].mappings['a'] == {'a': 0}
    assert len(p.measurement_requests) == 4
    zero = allocate({'z': {'ca_caas_element': 0.0}}, {'z': 0.1}, CORES,
                    kind='caas-ca', threshold=0.0)
    assert zero.mapping == {'z': 0}


def test_execution_failure_changes_winner_even_if_failed_mapping_was_fast():
    p = plan()
    measured = outcomes(p)
    measured[mapping_key('a', {'a': 1})] = MeasurementOutcome('ok', 1.0)
    measured[mapping_key('b', {'b': 1})] = MeasurementOutcome('workload_failure', None,
                                                              'deadline_miss')
    selected = select_threshold(p, measured)
    assert selected.status == 'complete'
    assert selected.threshold == 0.2
    assert selected.common_workloads == ('a', 'b')
    assert selected.candidates[0].failed_workloads == ('b',)


def test_partial_coverage_uses_common_successes_and_smallest_theta_tie_break():
    p = plan()
    measured = outcomes(p)
    measured[mapping_key('b', {'b': 1})] = MeasurementOutcome('workload_failure', None)
    measured[mapping_key('b', {'b': 0})] = MeasurementOutcome('workload_failure', None)
    selected = select_threshold(p, measured)
    assert selected.status == 'partial_coverage'
    assert selected.common_workloads == ('a',)
    assert selected.threshold == 0.0


def test_empty_common_success_set_remains_unresolved():
    p = plan()
    measured = outcomes(p)
    measured[mapping_key('b', {'b': 1})] = MeasurementOutcome('workload_failure', None)
    measured[mapping_key('a', {'a': 0})] = MeasurementOutcome('workload_failure', None)
    selected = select_threshold(p, measured)
    assert selected.status == 'calibration_unresolved'
    assert selected.threshold is None
    assert selected.common_workloads == ()


def test_infrastructure_error_cannot_be_scored_as_policy_failure():
    p = plan()
    measured = outcomes(p)
    measured[mapping_key('a', {'a': 1})] = MeasurementOutcome('infrastructure_error', None,
                                                              'log_missing')
    with pytest.raises(ValueError, match='infrastructure'):
        select_threshold(p, measured)


@pytest.mark.parametrize('values', [[], [None], [-0.1], [1.1], [float('nan')]])
def test_invalid_calibration_scalars_are_rejected(values):
    with pytest.raises(ValueError):
        threshold_candidates(values)


def test_all_seven_policies_use_same_d_theta_workloads():
    cases = {task: dict(ca_caas_element=0.2, ca_csrd_l1=0.3,
                        cls={str(alpha): 0.4 for alpha in (0.0, 0.3, 0.5, 0.7, 1.0)})
             for task in ('a', 'b')}
    plans = plan_all_policies(cases, ROWS, CORES)
    assert set(plans) == {'caas-ca', 'ca-csrd', 'cls-0', 'cls-0.3', 'cls-0.5',
                          'cls-0.7', 'cls-1'}
    assert all(p.workload_ids == ('a', 'b') for p in plans.values())


def test_p_batch_classifies_target_failure_and_infrastructure_separately(tmp_path, monkeypatch):
    snapshot, directory = tmp_path / 'snapshot', tmp_path / 'runs'
    (snapshot / 'p').mkdir(parents=True)
    directory.mkdir()
    (snapshot / 'p/plan.json').write_text(json.dumps(
        dict(contract_id=CONTRACT, plan_hash='plan')))
    (directory / 'protocol.json').write_text(json.dumps(dict(
        runs=3, timeout_seconds=100, mode=0, trace=False, empty=False,
        simulator_hash='sim', contract_id=CONTRACT, plan_hash='plan')))
    rows = [dict(run_id=str(i), architecture=2, mode=0, trace=False, empty=False,
                 execution_status='ok', returncode=0, tat_ns=value, errors=[])
            for i, value in enumerate((10, 20, 30))]
    monkeypatch.setattr(batch_classifier, 'load_batch', lambda *_: rows)

    def classify():
        return batch_classifier.classify_p_batch(
            snapshot, directory, expected_runs=3, timeout=100, simulator_hash='sim')

    assert classify() == MeasurementOutcome('ok', 20)
    rows[0].update(execution_status='failed', errors=['deadline_miss', 'job_completeness'])
    assert classify().status == 'workload_failure'
    rows[0]['returncode'] = 124
    assert classify().status == 'infrastructure_error'
    rows[0]['returncode'] = 0
    rows[0]['errors'] = ['job_completeness']
    assert classify().status == 'infrastructure_error'
    rows[0]['errors'] = ['checksum']
    assert classify().status == 'infrastructure_error'
    monkeypatch.setattr(batch_classifier, 'load_batch', lambda *_: (_ for _ in ()).throw(
        ValueError('Raw measurement log changed')))
    assert classify().status == 'infrastructure_error'
