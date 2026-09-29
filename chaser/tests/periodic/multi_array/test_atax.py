"""PolyBench-derived ATAX: independent numerical oracle and real access streams."""

from copy import deepcopy
import ctypes
import json
from pathlib import Path
import subprocess

import pytest

from chaser.periodic.arrays import normalize_arrays
from chaser.periodic.build import prepare, workload_source
from chaser.periodic.kernels import reference_events, task_from_plan
from chaser.periodic.measurement import make_plan


@pytest.fixture
def atax_config():
    path = Path(__file__).resolve().parents[3] / 'configs/periodic-multi-array/polybench-atax-u32-medium.json'
    config = json.loads(path.read_text())
    for array, shape in zip(config['arrays'], ([2, 3], [3], [2], [3])):
        array['shape'] = shape
    config['tasks'][0]['sweeps'] = 2
    return config


def padded(config):
    for array, strides, length, offset in zip(config['arrays'],
            ([8, 2], [2], [3], [2]), (16, 8, 8, 8), (1, 1, 2, 1)):
        array.update(strides_elements=strides, length=length)
        role = next(r for r, b in config['tasks'][0]['arrays'].items() if b['array_id'] == array['array_id'])
        config['tasks'][0]['arrays'][role]['offset_elements'] = offset
    return config


def fnv(values):
    result = 2166136261
    for value in values:
        result = ((result ^ value) * 16777619) % 2**32
    return result


def test_smoke_counts_and_constant_checksum(atax_config):
    task = make_plan(atax_config, 2)['tasks'][0]
    assert (task['source_loads'], task['source_stores']) == (75, 34)
    assert task['expected_checksum'] == fnv([12, 12, 12])
    assert task['unique_accessed_bytes'] == 56


def test_single_element_reference_order(atax_config):
    for array in atax_config['arrays']:
        array['shape'] = [1, 1] if array['array_id'] == 'a0' else [1]
    atax_config['tasks'][0]['sweeps'] = 1
    task = task_from_plan(make_plan(atax_config, 2)['tasks'][0])
    registry = {a.array_id: a for a in normalize_arrays(atax_config['arrays'])}
    events = list(reference_events(task, registry))
    assert [(e.array_id, e.operation) for e in events] == [
        ('y0', 'store'), ('tmp0', 'store'),
        ('tmp0', 'load'), ('a0', 'load'), ('x0', 'load'), ('tmp0', 'store'),
        ('y0', 'load'), ('a0', 'load'), ('tmp0', 'load'), ('y0', 'store'),
        ('y0', 'load')]
    assert all(e.offset_bytes == 0 and e.access_size_bytes == 4 for e in events)


@pytest.mark.parametrize('optimization', ['O0', 'O2'])
@pytest.mark.parametrize('overflow', [False, True])
@pytest.mark.parametrize('strided', [False, True])
def test_atax_nonuniform_output_reset_and_padding(atax_config, tmp_path, optimization, overflow, strided):
    config = padded(atax_config) if strided else atax_config
    plan = make_plan(config, 2)
    (tmp_path / 'workload.h').write_text('#include <stdint.h>\n')
    (tmp_path / 'workload.c').write_text(workload_source(plan['tasks'], arrays=plan['arrays']))
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-'+optimization,
                    '-shared', '-fPIC', str(tmp_path / 'workload.c'), '-o', str(tmp_path / 'workload.so')], check=True)
    lib = ctypes.CDLL(str(tmp_path / 'workload.so'))
    lib.workload_prepare()
    arrays = [(ctypes.c_uint32*a['length']).in_dll(lib, 'data_'+a['array_id']) for a in plan['arrays']]
    a, x, scratch, y = arrays
    aa, xx = [[2, 3, 5], [7, 11, 13]], [17, 19, 23]
    if overflow:
        aa[0][1], xx[2] = 0xffffffff, 0xfffffffe
    ai, xi, ti, yi = (([1, 3, 5, 9, 11, 13], [1, 3, 5], [2, 5], [1, 3, 5])
                      if strided else (list(range(6)), list(range(3)), list(range(2)), list(range(3))))
    for index, value in zip(ai, sum(aa, [])): a[index] = value
    for index, value in zip(xi, xx): x[index] = value
    before_a, before_x = list(a), list(x)
    tmp = [sum(v*w for v, w in zip(row, xx)) % 2**32 for row in aa]
    result = [sum(aa[i][j]*tmp[i] for i in range(2)) % 2**32 for j in range(3)]
    expected_tmp, expected_y = list(scratch), list(y)
    for index, value in zip(ti, tmp): expected_tmp[index] = value
    for index, value in zip(yi, result): expected_y[index] = value
    lib.task_job_atax0.restype = ctypes.c_uint32
    for _ in range(3):
        assert lib.task_job_atax0() == fnv(result)
        assert list(scratch) == expected_tmp and list(y) == expected_y
        assert list(a) == before_a and list(x) == before_x
    lib.workload_prepare()
    assert lib.task_job_atax0() == plan['tasks'][0]['expected_checksum']


@pytest.mark.parametrize('change', ['rank', 'missing_shape', 'vector_shape', 'dtype', 'bounds', 'budget'])
def test_atax_rejects_invalid_inputs(atax_config, change):
    a, x, tmp, y = atax_config['arrays']
    if change == 'rank': a['shape'] = [6]
    if change == 'missing_shape': a.pop('shape'); a['length'] = 6
    if change == 'vector_shape': x['shape'] = [2]
    if change == 'dtype': tmp['element_type'] = 'uint8_t'
    if change == 'bounds': atax_config['tasks'][0]['arrays']['y']['offset_elements'] = 1
    if change == 'budget': atax_config['tasks'][0]['sweeps'] = 1_000_000
    with pytest.raises(ValueError): make_plan(atax_config, 2)


@pytest.mark.parametrize('role', ['tmp', 'y'])
def test_atax_shares_inputs_but_requires_private_written_arrays(atax_config, role):
    second = deepcopy(atax_config['tasks'][0])
    second.update(task_id='atax1', core=1)
    atax_config['tasks'].append(second)
    for original in list(atax_config['arrays'][2:]):
        private = dict(original, array_id=original['array_id']+'other')
        atax_config['arrays'].append(private)
        key = 'tmp' if original['array_id'] == 'tmp0' else 'y'
        second['arrays'][key]['array_id'] = private['array_id']
    assert len(make_plan(atax_config, 2)['tasks']) == 2
    unused = second['arrays'][role]['array_id']
    second['arrays'][role]['array_id'] = atax_config['tasks'][0]['arrays'][role]['array_id']
    atax_config['arrays'] = [a for a in atax_config['arrays'] if a['array_id'] != unused]
    with pytest.raises(ValueError, match='exclusive'): make_plan(atax_config, 2)


@pytest.mark.parametrize('optimization', ['O0', 'O2'])
def test_atax_real_elf_and_ape_with_padded_views(atax_config, tmp_path, optimization):
    from chaser.periodic.analysis import analyze
    config = padded(atax_config)
    config['workload_optimization'] = optimization
    prepared = tmp_path / 'prepared'
    prepare(config, prepared)
    result = analyze(prepared)
    assert result['cases']['atax0']['modeled_accesses'] == 109
    assert result['dataset_eligible'] is False
    manifest = json.loads((prepared / 'manifest.json').read_text())
    for name in ('atax.py', 'atax.c.in'):
        relative = 'chaser/periodic/kernels/'+name
        assert relative in manifest['kernel_input_hashes']
        assert (prepared / 'kernel-inputs' / relative).exists()
    for arch in 'gcp':
        events = json.loads((prepared / f'analysis/{arch}/atax0/events.json').read_text())['events']
        assert sum(e['operation'] == 'store' for e in events) == 34
