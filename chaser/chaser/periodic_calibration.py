"""Validation-only mapping plans and provenance for measured theta calibration."""

from dataclasses import asdict
import json
from pathlib import Path
import shutil

from chaser.allocator import CoreGroups
from chaser.periodic import digest, make_plan
from chaser.periodic_dataset import characterize, load_batch
from chaser.periodic_membership import active_membership
from chaser.threshold import CalibrationWorkload, plan_calibration
from tools.rtems_periodic_characterize import checked_locality, feature_record
from tools.rtems_periodic_freeze import verify
from tools.rtems_smoke import SIMULATOR, file_hash


CORES = CoreGroups((0,), (1, 2, 3))
KINDS = ('caas-ca', 'ca-csrd', 'cls')
ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION = ('chaser/periodic_membership.py', 'chaser/periodic_calibration.py', 'chaser/threshold.py',
                  'chaser/allocator.py', 'chaser/features.py', 'chaser/periodic_build.py',
                  'chaser/periodic_analysis.py', 'chaser/periodic.py',
                  'chaser/periodic_dataset.py', 'tools/rtems_periodic_calibrate.py',
                  'tools/rtems_periodic.py', 'tools/rtems_periodic_characterize.py',
                  'tools/rtems_smoke.py', 'chaser/periodic_patterns.py',
                  'chaser/periodic_structures.py', 'chaser/periodic_recipes.py',
                  'chaser/periodic_staged_recipes.py', 'chaser/event_compression.py',
                  'chaser/event_storage.py', 'chaser/s1_artifacts.py',
                  'chaser/ca.py', 'chaser/cls.py', 'rtems/periodic/init.c',
                  'rtems/periodic/probe.c', 'rtems/periodic/probe.h',
                  'rtems/periodic/wscript', 'rtems/baseline/cache.yaml')


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def load_validation(frozen: Path, characterized: Path, *,
                    input_sources: Path | None = None) -> tuple[dict, list, dict]:
    """Recheck frozen membership and original U evidence; never load test features.

    The legacy calibration API accepts validation rows alone. Its split hash
    describes that subset; the complete frozen split hash is recorded separately.
    Original U ELF identities are retained, never relabeled as mapping ELF runs.
    """
    verify(frozen)
    population = read_json(frozen / 'population.json')
    supplements = {}
    if input_sources is not None:
        population, supplements, _ = active_membership(frozen, input_sources)
    members = [m for m in population['workloads'] if m['split_group'] == 'validation']
    cases, rows, inputs = {}, [], {}
    for member in members:
        name = member['workload_id']
        snapshot = characterized / 'prepared' / name
        directory = characterized / 'runs' / name
        u_directory = directory
        if name in supplements:
            source = supplements[name]
            snapshot = ROOT / source['snapshot']
            directory = ROOT / source['records']
            u_directory = ROOT / source['u_batches']
            config = read_json(snapshot / 'configuration.json')
        else:
            config = read_json(frozen / 'source/configs' / (name + '.json'))
        if (digest(config) != member['configuration_hash']
                or read_json(snapshot / 'configuration.json') != config):
            raise ValueError('Frozen characterization configuration mismatch')
        locality = checked_locality(snapshot)
        plan = read_json(snapshot / 'p/plan.json')
        utilization = characterize(plan, [load_batch(snapshot, u_directory / f'u{i}')
                                         for i in range(len(plan['tasks']))])
        if utilization != read_json(directory / 'utilization.json'):
            raise ValueError('Stored independent U differs from raw evidence')
        record = feature_record(member, locality, utilization)
        stored = read_json(directory / 'features.json')
        if any(stored.get(k) != v for k, v in record.items()):
            raise ValueError('Stored features differ from validated inputs')
        if not record['within_u_bounds'] or record['undefined_features']:
            raise ValueError('Validation input has invalid U or undefined locality')
        if set(cases).intersection(locality['cases']):
            raise ValueError('Calibration task IDs must be unique across workloads')
        cases.update(locality['cases'])
        rows.append(CalibrationWorkload(name, member['family_id'], 'validation',
                                        utilization['utilization']))
        inputs[name] = dict(u_directory=str(u_directory.resolve()), member=member, configuration=config, utilization=utilization,
                           snapshot=str(snapshot.resolve()),
                           manifest_hash=file_hash(snapshot / 'manifest.json'),
                           analysis_manifest_hash=file_hash(snapshot / 'analysis/manifest.json'),
                           cases=locality['cases'], provenance=locality['provenance'],
                           analyzer_tools=locality.get('tools', {}))
    return cases, rows, inputs


def tool_identity(inputs: dict) -> dict:
    """Pin the toolchain and simulator and require original U/analysis compatibility."""
    hashes = {}
    simulator_hash = file_hash(SIMULATOR)
    for origin in inputs.values():
        snapshot = Path(origin['snapshot'])
        tools = dict(read_json(snapshot / 'manifest.json')['tools'], **origin['analyzer_tools'])
        for name, expected in tools.items():
            if file_hash(Path(name)) != expected:
                raise ValueError('Toolchain differs from original characterization')
            hashes[name] = expected
        for index in range(len(origin['configuration']['tasks'])):
            batch = Path(origin['u_directory']) / f'u{index}' / 'protocol.json'
            if read_json(batch)['simulator_hash'] != simulator_hash:
                raise ValueError('Simulator differs from original independent U')
    for name in ('clang-14', 'opt-14'):
        path = Path(shutil.which(name) or name).resolve()
        hashes[str(path)] = file_hash(path)
    for path in (Path('/opt/rtems/6/bin/sparc-rtems6-nm'), Path('/opt/src/rtems/waf'), SIMULATOR):
        hashes[str(path)] = file_hash(path)
    return dict(files=hashes, simulator_hash=simulator_hash)


def mapping_id(name: str, mapping: dict) -> str:
    """Identify a workload and exact core assignment, independent of scalar kind."""
    return digest([name, mapping])


def mapping_configuration(original: dict, mapping: dict, identity: str) -> dict:
    """Change only policy/core assignment; preserve task order and frozen inputs."""
    if set(mapping) != {t['task_id'] for t in original['tasks']}:
        raise ValueError('A complete exact task mapping is required')
    return dict(original, policy_id='validation-mapping-' + identity,
                tasks=[dict(t, core=mapping[t['task_id']]) for t in original['tasks']])


def make_calibration_plan(frozen: Path, characterized: Path, *, workers: int = 16,
                          prepare_workers: int = 8, timeout: float = 1800,
                          input_sources: Path | None = None) -> tuple:
    """Pin a shared measurement plan before any timing-dependent selection."""
    if (type(workers) is not int or not 1 <= workers <= 32
            or type(prepare_workers) is not int or not 1 <= prepare_workers <= 16
            or not 0 < timeout < float('inf')):
        raise ValueError('Invalid simulator/build worker count or timeout')
    cases, rows, inputs = load_validation(frozen, characterized, input_sources=input_sources)
    representations, mappings = {}, {}
    for kind in KINDS:
        planned = plan_calibration(cases, rows, CORES, kind=kind,
                                   alpha=0.5 if kind == 'cls' else None)
        representations[kind] = asdict(planned)
        for name, mapping in planned.mappings:
            identity = mapping_id(name, mapping)
            mappings[identity] = dict(workload_id=name, mapping=mapping,
                configuration=mapping_configuration(inputs[name]['configuration'], mapping, identity))
    split = read_json(frozen / 'split.json')
    plan = dict(schema_version=1, scope='validation-P-mapping-calibration',
        frozen=str(frozen.resolve()), characterized=str(characterized.resolve()),
        frozen_population_hash=file_hash(frozen / 'population.json'),
        frozen_split_hash=file_hash(frozen / 'split.json'), seed=split['seed'],
        cores=asdict(CORES), cls_alpha=0.5, expected_runs=10, architecture=2,
        workers=workers, prepare_workers=prepare_workers, timeout_seconds=timeout,
        selection_rule='failed-workloads/common-mean-median-tat/min-theta-v1',
        inputs=inputs, representations=representations, mappings=mappings,
        planned_batches=len(mappings), planned_runs=10 * len(mappings),
        tool_identity=tool_identity(inputs),
        implementation_hashes={name: file_hash(ROOT / name) for name in IMPLEMENTATION})
    if input_sources is not None:
        _, _, plan['active_dataset'] = active_membership(frozen, input_sources)
    return plan, cases, rows


def check_mapping_snapshot(snapshot: Path, entry: dict, origin: dict) -> None:
    """Verify new final ELF analysis while retaining the original U provenance."""
    if read_json(snapshot / 'configuration.json') != entry['configuration']:
        raise ValueError('Mapping snapshot configuration changed')
    locality = checked_locality(snapshot)
    original = Path(origin['snapshot'])
    unchanged = ('source/workload.c', 'source/workload.h', 'source/init.c',
                 'source/probe.c', 'source/probe.h', 'layout.ld', 'cache.yaml', 'wscript', 'waf')
    if (any(file_hash(snapshot / name) != file_hash(original / name) for name in unchanged)
            or read_json(snapshot / 'layout.json') != read_json(original / 'layout.json')
            or locality['cases'] != origin['cases']):
        raise ValueError('Mapping changed task source, layout or locality')
    if (read_json(snapshot / 'manifest.json')['tools'] != read_json(original / 'manifest.json')['tools']
            or locality['tools'] != origin['analyzer_tools']):
        raise ValueError('Mapping changed build or analysis tools')
    for architecture, letter in enumerate(('g', 'c', 'p')):
        if read_json(snapshot / letter / 'plan.json') != make_plan(entry['configuration'], architecture):
            raise ValueError('Mapping execution plan differs from configuration')
    for task, evidence in locality['provenance'].items():
        if evidence['stream_hash'] != origin['provenance'][task]['stream_hash']:
            raise ValueError('Mapping changed linked task access stream')
