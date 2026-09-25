"""Literal address contracts for source-informed synthetic recipes."""

import json

import pytest

from chaser.periodic.measurement import make_plan
from chaser.periodic.patterns import access_offsets, job_access_count


# Width two, one block; two independent array regions retain their offsets.
TRACES = {
    'window-coeff': [0,4,1,5, 1,4,2,5, 2,4,3,5],
    'window-bank': [0,4,1,5, 0,6,1,7, 1,4,2,5, 1,6,2,7,
                    2,4,3,5, 2,6,3,7],
    'paired-pass': [0,1,0,1, 2,3,2,3, 0,2,1,3],
    'matrix-reuse': [0,4,1,5, 2,4,3,5, 0,6,1,7, 2,6,3,7],
    'row-column': [0,1,2,3, 0,2,1,3],
    'row-column-mirrored': [0,1,2,3, 0,2,1,3],
}


def configuration(pattern, *, width=2, blocks=2):
    from chaser.periodic.recipes import block_size

    return dict(workload_id='recipe-check', family_id='correctness-only',
                policy_id='correctness-only', horizon_ticks=40,
                warmup_ticks=20, u_repeats=5, tasks=[
                    dict(task_id='target', pattern=pattern, width=width,
                         distinct=blocks * block_size(pattern, width), stride=32,
                         sweeps=2, core=0, period_ticks=20)])


@pytest.mark.parametrize('pattern', TRACES)
def test_recipe_preserves_literal_region_order_and_repeated_blocks(pattern):
    config = configuration(pattern)
    task = make_plan(config, 2)['tasks'][0]
    width = max(TRACES[pattern]) + 1
    expected = [32 * (i + b * width) for b in range(2) for i in TRACES[pattern]] * 2
    assert list(access_offsets(task)) == expected
    assert job_access_count(task) == task['expected_checksum'] == len(expected)
    assert set(expected) == set(range(0, task['data_size'], 32))


@pytest.mark.parametrize('pattern', TRACES)
@pytest.mark.parametrize('change', [{'width': 3}, {'width': True}, {'width': 34},
                                   {'width': None}, {'distinct': 1}, {'hot_distinct': 1}])
def test_recipe_rejects_ambiguous_shapes_and_ignored_legacy_parameters(pattern, change):
    config = configuration(pattern)
    config['tasks'][0].update(change)
    with pytest.raises(ValueError, match='recipe'):
        make_plan(config, 2)


def test_legacy_pattern_does_not_silently_ignore_recipe_width():
    config = configuration('row-column')
    config['tasks'][0].update(pattern='overlap', distinct=24)
    with pytest.raises(ValueError, match='width'):
        make_plan(config, 2)


def test_mirrored_block_phase_retains_symmetry_at_width_four():
    task = make_plan(configuration('row-column-mirrored', width=4, blocks=1), 2)['tasks'][0]
    expected = [0,3,1,2,4,7,5,6,8,11,9,10,12,15,13,14,
                0,12,4,8,1,13,5,9,2,14,6,10,3,15,7,11]
    assert list(access_offsets(task)) == [32*i for i in expected] * 2


@pytest.mark.parametrize('pattern', TRACES)
@pytest.mark.parametrize('width', [4, 8, 32])
def test_recipe_counts_and_complete_footprint_hold_at_larger_widths(pattern, width):
    task = make_plan(configuration(pattern, width=width), 2)['tasks'][0]
    offsets = list(access_offsets(task))
    assert len(offsets) == job_access_count(task)
    assert set(offsets) == set(range(0, task['data_size'], task['stride']))


def test_recipes_match_literal_streams_in_all_final_elfs(tmp_path):
    from chaser.periodic.analysis import analyze
    from chaser.periodic.build import prepare

    config = configuration('window-coeff')
    config['tasks'] = [dict(configuration(p)['tasks'][0], task_id=f't{i}', core=i % 4)
                       for i, p in enumerate(TRACES)]
    prepare(config, tmp_path / 'snapshot')
    analyze(tmp_path / 'snapshot')
    for i, (pattern, expected) in enumerate(TRACES.items()):
        block = max(expected) + 1
        offsets = [32*(v+b*block) for b in range(2) for v in expected]*2
        for architecture in ('g', 'c', 'p'):
            path = tmp_path / f'snapshot/analysis/{architecture}/t{i}/events.json'
            events = json.loads(path.read_text())['events']
            assert [e['linked_address']-(0x1000000+i*4096) for e in events] == offsets
