"""Soft-deadline runs: continue_after_miss keeps every job running after a late completion or a postponed release."""
from copy import deepcopy

import pytest

from chaser.periodic.codegen.project import config_header
from chaser.periodic.measurement import make_plan


@pytest.fixture
def reads():
    return dict(schema_version=2, workload_id='soft-smoke', family_id='soft-diagnostic',
                policy_id='explicit-core-map-v1', horizon_ticks=40, warmup_ticks=20, u_repeats=1,
                arrays=[dict(array_id='r0', element_type='uint32_t', length=64, alignment_bytes=32, initial_value=3)],
                tasks=[dict(task_id='t0', pattern='cyclic', arrays=dict(input=dict(array_id='r0', offset_elements=0)),
                            distinct=16, stride_bytes=4, sweeps=5, core=0, period_ticks=10)])


def test_default_plan_and_header_are_unchanged_and_explicit_false_is_the_default(reads):
    plan = make_plan(reads, 2)
    assert 'continue_after_miss' not in plan
    assert 'CONTINUE_AFTER_MISS' not in config_header(plan)
    explicit = deepcopy(reads)
    explicit['continue_after_miss'] = False
    assert make_plan(explicit, 2) == plan


def test_soft_runs_are_recorded_in_the_plan_identity_and_the_header(reads):
    default = make_plan(reads, 2)
    reads['continue_after_miss'] = True
    plan = make_plan(reads, 2)
    assert plan['continue_after_miss'] is True and plan['plan_hash'] != default['plan_hash']
    assert '#define CHASER_CONTINUE_AFTER_MISS 1' in config_header(plan)


@pytest.mark.parametrize('value', [1, 'yes', None])
def test_continue_after_miss_must_be_a_boolean(reads, value):
    reads['continue_after_miss'] = value
    with pytest.raises(ValueError, match='continue_after_miss'):
        make_plan(reads, 2)


def soft_fixture():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).parent / 'fixtures/soft-laysim-p.json').read_text())


def parsed(fixture, mutate=None):
    import json
    from chaser.periodic.measurement import parse_log
    records = [json.loads(line.removeprefix('PERIODIC ')) for line in fixture['log'].splitlines()]
    if mutate:
        mutate(records)
    return parse_log(''.join('PERIODIC ' + json.dumps(r) + '\n' for r in records), fixture['plan'])


def test_recorded_overloaded_soft_run_keeps_every_job_and_counts_late_ones():
    fixture = soft_fixture()
    result = parsed(fixture)
    assert result['execution_status'] == 'ok', result['errors']
    assert len(result['jobs']) == sum(t['job_count'] for t in fixture['plan']['tasks'])
    # Measured window (after the 40-tick warm-up): t0 jobs 4-7 and t1 jobs 2-3 are late on the overloaded core.
    assert result['late_jobs'] == 6 and result['measured_jobs'] == 8
    assert result['postponed_releases'] == 6


def test_the_same_records_fail_without_the_soft_flag():
    fixture = soft_fixture()
    del fixture['plan']['continue_after_miss']  # header still carries the soft plan's hash
    errors = set(parsed(fixture)['errors'])
    assert {'deadline_miss', 'postponed_job', 'period_state', 'period_status'} <= errors


def test_soft_runs_still_reject_a_wrong_checksum():
    def corrupt(records):
        next(r for r in records if r.get('kind') == 'job' and r['task'] == 0 and r['job'] == 5)['checksum'] += 1
    assert 'checksum' in parsed(soft_fixture(), corrupt)['errors']


def test_a_postponed_jobs_accounting_epoch_must_be_an_earlier_release_of_its_task():
    def shift(records):
        job = next(r for r in records if r.get('kind') == 'job' and r['task'] == 0 and r['job'] == 5)
        job['wall_before_ns'] += 3_000_000
        job['wall_after_ns'] += 3_000_000
    assert 'release_mismatch' in parsed(soft_fixture(), shift)['errors']
