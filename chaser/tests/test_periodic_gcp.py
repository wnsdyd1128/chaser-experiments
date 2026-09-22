"""G/C/P-only orchestration tests never launch the simulator."""
import json
import threading

import pytest

from tools import rtems_periodic_gcp as collector
from tools.rtems_smoke import file_hash, write_json


@pytest.fixture
def snapshots(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, 'load_batch',
                        lambda _, p: json.loads((p / 'rows.json').read_text()))
    paths = []
    for name in 'abcdefghijk':
        path = tmp_path / 'prepared' / name
        files = {}
        for architecture, letter in enumerate(('g', 'c', 'p')):
            (path / letter).mkdir(parents=True)
            plan = path / letter / 'plan.json'
            write_json(plan, dict(workload_id=name, architecture=architecture,
                                  policy_id='frozen-policy', plan_hash=name + letter))
            files[str(plan.relative_to(path))] = file_hash(plan)
        write_json(path / 'manifest.json', dict(files=files))
        paths.append(path)
    return paths


def fake_run(snapshot, directory, **options):
    assert options == dict(architecture=options['architecture'], mode=0,
                          runs=10, timeout=600, trace=False, empty=False)
    directory.mkdir(parents=True)
    write_json(directory / 'protocol.json', dict(runs=10, timeout_seconds=600,
                                               mode=0, trace=False, empty=False))
    a = options['architecture']
    rows = [dict(architecture=a, mode=0, trace=False, empty=False,
                 execution_status='ok', run_id=str(i)) for i in range(10)]
    write_json(directory / 'rows.json', rows)
    return rows


@pytest.mark.parametrize('workers', [16, 32])
def test_gcp_shares_slots_and_never_runs_independent_u(snapshots, tmp_path, monkeypatch, workers):
    barrier = threading.Barrier(workers, timeout=10)
    lock = threading.Lock()
    active = peak = calls = 0

    def run(snapshot, directory, **options):
        nonlocal active, peak, calls
        with lock:
            active += 1
            calls += 1
            index = calls
            peak = max(peak, active)
        if index <= workers:
            barrier.wait()
        result = fake_run(snapshot, directory, **options)
        with lock:
            active -= 1
        return result

    monkeypatch.setattr(collector, 'run', run)
    output = tmp_path / 'runs'
    collector.collect(snapshots, output, workers=workers, timeout=600)
    assert calls == 3 * len(snapshots) and peak == workers
    assert {p.name for p in (output / 'runs').glob('*/*')} == {'g', 'c', 'p'}
    report = json.loads((output / 'run-progress.json').read_text())
    assert report['successful_batches'] == report['planned_batches'] == 3 * len(snapshots)
    assert report['dataset_stage'] == 'gcp_collected'
    assert 'label' not in report


def test_resume_revalidates_and_never_overwrites_completed_batches(snapshots, tmp_path, monkeypatch):
    monkeypatch.setattr(collector, 'run', fake_run)
    output = tmp_path / 'runs'
    collector.collect(snapshots[:1], output, workers=16, timeout=600)
    before = {p: p.read_bytes() for p in (output / 'runs').rglob('*') if p.is_file()}
    monkeypatch.setattr(collector, 'run', lambda *a, **k: pytest.fail('batch reran'))
    collector.collect(snapshots[:1], output, workers=16, timeout=600)
    assert all(p.read_bytes() == data for p, data in before.items())
    with pytest.raises(ValueError, match='protocol'):
        collector.collect(snapshots[:1], output, workers=8, timeout=600)


@pytest.mark.parametrize('damage', ['partial', 'failed', 'wrong_architecture', 'diagnostic'])
def test_bad_existing_batch_is_preserved_and_other_batches_finish(
        snapshots, tmp_path, monkeypatch, damage):
    monkeypatch.setattr(collector, 'run', fake_run)
    output = tmp_path / 'runs'
    collector.collect(snapshots[:1], output, workers=16, timeout=600)
    path = output / 'runs/a/g/rows.json'
    rows = json.loads(path.read_text())
    if damage == 'partial':
        rows.pop()
    elif damage == 'failed':
        rows[0]['execution_status'] = 'failed'
    elif damage == 'wrong_architecture':
        rows[0]['architecture'] = 2
    else:
        rows[0]['mode'] = 1
    write_json(path, rows)
    before = path.read_bytes()
    monkeypatch.setattr(collector, 'run', lambda *a, **k: pytest.fail('batch reran'))
    with pytest.raises(SystemExit):
        collector.collect(snapshots[:1], output, workers=16, timeout=600)
    assert path.read_bytes() == before
    report = json.loads((output / 'run-progress.json').read_text())
    assert report['successful_batches'] == 2
    assert report['processed_batches'] == 3
    assert report['dataset_stage'] == 'gcp_collection_failed'


def test_rejects_duplicate_snapshots_and_changed_inputs_before_execution(snapshots, tmp_path, monkeypatch):
    monkeypatch.setattr(collector, 'run', lambda *a, **k: pytest.fail('unexpected run'))
    with pytest.raises(ValueError, match='Duplicate'):
        collector.collect([snapshots[0], snapshots[0]], tmp_path / 'duplicate', workers=16, timeout=600)
    (snapshots[0] / 'g/plan.json').write_text('{}')
    with pytest.raises(ValueError, match='changed'):
        collector.collect(snapshots, tmp_path / 'changed', workers=16, timeout=600)


@pytest.mark.parametrize('workers,timeout', [
    (0, 600), (33, 600), (True, 600), (1.5, 600), (16, 0), (16, float('inf'))])
def test_invalid_settings_do_not_create_output(snapshots, tmp_path, workers, timeout):
    output = tmp_path / 'invalid'
    with pytest.raises(ValueError):
        collector.collect(snapshots, output, workers=workers, timeout=timeout)
    assert not output.exists()


def test_interrupt_drains_only_admitted_batches(snapshots, tmp_path, monkeypatch):
    calls = []
    original_wait = collector.wait

    def interrupt(futures, **kwargs):
        if threading.current_thread() is threading.main_thread():
            raise KeyboardInterrupt
        return original_wait(futures, **kwargs)

    def run(snapshot, directory, **options):
        calls.append((snapshot.name, options['architecture']))
        return fake_run(snapshot, directory, **options)

    monkeypatch.setattr(collector, 'run', run)
    monkeypatch.setattr(collector, 'wait', interrupt)
    output = tmp_path / 'runs'
    with pytest.raises(KeyboardInterrupt):
        collector.collect(snapshots, output, workers=2, timeout=600)
    assert sorted(calls) == [('a', 0), ('a', 1)]
    monkeypatch.setattr(collector, 'wait', original_wait)
    collector.collect(snapshots, output, workers=2, timeout=600)
    assert len(calls) == len(set(calls)) == 3 * len(snapshots)


def test_existing_batch_protocol_mismatch_is_not_reused(snapshots, tmp_path, monkeypatch):
    monkeypatch.setattr(collector, 'run', fake_run)
    output = tmp_path / 'runs'
    collector.collect(snapshots[:1], output, workers=16, timeout=600)
    path = output / 'runs/a/g/protocol.json'
    protocol = json.loads(path.read_text())
    protocol['timeout_seconds'] = 120
    write_json(path, protocol)
    monkeypatch.setattr(collector, 'run', lambda *a, **k: pytest.fail('batch reran'))
    with pytest.raises(SystemExit):
        collector.collect(snapshots[:1], output, workers=16, timeout=600)
    report = json.loads((output / 'run-progress.json').read_text())
    assert report['successful_batches'] == 2
    assert json.loads(path.read_text()) == protocol


def test_cli_defaults_to_sixteen_workers_and_thirty_minute_timeout(tmp_path, monkeypatch):
    import sys
    calls = []
    monkeypatch.setattr(collector, 'collect', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, 'argv', ['rtems_periodic_gcp', 'snapshot', '--output', str(tmp_path)])
    collector.main()
    assert calls == [(([collector.Path('snapshot')], tmp_path), dict(workers=16, timeout=1800))]


def test_failed_batch_does_not_prevent_new_architecture_batches(snapshots, tmp_path, monkeypatch):
    calls = []

    def run(snapshot, directory, **options):
        calls.append(options['architecture'])
        rows = fake_run(snapshot, directory, **options)
        if options['architecture'] == 0:
            rows[0]['execution_status'] = 'failed'
            write_json(directory / 'rows.json', rows)
        return rows

    monkeypatch.setattr(collector, 'run', run)
    output = tmp_path / 'runs'
    with pytest.raises(SystemExit):
        collector.collect(snapshots[:1], output, workers=1, timeout=600)
    assert calls == [0, 1, 2]
    assert json.loads((output / 'run-progress.json').read_text())['successful_batches'] == 2


def test_mixed_policy_snapshots_are_rejected_before_execution(snapshots, tmp_path, monkeypatch):
    path = snapshots[1] / 'g/plan.json'
    plan = json.loads(path.read_text())
    plan['policy_id'] = 'another-policy'
    write_json(path, plan)
    manifest_path = snapshots[1] / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files']['g/plan.json'] = file_hash(path)
    write_json(manifest_path, manifest)
    monkeypatch.setattr(collector, 'run', lambda *a, **k: pytest.fail('unexpected run'))
    output = tmp_path / 'runs'
    with pytest.raises(ValueError, match='policy'):
        collector.collect(snapshots, output, workers=16, timeout=600)
    assert not output.exists()


def test_default_timeout_is_forwarded_to_runner_and_persisted(snapshots, tmp_path, monkeypatch):
    def run(snapshot, directory, **options):
        assert options['timeout'] == 1800
        fake_run(snapshot, directory, **dict(options, timeout=600))
        path = directory / 'protocol.json'
        protocol = json.loads(path.read_text())
        protocol['timeout_seconds'] = 1800
        write_json(path, protocol)

    monkeypatch.setattr(collector, 'run', run)
    output = tmp_path / 'runs'
    collector.collect(snapshots[:1], output)
    protocol = json.loads((output / 'protocol.json').read_text())
    assert protocol['timeout_seconds'] == 1800
    assert protocol['workers'] == 16
    assert json.loads((output / 'run-progress.json').read_text())['successful_batches'] == 3
