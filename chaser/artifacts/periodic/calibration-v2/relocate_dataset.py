"""Move the active dataset locally while preserving frozen legacy path identities.

Run from the workspace with PYTHONPATH=. and phase plan, move, or verify.
The plan inventories bytes before movement. Real legacy directory anchors stay
in place; their children become relative links to the new canonical storage.
No measurements, policies, implementation snapshots, or source metadata change.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from chaser.periodic_calibration import ROOT, read_json
from tools.rtems_smoke import file_hash, write_json


DATA = ROOT / 'datasets/periodic-v2'
PROVENANCE = DATA / 'provenance'


def selection():
    population = read_json(ROOT / 'artifacts/periodic/validation-supplement-v2/active-population.json')
    binding = read_json(ROOT / 'artifacts/periodic/calibration-v2/input-sources.json')
    plan = read_json(ROOT / '.cache/calibration-v2/plan.json')
    units, copies, anchors, workloads = [], [], [], {}

    def unit(source, destination, copy=False):
        source, destination = Path(source), DATA / destination
        assert source.exists() and not source.is_symlink(), source
        assert not destination.exists(), destination
        (copies if copy else units).append(dict(source=str(source.relative_to(ROOT)),
            destination=str(destination.relative_to(ROOT))))

    def anchor(source, destination):
        source = Path(source)
        assert source.is_dir() and not source.is_symlink(), source
        anchors.append(str(source.relative_to(ROOT)))
        for child in sorted(source.iterdir()):
            unit(child, str(Path(destination) / child.name))

    anchor(ROOT / '.cache/characterization-v1-inputs/frozen', 'provenance/original-frozen')
    for member in population['workloads']:
        name = member['workload_id']
        supplement = binding['supplements'].get(name)
        snapshot = ROOT / (supplement['snapshot'] if supplement else
                           f'.cache/characterization-v1/prepared/{name}')
        records = ROOT / (supplement['records'] if supplement else
                          f'.cache/characterization-v1/runs/{name}')
        prefix = f'characterization/{name}'
        anchor(snapshot, prefix + '/prepared')
        if name == 'validation-supplement-v2-0001':
            anchor(ROOT / supplement['u_batches'], prefix + '/records')
            for filename in ('features.json', 'utilization.json'):
                unit(records / filename, prefix + '/records/' + filename)
        else:
            anchor(records, prefix + '/records')
        unit(snapshot / 'configuration.json', f'inputs/{name}.json', copy=True)
        workloads[name] = dict(split=member['split_group'], input=f'inputs/{name}.json',
            snapshot=prefix + '/prepared', records=prefix + '/records')
        if supplement:
            base = (ROOT / '.cache/validation-supplement-v2-validation/gcp/runs' if
                    name == 'validation-supplement-v2-0001' else
                    ROOT / '.cache/validation-supplement-v1-gcp/collection/runs')
            for letter in ('g', 'c', 'p'):
                anchor(base / name / letter, prefix + '/basic-gcp/' + letter)

    mappings = {}
    for identity, entry in plan['mappings'].items():
        old = ROOT / '.cache/calibration-v1'
        reused = (old / 'prepared' / identity).exists()
        source = old if reused else ROOT / '.cache/calibration-v2'
        anchor(source / 'prepared' / identity, f'calibration/prepared/{identity}')
        anchor(source / 'runs' / identity, f'calibration/runs/{identity}/p')
        if reused:
            for letter in ('g', 'c'):
                anchor(old / 'gcp-survey-v1/runs' / identity / letter,
                       f'calibration/runs/{identity}/{letter}')
        mappings[identity] = dict(workload_id=entry['workload_id'],
            snapshot=f'calibration/prepared/{identity}', runs=f'calibration/runs/{identity}',
            architectures=['g', 'c', 'p'] if reused else ['p'])

    for child in sorted((ROOT / '.cache/calibration-v2').iterdir()):
        if child.name not in ('prepared', 'runs'):
            unit(child, 'calibration/' + child.name)
    for name in ('plan.json', 'implementation'):
        unit(ROOT / '.cache/calibration-v1' / name, 'provenance/calibration-v1/' + name, copy=True)
    for name in ('input-sources.json', 'completion-summary.json', 'loader-validation.json'):
        unit(ROOT / 'artifacts/periodic/calibration-v2' / name, 'provenance/' + name, copy=True)
    unit(ROOT / 'artifacts/periodic/validation-supplement-v2/active-population.json',
         'membership.json', copy=True)
    for version in ('v1', 'v2'):
        source = ROOT / f'artifacts/periodic/validation-supplement-{version}'
        for child in sorted(source.iterdir()):
            if child.name != '__pycache__':
                unit(child, f'provenance/validation-supplement-{version}/' + child.name, copy=True)
    for relative in ('.cache/validation-supplement-v1-characterization',
                     '.cache/validation-supplement-v1-gcp',
                     '.cache/validation-supplement-v1-gcp/collection',
                     '.cache/validation-supplement-v2-validation',
                     '.cache/validation-supplement-v2-validation/gcp'):
        for name in ('summary.json', 'protocol.json', 'source-hashes.json', 'exit.json'):
            source = ROOT / relative / name
            if source.exists():
                unit(source, 'provenance/collection-records/' + relative.removeprefix('.cache/') + '/' + name,
                     copy=True)
    metadata = dict(schema_version=1, scope='active207 characterization and validation calibration evidence',
        active_tasksets=len(workloads), split_counts=population['active_split_counts'],
        theta_policy_frozen=True, final_labels_ready=False, workloads=workloads, mappings=mappings,
        compatibility='Legacy .cache directory anchors with relative child links; original artifacts unchanged',
        portability='Payload has no external links; historical commands and current CLI still use original workspace paths')
    anchors.extend(['.cache/characterization-v1', '.cache/calibration-v2'])
    return dict(units=units, copies=copies, anchors=anchors, metadata=metadata)


def create_plan():
    if DATA.exists():
        raise FileExistsError(DATA)
    plan = selection()
    PROVENANCE.mkdir(parents=True)
    total, count = 0, 0
    with (PROVENANCE / 'files.jsonl').open('x') as output:
        for item in [*plan['units'], *plan['copies']]:
            source, destination = ROOT / item['source'], ROOT / item['destination']
            files = sorted(source.rglob('*')) if source.is_dir() else [source]
            for path in files:
                if path.is_symlink():
                    raise ValueError(f'Unexpected source link: {path}')
                if not path.is_file():
                    continue
                target = destination / path.relative_to(source) if source.is_dir() else destination
                row = dict(source=str(path.relative_to(ROOT)), destination=str(target.relative_to(ROOT)),
                           size=path.stat().st_size, sha256=file_hash(path))
                output.write(json.dumps(row, sort_keys=True) + '\n')
                total += row['size']
                count += 1
    protected = ['artifacts/periodic/calibration-v2/input-sources.json',
                 'artifacts/periodic/validation-supplement-v2/active-population.json',
                 'artifacts/periodic/calibration-v2/frozen-policies.json',
                 '.cache/calibration-v2/plan.json', '.cache/calibration-v2/frozen-policies.json']
    plan.update(created_utc=datetime.now(timezone.utc).isoformat(), file_count=count, bytes=total,
                inventory_hash=file_hash(PROVENANCE / 'files.jsonl'),
                script_hash=file_hash(Path(__file__)), protected={name:file_hash(ROOT / name) for name in protected})
    write_json(PROVENANCE / 'migration-plan.json', plan)
    print(json.dumps(dict(files=count, bytes=total, move_units=len(plan['units']), copies=len(plan['copies']))))


def source_path(plan, name):
    """Find bytes after an interrupted rename, before its legacy link exists."""
    source = ROOT / name
    if source.exists():
        return source
    moved = {item['source']: item['destination'] for item in plan['units']}
    for parent in [Path(name), *Path(name).parents]:
        if str(parent) in moved:
            return ROOT / moved[str(parent)] / Path(name).relative_to(parent)
    return source


def check_identity(plan, moving=False):
    assert file_hash(PROVENANCE / 'files.jsonl') == plan['inventory_hash']
    assert file_hash(Path(__file__)) == plan['script_hash']
    for name in plan['anchors']:
        path = ROOT / name
        assert path.is_dir() and not path.is_symlink() and path.resolve() == path, name
    for name, expected in plan['protected'].items():
        path = source_path(plan, name) if moving else ROOT / name
        assert file_hash(path) == expected, name


def move(plan):
    check_identity(plan, moving=True)
    # Check every source byte before any movement or resumed admission.
    for line in (PROVENANCE / 'files.jsonl').open():
        row = json.loads(line)
        assert file_hash(source_path(plan, row['source'])) == row['sha256'], row['source']
    for item in plan['copies']:
        source, destination = ROOT / item['source'], ROOT / item['destination']
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
    for index, item in enumerate(plan['units'], 1):
        source, destination = ROOT / item['source'], ROOT / item['destination']
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            assert source.resolve() == destination and destination.exists(), source
            continue
        if destination.exists():
            assert not source.exists(), f'Conflicting destination: {destination}'
        else:
            assert source.stat().st_dev == destination.parent.stat().st_dev, 'Require same-filesystem rename'
            source.rename(destination)
        source.symlink_to(os.path.relpath(destination, source.parent), target_is_directory=destination.is_dir())
        if index % 1000 == 0:
            print(f'linked {index}/{len(plan["units"])} moved entries', flush=True)
    write_json(DATA / 'dataset.json', plan['metadata'])
    verify(plan)


def verify(plan):
    check_identity(plan)
    count = 0
    for line in (PROVENANCE / 'files.jsonl').open():
        row = json.loads(line)
        source, destination = ROOT / row['source'], ROOT / row['destination']
        assert destination.is_file() and not destination.is_symlink(), destination
        assert destination.stat().st_size == row['size'] and file_hash(destination) == row['sha256'], destination
        assert file_hash(source) == row['sha256'], source
        count += 1
    for item in plan['units']:
        source, destination = ROOT / item['source'], ROOT / item['destination']
        assert source.is_symlink() and source.resolve() == destination, source
    assert not any(path.is_symlink() for path in DATA.rglob('*')), 'Dataset contains links'
    assert len(plan['metadata']['workloads']) == 207 and len(plan['metadata']['mappings']) == 189
    assert Counter(row['split'] for row in plan['metadata']['workloads'].values()) == {'train':126,'validation':41,'test':40}
    report = dict(status='pass', verified_utc=datetime.now(timezone.utc).isoformat(), files=count,
        bytes=plan['bytes'], compatibility_links=len(plan['units']), external_dataset_links=0,
        directory_identities_unchanged=True, protected_hashes=plan['protected'],
        inventory_hash=plan['inventory_hash'], migration_plan_hash=file_hash(PROVENANCE / 'migration-plan.json'))
    write_json(PROVENANCE / 'migration-verification.json', report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('plan', 'move', 'verify'))
    phase = parser.parse_args().phase
    if phase == 'plan':
        create_plan()
    else:
        plan = read_json(PROVENANCE / 'migration-plan.json')
        (move if phase == 'move' else verify)(plan)
