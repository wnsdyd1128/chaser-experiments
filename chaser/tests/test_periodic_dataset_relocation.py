"""Exercise filesystem movement and interruption handling without real evidence."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def relocation(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'artifacts/periodic/calibration-v2/relocate_dataset.py'
    spec = importlib.util.spec_from_file_location('relocate_dataset', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = tmp_path / 'datasets/periodic-v2'
    provenance = data / 'provenance'
    provenance.mkdir(parents=True)
    source = tmp_path / '.cache/old/snapshot/raw'
    source.mkdir(parents=True)
    (source / 'run.log').write_bytes(b'original evidence\n')
    destination = data / 'characterization/example/prepared/raw'
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'DATA', data)
    monkeypatch.setattr(module, 'PROVENANCE', provenance)
    relative = str(source.relative_to(tmp_path))
    target = str(destination.relative_to(tmp_path))
    expected = module.file_hash(source / 'run.log')
    (provenance / 'files.jsonl').write_text(json.dumps(dict(source=relative + '/run.log',
        destination=target + '/run.log', size=18, sha256=expected)) + '\n')
    plan = dict(units=[dict(source=relative, destination=target)], copies=[],
        anchors=['.cache/old/snapshot'], protected={relative + '/run.log':expected},
        script_hash=module.file_hash(path), inventory_hash=module.file_hash(provenance / 'files.jsonl'),
        bytes=18, metadata=dict(workloads={str(i):dict(split='train' if i < 126 else
            'validation' if i < 167 else 'test') for i in range(207)},
            mappings={str(i):{} for i in range(189)}))
    module.write_json(provenance / 'migration-plan.json', plan)
    return module, plan, source, destination


def test_move_preserves_raw_bytes_and_legacy_directory_identity(relocation):
    module, plan, source, destination = relocation
    anchor = source.parent.resolve()
    module.move(plan)
    assert source.is_symlink() and not Path(source.readlink()).is_absolute()
    assert source.parent.resolve() == anchor
    assert (destination / 'run.log').read_bytes() == b'original evidence\n'
    assert not destination.is_symlink()
    module.move(plan)


def test_resume_repairs_interruption_between_rename_and_link(relocation):
    module, plan, source, destination = relocation
    destination.parent.mkdir(parents=True)
    source.rename(destination)
    module.move(plan)
    assert source.is_symlink() and source.resolve() == destination
    assert (source / 'run.log').read_bytes() == b'original evidence\n'


def test_changed_source_is_rejected_before_movement(relocation):
    module, plan, source, destination = relocation
    (source / 'run.log').write_bytes(b'changed evidence\n')
    with pytest.raises(AssertionError):
        module.move(plan)
    assert source.is_dir() and not source.is_symlink()
    assert not destination.exists()


def test_existing_destination_is_not_overwritten(relocation):
    module, plan, source, destination = relocation
    destination.mkdir(parents=True)
    (destination / 'keep').write_text('preserve')
    with pytest.raises(AssertionError, match='Conflicting destination'):
        module.move(plan)
    assert not source.is_symlink()
    assert (destination / 'keep').read_text() == 'preserve'
