"""Bound raw event generation and asynchronous, verified XZ storage together."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Condition

from chaser.event_storage import compress_events


class EventCompressionQueue:
    """Reserve a file slot before export; free it only after verified raw removal.

    The producer must execute event export through ``export_command`` so the OS
    enforces the per-file bound. Reservations include generating, queued, and
    compressing files. Any failure stops new reservations, preserving evidence
    without letting repeated failures accumulate unbounded raw files.
    """

    def __init__(self, *, workers=4, max_files=16, max_file_bytes=1024**3):
        if min(workers, max_files, max_file_bytes) < 1:
            raise ValueError('Compression limits must be positive')
        self.max_file_bytes = max_file_bytes
        self.max_files = max_files
        self._condition = Condition()
        self._active = 0
        self._failed = None
        self._executor = ThreadPoolExecutor(max_workers=workers,
                                            thread_name_prefix='event-compression')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._executor.shutdown(wait=True)

    def export_command(self, argv: list[str]) -> list[str]:
        """Limit each output file of the exporter, including its raw event JSON."""
        return ['prlimit', '--core=0:0',
                f'--fsize={self.max_file_bytes}:{self.max_file_bytes}',
                '--', *argv]

    def _fail(self, error):
        with self._condition:
            if self._failed is None:
                self._failed = error
            self._condition.notify_all()

    def _release(self):
        with self._condition:
            self._active -= 1
            self._condition.notify_all()

    @contextmanager
    def reserve(self):
        """Block before file creation until capacity exists, or propagate failure."""
        with self._condition:
            self._condition.wait_for(lambda: self._failed is not None
                                     or self._active < self.max_files)
            if self._failed is not None:
                raise RuntimeError(f'Compression pipeline stopped: {self._failed}')
            self._active += 1
        slot = _Reservation(self)
        try:
            yield slot
        except BaseException as error:
            self._fail(error)
            raise
        finally:
            if not slot.submitted:
                self._release()


class _Reservation:
    def __init__(self, queue):
        self.queue = queue
        self.submitted = False

    def submit(self, path: Path):
        if self.submitted:
            raise ValueError('A reservation accepts one event file')
        if path.stat().st_size > self.queue.max_file_bytes:
            raise ValueError('Event file exceeds reserved size limit')

        def archive():
            try:
                result = compress_events(path)
                path.unlink()
                return result
            except BaseException as error:
                self.queue._fail(error)
                raise
            finally:
                self.queue._release()

        future = self.queue._executor.submit(archive)
        self.submitted = True
        return future
