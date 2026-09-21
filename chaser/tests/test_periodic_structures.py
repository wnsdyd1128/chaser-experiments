"""Independent small traces for candidate structures, including actual ELF streams."""

import json

import pytest

from chaser.periodic import make_plan
from chaser.periodic_patterns import access_offsets, job_access_count, loop_iterations


TRACES = {
    'tile-reuse': [0,1,2,3,4,5]*2 + [6,7,8,9,10,11]*2
                  + [12,13,14,15,16,17]*2 + [18,19,20,21,22,23]*2,
    'overlap': [0,1,2,3,4,5, 3,4,5,6,7,8, 6,7,8,9,10,11,
                9,10,11,12,13,14, 12,13,14,15,16,17,
                15,16,17,18,19,20, 18,19,20,21,22,23],
    'lane-scan': [0,3,6,9,12,15,18,21, 1,4,7,10,13,16,19,22,
                  2,5,8,11,14,17,20,23],
    'forward-reverse': list(range(24)) + list(range(23, -1, -1)),
    'mirrored': [0,23,1,22,2,21,3,20,4,19,5,18,6,17,7,16,8,15,9,14,10,13,11,12],
    'hub-spoke': [0,1,0,2,0,3,0,4,0,5,0,6,0,7,0,8,0,9,0,10,0,11,0,12,
                  0,13,0,14,0,15,0,16,0,17,0,18,0,19,0,20,0,21,0,22,0,23],
    'tile-reverse': [0,1,2,3,4,5,5,4,3,2,1,0, 6,7,8,9,10,11,11,10,9,8,7,6,
                     12,13,14,15,16,17,17,16,15,14,13,12,
                     18,19,20,21,22,23,23,22,21,20,19,18],
    'hot-per-tile': [0,1,2,3,4,5]*2 + [6,7,8,9,10,11]
                    + [0,1,2,3,4,5]*2 + [12,13,14,15,16,17]
                    + [0,1,2,3,4,5]*2 + [18,19,20,21,22,23],
    'region-cycle': list(range(8)) + list(range(8,16)) + list(range(8))
                    + list(range(16,24)) + list(range(8,16)) + list(range(16,24)),
    'coarse-fine': [0,4,8,12,16,20] + list(range(24)),
}


def configuration(pattern):
    return dict(workload_id='structure', family_id=pattern,
                policy_id='correctness-only', horizon_ticks=40, tasks=[
                    dict(task_id='target', pattern=pattern, distinct=24, stride=32,
                         sweeps=2, core=0, period_ticks=20)])


@pytest.mark.parametrize('pattern', TRACES)
def test_new_structure_matches_independent_literal_trace(pattern):
    task = make_plan(configuration(pattern), 2)['tasks'][0]
    expected = [32 * i for i in TRACES[pattern]] * 2
    assert list(access_offsets(task)) == expected
    assert job_access_count(task) == task['expected_checksum'] == len(expected)
    assert loop_iterations(task) >= task['sweeps']
    assert set(expected) == set(range(0, 24*32, 32))


@pytest.mark.parametrize('pattern', TRACES)
@pytest.mark.parametrize('change', [{'distinct': 12}, {'hot_distinct': 2}])
def test_structures_reject_degenerate_bounds_and_ignored_fields(pattern, change):
    config = configuration(pattern)
    config['tasks'][0].update(change)
    with pytest.raises(ValueError, match='structure'):
        make_plan(config, 2)


def test_new_structures_match_literal_traces_in_all_final_elfs(tmp_path):
    from chaser.periodic_build import prepare
    from chaser.periodic_analysis import analyze

    config = configuration('tile-reuse')
    config['tasks'] = [dict(configuration(p)['tasks'][0], task_id=f't{i}', core=i % 4)
                       for i, p in enumerate(TRACES)]
    prepare(config, tmp_path / 'snapshot')
    result = analyze(tmp_path / 'snapshot')
    for i, (pattern, expected) in enumerate(TRACES.items()):
        assert result['cases'][f't{i}']['modeled_accesses'] == 2 * len(expected)
        for architecture in ('g', 'c', 'p'):
            path = tmp_path / f'snapshot/analysis/{architecture}/t{i}/events.json'
            events = json.loads(path.read_text())['events']
            base = 0x1000000 + i * 4096
            assert [r['linked_address'] - base for r in events] == [v*32 for v in expected]*2
