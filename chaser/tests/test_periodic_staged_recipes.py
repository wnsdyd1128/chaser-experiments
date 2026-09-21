"""Source-derived stage/triangle contracts use independent literal streams."""

import json

import pytest

from chaser.periodic import make_plan
from chaser.periodic_patterns import access_offsets, job_access_count


TRACES = {
    'butterfly-twiddle': [4, 5, 2, 3, 0, 1],
    'butterfly-scale': [4, 5, 2, 3, 0, 1, 0, 1, 2, 3],
    'triangular-solve': [4, 5, 2, 6, 7, 3, 6, 1, 8, 0],
    'triangular-solve-transposed': [4, 5, 1, 6, 7, 3, 6, 2, 8, 0],
}


def configuration(pattern, width=2, blocks=2):
    from chaser.periodic_staged_recipes import block_size

    return dict(workload_id='staged-check', family_id='correctness-only',
        policy_id='correctness-only', horizon_ticks=40, tasks=[dict(
            task_id='target', pattern=pattern, width=width,
            distinct=blocks*block_size(pattern, width), stride=32, sweeps=2,
            core=0, period_ticks=20)])


@pytest.mark.parametrize('pattern', TRACES)
def test_staged_literal_order_blocks_and_sweeps(pattern):
    task = make_plan(configuration(pattern), 2)['tasks'][0]
    block = max(TRACES[pattern]) + 1
    expected = [32*(i+b*block) for b in range(2) for i in TRACES[pattern]]*2
    assert list(access_offsets(task)) == expected
    assert task['expected_checksum'] == job_access_count(task) == len(expected)


@pytest.mark.parametrize('pattern', TRACES)
@pytest.mark.parametrize('width', [4, 8, 32])
def test_staged_load_count_and_complete_footprint(pattern, width):
    task = make_plan(configuration(pattern, width), 2)['tasks'][0]
    offsets = list(access_offsets(task))
    assert len(offsets) == job_access_count(task)
    assert set(offsets) == set(range(0, task['data_size'], 32))


@pytest.mark.parametrize('pattern', TRACES)
@pytest.mark.parametrize('change', [{'width': True}, {'width': 0}, {'width': 33},
                                   {'width': None}, {'distinct': 1}, {'hot_distinct': 1}])
def test_staged_rejects_invalid_shapes(pattern, change):
    config = configuration(pattern)
    config['tasks'][0].update(change)
    with pytest.raises(ValueError, match='recipe'):
        make_plan(config, 2)


def test_butterfly_rejects_non_power_of_two_width():
    config = configuration('butterfly-twiddle', width=6)
    with pytest.raises(ValueError, match='power of two'):
        make_plan(config, 2)


def test_twiddle_pair_is_outside_butterfly_group_loop():
    task = make_plan(configuration('butterfly-twiddle', width=4, blocks=1), 2)['tasks'][0]
    expected = [8,9,2,3,0,1,6,7,4,5,10,11,4,5,0,1,12,13,6,7,2,3]
    assert list(access_offsets(task)) == [32*i for i in expected]*2


def test_new_roles_are_two_families_and_development_exposure_propagates():
    from chaser.periodic_registry import build_registry

    records = []
    for pattern in TRACES:
        config = configuration(pattern)
        config['workload_id'] = pattern
        records.append(dict(configuration=config, recipe_id=pattern, role='candidate',
                            development_exposed=False))
    assert build_registry(records)['primary_family_count'] == 2
    records[0]['development_exposed'] = True
    registry = build_registry(records)
    assert registry['primary_family_count'] == 1
    assert sum(r['primary_candidate'] for r in registry['workloads']) == 2


def test_staged_literal_streams_match_all_linked_elfs(tmp_path):
    from chaser.periodic_analysis import analyze
    from chaser.periodic_build import prepare

    config = configuration('butterfly-twiddle')
    config['tasks'] = [dict(configuration(p)['tasks'][0], task_id=f't{i}', core=i)
                       for i, p in enumerate(TRACES)]
    prepare(config, tmp_path / 'snapshot')
    analyze(tmp_path / 'snapshot')
    for i, (pattern, trace) in enumerate(TRACES.items()):
        block = max(trace) + 1
        expected = [32*(v+b*block) for b in range(2) for v in trace]*2
        for arch in ('g', 'c', 'p'):
            events = json.loads((tmp_path / f'snapshot/analysis/{arch}/t{i}/events.json').read_text())['events']
            assert [e['linked_address']-(0x1000000+i*4096) for e in events] == expected
