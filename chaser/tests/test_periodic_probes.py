"""Development coverage is distinct from training data and run repetitions."""

from copy import deepcopy
import sys

import pytest

from chaser.periodic import make_plan
from tools.rtems_periodic_probes import configurations, boundary_configurations, initialize, _profile
from tools.rtems_periodic_probes import build_suite, execute_suite
from tools.rtems_smoke import write_json, file_hash


def test_initialization_preserves_all_inputs_and_refuses_existing_output(tmp_path):
    root = tmp_path / 'suite'
    initialize(root)
    assert len(list((root / 'configs').glob('*.json'))) == 19
    assert (root / 'suite.json').is_file()
    with pytest.raises(FileExistsError):
        initialize(root)


def test_eleven_probes_cover_layout_capacity_and_region_order():
    configs = configurations()
    assert len(configs) == 11
    assert len({c['workload_id'] for c in configs}) == 11
    targets = [c['tasks'][0] for c in configs]
    assert [(t['distinct'], t['stride']) for t in targets[:9]] == [
        (64, 1), (64, 32), (64, 4096),
        (511, 32), (512, 32), (513, 32),
        (65535, 32), (65536, 32), (65537, 32)]
    assert [(t['pattern'], t['hot_repeats'], t['cold_repeats'])
            for t in targets[9:]] == [('hot-cold', 4, 1), ('phase', 4, 4)]
    for config in configs:
        assert config['eligible_for_training'] is False
        assert config['test_eligible'] is False
        assert len(config['tasks']) == 2
        companion = config['tasks'][1]
        assert (companion['distinct'], companion['stride']) == (64, 32)
        for architecture in range(3):
            plan = make_plan(config, architecture)
            assert all(t['sweeps'] >= 2 and t['job_count'] == 2 for t in plan['tasks'])
    assert sum(10 * (3 + len(c['tasks'])) for c in configs) == 550


def test_boundary_suite_reaches_task_record_and_aligned_data_limits():
    configs = {c['workload_id']: c for c in boundary_configurations()}
    for n in (4, 8, 12, 16):
        assert len(configs[f'tasks-{n:02d}']['tasks']) == n
    balanced = make_plan(configs['jobs-balanced'], 2)
    skewed = make_plan(configs['jobs-skewed'], 2)
    for plan in (balanced, skewed):
        assert sum(t['job_count'] for t in plan['tasks']) == 4096
    assert 16 * max(t['job_count'] for t in balanced['tasks']) == 4096
    assert 16 * max(t['job_count'] for t in skewed['tasks']) == 65296
    data = make_plan(configs['data-limit'], 2)
    assert sum((t['data_size'] + 4095) // 4096 * 4096 for t in data['tasks']) == 16 * 1024**2


@pytest.mark.parametrize('kind,reason', [('tasks', '16 tasks'), ('jobs', '4096'),
                                       ('data', '16 MiB')])
def test_next_boundary_input_is_rejected(kind, reason):
    configs = {c['workload_id']: c for c in boundary_configurations()}
    config = deepcopy(configs[{'tasks': 'tasks-16', 'jobs': 'jobs-skewed',
                              'data': 'data-limit'}[kind]])
    if kind == 'tasks':
        config['tasks'].append(dict(config['tasks'][0], task_id='extra'))
    elif kind == 'jobs':
        config['horizon_ticks'] += 1
        for task in config['tasks'][1:]:
            task['period_ticks'] = config['horizon_ticks']
    else:
        config['tasks'][0]['distinct'] += 1
    for architecture in range(3):
        with pytest.raises(ValueError, match=reason):
            make_plan(config, architecture)


def test_padding_overflow_is_rejected_even_with_sixteen_mib_of_array_bytes():
    config = next(c for c in boundary_configurations() if c['workload_id'] == 'data-limit')
    config['tasks'][0]['distinct'] += 1
    config['tasks'][1]['distinct'] -= 1
    assert sum(t['distinct'] * t['stride'] for t in config['tasks']) == 16 * 1024**2
    with pytest.raises(ValueError, match='16 MiB'):
        make_plan(config, 2)


def test_profile_keeps_failed_command_output_and_resource_cost(tmp_path):
    output = tmp_path / 'failed'
    result = _profile([sys.executable, '-c', 'print("partial evidence"); raise SystemExit(7)'], output)
    assert result['returncode'] == 7
    assert result['wall_seconds'] > 0
    assert result['peak_rss_kib'] > 0
    assert (output / 'command.log').read_text() == 'partial evidence\n'
    assert (output / 'resources.json').is_file()
    with pytest.raises(FileExistsError):
        _profile([sys.executable, '-c', 'pass'], output)


def test_build_rejects_config_changed_after_suite_initialization(tmp_path, monkeypatch):
    root = tmp_path / 'suite'
    initialize(root)
    config = configurations()[0]
    changed = deepcopy(config)
    changed['tasks'][0]['sweeps'] += 1
    write_json(root / 'configs' / (config['workload_id'] + '.json'), changed)
    monkeypatch.setattr('tools.rtems_periodic_probes._profile',
                        lambda *a: pytest.fail('must reject before starting build'))
    with pytest.raises(ValueError, match='configuration'):
        build_suite(root, [config], analysis=True)


def test_repeat_rejects_analysis_from_another_snapshot(tmp_path):
    root = tmp_path / 'suite'
    initialize(root)
    config = configurations()[0]
    snapshot = root / 'snapshots' / config['workload_id']
    analysis = snapshot / 'analysis'
    analysis.mkdir(parents=True)
    write_json(snapshot / 'configuration.json', config)
    write_json(snapshot / 'manifest.json', dict(files={
        'configuration.json': file_hash(snapshot / 'configuration.json')}, tools={}))
    write_json(analysis / 'locality.json', dict(manifest_hash='other-snapshot'))
    write_json(analysis / 'manifest.json', dict(files={
        'locality.json': file_hash(analysis / 'locality.json')}, tools={}))
    with pytest.raises(ValueError, match='Analysis/execution'):
        execute_suite(root, [config], stage='repeat', workers=1, timeout=1)
    assert not (root / 'runs/repeat').exists()
