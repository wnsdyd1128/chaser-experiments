"""Literal access sequences distinguish interleaved hot/cold jobs from phases."""

from copy import deepcopy

import pytest

from chaser.periodic import make_plan
from chaser.periodic_analysis import check_stream
from chaser.periodic_patterns import access_offsets, loop_iterations


def pattern_configuration():
    return dict(workload_id='patterns', family_id='development-patterns',
                policy_id='explicit-development-v1', horizon_ticks=40,
                tasks=[dict(task_id=name, pattern=pattern, distinct=5, stride=32,
                            hot_distinct=2, hot_repeats=2, cold_repeats=1,
                            sweeps=2, period_ticks=20, core=i)
                       for i, (name, pattern) in enumerate(
                           [('hot', 'hot-cold'), ('phase', 'phase')])])


def test_pattern_checksum_counts_repeated_regions_not_only_distinct_elements():
    tasks = make_plan(pattern_configuration(), 2)['tasks']
    assert [t['expected_checksum'] for t in tasks] == [14, 14]
    assert [t['data_size'] for t in tasks] == [160, 160]


@pytest.mark.parametrize('field,value', [
    ('pattern', 'unknown'), ('pattern', None),
    ('hot_distinct', 0), ('hot_distinct', 5), ('hot_distinct', True),
    ('hot_repeats', 0), ('hot_repeats', 1_000_001),
    ('cold_repeats', -1), ('cold_repeats', 1.5),
])
def test_invalid_region_pattern_is_rejected(field, value):
    config = pattern_configuration()
    config['tasks'][0][field] = value
    with pytest.raises(ValueError, match='pattern|hot_distinct|hot_repeats|cold_repeats'):
        make_plan(config, 2)


@pytest.mark.parametrize('field', ['hot_distinct', 'hot_repeats', 'cold_repeats'])
def test_region_pattern_requires_explicit_bounds(field):
    config = pattern_configuration()
    del config['tasks'][0][field]
    with pytest.raises(ValueError, match=field):
        make_plan(config, 2)


def test_cyclic_cannot_silently_ignore_region_parameters():
    config = pattern_configuration()
    config['tasks'][0]['pattern'] = 'cyclic'
    with pytest.raises(ValueError, match='cyclic'):
        make_plan(config, 2)


def test_pattern_planning_does_not_mutate_configuration():
    config = pattern_configuration()
    original = deepcopy(config)
    make_plan(config, 1)
    assert config == original


@pytest.mark.parametrize('index,offsets,iterations', [
    (0, [0, 32, 0, 32, 64, 96, 128] * 2, 22),
    (1, [0, 32] * 4 + [64, 96, 128] * 2, 25),
])
def test_interleaved_and_phase_jobs_match_literal_sequences(index, offsets, iterations):
    task = make_plan(pattern_configuration(), 2)['tasks'][index]
    assert list(access_offsets(task)) == offsets
    assert loop_iterations(task) == iterations


@pytest.mark.parametrize('change', ['missing', 'order', 'size', 'store', 'object', 'address'])
def test_wrong_access_stream_is_rejected_even_with_an_unchanged_checksum(change):
    task = make_plan(pattern_configuration(), 2)['tasks'][0]
    events = [dict(linked_address=0x1000000 + offset, access_size=1,
                   operation='load', object_id='global::data_hot')
              for offset in [0, 32, 0, 32, 64, 96, 128] * 2]
    check_stream(task, events, 0x1000000)
    if change == 'missing':
        events.pop()
    elif change == 'order':
        events[0], events[1] = events[1], events[0]
    else:
        key, value = {'size': ('access_size', 2), 'store': ('operation', 'store'),
                      'object': ('object_id', 'global::data_phase'),
                      'address': ('linked_address', 0x1001000)}[change]
        events[0][key] = value
    with pytest.raises(ValueError, match='access'):
        check_stream(task, events, 0x1000000)


def test_cold_repetition_and_checksum_wrap_cover_all_loads():
    config = pattern_configuration()
    for t in config['tasks']:
        t.update(sweeps=1_000_000, hot_repeats=1_000_000, cold_repeats=3)
    tasks = make_plan(config, 2)['tasks']
    assert [t['expected_checksum'] for t in tasks] == [(2_000_009_000_000 % 2**32)] * 2


def test_region_bounds_include_the_entire_allocated_array():
    config = pattern_configuration()
    config['tasks'][0].update(distinct=131072, stride=4096)
    with pytest.raises(ValueError, match='16 MiB'):
        make_plan(config, 2)
