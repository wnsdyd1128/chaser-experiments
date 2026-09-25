"""Losslessly retain full event JSON with verified XZ compression."""

from hashlib import sha256
import lzma
from pathlib import Path


def compress_events(path: Path) -> dict:
    """Write a new XZ file and verify exact restoration; leave source removal to caller.

    Chunked I/O avoids loading another event document. Preset 6 reduces collection
    time relative to 9 extreme while retaining every original byte.
    """
    destination = path.with_suffix(path.suffix + '.xz')
    original, size = sha256(), 0
    with destination.open('xb') as raw:
        with lzma.LZMAFile(raw, 'wb', preset=6) as compressed:
            with path.open('rb') as source:
                while chunk := source.read(1024 * 1024):
                    original.update(chunk)
                    size += len(chunk)
                    compressed.write(chunk)
    restored, restored_size = sha256(), 0
    with lzma.open(destination, 'rb') as source:
        while chunk := source.read(1024 * 1024):
            restored.update(chunk)
            restored_size += len(chunk)
    if restored.digest() != original.digest() or restored_size != size:
        raise ValueError('Compressed event restoration differs from original')
    return dict(codec='xz', preset='6', original_sha256=original.hexdigest(),
                original_bytes=size, compressed_bytes=destination.stat().st_size)
