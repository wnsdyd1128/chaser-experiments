import hashlib
import json

import pytest

from tools import freeze_baseline


def test_snapshot_is_byte_stable_and_refuses_overwrite(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    freeze_baseline.snapshot(first)
    freeze_baseline.snapshot(second)
    assert (first / 'manifest.json').read_bytes() == (second / 'manifest.json').read_bytes()
    manifest = json.loads((first / 'manifest.json').read_bytes())
    for name, expected in manifest['files'].items():
        data = (first / name).read_bytes()
        assert data == (second / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected
    with pytest.raises(FileExistsError):
        freeze_baseline.snapshot(first)


def test_snapshot_rejects_wrong_case_log(tmp_path, monkeypatch):
    (tmp_path / 'exports').mkdir()
    element = freeze_baseline.ROOT / 'exports/element.rdh.json'
    (tmp_path / 'exports/element.rdh.json').write_bytes(element.read_bytes())
    logs = tmp_path / 'rtems/baseline/build'
    logs.mkdir(parents=True)
    (logs / 'laysim-packed.log').write_text(
        'RESULT,case=conflict,elapsed_ns=1\nCHASER PASS\n[ RTEMS shutdown ]\n')
    monkeypatch.setattr(freeze_baseline, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='Invalid standalone execution log: packed'):
        freeze_baseline.snapshot(tmp_path / 'output')
    assert not (tmp_path / 'output').exists()
