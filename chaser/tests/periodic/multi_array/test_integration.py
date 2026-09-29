"""Real SPARC/APE typed streams and immutable execution provenance."""

import json
from pathlib import Path
import pytest
from chaser.periodic.build import prepare, read_symbols, check_layout
from chaser.periodic.analysis import analyze
from chaser.periodic.dataset import feature_record, load_batch, to_measurement
from chaser.periodic.measurement import make_plan
from tools.rtems_periodic import run


@pytest.mark.parametrize('optimization', ['O0', 'O2'])
def test_gemm_real_elf_typed_store_stream_and_layout(shaped_config, tmp_path, optimization):
    config = shaped_config
    config['workload_optimization'] = optimization
    config['arrays'][1]['alignment_bytes'] = 4096
    prepared = tmp_path / 'prepared'
    prepare(config, prepared)
    plan = make_plan(config, 2)
    layouts = json.loads((prepared / 'layout.json').read_text())
    assert layouts['g'] == layouts['c'] == layouts['p']
    assert [a['address'] for a in layouts['p']] == [0x1000000, 0x1001000, 0x1001020]
    symbols = read_symbols(prepared / 'build/p.exe')
    assert symbols['data_a0'][1] == 24
    assert symbols['data_c0'][1] == 16
    for replacement in ((0x1000004, 24), (0x1000000, 25)):
        with pytest.raises(ValueError):
            check_layout(dict(symbols, data_a0=replacement), plan['arrays'])
    result = analyze(prepared)
    assert result['cases']['gemm0']['modeled_accesses'] == 60
    assert result['cases']['gemm0']['clp'] == [57/60, 0, 3/60]
    assert result['analysis_compiler'] == 'clang-14-O0'
    assert result['workload_optimization'] == optimization
    assert result['dataset_eligible'] is False
    features = feature_record({}, result, dict(utilization={'gemm0': 0.1},
        characterization_id='test', utilization_source='test', utilization_rule_id='test'))
    assert features['feature_eligible'] is False
    assert 'diagnostic_kernel_requires_dataset_qualification' in features['exclusion_reasons']
    for arch in 'gcp':
        events = json.loads((prepared / f'analysis/{arch}/gemm0/events.json').read_text())['events']
        assert sum(e['operation'] == 'store' for e in events) == 8
        assert all(e['access_size'] == 4 for e in events)


@pytest.mark.parametrize('dtype', ['uint8_t', 'uint32_t'])
def test_shared_paired_and_cyclic_real_analysis(config, tmp_path, dtype):
    config['arrays'] = [dict(array_id='a', element_type=dtype, length=65, alignment_bytes=32, initial_value=3),
                        dict(array_id='b', element_type=dtype, length=65, alignment_bytes=4096, initial_value=5)]
    config['tasks'] = [dict(task_id='pair', pattern='paired-read', arrays={
        'a': dict(array_id='a', offset_elements=1), 'b': dict(array_id='b', offset_elements=1)},
        distinct=3, stride_bytes=32, sweeps=2, core=0, period_ticks=10),
        dict(task_id='cycle', pattern='cyclic', arrays={'input': dict(array_id='a')},
             distinct=3, stride_bytes=32, sweeps=2, core=1, period_ticks=10)]
    # uint8 accesses are indices 1,33,65, so reserve that final element too.
    for a in config['arrays']: a['length'] = 66
    prepared = tmp_path / 'prepared'
    prepare(config, prepared)
    result = analyze(prepared)
    assert result['cases']['pair']['clp'] == [6/12, 0, 6/12]
    assert result['cases']['cycle']['modeled_accesses'] == 6
    assert len(json.loads((prepared / 'layout.json').read_text())['p']) == 2


def test_snapshot_revalidation_and_diagnostic_dataset_guard(config, tmp_path):
    prepared = tmp_path / 'prepared'
    prepare(config, prepared)
    plan = make_plan(config, 2)
    saved = json.loads((Path(__file__).parent / 'fixtures/legacy-raw.json').read_text())
    records = [json.loads(line.removeprefix('PERIODIC ')) for line in saved['raw'].splitlines()]
    records = [r for r in records if r.get('task', 0) == 0]
    records[0]['plan_hash'] = plan['plan_hash']
    for r in records:
        if r['kind'] == 'job': r['checksum'] = plan['tasks'][0]['expected_checksum']
    fake = tmp_path / 'simulator'
    fake.write_text("#!/bin/sh\ncat <<'LOG'\n" + '\n'.join('PERIODIC '+json.dumps(r) for r in records) + '\nLOG\n')
    fake.chmod(0o755)
    output = tmp_path / 'runs'
    rows = run(prepared, output, architecture=2, runs=1, simulator=fake)
    assert rows[0]['execution_status'] == 'ok'
    assert load_batch(prepared, output) == rows
    with pytest.raises(ValueError, match='diagnostic'): to_measurement(plan, rows[0])
    for relative in ('arrays.py', 'kernels/__init__.py', 'kernels/gemm.py', 'kernels/reads.py'):
        path = output / 'implementation/chaser/periodic' / relative
        original = path.read_bytes()
        path.write_bytes(original + b'\n# tampered\n')
        with pytest.raises(ValueError, match='implementation'): load_batch(prepared, output)
        path.write_bytes(original)
    for path in (prepared / 'configuration.json', prepared / 'build/p.exe',
                 prepared / 'p/plan.json', output / '0.log'):
        original = path.read_bytes()
        path.write_bytes(original+b' ')
        with pytest.raises(ValueError): load_batch(prepared, output)
        path.write_bytes(original)

    path = output / 'protocol.json'
    original = path.read_text()
    protocol = json.loads(original)
    del protocol['implementation_hashes']['implementation/chaser/periodic/kernels/gemm.py']
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match='provenance'): load_batch(prepared, output)
    path.write_text(original)

@pytest.mark.parametrize('column_step', [1, 2])
def test_padded_offset_gemm_real_ape_stream(shaped_config, tmp_path, column_step):
    config = shaped_config
    for a, length in zip(config['arrays'], (14, 17, 12)):
        a['length'] = length
    task = config['tasks'][0]
    for array, ld in zip(config['arrays'], (5, 4, 4)):
        array['strides_elements'] = [ld, column_step]
    for role, offset in zip(('A', 'B', 'C'), (2, 3, 1)):
        task['arrays'][role]['offset_elements'] = offset
    prepared = tmp_path / 'padded'
    prepare(config, prepared)
    result = analyze(prepared)
    assert result['cases']['gemm0']['modeled_accesses'] == 60
    if column_step == 1:
        assert result['cases']['gemm0']['clp'] == [55/60, 0, 5/60]
    events = json.loads((prepared / 'analysis/p/gemm0/events.json').read_text())['events']
    symbols = read_symbols(prepared / 'build/p.exe')
    assert [(e['object_id'], e['linked_address']) for e in events[:7]] == [
        ('global::data_'+name, symbols['data_'+name][0]+offset)
        for name, offset in [('a0',8),('b0',12),('a0',8+4*column_step),('b0',28),
                             ('a0',8+8*column_step),('b0',44),('c0',4)]]

