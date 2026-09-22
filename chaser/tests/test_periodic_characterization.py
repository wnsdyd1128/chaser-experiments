"""Pre-label characterization preserves fixed membership and measured bounds."""
import pytest
from tools.rtems_periodic_characterize import feature_record


def test_prepare_workers_can_increase_without_changing_simulator_protocol(tmp_path, monkeypatch):
    import json
    import tools.rtems_periodic_characterize as collector
    from tools.rtems_smoke import write_json

    frozen, output = tmp_path / 'frozen', tmp_path / 'output'
    frozen.mkdir()
    write_json(frozen / 'population.json', dict(workloads=[]))
    write_json(frozen / 'split.json', {})
    monkeypatch.setattr(collector, 'verify', lambda _: None)
    collector.collect(frozen, output, phase='prepare', workers=8, timeout=120)
    original = (output / 'protocol.json').read_bytes()
    limits = []
    executor = collector.ThreadPoolExecutor

    def pool(*, max_workers):
        limits.append(max_workers)
        return executor(max_workers=max_workers)

    monkeypatch.setattr(collector, 'ThreadPoolExecutor', pool)
    collector.collect(frozen, output, phase='prepare', workers=8, timeout=120,
                      prepare_workers=16)
    assert limits == [16]
    assert (output / 'protocol.json').read_bytes() == original
    assert json.loads(original)['workers'] == 8
    with pytest.raises(ValueError):
        collector.collect(frozen, output, phase='run', workers=17, timeout=120)
    with pytest.raises(ValueError):
        collector.collect(frozen, output, phase='prepare', workers=8, timeout=120,
                          prepare_workers=17)


def inputs():
    member = dict(workload_id='w', input_signature='sig', split_group='test', family_id='f')
    locality = {'cases': {'b': dict(ca_caas_element=0.2, ca_global_line=0.3,
                                  ca_csrd_l1=0.4, cls={'0.5': 0.5}),
                          'a': dict(ca_caas_element=0.8, ca_global_line=0.7,
                                  ca_csrd_l1=0.6, cls={'0.5': 0.5})}}
    u = dict(utilization={'a': 0.25, 'b': 0.1}, characterization_id='id')
    return member, locality, u


def test_feature_record_keeps_membership_and_has_no_label():
    member, locality, u = inputs()
    row = feature_record(member, locality, u)
    assert row['split_group'] == 'test'
    assert row['input_signature'] == 'sig'
    assert row['within_u_bounds'] is True
    assert row['features']['caas-ca'][-1] == pytest.approx(0.35)
    assert 'label' not in row
    assert row['dataset_stage'] == 'characterized'
    assert 'dataset_ready' not in row


def test_out_of_bounds_keeps_features_and_exclusion_reason():
    member, locality, u = inputs()
    u['utilization']['a'] = 0.251
    row = feature_record(member, locality, u)
    assert row['within_u_bounds'] is False
    assert row['exclusion_reasons'] == ['task_u_exceeds_0.25']
    assert row['split_group'] == 'test'


def test_feature_join_rejects_extra_or_missing_tasks():
    member, locality, u = inputs()
    locality['cases']['extra'] = locality['cases']['a']
    with pytest.raises(ValueError, match='task IDs'):
        feature_record(member, locality, u)


def test_total_u_bound_is_checked_independently():
    member, locality, u = inputs()
    locality['cases'] = {str(i): locality['cases']['a'] for i in range(9)}
    u['utilization'] = {str(i): 0.25 for i in range(9)}
    row = feature_record(member, locality, u)
    assert row['exclusion_reasons'] == ['taskset_u_exceeds_2.0']


def test_undefined_locality_is_preserved_without_inventing_features():
    member, locality, u = inputs()
    locality['cases']['a']['ca_caas_element'] = None
    row = feature_record(member, locality, u)
    assert 'caas-ca' not in row['features']
    assert 'caas-ca' in row['undefined_features']
    assert row['split_group'] == 'test'


@pytest.mark.parametrize('workers', [1, 3])
def test_prepare_resumes_complete_snapshot_and_preserves_incomplete_one(tmp_path, monkeypatch, workers):
    import json
    import tools.rtems_periodic_characterize as collector
    from chaser.periodic import digest
    from tools.rtems_smoke import write_json

    frozen, output = tmp_path / 'frozen', tmp_path / 'output'
    (frozen / 'source/configs').mkdir(parents=True)
    members = []
    for name in ('complete', 'incomplete', 'new'):
        config = dict(workload_id=name)
        write_json(frozen / 'source/configs' / (name + '.json'), config)
        members.append(dict(workload_id=name, configuration_hash=digest(config), split_group='test'))
    write_json(frozen / 'population.json', dict(workloads=members))
    write_json(frozen / 'split.json', {})
    built, analyzed = [], []

    def build(config, path):
        built.append(config['workload_id'])
        path.mkdir(parents=True)
        write_json(path / 'configuration.json', config)
        write_json(path / 'manifest.json', dict(files={}))

    def analysis(path, **kwargs):
        analyzed.append(path.name)
        (path / 'analysis').mkdir()
        write_json(path / 'analysis/locality.json', {})

    def checked(path):
        return json.loads((path / 'analysis/locality.json').read_text())

    for name in ('complete', 'incomplete'):
        path = output / 'prepared' / name
        build(dict(workload_id=name), path)
        analysis(path)
    (output / 'prepared/incomplete/analysis/locality.json').unlink()
    built.clear(); analyzed.clear()
    monkeypatch.setattr(collector, 'verify', lambda _: None)
    monkeypatch.setattr(collector, 'prepare', build)
    monkeypatch.setattr(collector, 'analyze', analysis)
    monkeypatch.setattr(collector, 'checked_locality', checked)
    with pytest.raises(SystemExit):
        collector.collect(frozen, output, phase='prepare', workers=workers, timeout=120)
    assert built == ['new']
    assert analyzed == ['new']
    report = json.loads((output / 'prepare-progress.json').read_text())
    assert {r['workload_id']: r['status'] for r in report['workloads']} == {
        'complete': 'ok', 'incomplete': 'failed', 'new': 'ok'}
    assert all(r['split_group'] == 'test' for r in report['workloads'])
    assert report['processed_workloads'] == 3
    assert report['dataset_stage'] == 'prepare_failed'
    assert 'dataset_ready' not in report


def test_prepare_runs_concurrently_with_worker_limit_and_keeps_failures(tmp_path, monkeypatch):
    import json
    import threading
    import tools.rtems_periodic_characterize as collector
    from chaser.periodic import digest
    from tools.rtems_smoke import write_json

    frozen, output = tmp_path / 'frozen', tmp_path / 'output'
    (frozen / 'source/configs').mkdir(parents=True)
    members = []
    for name in ('a', 'b', 'c', 'd'):
        config = dict(workload_id=name)
        write_json(frozen / 'source/configs' / (name + '.json'), config)
        members.append(dict(workload_id=name, configuration_hash=digest(config),
                            split_group='validation'))
    write_json(frozen / 'population.json', dict(workloads=members))
    write_json(frozen / 'split.json', {})
    barrier, lock = threading.Barrier(2, timeout=5), threading.Lock()
    active, peak = 0, 0

    def build(config, path):
        path.mkdir(parents=True)
        write_json(path / 'configuration.json', config)
        write_json(path / 'manifest.json', dict(files={}))

    def analysis(path, **kwargs):
        nonlocal active, peak
        assert kwargs['compress_events'] is True
        assert kwargs['compression_queue'].max_files == 16
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            barrier.wait()
            with lock:
                active -= 1
            barrier.wait()
            if path.name == 'b':
                raise ValueError('analysis failure')
            (path / 'analysis').mkdir()
            write_json(path / 'analysis/locality.json', {'workload_id': path.name})
        except threading.BrokenBarrierError:
            pytest.fail('Preparation did not execute concurrently')

    monkeypatch.setattr(collector, 'verify', lambda _: None)
    monkeypatch.setattr(collector, 'prepare', build)
    monkeypatch.setattr(collector, 'analyze', analysis)
    monkeypatch.setattr(collector, 'checked_locality',
                        lambda p: json.loads((p / 'analysis/locality.json').read_text()))
    with pytest.raises(SystemExit) as error:
        collector.collect(frozen, output, phase='prepare', workers=2, timeout=120)
    assert error.value.code == 1
    assert peak == 2
    report = json.loads((output / 'prepare-progress.json').read_text())
    assert report['processed_workloads'] == 4
    assert report['successful_workloads'] == 3
    rows = {r['workload_id']: r for r in report['workloads']}
    assert rows['b']['error'] == 'ValueError: analysis failure'
    assert all(r['split_group'] == 'validation' for r in rows.values())
    assert all(rows[n]['status'] == 'ok' for n in ('a', 'c', 'd'))


@pytest.mark.parametrize('phase, statuses, total, expected', [
    ('prepare', [], 2, 'preparing'),
    ('prepare', ['ok'], 2, 'preparing'),
    ('prepare', ['ok', 'ok'], 2, 'prepared'),
    ('prepare', ['ok', 'failed'], 2, 'prepare_failed'),
    ('run', [], 2, 'characterizing'),
    ('run', ['failed'], 2, 'characterizing'),
    ('run', ['ok', 'ok'], 2, 'characterized'),
    ('run', ['ok', 'failed'], 2, 'characterization_failed'),
])
def test_dataset_stage_distinguishes_progress_success_and_failure(phase, statuses, total, expected):
    from tools.rtems_periodic_characterize import _dataset_stage
    assert _dataset_stage(phase, [dict(status=s) for s in statuses], total) == expected


@pytest.mark.parametrize('legacy_ready, change_timeout', [(False, False), (True, False), (False, True)])
def test_legacy_protocol_migration_keeps_measurement_contract(tmp_path, monkeypatch,
                                                          legacy_ready, change_timeout):
    import json
    import tools.rtems_periodic_characterize as collector
    from tools.rtems_smoke import write_json
    frozen, output = tmp_path / 'frozen', tmp_path / 'output'
    frozen.mkdir()
    write_json(frozen / 'population.json', dict(workloads=[]))
    write_json(frozen / 'split.json', {})
    monkeypatch.setattr(collector, 'verify', lambda _: None)
    collector.collect(frozen, output, phase='prepare', workers=8, timeout=120)
    path = output / 'protocol.json'
    original = json.loads(path.read_text())
    legacy = dict(original, dataset_ready=legacy_ready)
    if change_timeout:
        legacy['timeout_seconds'] = 121
    write_json(path, legacy)
    if legacy_ready or change_timeout:
        with pytest.raises(ValueError, match='protocol changed'):
            collector.collect(frozen, output, phase='prepare', workers=8, timeout=120)
        assert json.loads(path.read_text()) == legacy
    else:
        collector.collect(frozen, output, phase='prepare', workers=8, timeout=120)
        assert json.loads(path.read_text()) == original
        assert 'dataset_ready' not in original
        assert json.loads((output / 'prepare-progress.json').read_text())['dataset_stage'] == 'prepared'
