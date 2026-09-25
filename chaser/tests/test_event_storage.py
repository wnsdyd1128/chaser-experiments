"""Compressed event evidence must restore the original bytes before removal."""
import lzma
from hashlib import sha256

import pytest

from chaser.periodic.event_storage import compress_events


def test_compression_preserves_exact_bytes_and_records_original_identity(tmp_path):
    path = tmp_path / 'events.json'
    data = b'{"events": [1, 2, 3]}\n' * 100
    path.write_bytes(data)
    record = compress_events(path)
    assert lzma.decompress(path.with_suffix('.json.xz').read_bytes()) == data
    assert path.read_bytes() == data
    assert record['original_sha256'] == sha256(data).hexdigest()
    assert record['original_bytes'] == len(data)
    assert record['preset'] == '6'
    assert path.with_suffix('.json.xz').read_bytes() == lzma.compress(data, preset=6)


def test_existing_compressed_evidence_is_not_overwritten(tmp_path):
    path = tmp_path / 'events.json'
    path.write_bytes(b'original')
    path.with_suffix('.json.xz').write_bytes(b'preserved')
    with pytest.raises(FileExistsError):
        compress_events(path)
    assert path.read_bytes() == b'original'
    assert path.with_suffix('.json.xz').read_bytes() == b'preserved'


def test_failed_restoration_keeps_original_evidence(tmp_path, monkeypatch):
    from io import BytesIO
    import chaser.periodic.event_storage as storage

    path = tmp_path / 'events.json'
    path.write_bytes(b'original evidence')
    monkeypatch.setattr(storage.lzma, 'open', lambda *args: BytesIO(b'corrupt'))
    with pytest.raises(ValueError, match='restoration differs'):
        compress_events(path)
    assert path.read_bytes() == b'original evidence'
