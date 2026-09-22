"""Synthetic TAT fixtures verify selection rules, not scheduling performance."""

from dataclasses import asdict, replace
import json
from math import nextafter
from pathlib import Path

import pytest

from chaser.allocator import CoreGroups, allocate
from chaser.threshold import (CalibrationWorkload, calibrate, plan_calibration,
                              threshold_candidates)


CORES = CoreGroups((0,), (1,))
CASES = {
    'a': {'ca_caas_element': 0.2, 'ca_csrd_l1': 0.4,
          'cls': {'0.5': 0.6, '1.0': 0.3}},
    'b': {'ca_caas_element': 0.8, 'ca_csrd_l1': 1.0,
          'cls': {'0.5': 0.9, '1.0': 0.5}},
}


def sample(name='v', tasks=None, split='validation', family=None):
    return CalibrationWorkload(name, family or name, split,
                               {'a': 0.6, 'b': 0.6} if tasks is None else tasks)


def run(rows=None, tat=None, **kwargs):
    return calibrate(CASES, [sample()] if rows is None else rows, CORES,
                     kind=kwargs.pop('kind', 'caas-ca'),
                     tat=tat or (lambda workload_id, mapping: 10.0), seed=42,
                     analyzer_version='fixture-analyzer', feature_version='fixture-v1',
                     measurement_source='synthetic', **kwargs)


def test_candidates_cover_every_branch_partition_including_adjacent_floats():
    values = [0.0, 0.2, nextafter(0.2, 1.0), 1.0]
    candidates = threshold_candidates(reversed(values + values))
    partitions = [tuple(value < theta for value in values) for theta in candidates]
    assert partitions == [tuple(i < cut for i in range(4)) for cut in range(5)]


@pytest.mark.parametrize('values', [[], [None], [-0.1], [1.1], [float('nan')],
                                   [float('inf')]])
def test_invalid_candidate_scalars_are_rejected(values):
    with pytest.raises(ValueError):
        threshold_candidates(values)


def test_failure_count_precedes_tat_and_infeasible_mappings_are_not_measured():
    calls = []

    def tat(workload_id, mapping):
        calls.append((workload_id, mapping))
        return 1000.0

    result = run(tat=tat)
    assert result.threshold == 0.5
    assert [len(c.failed_workloads) for c in result.candidates] == [1, 0, 1]
    assert calls == [('v', {'a': 0, 'b': 1})]


def test_tat_then_smallest_threshold_break_ties():
    rows = [sample(tasks={'a': 0.2, 'b': 0.2})]
    result = run(rows, lambda _, mapping: 1.0 if mapping['a'] == 0 else 20.0)
    assert result.threshold == 0.5
    assert run(rows).threshold == 0.2


def test_common_success_set_excludes_candidate_specific_successes():
    cases = {key: {'ca_caas_element': value}
             for key, value in {'a': 0.1, 'b': 0.3, 'c': 0.7, 'd': 0.9}.items()}
    rows = [sample('left', {'a': 0.6, 'b': 0.6}),
            sample('right', {'c': 0.6, 'd': 0.6}), sample('common', {'b': 0.1})]
    calls = []

    def tat(workload_id, mapping):
        calls.append(workload_id)
        return 1.0 if mapping['b'] == 0 else 10.0

    result = calibrate(cases, rows, CORES, kind='caas-ca', tat=tat, seed=42,
                       analyzer_version='fixture', feature_version='fixture',
                       measurement_source='synthetic')
    assert result.threshold == pytest.approx(0.8)
    assert result.common_workloads == ('common',)
    assert calls == ['common', 'common']


def test_duplicate_workload_mapping_is_measured_once():
    calls = []

    def tat(workload_id, mapping):
        calls.append((workload_id, tuple(sorted(mapping.items()))))
        return 10.0

    run([sample('one', {'a': 0.1}), sample('two', {'b': 0.1})], tat)
    assert len(calls) == len(set(calls)) == 4


def test_measurement_plan_has_no_synthetic_scores_and_matches_calibration():
    rows = [sample('one', {'a': 0.1}), sample('two', {'b': 0.1})]
    plan = plan_calibration(CASES, rows, CORES, kind='caas-ca')
    calls = []
    result = run(rows, lambda name, mapping: calls.append((name, mapping)) or 10.0)
    assert list(plan.mappings) == calls
    assert plan.common_workloads == result.common_workloads
    assert [c.threshold for c in plan.candidates] == [c.threshold for c in result.candidates]
    assert all(c.mean_tat is None for c in plan.candidates)
    assert plan.split_hash == result.split_hash
    assert plan.validation_hash == result.validation_hash


def test_measurement_plan_omits_infeasible_and_nonfinalist_mappings():
    plan = plan_calibration(CASES, [sample()], CORES, kind='caas-ca')
    assert plan.mappings == (('v', {'a': 0, 'b': 1}),)


def test_calibration_ignores_train_test_payload_and_is_order_independent():
    rows = [sample(), sample('test', {'missing': None}, 'test'),
            sample('train', {'missing': None}, 'train')]
    first = run(rows)
    rows[1] = replace(rows[1], utilization={'b': 100.0})
    second = run(reversed(rows))
    assert json.dumps(asdict(first), sort_keys=True, allow_nan=False) == json.dumps(
        asdict(second), sort_keys=True, allow_nan=False)
    assert first.seed == 42 and first.measurement_source == 'synthetic'
    assert len(first.split_hash) == len(first.validation_hash) == 64


def test_family_overlap_and_duplicate_workload_ids_are_rejected():
    for rows in ([sample(), sample('t', split='test', family='v')],
                 [sample(), sample()], [sample(split='unknown')]):
        with pytest.raises(ValueError):
            run(rows)


@pytest.mark.parametrize('rows', [[], [sample(split='test')],
                                  [sample(tasks={})], [sample(tasks={'a': 1.1})]])
def test_no_usable_validation_comparison_is_rejected(rows):
    with pytest.raises(ValueError):
        run(rows)


@pytest.mark.parametrize('tat', [None, 0.0, -1.0, float('nan'), float('inf')])
def test_missing_or_invalid_tat_cannot_select_a_threshold(tat):
    with pytest.raises(ValueError):
        run(tat=lambda *_: tat)


def test_threshold_is_per_representation_and_alpha():
    results = [run(kind=kind, alpha=alpha) for kind, alpha in
               [('caas-ca', None), ('ca-csrd', None), ('cls', 0.5), ('cls', 1.0)]]
    assert [result.threshold for result in results] == pytest.approx([0.5, 0.7, 0.75, 0.4])
    for result in results:
        placement = allocate(CASES, {'a': 0.6, 'b': 0.6}, CORES,
                             kind=result.kind, alpha=result.alpha,
                             threshold=result.threshold)
        assert placement.mapping == {'a': 0, 'b': 1}


def test_disjoint_success_sets_cannot_be_compared_by_different_workloads():
    rows = [sample('left', {'a': 0.6, 'b': 0.6}),
            sample('right', {'c': 0.6, 'd': 0.6})]
    cases = {task: {'ca_caas_element': value} for task, value in
             {'a': 0.1, 'b': 0.3, 'c': 0.7, 'd': 0.9}.items()}
    with pytest.raises(ValueError, match='No common successful'):
        calibrate(cases, rows, CORES, kind='caas-ca', tat=lambda *_: pytest.fail(
            'No measurement is comparable'), seed=42, analyzer_version='fixture',
            feature_version='fixture', measurement_source='synthetic')


@pytest.mark.parametrize('kind, alpha', [('caas-ca', None), ('ca-csrd', None),
                                      ('cls', 0.0), ('cls', 0.5), ('cls', 1.0)])
def test_export_to_calibration_to_frozen_test_allocation(kind, alpha):
    cases = json.loads(Path('exports/locality.json').read_text())['cases']
    result = calibrate(cases, [sample(tasks={'spread': 0.2, 'conflict': 0.3})],
                       CORES, kind=kind, alpha=alpha, tat=lambda *_: 10.0,
                       seed=42, analyzer_version='fixture', feature_version='fixture',
                       measurement_source='synthetic')
    before = json.dumps(asdict(result), sort_keys=True, allow_nan=False)
    assert allocate(cases, {'packed': 0.4}, CORES, kind=result.kind,
                    alpha=result.alpha, threshold=result.threshold).infeasible == []
    assert json.dumps(asdict(result), sort_keys=True, allow_nan=False) == before
