"""Expanded source families preserve excluded duplicates and old pool behavior."""

import json
import tarfile

from tools.rtems_periodic_pool import ROOT, initialize
from tools.rtems_periodic_pool_audit import input_signature


def test_v2_inputs_still_match_preserved_archive():
    from tools.rtems_periodic_pool_v2 import candidate_pool

    with tarfile.open(ROOT / 'artifacts/periodic/candidates-v2/input-pool.tar.gz') as archive:
        archived = json.load(archive.extractfile('pool/pool.json'))
    generated = candidate_pool()
    assert generated['design'] == archived['design']
    assert [input_signature(r['configuration']) for r in generated['candidates']] == [
        input_signature(r['configuration']) for r in archived['candidates']]


