from copy import deepcopy
import json
from pathlib import Path
import pytest
from chaser.periodic.measurement import make_plan, parse_log
from chaser.periodic.build import workload_source


def test_legacy_plans_and_source_remain_byte_identical():
    rows = json.loads((Path(__file__).parent / 'fixtures/legacy.json').read_text())
    for row in rows:
        config = row['configuration']
        assert [make_plan(config, a) for a in range(3)] == row['plans']
        assert workload_source(row['plans'][0]['tasks'], config['array_alignment_bytes']) == row['source']


def test_gemm_plan_counts_and_identity(config):
    original = deepcopy(config)
    plan = make_plan(config, 2)
    assert config == original
    assert plan['input_schema_version'] == 2
    task = plan['tasks'][0]
    assert (task['source_loads'], task['source_stores'], task['source_accesses']) == (52, 8, 60)
    h = 2166136261
    for v in [6, 6, 6, 6]:
        h = ((h ^ v) * 16777619) % 2**32
    assert task['expected_checksum'] == h
    config['workload_optimization'] = 'O2'
    assert make_plan(config, 2)['plan_hash'] != plan['plan_hash']


@pytest.mark.parametrize('key,value', [('schema_version', 3), ('schema_version', True),
    ('schema_version', 2.0), ('array_alignment_bytes', 32), ('unknown', 1)])
def test_unknown_schema_or_top_level_fields_rejected(config, key, value):
    config[key] = value
    with pytest.raises(ValueError):
        make_plan(config, 2)


@pytest.mark.parametrize('key,value', [('length', True), ('length', 0), ('length', 2**32),
    ('element_type', 'float32'), ('initial_value', -1), ('initial_value', 2**32),
    ('alignment_bytes', 64), ('unknown', 1), ('array_id', 'bad-id')])
def test_invalid_array_rejected(config, key, value):
    config['arrays'][0][key] = value
    with pytest.raises(ValueError):
        make_plan(config, 2)


@pytest.mark.parametrize('change', ['duplicate', 'unused', 'missing', 'alias', 'bounds', 'stride', 'width'])
def test_invalid_binding_or_kernel_rejected(config, change):
    if change == 'duplicate': config['arrays'].append(deepcopy(config['arrays'][0]))
    elif change == 'unused': config['arrays'].append(dict(config['arrays'][0], array_id='unused'))
    elif change == 'missing': config['tasks'][0]['arrays']['A']['array_id'] = 'missing'
    elif change == 'alias': config['tasks'][0]['arrays']['B']['array_id'] = 'a0'
    elif change == 'bounds': config['tasks'][0]['arrays']['A']['offset_elements'] = 1
    else: config['tasks'][0][change] = 1
    with pytest.raises(ValueError): make_plan(config, 2)


def test_no_schema_cannot_silently_ignore_arrays(config):
    del config['schema_version']
    with pytest.raises(ValueError): make_plan(config, 2)


def test_read_sharing_allowed_but_output_sharing_rejected(config):
    other = deepcopy(config['tasks'][0])
    other['task_id'] = 'other'
    config['tasks'].append(other)
    with pytest.raises(ValueError): make_plan(config, 2)
    config['arrays'].append(dict(config['arrays'][2], array_id='c1'))
    other['arrays']['C']['array_id'] = 'c1'
    assert len(make_plan(config, 2)['arrays']) == 4


@pytest.mark.parametrize('pattern,dtype', [('cyclic', 'uint8_t'), ('cyclic', 'uint32_t'),
                                          ('paired-read', 'uint8_t'), ('paired-read', 'uint32_t')])
def test_read_bounds_and_footprint(config, pattern, dtype):
    size = 1 if dtype == 'uint8_t' else 4
    count = 1 if pattern == 'cyclic' else 2
    config['arrays'] = [dict(array_id=f'x{i}', element_type=dtype, length=18,
                             alignment_bytes=32, initial_value=i+2) for i in range(count)]
    roles = ('input',) if count == 1 else ('a', 'b')
    config['tasks'] = [dict(task_id='reader', pattern=pattern, arrays={
        role: dict(array_id=f'x{i}', offset_elements=1) for i, role in enumerate(roles)},
        distinct=3, stride_bytes=8*size, sweeps=2, core=0, period_ticks=10)]
    task = make_plan(config, 2)['tasks'][0]
    assert task['allocation_bytes'] == count*18*size
    assert task['unique_accessed_bytes'] == count*3*size
    assert task['unique_cache_lines'] == count*(1 if size == 1 else 3)
    config['arrays'][0]['length'] = 17
    with pytest.raises(ValueError): make_plan(config, 2)


def test_padding_is_included_in_allocation_budget(config):
    config['arrays'][0].update(element_type='uint8_t', length=16*1024**2-64)
    config['arrays'][1].update(element_type='uint8_t', length=1, alignment_bytes=4096)
    with pytest.raises(ValueError, match='16 MiB'): make_plan(config, 2)


def test_large_gemm_is_rejected_before_checksum_enumeration(config):
    for array in config['arrays']: array['length'] = 1024*1024
    config['tasks'][0].update(m=1024, n=1024, k=1024, lda=1024, ldb=1024, ldc=1024)
    with pytest.raises(ValueError, match='source accesses'): make_plan(config, 2)


def test_stored_legacy_plan_and_raw_reparse_without_regeneration():
    saved = json.loads((Path(__file__).parent / 'fixtures/legacy-raw.json').read_text())
    assert parse_log(saved['raw'], saved['plan']) == saved['parsed']


@pytest.mark.parametrize('target,key,value', [
    ('top','tasks',None), ('task','task_id',None), ('task','arrays',[]),
    ('task','m',True), ('task','n',1.5), ('task','k','3'), ('task','ldc',1),
    ('task','stride_bytes',4), ('task','distinct',2), ('task','width',2)])
def test_malformed_or_ignored_fields_raise_value_error(config, target, key, value):
    (config if target == 'top' else config['tasks'][0])[key] = value
    with pytest.raises(ValueError): make_plan(config, 2)


def test_identity_covers_order_initialization_offsets_and_key_canonicalization(config):
    baseline = make_plan(config, 2)['plan_hash']
    assert make_plan(json.loads(json.dumps(config, sort_keys=True)), 2)['plan_hash'] == baseline
    for changed in (dict(config, arrays=list(reversed(config['arrays']))),
                    dict(config, workload_optimization='O2')):
        assert make_plan(changed, 2)['plan_hash'] != baseline
    changed = deepcopy(config)
    changed['arrays'][0]['initial_value'] = 42
    assert make_plan(changed, 2)['plan_hash'] != baseline
