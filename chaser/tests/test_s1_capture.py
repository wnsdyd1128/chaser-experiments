"""A failed or bounded external capture retains evidence and never returns success."""

import gzip
import subprocess
import sys

import pytest

from chaser.s1_capture import capture


def test_capture_preserves_stderr_gzip_and_stdout(tmp_path):
    record = capture([sys.executable, '-c', 'import sys; print("ok"); sys.stderr.write("I 100,1\\n")'],
                     tmp_path, timeout=5, max_bytes=1000)
    assert record['returncode'] == 0
    assert gzip.decompress((tmp_path / 'trace.log.gz').read_bytes()) == b'I 100,1\n'
    assert (tmp_path / 'stdout.txt').read_text() == 'ok\n'


@pytest.mark.parametrize('code,timeout,limit,error', [
    ('import time; time.sleep(10)', 0.1, 1000, subprocess.TimeoutExpired),
    ('import sys; sys.stderr.write("x" * 10000)', 5, 100, ValueError),
    ('import sys; print("x" * 10000)', 5, 100, ValueError),
    ('raise SystemExit(3)', 5, 1000, subprocess.CalledProcessError),
])
def test_capture_failure_is_recorded(tmp_path, code, timeout, limit, error):
    with pytest.raises(error):
        capture([sys.executable, '-c', code], tmp_path, timeout=timeout, max_bytes=limit)
    assert (tmp_path / 'capture.json').is_file()
    assert (tmp_path / 'trace.log.gz').is_file()
    gzip.decompress((tmp_path / 'trace.log.gz').read_bytes())
