"""Release offsets: offset_ticks puts a task's first release at t0 + offset; later releases follow every period."""
from copy import deepcopy

import pytest

from chaser.periodic.codegen.project import config_header
from chaser.periodic.measurement import make_plan


@pytest.fixture
def reads():
    return dict(schema_version=2, workload_id='offset-smoke', family_id='offset-diagnostic',
                policy_id='explicit-core-map-v1', horizon_ticks=40, warmup_ticks=20, u_repeats=1,
                arrays=[dict(array_id=f'r{i}', element_type='uint32_t', length=64, alignment_bytes=32, initial_value=i + 3)
                        for i in range(2)],
                tasks=[dict(task_id=f't{i}', pattern='cyclic', arrays=dict(input=dict(array_id=f'r{i}', offset_elements=0)),
                            distinct=16, stride_bytes=4, sweeps=5, core=i, period_ticks=(10, 20)[i]) for i in range(2)])


def test_plans_and_headers_without_offsets_are_unchanged_and_explicit_zero_is_the_default(reads):
    plan = make_plan(reads, 2)
    assert all('offset_ticks' not in t for t in plan['tasks'])
    assert 'CHASER_OFFSETS' not in config_header(plan)
    explicit = deepcopy(reads)
    explicit['tasks'][0]['offset_ticks'] = 0
    assert make_plan(explicit, 2) == plan


def test_an_offset_is_recorded_in_the_plan_identity_and_the_header(reads):
    default = make_plan(reads, 2)
    reads['tasks'][1]['offset_ticks'] = 7
    plan = make_plan(reads, 2)
    assert plan['tasks'][1]['offset_ticks'] == 7 and 'offset_ticks' not in plan['tasks'][0]
    assert plan['plan_hash'] != default['plan_hash']
    assert '#define CHASER_OFFSETS {0, 7}' in config_header(plan)


def test_an_offset_keeps_the_job_count_and_warmup_of_its_period(reads):
    reads['tasks'][1]['offset_ticks'] = 7
    task = make_plan(reads, 2)['tasks'][1]
    assert task['job_count'] == 2 and task['warmup_jobs'] == 1


@pytest.mark.parametrize('value', [-1, 20, 25, 1.5, True, '3'])
def test_an_offset_must_be_a_whole_tick_count_below_the_period(reads, value):
    reads['tasks'][1]['offset_ticks'] = value
    with pytest.raises(ValueError, match='offset_ticks'):
        make_plan(reads, 2)


def offset_fixture():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).parent / 'fixtures/offset-laysim-p.json').read_text())


def test_recorded_laysim_run_releases_each_job_at_its_offset_plus_whole_periods():
    # Recorded laysim run (fixture note): t1 (period 20, offset 7) and t2 (period 40, offset 13); t0 has no offset.
    from chaser.periodic.measurement import parse_log
    fixture = offset_fixture()
    plan = fixture['plan']
    result = parse_log(fixture['log'], plan)
    assert result['execution_status'] == 'ok', result['errors']
    t0, tick = result['header']['t0_ns'], plan['tick_ns']
    for job in result['jobs']:
        task = plan['tasks'][job['task']]
        assert job['release_ns'] == t0 + (task.get('offset_ticks', 0) + job['job'] * task['period_ticks']) * tick
        # No job starts before its release or waits a tick for it (t0's first job starts 0.2 ms after t0).
        assert job['release_ns'] <= job['start_ns'] < job['release_ns'] + tick // 2


def test_an_offset_jobs_edf_deadline_follows_its_own_release():
    # On core 0, t1's first job (released at 7 ms, deadline 27 ms) yields to t0's job released at 10 ms (deadline 20 ms).
    from chaser.periodic.measurement import parse_log
    fixture = offset_fixture()
    jobs = {(j['task'], j['job']): j for j in parse_log(fixture['log'], fixture['plan'])['jobs']}
    assert jobs[1, 0]['start_ns'] < jobs[0, 1]['start_ns'] < jobs[0, 1]['completion_ns'] < jobs[1, 0]['completion_ns']


def test_the_same_records_fail_without_the_offset():
    from chaser.periodic.measurement import parse_log
    fixture = offset_fixture()
    del fixture['plan']['tasks'][1]['offset_ticks']  # header still carries the offset plan's hash
    assert 'release_mismatch' in parse_log(fixture['log'], fixture['plan'])['errors']
