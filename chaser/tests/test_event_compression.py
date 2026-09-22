"""A reservation bounds raw files before generation, not just queued requests."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from chaser.event_compression import EventCompressionQueue


def test_reservation_waits_until_verified_compression_removes_raw(tmp_path, monkeypatch):
    import chaser.event_compression as module
    entered, finish, waiting, acquired = (threading.Event() for _ in range(4))
    raw = tmp_path / 'events.json'
    raw.write_bytes(b'evidence')

    def compress(path):
        entered.set()
        assert finish.wait(5)
        assert path.exists()
        return {'verified': True}

    monkeypatch.setattr(module, 'compress_events', compress)
    with EventCompressionQueue(workers=1, max_files=1) as queue:
        with queue.reserve() as slot:
            future = slot.submit(raw)
            assert entered.wait(5)

            def next_file():
                waiting.set()
                with queue.reserve():
                    acquired.set()
                    assert not raw.exists()

            with ThreadPoolExecutor(max_workers=1) as executor:
                other = executor.submit(next_file)
                assert waiting.wait(5)
                assert not acquired.wait(0.05)
                finish.set()
                assert future.result(timeout=5) == {'verified': True}
                other.result(timeout=5)
    assert acquired.is_set()


def test_failed_compression_preserves_raw_and_wakes_blocked_producer(tmp_path, monkeypatch):
    import chaser.event_compression as module
    entered, finish, waiting = (threading.Event() for _ in range(3))
    raw = tmp_path / 'events.json'
    raw.write_bytes(b'evidence')

    def compress(path):
        entered.set()
        assert finish.wait(5)
        raise ValueError('restore mismatch')

    monkeypatch.setattr(module, 'compress_events', compress)
    with EventCompressionQueue(workers=1, max_files=1) as queue:
        with queue.reserve() as slot:
            future = slot.submit(raw)
            assert entered.wait(5)

            def next_file():
                waiting.set()
                with queue.reserve():
                    pytest.fail('A failed pipeline must not admit another file')

            with ThreadPoolExecutor(max_workers=1) as executor:
                other = executor.submit(next_file)
                assert waiting.wait(5)
                finish.set()
                with pytest.raises(ValueError, match='restore mismatch'):
                    future.result(timeout=5)
                with pytest.raises(RuntimeError, match='pipeline stopped'):
                    other.result(timeout=5)
    assert raw.read_bytes() == b'evidence'


def test_generation_failure_stops_admission_and_preserves_partial_raw(tmp_path):
    raw = tmp_path / 'events.json'
    with EventCompressionQueue(workers=1, max_files=1) as queue:
        with pytest.raises(ValueError, match='invalid stream'):
            with queue.reserve():
                raw.write_bytes(b'partial')
                raise ValueError('invalid stream')
        with pytest.raises(RuntimeError, match='pipeline stopped'):
            with queue.reserve():
                pytest.fail('No new event should be generated')
    assert raw.read_bytes() == b'partial'


def test_export_size_limit_is_enforced_before_compression(tmp_path):
    import subprocess
    import sys
    raw = tmp_path / 'events.json'
    with EventCompressionQueue(workers=1, max_files=1, max_file_bytes=1024) as queue:
        with pytest.raises(subprocess.CalledProcessError):
            with queue.reserve():
                subprocess.run(queue.export_command([
                    sys.executable, '-c',
                    'import sys\nwith open(sys.argv[1], "wb") as f:\n f.write(b"x" * 2048)',
                    str(raw)
                ]), check=True, capture_output=True)
        assert raw.stat().st_size == 1024
        with pytest.raises(RuntimeError, match='pipeline stopped'):
            with queue.reserve():
                pytest.fail('An oversized export must stop new generation')
