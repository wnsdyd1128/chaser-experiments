"""Calibration orchestration rejects leakage, changed inputs and failed timing."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from chaser import periodic_calibration as planning
from chaser.periodic import digest
from tools import rtems_periodic_calibrate as runner
from tools.rtems_smoke import write_json


def test_mapping_configuration_preserves_task_order_and_every_input():
    original = dict(policy_id='old', horizon_ticks=100, tasks=[
        dict(task_id='b', core=3, sweeps=2), dict(task_id='a', core=2, sweeps=1)])
    before = deepcopy(original)
    updated = planning.mapping_configuration(original, {'a': 0, 'b': 1}, 'mapping')
    assert original == before
    assert updated == dict(original, policy_id='validation-mapping-mapping', tasks=[
        dict(task_id='b', core=1, sweeps=2), dict(task_id='a', core=0, sweeps=1)])
    with pytest.raises(ValueError, match='complete exact'):
        planning.mapping_configuration(original, {'a': 0}, 'mapping')


@pytest.fixture
def validation(tmp_path, monkeypatch):
    frozen, characterized = tmp_path / 'frozen', tmp_path / 'characterized'
    snapshot = characterized / 'prepared/v'
    directory = characterized / 'runs/v'
    (snapshot / 'p').mkdir(parents=True)
    (snapshot / 'analysis').mkdir()
    (frozen / 'source/configs').mkdir(parents=True)
    directory.mkdir(parents=True)
    config = dict(tasks=[dict(task_id='a', core=1)], policy_id='old')
    member = dict(workload_id='v', family_id='shared', split_group='validation',
                  configuration_hash=digest(config))
    # No files for train or test exist; any accidental payload access fails.
    write_json(frozen / 'population.json', dict(workloads=[member,
        dict(workload_id='train', family_id='shared', split_group='train'),
        dict(workload_id='test', family_id='shared', split_group='test')]))
    write_json(frozen / 'source/configs/v.json', config)
    write_json(snapshot / 'configuration.json', config)
    write_json(snapshot / 'p/plan.json', config)
    for path in [snapshot / 'manifest.json', snapshot / 'analysis/manifest.json']:
        write_json(path, {})
    utilization = dict(utilization={'a': 0.2}, characterization_id='original', elf_hash='U-elf')
    record = dict(within_u_bounds=True, undefined_features={}, utilization={'a': 0.2})
    write_json(directory / 'utilization.json', utilization)
    write_json(directory / 'features.json', record)
    locality = dict(cases={'a': dict(ca_caas_element=0.2, ca_csrd_l1=0.3, cls={'0.5': 0.4})},
                    provenance={'a': {'stream_hash': 'stream'}})
    monkeypatch.setattr(planning, 'verify', lambda _: None)
    monkeypatch.setattr(planning, 'checked_locality', lambda _: locality)
    monkeypatch.setattr(planning, 'tool_identity', lambda _: {'simulator_hash': 'sim'}, raising=False)
    monkeypatch.setattr(planning, 'load_batch', lambda *_: [])
    monkeypatch.setattr(planning, 'characterize', lambda *_: utilization)
    monkeypatch.setattr(planning, 'feature_record', lambda *_: record)
    return frozen, characterized, snapshot, directory, locality


def test_only_validation_payloads_are_loaded_and_original_u_identity_is_retained(validation):
    frozen, characterized, _, _, _ = validation
    cases, rows, inputs = planning.load_validation(frozen, characterized)
    assert set(cases) == {'a'}
    assert [r.workload_id for r in rows] == ['v']
    assert inputs['v']['utilization']['elf_hash'] == 'U-elf'


@pytest.mark.parametrize('filename', ['utilization.json', 'features.json'])
def test_changed_characterization_record_prevents_calibration(validation, filename):
    frozen, characterized, _, directory, _ = validation
    write_json(directory / filename, {})
    with pytest.raises(ValueError, match='differs from|differ from'):
        planning.load_validation(frozen, characterized)


def test_plan_deduplicates_same_exact_mapping_across_representations(validation, monkeypatch):
    frozen, characterized, _, _, _ = validation
    write_json(frozen / 'split.json', dict(seed=42))
    plan, _, _ = planning.make_calibration_plan(frozen, characterized)
    # One task has two placements, shared by all three representation searches.
    assert plan['planned_batches'] == 2
    assert plan['planned_runs'] == 20
    assert all(len(p['mappings']) == 2 for p in plan['representations'].values())
    assert all(c['mean_tat'] is None for p in plan['representations'].values()
               for c in p['candidates'])


@pytest.fixture
def timing(tmp_path, monkeypatch):
    write_json(tmp_path / 'protocol.json', dict(runs=10, timeout_seconds=1800,
                                              mode=0, trace=False, empty=False, simulator_hash='sim'))
    rows = [dict(run_id=str(i), architecture=2, execution_status='ok', mode=0,
                 trace=False, empty=False, tat_ns=i + 10) for i in range(10)]
    monkeypatch.setattr(runner, 'load_batch', lambda *_: rows)
    return tmp_path, rows


def test_measurement_uses_median_of_ten_validated_runs(timing):
    path, _ = timing
    assert runner.measured_tat(path, path, 1800, 'sim') == 14.5


@pytest.mark.parametrize('change', [dict(execution_status='failed'), dict(architecture=1),
    dict(mode=1), dict(trace=True), dict(empty=True), dict(run_id='9')])
def test_invalid_or_duplicate_run_cannot_supply_calibration_tat(timing, change):
    path, rows = timing
    rows[0].update(change)
    with pytest.raises(ValueError, match='ten successful'):
        runner.measured_tat(path, path, 1800, 'sim')


def test_incomplete_batch_cannot_supply_calibration_tat(timing):
    path, rows = timing
    rows.pop()
    with pytest.raises(ValueError, match='ten successful'):
        runner.measured_tat(path, path, 1800, 'sim')


def test_changed_protocol_cannot_supply_calibration_tat(timing):
    path, _ = timing
    with pytest.raises(ValueError, match='protocol differs'):
        runner.measured_tat(path, path, 600, 'sim')


def test_different_simulator_cannot_enter_common_calibration(timing):
    path, _ = timing
    with pytest.raises(ValueError, match='protocol differs'):
        runner.measured_tat(path, path, 1800, 'different-simulator')


def test_changed_mapping_stream_is_rejected(validation, tmp_path, monkeypatch):
    _, _, original, _, locality = validation
    snapshot = tmp_path / 'new'
    (snapshot / 'source').mkdir(parents=True)
    (original / 'source').mkdir()
    for root in (snapshot, original):
        for name in ('source/workload.c', 'source/workload.h', 'source/init.c',
                     'source/probe.c', 'source/probe.h', 'layout.ld', 'cache.yaml', 'wscript', 'waf'):
            (root / name).write_text('same source')
        write_json(root / 'layout.json', dict(p=[dict(address=0x1000000)]))
        write_json(root / 'manifest.json', dict(tools={}))
    monkeypatch.setattr(planning, 'make_plan', lambda *_: {})
    for letter in ('g', 'c', 'p'):
        (snapshot / letter).mkdir()
        write_json(snapshot / letter / 'plan.json', {})
    write_json(snapshot / 'configuration.json', {'policy_id': 'new'})
    locality['tools'] = {}
    origin = dict(snapshot=str(original), cases=locality['cases'], analyzer_tools={},
                  provenance={'a': {'stream_hash': 'different'}})
    with pytest.raises(ValueError, match='linked task access stream'):
        planning.check_mapping_snapshot(snapshot, dict(configuration={'policy_id': 'new'}), origin)


def test_failed_batch_preserves_evidence_and_prevents_freeze(validation, tmp_path, monkeypatch):
    frozen, characterized, _, _, _ = validation
    write_json(frozen / 'split.json', dict(seed=42))
    output = tmp_path / 'calibration'
    runner.collect(frozen, characterized, output, phase='plan', workers=1)
    monkeypatch.setattr(runner, 'check_mapping_snapshot', lambda *_: None)

    def fail_run(_, directory, **kwargs):
        directory.mkdir(parents=True)
        (directory / 'partial.log').write_text('preserved')
        raise ValueError('measurement failure')

    monkeypatch.setattr(runner, 'run', fail_run)
    with pytest.raises(SystemExit):
        runner.collect(frozen, characterized, output, phase='run', workers=1)
    assert len(list((output / 'runs').iterdir())) == 1
    assert next((output / 'runs').glob('*/partial.log')).read_text() == 'preserved'
    with pytest.raises(FileNotFoundError):
        runner.collect(frozen, characterized, output, phase='freeze', workers=1)
    assert not (output / 'frozen-policies.json').exists()
    monkeypatch.setattr(runner, 'run', lambda *_a, **_kw: pytest.fail('Do not overwrite failed run'))
    with pytest.raises(SystemExit):
        runner.collect(frozen, characterized, output, phase='run', workers=1)


@pytest.mark.parametrize('active', [False, True])
def test_complete_evidence_freezes_measured_policies_and_is_repeatable(
        validation, active_validation, tmp_path, monkeypatch, active):
    frozen, characterized, _, _, _ = validation
    write_json(frozen / 'split.json', dict(seed=42))
    options = {'input_sources': active_validation[2]} if active else {}
    output = tmp_path / 'calibration'
    runner.collect(frozen, characterized, output, phase='plan', **options)
    monkeypatch.setattr(runner, 'check_mapping_snapshot', lambda *_: None)
    plan = json.loads((output / 'plan.json').read_text())
    for identity in plan['mappings']:
        for base, names in [('prepared', ['manifest.json', 'analysis/manifest.json']),
                            ('runs', ['protocol.json', 'measurements.jsonl'])]:
            for name in names:
                path = output / base / identity / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}')
    monkeypatch.setattr(runner, 'measured_tat', lambda snapshot, *_: (
        10 if plan['mappings'][snapshot.name]['mapping']['a'] == 0 else 20))
    result = runner.collect(frozen, characterized, output, phase='freeze', **options)
    assert result['dataset_stage'] == 'theta_policy_frozen'
    if active:
        assert all(p['active_dataset'] == plan['active_dataset'] for p in result['policies'].values())
    assert all(r['measurement_source'] == 'measured' for r in result['results'].values())
    assert all(r['threshold'] > 0.2 for r in result['results'].values())
    before = (output / 'frozen-policies.json').read_bytes()
    runner.collect(frozen, characterized, output, phase='freeze', **options)
    assert (output / 'frozen-policies.json').read_bytes() == before


@pytest.fixture
def active_validation(validation, tmp_path):
    frozen, characterized, snapshot, directory, _ = validation
    original = planning.read_json(frozen / 'population.json')['workloads']
    # Keep original validation evidence on disk, but admit only its replacement.
    replacement = dict(original[0], workload_id='replacement')
    active = [replacement, *original[1:]]
    population = dict(workloads=active, assignments={m['workload_id']: m['split_group'] for m in active},
        membership_hash=digest(active), active_tasksets=3,
        active_split_counts=dict(train=1, validation=1, test=1),
        added_workload_ids=['replacement'], excluded=[dict(workload_id='v')])
    population_path = tmp_path / 'active.json'
    write_json(population_path, population)
    write_json(frozen / 'split.json', dict(seed=42))
    binding = dict(schema_version=1, files={}, active_population=str(population_path),
        active_population_hash=planning.file_hash(population_path),
        original_population_hash=planning.file_hash(frozen / 'population.json'),
        original_split_hash=planning.file_hash(frozen / 'split.json'),
        supplements={'replacement': dict(snapshot=str(snapshot), records=str(directory),
                                        u_batches=str(directory))})
    path = tmp_path / 'input-sources.json'
    write_json(path, binding)
    return frozen, characterized, path, population_path


def test_active_loader_excludes_original_and_keeps_original_u_identity(active_validation, monkeypatch):
    frozen, characterized, binding, _ = active_validation
    seen = []
    monkeypatch.setattr(planning, 'load_batch', lambda snapshot, directory: seen.append(directory) or [])
    _, rows, inputs = planning.load_validation(frozen, characterized, input_sources=binding)
    assert [r.workload_id for r in rows] == ['replacement']
    assert inputs['replacement']['utilization']['elf_hash'] == 'U-elf'
    assert seen == [Path(inputs['replacement']['u_directory']) / 'u0']


@pytest.mark.parametrize('change', ['train', 'excluded', 'duplicate', 'family', 'hash'])
def test_active_membership_drift_is_rejected_before_loading_evidence(active_validation, monkeypatch, change):
    frozen, characterized, binding, population_path = active_validation
    data = planning.read_json(population_path)
    if change == 'train':
        data['workloads'][1]['split_group'] = 'test'
        data['workloads'][2]['split_group'] = 'train'
    elif change == 'excluded':
        data['excluded'].append(dict(workload_id='replacement'))
    elif change == 'duplicate':
        data['workloads'].append(data['workloads'][0])
    elif change == 'family':
        data['workloads'][0]['family_id'] = 'other'
    else:
        data['membership_hash'] = 'changed'
    if change != 'hash':
        data['membership_hash'] = digest(data['workloads'])
        data['assignments'] = {m['workload_id']: m['split_group'] for m in data['workloads']}
    write_json(population_path, data)
    # Repin the file to exercise semantic validation, not merely the file hash.
    b = planning.read_json(binding)
    b['active_population_hash'] = planning.file_hash(population_path)
    write_json(binding, b)
    monkeypatch.setattr(planning, 'checked_locality', lambda _: pytest.fail('Payload loaded before membership check'))
    with pytest.raises(ValueError, match='[Aa]ctive|[Mm]embership|[Ss]plit|[Ff]amily|[Ee]xcluded'):
        planning.load_validation(frozen, characterized, input_sources=binding)


def test_active_plan_records_both_original_and_active_split_identity(active_validation):
    frozen, characterized, binding, population_path = active_validation
    plan, _, _ = planning.make_calibration_plan(frozen, characterized, input_sources=binding)
    assert set(plan['inputs']) == {'replacement'}
    assert plan['active_dataset']['population_hash'] == planning.file_hash(population_path)
    assert plan['active_dataset']['assignments_hash'] == digest(planning.read_json(population_path)['assignments'])
    assert plan['frozen_split_hash'] == planning.file_hash(frozen / 'split.json')


def test_active_raw_failure_is_not_hidden_by_successful_stored_features(active_validation, monkeypatch):
    frozen, characterized, binding, _ = active_validation
    def bad_raw(*_):
        raise ValueError('Raw measurement log changed')
    monkeypatch.setattr(planning, 'load_batch', bad_raw)
    with pytest.raises(ValueError, match='Raw measurement log changed'):
        planning.load_validation(frozen, characterized, input_sources=binding)


def test_active_binding_rejects_modified_evidence_file(active_validation):
    frozen, characterized, binding, _ = active_validation
    data = planning.read_json(binding)
    features = Path(data['supplements']['replacement']['records']) / 'features.json'
    data['files'] = {str(features): planning.file_hash(features)}
    write_json(binding, data)
    write_json(features, {})
    with pytest.raises(ValueError):
        planning.load_validation(frozen, characterized, input_sources=binding)


def test_runner_uses_active_membership_and_rejects_changed_binding(active_validation, tmp_path):
    frozen, characterized, binding, _ = active_validation
    output = tmp_path / 'active-calibration'
    runner.collect(frozen, characterized, output, phase='plan', input_sources=binding)
    plan = planning.read_json(output / 'plan.json')
    assert set(plan['inputs']) == {'replacement'}
    assert plan['active_dataset']['source_hash'] == planning.file_hash(binding)
    # Semantically identical JSON still changes the pinned binding identity.
    binding.write_text(binding.read_text() + '\n')
    with pytest.raises(ValueError, match='plan or implementation changed'):
        runner.collect(frozen, characterized, output, phase='plan', input_sources=binding)


def test_tool_identity_checks_explicit_u_directory(tmp_path, monkeypatch):
    snapshot = tmp_path / 'prepared/replacement'
    snapshot.mkdir(parents=True)
    write_json(snapshot / 'manifest.json', dict(tools={}))
    u_directory = tmp_path / 'v2-u'
    (u_directory / 'u0').mkdir(parents=True)
    write_json(u_directory / 'u0/protocol.json', dict(simulator_hash='sim'))
    origin = dict(snapshot=str(snapshot), u_directory=str(u_directory), analyzer_tools={},
                  configuration=dict(tasks=[{}]))
    monkeypatch.setattr(planning, 'file_hash', lambda _: 'sim')
    assert planning.tool_identity({'replacement': origin})['simulator_hash'] == 'sim'
    write_json(u_directory / 'u0/protocol.json', dict(simulator_hash='different'))
    with pytest.raises(ValueError, match='Simulator differs'):
        planning.tool_identity({'replacement': origin})
