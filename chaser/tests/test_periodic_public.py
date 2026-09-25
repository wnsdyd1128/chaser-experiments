"""Public status bounds must validate measurements without invented internals."""

import pytest

from chaser.periodic.measurement import CONTRACT, aggregate
from test_periodic import evidence


def public_evidence(*, trace=False):
    plan, records = evidence()
    records[0]['trace'] = int(trace)
    if trace:
        for row in records:
            if row['kind'] != 'job':
                continue
            task = plan['tasks'][row['task']]
            deadline = 100 + (row['job'] + 1) * task['period_ticks']
            row.update(epoch_before_ns=row['release_ns'] + 100,
                       epoch_after_ns=row['release_ns'] + 100,
                       timer_before=deadline, timer_after=deadline,
                       edf_before=deadline, edf_after=deadline)
        records.extend([dict(kind='switch', thread=101, core=0, ns=1),
                        dict(kind='switch', thread=102, core=2, ns=2)])
    return plan, records


def test_public_timing_needs_no_private_fields_and_reports_elapsed_separately():
    plan, records = public_evidence()
    assert plan['contract_id'] == CONTRACT
    result = aggregate(records, plan)
    assert result['execution_status'] == 'ok'
    assert result['tet_ns'] == 21_000
    assert result['tat_ns'] == 20_000
    assert result['mean_elapsed_ns'] == result['max_elapsed_ns'] == 10_000
    assert result['ready_ns'] is None


@pytest.mark.parametrize('field,value,reason', [
    ('wall_after_ns', 0, 'accounting_epoch'),
    ('wall_before_ns', 2_002_250, 'release_mismatch'),
    ('status_before_end_ns', 100_020_000, 'timestamps'),
    ('status_after_start_ns', 100_000_000, 'timestamps'),
    ('cpu_after_ns', 999, 'cpu_accounting'),
    ('state_after', 2, 'period_state'),
    ('postponed_after', 1, 'postponed_job'),
    ('period_status', 6, 'period_status'),
    ('completion_ns', 110_000_001, 'deadline_miss'),
])
def test_invalid_public_sample_fails_closed(field, value, reason):
    plan, records = public_evidence()
    records[3][field] = value
    result = aggregate(records, plan)
    assert result['execution_status'] == 'failed'
    assert reason in result['errors']


def test_shifted_first_arm_fails_even_with_plausible_job_timestamps():
    plan, records = public_evidence()
    records[1]['arm_after_tick'] += 1
    assert 'arm_phase' in aggregate(records, plan)['errors']


def test_preemption_after_one_status_call_can_be_resolved_by_the_other_sample():
    plan, records = public_evidence()
    job = records[3]
    job['status_before_end_ns'] += 1_400_000
    job['status_after_start_ns'] += 2_000_000
    job['completion_ns'] += 2_000_000
    job['wall_after_ns'] += 2_000_000
    assert aggregate(records, plan)['execution_status'] == 'ok'


def test_public_epoch_with_unresolved_tick_wide_uncertainty_is_rejected():
    plan, records = public_evidence()
    job = records[3]
    job['status_before_end_ns'] += 1_400_000
    job['status_after_start_ns'] += 2_000_000
    job['completion_ns'] += 3_400_000
    job['wall_after_ns'] += 2_000_000
    assert 'epoch_resolution' in aggregate(records, plan)['errors']


def test_private_fields_are_rejected_in_normal_public_measurement():
    plan, records = public_evidence()
    records[3]['edf_before'] = 110
    assert 'unexpected_probe' in aggregate(records, plan)['errors']


def test_diagnostic_run_requires_real_private_epoch_and_deadline():
    plan, records = public_evidence(trace=True)
    assert aggregate(records, plan, trace=True)['execution_status'] == 'ok'
    del records[3]['edf_before']
    assert aggregate(records, plan, trace=True)['execution_status'] == 'failed'


def test_header_contract_must_match_plan():
    plan, records = public_evidence()
    records[0]['contract_id'] = 'chaser-periodic-measurement-v1'
    assert 'provenance' in aggregate(records, plan)['errors']


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'final_overrun'])
def test_public_job_completeness_and_final_deadline(change):
    plan, records = public_evidence()
    if change == 'missing':
        records.pop(3)
    elif change == 'duplicate':
        records.insert(3, records[3].copy())
    else:
        records[-2]['completion_ns'] = 140_000_001
    assert aggregate(records, plan)['execution_status'] == 'failed'
