import hashlib
import json
from pathlib import Path

import pytest

from chaser.ca import ca_caas, ca_csrd, ca_from_histogram

ROOT = Path(__file__).resolve().parents[1]


def test_cold_exclusion_and_no_reuse():
    assert ca_from_histogram({'0': 2, '3': 1}) == 0.5
    assert ca_from_histogram({}) is None
    assert ca_caas({'profile': {'histogram': {'0': 2, '3': 1}, 'cold_misses': 999}}) == 0.5
    assert ca_csrd({'l1': {'csrd_histogram': {}},
                    'llc': {'csrd_histogram': {'0': 100}}}) is None


@pytest.mark.parametrize('case,hist,cold,l1_hits,llc_hits', [
    ('packed', {'0': 1048591}, 1, 1048591, 0),
    ('spread', {'0': 1048584}, 8, 1048584, 0),
    ('conflict', {'0': 524296, '7': 524288}, 8, 524296, 524288),
])
def test_linked_l1_csrd(case, hist, cold, l1_hits, llc_hits):
    result = json.loads((ROOT / f'exports/{case}.csrd.json').read_bytes())
    assert result['schema_version'] == 2
    assert result['model_id'] == 'exact-two-level-lru-demand-v1'
    assert result['address_basis'] == 'linked_absolute'
    for key, path in [('elf_sha256', f'rtems/baseline/build/{case}.exe'),
                      ('map_sha256', f'rtems/baseline/build/{case}.ape.json'),
                      ('cache_config_sha256', 'rtems/baseline/cache.yaml')]:
        assert result['inputs'][key] == hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    assert len(result['tasks']) == 1
    task = result['tasks'][0]
    assert task['task_id'] == 'chaser_' + case
    assert task['source_accesses'] == task['modeled_accesses'] == 1048592
    assert task['l1']['csrd_histogram'] == hist
    assert task['l1']['cold_misses'] == cold
    assert task['l1_first_hit_count'] == l1_hits
    assert task['llc_first_hit_count'] == llc_hits
    assert task['all_cache_miss_count'] == cold
    assert task['llc']['lookups'] == task['l1']['misses']
    assert task['coverage']['complete']
    assert all(task['invariants'].values())
    ratios = [task[k] for k in ('l1_first_hit_ratio', 'llc_first_hit_ratio', 'all_cache_miss_ratio')]
    assert sum(ratios) == pytest.approx(1)
    assert ca_csrd(task) == (131073 / 589825 if case == 'conflict' else 1.0)
