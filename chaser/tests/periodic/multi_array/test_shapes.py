"""Array shapes describe storage; kernels own their access and result contracts."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from chaser.periodic.arrays import normalize_arrays
from chaser.periodic.kernels import reference_events, task_from_plan
from chaser.periodic.workload import ArraySpec
from chaser.periodic.measurement import make_plan


def test_flat_v2_plan_is_unchanged(config):
    saved = json.loads((Path(__file__).parent / 'fixtures/gemm-flat.json').read_text())
    plans = [make_plan(config, a) for a in range(3)]
    assert [p['plan_hash'] for p in plans] == saved['plan_hashes']


@pytest.mark.parametrize('shape,strides,length', [
    ([6], [1], 6), ([2, 3], [3, 1], 6), ([2, 3, 4], [12, 4, 1], 24),
])
def test_shape_derives_dense_storage(shape, strides, length):
    raw = dict(array_id='x', element_type='uint32_t', shape=shape)
    original = deepcopy(raw)
    array, = normalize_arrays([raw])
    assert raw == original
    assert array.shape == tuple(shape)
    assert array.strides_elements == tuple(strides)
    assert (array.length, array.size_bytes) == (length, 4*length)
    shape[0] = 99
    assert array.shape == tuple(original['shape'])


def test_padded_three_dimensional_storage_uses_extent_not_shape_product():
    array, = normalize_arrays([dict(array_id='x', element_type='uint32_t',
                                   shape=[2, 3, 4], strides_elements=[40, 12, 2])])
    assert array.length == 71


@pytest.mark.parametrize('extra', [
    {'shape': []}, {'shape': None}, {'shape': '2,3'}, {'shape': [2, 0]},
    {'shape': [True, 3]}, {'shape': [2, 3.0]}, {'shape': [2, -1]},
    {'shape': [2, 3], 'strides_elements': [3]},
    {'shape': [2, 3], 'strides_elements': None},
    {'shape': [2, 3], 'strides_elements': [3, 0]},
    {'shape': [2, 3], 'strides_elements': [3, True]},
    {'shape': [2, 3], 'strides_elements': [4, 2]},
    {'shape': [2, 3], 'length': 5},
    {'length': 6, 'strides_elements': [3, 1]},
    {},
])
def test_invalid_shape_stride_or_storage_is_rejected(extra):
    with pytest.raises(ValueError):
        normalize_arrays([dict(array_id='x', element_type='uint32_t', **extra)])


def test_shape_allocation_budget_is_checked():
    with pytest.raises(ValueError):
        normalize_arrays([dict(array_id='x', element_type='uint32_t', shape=[4096, 4096])])


def test_gemm_infers_dimensions_without_mutating_input(shaped_config):
    original = deepcopy(shaped_config)
    plan = make_plan(shaped_config, 2)
    assert shaped_config == original
    task = plan['tasks'][0]
    assert [task[k] for k in ('m', 'n', 'k', 'lda', 'ldb', 'ldc')] == [2, 2, 3, 3, 2, 2]
    assert (task['source_loads'], task['source_stores']) == (52, 8)
    assert (task['unique_accessed_bytes'], task['unique_cache_lines']) == (64, 3)
    explicit = deepcopy(shaped_config)
    explicit['tasks'][0].update(m=2, n=2, k=3, lda=3, ldb=2, ldc=2)
    assert make_plan(explicit, 2) == plan


@pytest.mark.parametrize('change', ['rank', 'inner', 'output', 'm', 'lda', 'bounds'])
def test_gemm_rejects_inconsistent_shapes_and_explicit_parameters(shaped_config, change):
    if change == 'rank': shaped_config['arrays'][0]['shape'] = [6]
    elif change == 'inner': shaped_config['arrays'][1]['shape'] = [4, 2]
    elif change == 'output': shaped_config['arrays'][2]['shape'] = [2, 3]
    elif change in ('m', 'lda'): shaped_config['tasks'][0][change] = 9
    else: shaped_config['tasks'][0]['arrays']['A']['offset_elements'] = 1
    with pytest.raises(ValueError): make_plan(shaped_config, 2)


def test_gemm_strided_reference_stream_and_footprint(shaped_config):
    for array in shaped_config['arrays']:
        array['strides_elements'] = [24, 8]
        array['length'] = 80
    for binding in shaped_config['tasks'][0]['arrays'].values():
        binding['offset_elements'] = 1
    plan = make_plan(shaped_config, 2)
    task = plan['tasks'][0]
    events = list(reference_events(task_from_plan(task), {a['array_id']: ArraySpec.from_dict(a) for a in plan['arrays']}))
    assert [(e.array_id, e.offset_bytes) for e in events[:7]] == [
        ('a0', 4), ('b0', 4), ('a0', 36), ('b0', 100),
        ('a0', 68), ('b0', 196), ('c0', 4)]
    assert [e.offset_bytes for e in events[-4:]] == [4, 36, 100, 132]
    assert task['unique_accessed_bytes'] == 64
    assert task['unique_cache_lines'] == 16
    assert task['allocation_bytes'] == 960


def test_three_dimensional_array_with_existing_linear_read_kernel(config):
    config['arrays'] = [dict(array_id='x', element_type='uint32_t', shape=[2, 3, 4])]
    config['tasks'] = [dict(task_id='reader', pattern='cyclic', arrays={'input': {'array_id': 'x'}},
                           distinct=24, stride_bytes=4, sweeps=1, core=0, period_ticks=10)]
    task = make_plan(config, 2)['tasks'][0]
    assert task['expected_checksum'] == 24
    assert (task['allocation_bytes'], task['unique_accessed_bytes']) == (96, 96)


def test_shape_and_strides_participate_in_plan_identity(shaped_config):
    baseline = make_plan(shaped_config, 2)
    shaped_config['arrays'][0]['strides_elements'] = [5, 1]
    padded = make_plan(shaped_config, 2)
    assert baseline['plan_hash'] != padded['plan_hash']


@pytest.mark.parametrize('step', [1, 2, 7, 8, 9])
@pytest.mark.parametrize('offset', [0, 1, 7])
def test_strided_footprint_counts_shared_boundary_lines(shaped_config, step, offset):
    expected_lines = 0
    for array in shaped_config['arrays']:
        rows, cols = array['shape']
        ld = (cols-1)*step+1
        array.update(strides_elements=[ld, step], length=offset+(rows-1)*ld+(cols-1)*step+1)
        expected_lines += len({(offset+r*ld+c*step)//8 for r in range(rows) for c in range(cols)})
    for binding in shaped_config['tasks'][0]['arrays'].values():
        binding['offset_elements'] = offset
    assert make_plan(shaped_config, 2)['tasks'][0]['unique_cache_lines'] == expected_lines


@pytest.mark.parametrize('name', ['gemm-u32-smoke.json', 'gemm-u32-shared-smoke.json'])
def test_public_gemm_examples_use_inferred_shapes(name):
    path = Path(__file__).resolve().parents[3] / 'configs/periodic-multi-array' / name
    config = json.loads(path.read_text())
    assert all('shape' in a for a in config['arrays'])
    assert all('m' not in t for t in config['tasks'])
    checksum = 2166136261
    for _ in range(4):
        checksum = ((checksum ^ 6)*16777619) % 2**32
    assert all(t['expected_checksum'] == checksum for t in make_plan(config, 2)['tasks'])
