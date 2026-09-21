"""Candidate coverage counts inputs rather than target tags or renamed IDs."""

from copy import deepcopy

import pytest

from tools.rtems_periodic_pool_audit import audit_pool, input_signature
from tools.rtems_periodic_pool_v2 import candidate_pool


def test_identity_and_target_tags_do_not_create_new_inputs():
    pool = candidate_pool()
    first = pool['candidates'][0]
    renamed = deepcopy(first)
    renamed['target_total_u'] = 9
    config = renamed['configuration']
    config.update(workload_id='renamed', family_id='renamed-family', test_eligible=True)
    for i, task in enumerate(config['tasks']):
        task['task_id'] = f'renamed_{i}'
    assert input_signature(first['configuration']) == input_signature(config)
    report = audit_pool(dict(pool, candidates=[first, renamed]))
    assert report['unique_inputs'] == 1
    assert report['redundant_candidates'] == 1
    assert report['all_candidates_runs_one_policy'] == 140
    assert report['unique_inputs_runs_one_policy'] == 70


@pytest.mark.parametrize('field,value', [('core', 1), ('period_ticks', 999),
                                       ('sweeps', 999), ('width', 4), ('stride', 32)])
def test_execution_parameters_remain_part_of_identity(field, value):
    config = candidate_pool()['candidates'][0]['configuration']
    changed = deepcopy(config)
    changed['tasks'][0][field] = value
    assert input_signature(config) != input_signature(changed)


def test_policy_horizon_and_task_order_remain_part_of_identity():
    config = candidate_pool()['candidates'][0]['configuration']
    for field, value in [('policy_id', 'other'), ('horizon_ticks', 999)]:
        changed = dict(config, **{field: value})
        assert input_signature(config) != input_signature(changed)
    changed = dict(config, tasks=list(reversed(config['tasks'])))
    assert input_signature(config) != input_signature(changed)


def test_v2_target_saturation_and_saved_runs_are_reported_without_filtering():
    pool = candidate_pool()
    original = deepcopy(pool)
    report = audit_pool(pool)
    assert pool == original
    assert report['candidate_workloads'] == 180
    assert report['unique_inputs'] == 123
    assert report['redundant_candidates'] == 57
    assert report['all_candidates_runs_one_policy'] == 23400
    assert report['unique_inputs_runs_one_policy'] == 16530
    assert report['avoidable_runs_one_policy'] == 6870
    assert report['primary_families'] == 3
    assert report['proposed_split_family_counts'] == {'train': 1, 'validation': 1, 'test': 1}
    llc = [c for c in report['coverage'] if c['profile'] in ('llc-one', 'llc-two')]
    assert len(llc) == 24
    assert all(c['candidate_workloads'] == 3 and c['unique_inputs'] == 1 for c in llc)
    assert report['dataset_ready'] is report['split_frozen'] is False
    assert report['runtime_runs_collected'] == 0


def test_development_exposure_removes_whole_family_from_primary_report():
    pool = candidate_pool()
    pool['candidates'][0]['development_exposed'] = True
    report = audit_pool(pool)
    assert report['primary_families'] == 2
    assert report['primary_candidate_workloads'] == 120
    assert report['proposed_split_family_counts'] is None
