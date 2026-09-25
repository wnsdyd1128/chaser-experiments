"""Measurement-contract failures must never turn into successful RF labels."""

from copy import deepcopy

import pytest

from chaser.periodic.measurement import CONTRACT, make_plan, aggregate, parse_log


def configuration():
    return {'workload_id': 'tiny', 'family_id': 'layout',
            'policy_id': 'pilot-explicit-v1', 'horizon_ticks': 40,
            'warmup_ticks': 20, 'u_repeats': 5,
            'tasks': [dict(task_id='a', period_ticks=10, core=0,
                           distinct=8, stride=1, sweeps=100),
                      dict(task_id='b', period_ticks=20, core=2,
                           distinct=8, stride=4096, sweeps=100)]}


def evidence():
    plan = make_plan(configuration(), 2)
    header = dict(kind='run', contract_id=CONTRACT, plan_hash=plan['plan_hash'], cpus=4, mode=0,
                  trace=0, empty=0, t0_ns=100_000_000, t0_tick=100, tick_ns=1_000_000)
    tasks, jobs = [], []
    for i, task in enumerate(plan['tasks']):
        tasks.append(dict(kind='task', task=i, domain_mask=1 << task['core'],
                          affinity_mask=15, scheduler_ok=1, arm_before_tick=100,
                          arm_after_tick=100, thread=101 + i))
        for j in range(task['job_count']):
            release = header['t0_ns'] + j * task['period_ticks'] * 1_000_000
            jobs.append(dict(kind='job', task=i, job=j, release_ns=release,
                             start_ns=release + 2_000, completion_ns=release + 12_000,
                             cpu_before_ns=1_000, cpu_after_ns=8_000,
                             status_before_end_ns=release + 2_500,
                             status_after_start_ns=release + 11_500,
                             wall_before_ns=2_400, wall_after_ns=11_400,
                             state_before=1, state_after=1,
                             postponed_before=0, postponed_after=0, period_status=0,
                             start_core=task['core'], end_core=task['core'],
                             checksum=task['expected_checksum']))
    return plan, [header, *tasks, *jobs, dict(kind='end', complete=1)]


def test_tat_sums_measured_cohort_spans_and_cpu_is_not_wall_time():
    plan, records = evidence()
    result = aggregate(records, plan)
    assert result['execution_status'] == 'ok'
    assert result['tet_ns'] == 3 * 7_000
    assert result['tat_ns'] == 2 * 10_000
    assert result['makespan_ns'] == 30_012_000


@pytest.mark.parametrize('field,value,reason', [
    ('release_ns', 100_002_000, 'release_mismatch'),
    ('cpu_after_ns', 999, 'cpu_accounting'),
    ('wall_after_ns', 0, 'accounting_epoch'),
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


@pytest.mark.parametrize('payload', ['[]', 'null', '42', '"bad"'])
def test_non_object_target_record_is_a_parse_error(payload):
    plan, _ = evidence()
    with pytest.raises(ValueError, match='record'):
        parse_log('PERIODIC ' + payload, plan)
