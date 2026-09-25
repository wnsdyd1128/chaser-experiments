"""Measurements use the post-warm-up job set and release cohorts."""

import pytest

from chaser.periodic.measurement import aggregate, make_plan, parse_log
from chaser.periodic.dataset import characterize, feature_record
from test_periodic import configuration
from test_periodic_public import public_evidence


def measurement_evidence():
    return public_evidence()


def test_counts_only_measured_jobs_and_sums_cohort_spans():
    plan, records = measurement_evidence()
    result = aggregate(records, plan)
    assert result['execution_status'] == 'ok'
    assert result['warmup_jobs'] == 3
    assert result['measured_jobs'] == 3
    assert result['tet_ns'] == 21_000
    assert result['tat_ns'] == 20_000
    assert result['response_sum_ns'] == 36_000
    assert result['cohort_response_sum_ns'] == 24_000
    assert result['cohort_start_delay_sum_ns'] == 4_000
    assert [row['job_count'] for row in result['cohorts']] == [2, 1]
    assert result['run_release_span_ns'] == 30_012_000
    assert result['run_execution_span_ns'] == 10_010_000


def test_common_start_delay_changes_response_but_not_tat():
    plan, records = measurement_evidence()
    for job in records:
        if job['kind'] == 'job' and job['release_ns'] == 120_000_000:
            for field in ('start_ns', 'completion_ns', 'status_before_end_ns',
                          'status_after_start_ns'):
                job[field] += 1_000
            for field in ('wall_before_ns', 'wall_after_ns'):
                job[field] += 1_000
    result = aggregate(records, plan)
    assert result['execution_status'] == 'ok'
    assert result['tat_ns'] == 20_000
    assert result['response_sum_ns'] == 38_000


@pytest.mark.parametrize('change,reason', [('warmup_missing', 'job_completeness'),
                                           ('last_deadline', 'deadline_miss')])
def test_warmup_and_last_job_failures_invalidate_run(change, reason):
    plan, records = measurement_evidence()
    if change == 'warmup_missing':
        records.pop(3)
    else:
        records[-2]['completion_ns'] = 140_000_001
    assert reason in aggregate(records, plan)['errors']


def test_requires_explicit_warmup_boundary_and_repeat_count():
    config = configuration()
    del config['warmup_ticks']
    with pytest.raises(ValueError, match='warmup'):
        make_plan(config, 2)
    config['warmup_ticks'] = 20
    del config['u_repeats']
    with pytest.raises(ValueError, match='u_repeats'):
        make_plan(config, 2)


def test_independent_u_uses_median_of_measured_run_means():
    plan, _ = measurement_evidence()
    batches = []
    for task_index, task in enumerate(plan['tasks']):
        rows = []
        for run, cpu in enumerate((100, 100, 100, 100, 1000)):
            jobs = [dict(task=task_index, job=j, cpu_before_ns=0,
                         cpu_after_ns=9000 if j < task['warmup_jobs'] else cpu)
                    for j in range(task['job_count'])]
            rows.append(dict(run_id=str(run), plan_hash=plan['plan_hash'],
                             mode=task_index + 1, trace=False, empty=False,
                             execution_status='ok', elf_hash='same', log_hash=str(run),
                             jobs=jobs))
        batches.append(rows)
    result = characterize(plan, batches)
    assert result['utilization_source'] == 'measured-run-median-v3'
    assert result['utilization'] == {'a': 100 / 10_000_000,
                                     'b': 100 / 20_000_000}
    assert result['tasks']['a']['run_mean_cpu_ns'] == [100] * 4 + [1000]
    batches[0][0]['jobs'].pop(0)
    with pytest.raises(ValueError, match='Incomplete'):
        characterize(plan, batches)


def test_feature_gate_accepts_valid_cls_zero_and_u_above_old_cap():
    member = dict(workload_id='example', split_group='train')
    locality = dict(cases={
        'a': dict(ca_caas_element=0.2, ca_csrd_l1=0.3, cls={'0.5': 0.0},
                  clp=[0.0, 0.0, 1.0]),
        'b': dict(ca_caas_element=0.4, ca_csrd_l1=0.5, cls={'0.5': 0.2},
                  clp=[0.2, 0.3, 0.5]),
    })
    utilization = dict(utilization={'a': 0.8, 'b': 0.9},
                       utilization_source='measured-run-median-v3',
                       utilization_rule_id='isolated-measured-run-mean-median-v3',
                       characterization_id='u-v3')
    record = feature_record(member, locality, utilization)
    assert record['within_u_bounds']
    assert record['utilization_rule_id'] == 'isolated-measured-run-mean-median-v3'
    assert record['undefined_features'] == {}
    assert {kind: len(values) for kind, values in record['features'].items()} == {
        'caas-ca': 11, 'ca-csrd': 11, 'cls': 11, 'clp': 21}
    locality['cases']['b']['ca_caas_element'] = None
    record = feature_record(member, locality, utilization)
    assert 'caas-ca' in record['undefined_features']


def test_truncated_run_keeps_complete_raw_jobs_for_failure_audit():
    import json

    plan, records = measurement_evidence()
    text = '\n'.join('PERIODIC ' + json.dumps(row) for row in records[:-1])
    result = parse_log(text + '\nPERIODIC {"kind":"job","task":0,"job":',
                       plan, salvage_partial=True)
    assert result['execution_status'] == 'failed'
    assert 'truncated_record' in result['errors']
    assert len(result['jobs']) == 6
