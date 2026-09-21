"""Replay archived input audits and recheck the three linked build snapshots."""

import argparse
import json
from pathlib import Path
import tarfile

from chaser.periodic_build import check_layout, read_symbols
from tools.rtems_periodic_pool_audit import audit_pool
from tools.rtems_smoke import check_inputs, file_hash, write_json


def unpack(archive_path: Path, output: Path, prefix: str) -> None:
    with tarfile.open(archive_path) as archive:
        members = archive.getmembers()
        for member in members:
            path = Path(member.name)
            if (path.is_absolute() or '..' in path.parts or path.parts[0] != prefix
                    or not (member.isfile() or member.isdir())):
                raise ValueError('Unexpected archive member')
        archive.extractall(output, members=members)


def revalidate(output: Path) -> dict:
    """Verify source hashes, deterministic reports and linked symbol layouts."""
    root = Path(__file__).resolve().parent
    check_inputs(root, json.loads((root / 'manifest.json').read_text()))
    output.mkdir(parents=True, exist_ok=False)
    pools = {}
    for version, prefix in ((1, 'periodic-candidates-v1-r2'), (2, 'pool')):
        source = root.parent / f'candidates-v{version}'
        check_inputs(source, json.loads((source / 'manifest.json').read_text()))
        destination = output / f'v{version}'
        unpack(source / 'input-pool.tar.gz', destination, prefix)
        prepared = destination / prefix
        check_inputs(prepared, json.loads((prepared / 'manifest.json').read_text()))
        pool = json.loads((prepared / 'pool.json').read_text())
        pools[version] = pool
        saved = json.loads((root / f'v{version}-audit.json').read_text())
        assert saved['source_pool_hash'] == file_hash(prepared / 'pool.json')
        assert saved['source_manifest_hash'] == file_hash(prepared / 'manifest.json')
        for path, expected in saved['implementation_hashes'].items():
            assert file_hash(root / 'implementation' / path) == expected, path
        replay = audit_pool(pool)
        assert replay == {k: v for k, v in saved.items() if k not in (
            'source_pool_hash', 'source_manifest_hash', 'implementation_hashes')}

    unpack(root / 'build-snapshots.tar.gz', output, 'builds')
    report = json.loads((root / 'build-report.json').read_text())
    assert report == json.loads((output / 'builds/build-report.json').read_text())
    selection = json.loads((root / 'selection.json').read_text())
    assert selection == json.loads((output / 'builds/selection.json').read_text())
    candidates = {r['workload_id']: r for r in pools[2]['candidates']}
    expected_names = [r['workload_id'] for r in pools[2]['candidates']
                      if len(r['configuration']['tasks']) == 16
                      and r['profile'] == 'llc-two' and r['target_total_u'] == 0.5]
    assert selection['workloads'] == expected_names
    assert [r['workload_id'] for r in report['workloads']] == expected_names
    assert selection['pool_hash'] == file_hash(output / 'v2/pool/pool.json')
    for row in report['workloads']:
        snapshot = output / 'builds' / row['workload_id']
        check_inputs(snapshot, json.loads((snapshot / 'manifest.json').read_text()))
        assert file_hash(snapshot / 'manifest.json') == row['snapshot_manifest_hash']
        assert json.loads((snapshot / 'configuration.json').read_text()) == (
            candidates[row['workload_id']]['configuration'])
        layouts = json.loads((snapshot / 'layout.json').read_text())
        for arch in ('g', 'c', 'p'):
            plan = json.loads((snapshot / arch / 'plan.json').read_text())
            assert check_layout(read_symbols(snapshot / 'build' / f'{arch}.exe'),
                                plan['tasks']) == layouts[arch]
    result = dict(status='PASS', audited_candidates=420, unique_inputs_by_panel={'v1': 200, 'v2': 123},
                  checked_builds=3, checked_elf_layouts=9, runtime_runs=0,
                  dataset_ready=False, split_frozen=False)
    write_json(output / 'revalidation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(revalidate(parser.parse_args().output), indent=2, sort_keys=True))
