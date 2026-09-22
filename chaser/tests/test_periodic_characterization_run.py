"""Cross-taskset U scheduling preserves the global limit and batch evidence."""
import json
import threading

import pytest

import tools.rtems_periodic_characterize as collector
from chaser.periodic import digest
from tools.rtems_smoke import write_json


@pytest.fixture
def collection(tmp_path, monkeypatch):
    frozen, output = tmp_path / 'frozen', tmp_path / 'output'
    (frozen / 'source/configs').mkdir(parents=True)

    def setup(counts):
        members = []
        for name, count in counts.items():
            config = dict(workload_id=name)
            write_json(frozen / 'source/configs' / (name + '.json'), config)
            snapshot = output / 'prepared' / name
            (snapshot / 'p').mkdir(parents=True)
            write_json(snapshot / 'configuration.json', config)
            write_json(snapshot / 'manifest.json', {})
            (snapshot / 'analysis').mkdir()
            write_json(snapshot / 'analysis/manifest.json', {})
            write_json(snapshot / 'p/plan.json', dict(tasks=list(range(count))))
            members.append(dict(workload_id=name, configuration_hash=digest(config),
                                split_group='test'))
        write_json(frozen / 'population.json', dict(workloads=members))
        write_json(frozen / 'split.json', {})
        return frozen, output

    def characterize(plan, batches):
        assert len(batches) == len(plan['tasks'])
        assert [rows[0]['mode'] for rows in batches] == list(range(1, len(batches) + 1))
        return {}

    monkeypatch.setattr(collector, 'verify', lambda _: None)
    monkeypatch.setattr(collector, 'checked_locality', lambda _: {})
    monkeypatch.setattr(collector, 'characterize', characterize)
    monkeypatch.setattr(collector, 'feature_record', lambda member, *_: dict(
        member, within_u_bounds=True, exclusion_reasons=[], undefined_features={}))
    monkeypatch.setattr(collector, 'load_batch', lambda _, p: json.loads((p / 'rows.json').read_text()))
    return setup


def save_batch(path, mode, count=10):
    path.mkdir(parents=True)
    write_json(path / 'protocol.json', dict(runs=10, timeout_seconds=120,
                                          mode=mode, trace=False, empty=False))
    write_json(path / 'rows.json', [dict(mode=mode) for _ in range(count)])


def test_run_overlaps_distinct_tasksets_and_reuses_completed_batches(collection, monkeypatch):
    frozen, output = collection({'a': 1, 'b': 1})
    barrier = threading.Barrier(2, timeout=5)
    started = []

    def run(snapshot, directory, **kwargs):
        started.append(snapshot.name)
        barrier.wait()
        save_batch(directory, kwargs['mode'])

    monkeypatch.setattr(collector, 'run', run)
    collector.collect(frozen, output, phase='run', workers=2, timeout=120)
    assert sorted(started) == ['a', 'b']
    before = {p: p.read_bytes() for p in (output / 'runs').glob('*/u*/*')}
    monkeypatch.setattr(collector, 'run', lambda *a, **k: pytest.fail('Complete batch reran'))
    collector.collect(frozen, output, phase='run', workers=2, timeout=120)
    assert all(p.read_bytes() == contents for p, contents in before.items())
    progress = json.loads((output / 'run-progress.json').read_text())
    assert progress['dataset_stage'] == 'characterized'
    assert progress['successful_workloads'] == 2


def test_run_caps_simulators_globally_and_preserves_task_order(collection, monkeypatch):
    frozen, output = collection({'a': 3, 'b': 3, 'c': 2})
    barrier = threading.Barrier(2, timeout=5)
    lock = threading.Lock()
    active = peak = 0

    def run(snapshot, directory, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        barrier.wait()
        save_batch(directory, kwargs['mode'])
        with lock:
            active -= 1
        barrier.wait()

    monkeypatch.setattr(collector, 'run', run)
    collector.collect(frozen, output, phase='run', workers=2, timeout=120)
    assert peak == 2
    assert json.loads((output / 'run-progress.json').read_text())['successful_workloads'] == 3


def test_run_preserves_incomplete_batch_and_finishes_other_work(collection, monkeypatch):
    frozen, output = collection({'a': 2, 'b': 1})
    incomplete = output / 'runs/a/u0'
    save_batch(incomplete, 1, count=3)
    original = {p: p.read_bytes() for p in incomplete.iterdir()}
    started = []

    def run(snapshot, directory, **kwargs):
        started.append((snapshot.name, kwargs['mode']))
        save_batch(directory, kwargs['mode'])

    monkeypatch.setattr(collector, 'run', run)
    with pytest.raises(SystemExit):
        collector.collect(frozen, output, phase='run', workers=2, timeout=120)
    assert sorted(started) == [('a', 2), ('b', 1)]
    assert all(p.read_bytes() == contents for p, contents in original.items())
    progress = json.loads((output / 'run-progress.json').read_text())
    assert progress['dataset_stage'] == 'characterization_failed'
    assert {r['workload_id']: r['status'] for r in progress['workloads']} == {
        'a': 'failed', 'b': 'ok'}
    assert not (output / 'runs/a/features.json').exists()


def test_interrupt_drains_only_admitted_tasksets(collection, monkeypatch):
    frozen, output = collection({'a': 2, 'b': 2, 'c': 2, 'd': 2})
    started = []
    original_wait = collector.wait

    def interrupted_wait(futures, **kwargs):
        if threading.current_thread() is threading.main_thread():
            raise KeyboardInterrupt
        return original_wait(futures, **kwargs)

    def run(snapshot, directory, **kwargs):
        save_batch(directory, kwargs['mode'])
        started.append((snapshot.name, kwargs['mode']))

    monkeypatch.setattr(collector, 'run', run)
    monkeypatch.setattr(collector, 'wait', interrupted_wait)
    with pytest.raises(KeyboardInterrupt):
        collector.collect(frozen, output, phase='run', workers=2, timeout=120)
    assert sorted(started) == [('a', 1), ('a', 2), ('b', 1), ('b', 2)]
    assert len(list((output / 'runs').glob('*/u*/rows.json'))) == 4

