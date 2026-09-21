"""Recheck preserved inputs and literal ELF streams in a fresh directory."""

import argparse
from collections import Counter
import json
from pathlib import Path
import tarfile

from chaser.periodic import digest, make_plan
from chaser.periodic_analysis import check_stream
from chaser.periodic_registry import build_registry
from tools.rtems_smoke import check_inputs, file_hash, write_json


def revalidate(output: Path) -> dict:
    """Refuse overwrite, verify hashes, and replay all saved plan/stream checks."""
    root = Path(__file__).resolve().parent
    check_inputs(root, json.loads((root / 'manifest.json').read_text()))
    output.mkdir(parents=True, exist_ok=False)
    for filename, prefix in (('input-pool.tar.gz', 'pool'),
                             ('recipe-correctness.tar.gz', 'correctness')):
        with tarfile.open(root / filename) as archive:
            members = archive.getmembers()
            for member in members:
                path = Path(member.name)
                if (path.is_absolute() or '..' in path.parts or path.parts[0] != prefix
                        or not (member.isfile() or member.isdir())):
                    raise ValueError('Unexpected archive member')
            archive.extractall(output, members=members)

    pool_root, fixture = output / 'pool', output / 'correctness'
    snapshot = fixture / 'snapshot'
    for path in (pool_root, fixture, snapshot, snapshot / 'analysis'):
        check_inputs(path, json.loads((path / 'manifest.json').read_text()))
    pool = json.loads((pool_root / 'pool.json').read_text())
    registry = json.loads((pool_root / 'registry.json').read_text())
    split = json.loads((pool_root / 'split-proposal.json').read_text())
    summary = json.loads((pool_root / 'summary.json').read_text())
    assert summary == json.loads((root / 'summary.json').read_text())
    assert build_registry(registry['workloads']) == registry
    candidates = [r for r in registry['workloads'] if r['primary_candidate']]
    assert pool['candidates'] == candidates
    assert pool['dataset_ready'] is pool['split_frozen'] is False
    assert pool['design']['excluded_pattern_sources'] == ['PolyBench']
    assert pool['design']['source_manifest_hash'] == file_hash(
        pool_root / 'implementation/recipe-sources.json')
    assert split['workloads'] == {r['workload_id']: r['family_id'] for r in candidates}
    assert summary['split_hash'] == digest(split)
    assert summary['family_counts'] == dict(Counter(split['families'].values()))
    assert summary['workload_counts'] == dict(Counter(
        split['families'][r['family_id']] for r in candidates))
    plans = 0
    for row in candidates:
        config = row['configuration']
        assert config == json.loads((pool_root / 'configs' / (row['workload_id'] + '.json')).read_text())
        assert digest(config) == row['configuration_hash']
        assert config['eligible_for_training'] is config['test_eligible'] is False
        assert row['measured_utilization'] is None
        assert row['eligibility_status'] == 'pending_measurement'
        for architecture in range(3):
            plan = make_plan(config, architecture)
            assert sum(t['job_count'] for t in plan['tasks']) <= 64
            assert len(plan['tasks']) * max(t['job_count'] for t in plan['tasks']) <= 64
            plans += 1

    references = json.loads((fixture / 'reference-traces.json').read_text())
    layout = json.loads((snapshot / 'layout.json').read_text())
    streams = 0
    for arch in ('g', 'c', 'p'):
        plan = json.loads((snapshot / arch / 'plan.json').read_text())
        for task in plan['tasks']:
            name = task['task_id']
            address = next(r['address'] for r in layout[arch] if r['symbol'] == 'data_' + name)
            events = json.loads((snapshot / 'analysis' / arch / name / 'events.json').read_text())['events']
            assert [e['linked_address'] - address for e in events] == references[name]
            check_stream(task, events, address)
            streams += 1
    result = dict(status='PASS', candidate_workloads=len(candidates), plans=plans,
                  primary_families=registry['primary_family_count'], linked_streams=streams,
                  fixture_tasks=len(references), measured_workloads=0,
                  dataset_ready=False, split_frozen=False)
    assert (len(candidates), plans, streams) == (180, 540, 36)
    write_json(output / 'revalidation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(revalidate(parser.parse_args().output), indent=2, sort_keys=True))
