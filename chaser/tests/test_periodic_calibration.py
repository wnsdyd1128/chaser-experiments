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


def test_complete_evidence_freezes_measured_policies_and_is_repeatable(validation, tmp_path, monkeypatch):
    frozen, characterized, _, _, _ = validation
    write_json(frozen / 'split.json', dict(seed=42))
    output = tmp_path / 'calibration'
    runner.collect(frozen, characterized, output, phase='plan')
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
    result = runner.collect(frozen, characterized, output, phase='freeze')
    assert result['dataset_stage'] == 'theta_policy_frozen'
    assert all(r['measurement_source'] == 'measured' for r in result['results'].values())
    assert all(r['threshold'] > 0.2 for r in result['results'].values())
    before = (output / 'frozen-policies.json').read_bytes()
    runner.collect(frozen, characterized, output, phase='freeze')
    assert (output / 'frozen-policies.json').read_bytes() == before
