"""Expanded source families preserve excluded duplicates and old pool behavior."""

import json
import tarfile

from tools.rtems_periodic_pool import ROOT, initialize
from tools.rtems_periodic_pool_audit import input_signature


def test_v3_contains_five_source_families_without_duplicate_inputs():
    from tools.rtems_periodic_pool_v3 import candidate_pool

    pool = candidate_pool()
    rows = pool['candidates']
    assert len({r['recipe_id'] for r in rows}) == 5
    signatures = [input_signature(r['configuration']) for r in rows]
    assert len(set(signatures)) == len(signatures)
    assert len(rows)+len(pool['duplicate_candidates']) == 300
    originals = {r['configuration']['workload_id']: r for r in rows}
    for duplicate in pool['duplicate_candidates']:
        original = originals[duplicate['duplicate_of']]
        assert input_signature(duplicate['configuration']) == input_signature(original['configuration'])
        assert duplicate['exclusion_reason'] == 'duplicate_generator_input'
    assert pool['dataset_ready'] is pool['split_frozen'] is False
    assert pool['design']['excluded_pattern_sources'] == ['PolyBench']
    assert all(t['width'] == 8 for r in rows for t in r['configuration']['tasks'])


def test_v2_inputs_still_match_preserved_archive():
    from tools.rtems_periodic_pool_v2 import candidate_pool

    with tarfile.open(ROOT / 'artifacts/periodic/candidates-v2/input-pool.tar.gz') as archive:
        archived = json.load(archive.extractfile('pool/pool.json'))
    generated = candidate_pool()
    assert generated['design'] == archived['design']
    assert [input_signature(r['configuration']) for r in generated['candidates']] == [
        input_signature(r['configuration']) for r in archived['candidates']]


def test_v3_initialization_preserves_provenance_and_pending_split(tmp_path):
    output = tmp_path / 'pool'
    report = initialize(output, version=3)
    assert report['primary_families'] == 5
    assert report['family_counts'] == {'train': 3, 'validation': 1, 'test': 1}
    assert report['measured_workloads'] == 0
    assert report['split_frozen'] is False
    pool = json.loads((output / 'pool.json').read_text())
    assert len(pool['duplicate_candidates']) > 0
    for filename in ('periodic_staged_recipes.py', 'STAGED-RECIPES.md',
                     'staged-recipe-sources.json', 'rtems_periodic_pool_v3.py'):
        assert (output / 'implementation' / filename).is_file()
