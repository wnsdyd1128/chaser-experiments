"""Measurement-contract failures must never turn into successful RF labels."""

from copy import deepcopy

import pytest

from chaser.periodic import make_plan, aggregate, parse_log, digest


def configuration():
    return {'workload_id': 'tiny', 'family_id': 'layout',
            'policy_id': 'pilot-explicit-v1', 'horizon_ticks': 40,
            'tasks': [dict(task_id='a', period_ticks=10, core=0,
                           distinct=8, stride=1, sweeps=100),
                      dict(task_id='b', period_ticks=20, core=2,
                           distinct=8, stride=4096, sweeps=100)]}


def evidence():
    plan = make_plan(configuration(), 2)
    # Archived v1 records remain readable under their original contract.
    plan['contract_id'] = 'chaser-periodic-measurement-v1'
    plan['plan_hash'] = digest({k: v for k, v in plan.items() if k != 'plan_hash'})
    header = dict(kind='run', plan_hash=plan['plan_hash'], cpus=4, mode=0,
                  trace=0, empty=0, t0_ns=100_000_000, t0_tick=100, tick_ns=1_000_000)
    tasks, jobs = [], []
    for i, task in enumerate(plan['tasks']):
        tasks.append(dict(kind='task', task=i, domain_mask=1 << task['core'],
                          affinity_mask=15, scheduler_ok=1))
        for j in range(task['job_count']):
            release = header['t0_ns'] + j * task['period_ticks'] * 1_000_000
            deadline = 100 + (j + 1) * task['period_ticks']
            jobs.append(dict(kind='job', task=i, job=j, release_ns=release,
                             start_ns=release + 2_000, completion_ns=release + 12_000,
                             cpu_before_ns=1_000, cpu_after_ns=8_000,
                             epoch_before_ns=release + 100, epoch_after_ns=release + 100,
                             timer_before=deadline, timer_after=deadline,
                             edf_before=deadline, edf_after=deadline,
                             state_before=1, state_after=1,
                             postponed_before=0, postponed_after=0, period_status=0,
                             start_core=task['core'], end_core=task['core'],
                             checksum=task['expected_checksum']))
    return plan, [header, *tasks, *jobs, dict(kind='end', complete=1)]


def test_tat_sums_release_to_completion_and_cpu_is_not_wall_time():
    plan, records = evidence()
    result = aggregate(records, plan)
    assert result['execution_status'] == 'ok'
    assert result['tet_ns'] == 6 * 7_000
    assert result['tat_ns'] == 6 * 12_000
    assert result['makespan_ns'] == 30_012_000


@pytest.mark.parametrize('field,value,reason', [
    ('release_ns', 100_002_000, 'release_mismatch'),
    ('cpu_after_ns', 999, 'cpu_accounting'),
    ('epoch_after_ns', 110_000_000, 'accounting_epoch'),
    ('timer_after', 111, 'release_mismatch'),
    ('edf_before', 999, 'edf_deadline'),
    ('state_after', 2, 'period_state'),
    ('postponed_after', 1, 'postponed_job'),
    ('period_status', 6, 'period_status'),
    ('end_core', 1, 'domain'),
    ('checksum', 0, 'checksum'),
])
def test_invalid_job_is_preserved_but_cannot_succeed(field, value, reason):
    plan, records = evidence()
    records[3][field] = value
    result = aggregate(records, plan)
    assert result['execution_status'] == 'failed'
    assert reason in result['errors']
    assert result['jobs'][0][field] == value


def test_final_job_deadline_miss_fails_without_a_next_period_call():
    plan, records = evidence()
    records[-2]['completion_ns'] = 140_000_001
    assert 'deadline_miss' in aggregate(records, plan)['errors']


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'marker', 'provenance'])
def test_incomplete_or_mismatched_run_is_rejected(change):
    plan, records = evidence()
    if change == 'missing':
        records.pop(3)
    elif change == 'duplicate':
        records.insert(3, deepcopy(records[3]))
    elif change == 'marker':
        records.pop()
    else:
        records[0]['plan_hash'] = 'wrong'
    assert aggregate(records, plan)['execution_status'] == 'failed'


def test_periods_determine_job_counts_with_a_common_horizon():
    plan = make_plan(configuration(), 1)
    assert [t['job_count'] for t in plan['tasks']] == [4, 2]
    assert [t['domain'] for t in plan['tasks']] == [[0], [1, 2, 3]]
    config = configuration()
    config['horizon_ticks'] = 41
    with pytest.raises(ValueError, match='horizon'):
        make_plan(config, 0)


def test_topology_and_effective_domains_are_in_mapping_hash():
    plans = [make_plan(configuration(), a) for a in range(3)]
    assert len({p['mapping_hash'] for p in plans}) == 3
    config = configuration()
    config['tasks'][1]['core'] = 3
    assert make_plan(config, 1)['mapping_hash'] == plans[1]['mapping_hash']
    assert make_plan(config, 2)['mapping_hash'] != plans[2]['mapping_hash']


def test_early_subtick_epoch_is_valid_only_with_the_exact_expected_deadline():
    plan, records = evidence()
    records[3]['epoch_before_ns'] = records[3]['epoch_after_ns'] = 99_998_000
    assert aggregate(records, plan)['execution_status'] == 'ok'
    records[3]['timer_before'] -= 1
    assert 'release_mismatch' in aggregate(records, plan)['errors']


@pytest.mark.parametrize('epoch', [99_000_000, 101_000_000])
def test_a_full_tick_of_epoch_skew_is_rejected(epoch):
    plan, records = evidence()
    records[3]['epoch_before_ns'] = records[3]['epoch_after_ns'] = epoch
    assert 'release_mismatch' in aggregate(records, plan)['errors']


@pytest.mark.parametrize('payload', ['[]', 'null', '42', '"bad"'])
def test_non_object_target_record_is_a_parse_error(payload):
    plan, _ = evidence()
    with pytest.raises(ValueError, match='record'):
        parse_log('PERIODIC ' + payload, plan)
