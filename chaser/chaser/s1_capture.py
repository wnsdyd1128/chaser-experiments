"""Bound an external trace by wall time and decoded output bytes, retaining failures."""

import gzip
import json
import os
import selectors
import signal
import subprocess
from time import monotonic


def capture(argv, directory, *, timeout, max_bytes):
    """Stream stderr to gzip and stdout to a file; kill the process group on failure."""
    record = dict(argv=[str(a) for a in argv], timeout_seconds=timeout,
                  max_decoded_bytes=max_bytes, decoded_bytes=0)
    start = monotonic()
    process = None
    try:
        with gzip.open(directory / 'trace.log.gz', 'xb', compresslevel=1) as trace, \
                (directory / 'stdout.txt').open('xb') as stdout, \
                selectors.DefaultSelector() as selector:
            process = subprocess.Popen(record['argv'], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
            selector.register(process.stderr, selectors.EVENT_READ, trace)
            selector.register(process.stdout, selectors.EVENT_READ, stdout)
            while selector.get_map():
                remaining = timeout - (monotonic() - start)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(record['argv'], timeout)
                for key, _ in selector.select(min(remaining, 0.1)):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    room = max_bytes - record['decoded_bytes']
                    key.data.write(data[:room])
                    record['decoded_bytes'] += len(data)
                    if record['decoded_bytes'] > max_bytes:
                        raise ValueError('Decoded trace byte limit exceeded')
            remaining = timeout - (monotonic() - start)
            record['returncode'] = process.wait(timeout=max(0, remaining))
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, record['argv'])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        record['error'] = f'{type(error).__name__}: {error}'
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    finally:
        if process is not None:
            record['returncode'] = process.returncode
            process.stdout.close()
            process.stderr.close()
        record['wall_seconds'] = monotonic() - start
        (directory / 'capture.json').write_text(json.dumps(record, indent=2) + '\n')
    return record
