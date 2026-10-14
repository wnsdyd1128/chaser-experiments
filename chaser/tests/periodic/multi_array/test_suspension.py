"""Self-suspending jobs: k sweeps, rtems_task_wake_after(S), then the remaining sweeps (schema v2 task fields)."""
from copy import deepcopy
import re

import pytest

from chaser.periodic.codegen import workload_source
from chaser.periodic.codegen.project import config_header
from chaser.periodic.kernels import reference_events, segment_tasks, task_from_plan
from chaser.periodic.measurement import make_plan
from chaser.periodic.workload import ArraySpec


@pytest.fixture
def reads():
    return dict(schema_version=2, workload_id='suspend-smoke', family_id='suspend-diagnostic',
                policy_id='explicit-core-map-v1', horizon_ticks=40, warmup_ticks=20, u_repeats=1,
                arrays=[dict(array_id='r0', element_type='uint32_t', length=64, alignment_bytes=32, initial_value=3),
                        dict(array_id='r1', element_type='uint32_t', length=64, alignment_bytes=32, initial_value=5)],
                tasks=[dict(task_id='t0', pattern='cyclic', arrays=dict(input=dict(array_id='r0', offset_elements=0)),
                            distinct=16, stride_bytes=4, sweeps=5, core=0, period_ticks=10),
                       dict(task_id='t1', pattern='cyclic', arrays=dict(input=dict(array_id='r1', offset_elements=0)),
                            distinct=8, stride_bytes=4, sweeps=2, core=1, period_ticks=20)])


def suspended(config, ticks=3, after=2):
    config = deepcopy(config)
    config['tasks'][0].update(suspend_ticks=ticks, suspend_after_sweeps=after)
    return config


def test_plan_without_suspension_is_unchanged_and_explicit_zero_is_the_default(reads):
    plan = make_plan(reads, 2)
    assert all('suspend_ticks' not in t and 'suspend_after_sweeps' not in t for t in plan['tasks'])
    explicit = deepcopy(reads)
    explicit['tasks'][0]['suspend_ticks'] = 0
    assert make_plan(explicit, 2) == plan


def test_suspended_task_records_split_and_counts_both_segments(reads):
    task = make_plan(suspended(reads), 2)['tasks'][0]
    assert (task['suspend_ticks'], task['suspend_after_sweeps']) == (3, 2)
    assert task['source_loads'] == 5 * 16 and task['source_accesses'] == 5 * 16
    assert task['loop_iterations'] == 5 * (1 + 16)
    # The job's recorded checksum is the resumed segment's: 3 sweeps x 16 loads x initial value 3.
    assert task['expected_checksum'] == 3 * 16 * 3


def test_segments_split_sweeps_and_name_the_resumed_function(reads):
    plan = make_plan(suspended(reads), 2)
    registry = {a['array_id']: ArraySpec.from_dict(a) for a in plan['arrays']}
    first, resumed = segment_tasks(task_from_plan(plan['tasks'][0]), registry)
    assert (first.task_id, first.sweeps, first.metrics.expected_checksum) == ('t0', 2, 2 * 16 * 3)
    assert (resumed.task_id, resumed.sweeps, resumed.metrics.expected_checksum) == ('resume_t0', 3, 3 * 16 * 3)
    assert segment_tasks(task_from_plan(plan['tasks'][1]), registry) == (task_from_plan(plan['tasks'][1]),)


def test_reference_events_cover_the_first_then_the_resumed_segment(reads):
    plan = make_plan(suspended(reads, after=1), 2)
    registry = {a['array_id']: ArraySpec.from_dict(a) for a in plan['arrays']}
    events = list(reference_events(task_from_plan(plan['tasks'][0]), registry))
    assert len(events) == plan['tasks'][0]['source_accesses'] == 5 * 16
    assert [e.offset_bytes for e in events[:16]] == [4 * i for i in range(16)]


@pytest.mark.parametrize('change, message', [
    (dict(suspend_ticks=10), 'suspend_ticks'),              # not below the 10-tick period
    (dict(suspend_ticks=-1), 'suspend_ticks'),
    (dict(suspend_ticks=True), 'suspend_ticks'),
    (dict(suspend_ticks=3), 'suspend_after_sweeps'),         # split missing
    (dict(suspend_ticks=3, suspend_after_sweeps=0), 'suspend_after_sweeps'),
    (dict(suspend_ticks=3, suspend_after_sweeps=5), 'suspend_after_sweeps'),  # no resumed sweep left
    (dict(suspend_after_sweeps=2), 'suspend_after_sweeps'),  # split without a suspension
])
def test_invalid_suspension_is_rejected(reads, change, message):
    reads['tasks'][0].update(change)
    with pytest.raises(ValueError, match=message):
        make_plan(reads, 2)


def test_resumed_function_name_must_not_collide_with_a_task(reads):
    reads = suspended(reads)
    reads['tasks'][1]['task_id'] = 'resume_t0'
    with pytest.raises(ValueError, match='unique'):
        make_plan(reads, 2)


def test_source_without_suspension_has_no_resume_tables(reads):
    plan = make_plan(reads, 2)
    source = workload_source(plan['tasks'], arrays=plan['arrays'])
    assert 'resume' not in source and 'suspend' not in source


def test_source_emits_both_segments_and_resume_tables(reads):
    plan = make_plan(suspended(reads), 2)
    source = workload_source(plan['tasks'], arrays=plan['arrays'])
    first = source[source.index('uint32_t task_job_t0(void)'):]
    resumed = source[source.index('uint32_t task_job_resume_t0(void)'):]
    assert re.search(r's < 2;', first[:first.index('return')])
    assert re.search(r's < 3;', resumed[:resumed.index('return')])
    assert 'workload_resume_jobs[])(void) = {\n    task_job_resume_t0,\n    0,\n};' in source
    assert 'workload_suspend_expected[] = {96U, 0U};' in source
    assert 'workload_expected[] = {\n144U, 80U\n};' in source


def test_config_header_lists_suspensions_only_when_a_task_suspends(reads):
    assert 'CHASER_SUSPENDS' not in config_header(make_plan(reads, 0))
    assert '#define CHASER_SUSPENDS {3, 0}' in config_header(make_plan(suspended(reads), 0))


def test_recorded_laysim_run_keeps_the_sleep_inside_the_measured_job():
    # Recorded laysim run (fixture note): t0 sleeps 3 ticks between its segments; t1 does not suspend.
    from pathlib import Path
    import json
    from chaser.periodic.measurement import parse_log
    fixture = json.loads((Path(__file__).parent / 'fixtures/suspend-laysim-p.json').read_text())
    plan = fixture['plan']
    result = parse_log(fixture['log'], plan)
    assert result['execution_status'] == 'ok', result['errors']
    tick = plan['tick_ns']
    for job in result['jobs']:
        cpu = job['cpu_after_ns'] - job['cpu_before_ns']
        off_cpu = job['completion_ns'] - job['start_ns'] - cpu
        assert job['checksum'] == plan['tasks'][job['task']]['expected_checksum']
        if job['task'] == 0:   # the sleep ends at a tick boundary: between 2 and 3 ticks off the CPU
            assert 2 * tick < off_cpu < 3 * tick + tick // 20
        else:
            assert off_cpu < tick // 20


SDK = __import__('pathlib').Path('/opt/rtems/6')


@pytest.mark.skipif(not (SDK / 'bin/sparc-rtems6-gcc').exists(), reason='requires the RTEMS SDK')
def test_suspended_build_links_both_segments_into_every_elf(reads, tmp_path):
    from chaser.periodic.build import prepare, read_symbols
    prepare(suspended(reads), tmp_path / 'prepared')
    for name in ('g', 'c', 'p', 'c2'):
        assert '#define CHASER_SUSPENDS {3, 0}' in (tmp_path / f'prepared/{name}/config.h').read_text()
        symbols = read_symbols(tmp_path / f'prepared/build/{name}.exe')
        assert {'task_job_t0', 'task_job_resume_t0', 'workload_resume_jobs', 'workload_suspend_expected'} <= set(symbols)


@pytest.mark.skipif(not (SDK / 'bin/sparc-rtems6-gcc').exists() or __import__('shutil').which('clang-14') is None,
                    reason='requires the RTEMS SDK and clang-14')
def test_analysis_combines_both_cold_segments_of_a_suspending_task(reads, tmp_path):
    from chaser.locality.cls import cls
    from chaser.periodic.analysis import analyze
    reads['arrays'][0]['length'] = 128
    reads['tasks'][0].update(stride_bytes=32, suspend_ticks=3, suspend_after_sweeps=2)  # one line per element
    prepare = __import__('chaser.periodic.build', fromlist=['prepare']).prepare
    prepare(reads, tmp_path / 'prepared')
    cases = analyze(tmp_path / 'prepared')['cases']
    # Each segment is analyzed from a cold cache: 16 memory misses, then L1 hits for its remaining sweeps.
    assert cases['t0']['segments']['t0']['clp'] == [16 / 32, 0, 16 / 32]
    assert cases['t0']['segments']['resume_t0']['clp'] == [32 / 48, 0, 16 / 48]
    assert cases['t0']['modeled_accesses'] == 80 and cases['t0']['clp'] == [48 / 80, 0, 32 / 80]
    profile = dict(modeled_accesses=80, l1_first_hit_ratio=0.6, llc_first_hit_ratio=0, all_cache_miss_ratio=0.4)
    assert cases['t0']['cls']['0.5'] == cls(profile, dict(l1_capacity=16384, llc_capacity=2 * 1024 ** 2), 0.5)
    assert 'segments' not in cases['t1']
