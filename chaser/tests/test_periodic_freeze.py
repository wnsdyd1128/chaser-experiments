"""Freeze the preserved input population without changing the old proposal."""

import json

import pytest

from tools.rtems_periodic_pool import initialize
from tools.rtems_smoke import file_hash, write_json


@pytest.fixture(scope='module')
def source_pool(tmp_path_factory):
    path = tmp_path_factory.mktemp('freeze-source') / 'pool'
    initialize(path, version=3)
    return path


def test_freeze_is_replayable_and_preserves_inputs_and_excluded_aliases(tmp_path, source_pool):
    from tools.rtems_periodic_freeze import freeze, verify

    before = file_hash(source_pool / 'manifest.json')
    output = tmp_path / 'frozen'
    report = freeze(source_pool, output)
    assert report == verify(output)
    assert report['workload_counts'] == dict(train=126, validation=41, test=40)
    assert report['family_counts'] == dict(train=5, validation=5, test=5)
    assert report['inputs_frozen'] is report['split_frozen'] is True
    assert report['dataset_ready'] is False
    assert report['plans_validated'] == 621
    assert report['independent_u_runs'] == 21680
    assert report['timing_runs_one_policy'] == 6210
    population = json.loads((output / 'population.json').read_text())
    split = json.loads((output / 'split.json').read_text())
    assert len(population['workloads']) == 207
    assert len(population['excluded_duplicates']) == 93
    for alias in population['excluded_duplicates']:
        assert alias['split_group'] == split['assignments'][alias['duplicate_of']]
    assert file_hash(source_pool / 'manifest.json') == before
    for source in (source_pool / 'configs').iterdir():
        assert source.read_bytes() == (output / 'source' / 'configs' / source.name).read_bytes()
    assert freeze(source_pool, tmp_path / 'repeat') == report
    assert (output / 'split.json').read_bytes() == (tmp_path / 'repeat/split.json').read_bytes()
    with pytest.raises(FileExistsError):
        freeze(source_pool, output)


def test_source_hash_changes_are_rejected_before_freezing(tmp_path, source_pool):
    from tools.rtems_periodic_freeze import freeze
    import shutil

    changed = tmp_path / 'changed'
    shutil.copytree(source_pool, changed)
    path = next((changed / 'configs').iterdir())
    path.write_text('{}')
    with pytest.raises(ValueError):
        freeze(changed, tmp_path / 'frozen')
    assert not (tmp_path / 'frozen').exists()


@pytest.mark.parametrize('target', ['split.json', 'population.json', 'summary.json'])
def test_replay_rejects_inconsistent_content_even_with_updated_file_hash(tmp_path, source_pool, target):
    from tools.rtems_periodic_freeze import freeze, verify

    output = tmp_path / 'frozen'
    freeze(source_pool, output)
    path = output / target
    changed = json.loads(path.read_text())
    if target == 'split.json':
        changed['seed'] += 1
    elif target == 'population.json':
        changed['excluded_duplicates'][0]['split_group'] = 'unknown'
    else:
        changed['dataset_ready'] = True
    write_json(path, changed)
    manifest = json.loads((output / 'manifest.json').read_text())
    manifest['files'][target] = file_hash(path)
    write_json(output / 'manifest.json', manifest)
    with pytest.raises(ValueError):
        verify(output)
