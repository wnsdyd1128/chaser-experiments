"""Pre-label characterization preserves fixed membership and measured bounds."""
import pytest
from tools.rtems_periodic_characterize import feature_record


def inputs():
    member = dict(workload_id='w', input_signature='sig', split_group='test', family_id='f')
    locality = {'cases': {'b': dict(ca_caas_element=0.2, ca_global_line=0.3,
                                  ca_csrd_l1=0.4, cls={'0.5': 0.5}),
                          'a': dict(ca_caas_element=0.8, ca_global_line=0.7,
                                  ca_csrd_l1=0.6, cls={'0.5': 0.5})}}
    u = dict(utilization={'a': 0.25, 'b': 0.1}, characterization_id='id')
    return member, locality, u


def test_feature_record_keeps_membership_and_has_no_label():
    member, locality, u = inputs()
    row = feature_record(member, locality, u)
    assert row['split_group'] == 'test'
    assert row['input_signature'] == 'sig'
    assert row['within_u_bounds'] is True
    assert row['features']['caas-ca'][-1] == pytest.approx(0.35)
    assert 'label' not in row
    assert row['dataset_ready'] is False


def test_out_of_bounds_keeps_features_and_exclusion_reason():
    member, locality, u = inputs()
    u['utilization']['a'] = 0.251
    row = feature_record(member, locality, u)
    assert row['within_u_bounds'] is False
    assert row['exclusion_reasons'] == ['task_u_exceeds_0.25']
    assert row['split_group'] == 'test'


def test_feature_join_rejects_extra_or_missing_tasks():
    member, locality, u = inputs()
    locality['cases']['extra'] = locality['cases']['a']
    with pytest.raises(ValueError, match='task IDs'):
        feature_record(member, locality, u)


def test_total_u_bound_is_checked_independently():
    member, locality, u = inputs()
    locality['cases'] = {str(i): locality['cases']['a'] for i in range(9)}
    u['utilization'] = {str(i): 0.25 for i in range(9)}
    row = feature_record(member, locality, u)
    assert row['exclusion_reasons'] == ['taskset_u_exceeds_2.0']


def test_undefined_locality_is_preserved_without_inventing_features():
    member, locality, u = inputs()
    locality['cases']['a']['ca_caas_element'] = None
    row = feature_record(member, locality, u)
    assert 'caas-ca' not in row['features']
    assert 'caas-ca' in row['undefined_features']
    assert row['split_group'] == 'test'


def test_prepare_resumes_complete_snapshot_and_preserves_incomplete_one(tmp_path, monkeypatch):
    import json
    import tools.rtems_periodic_characterize as collector
    from chaser.periodic import digest
    from tools.rtems_smoke import write_json

    frozen, output = tmp_path / 'frozen', tmp_path / 'output'
    (frozen / 'source/configs').mkdir(parents=True)
    members = []
    for name in ('complete', 'incomplete', 'new'):
        config = dict(workload_id=name)
        write_json(frozen / 'source/configs' / (name + '.json'), config)
        members.append(dict(workload_id=name, configuration_hash=digest(config), split_group='test'))
    write_json(frozen / 'population.json', dict(workloads=members))
    write_json(frozen / 'split.json', {})
    built, analyzed = [], []

    def build(config, path):
        built.append(config['workload_id'])
        path.mkdir(parents=True)
        write_json(path / 'configuration.json', config)
        write_json(path / 'manifest.json', dict(files={}))

    def analysis(path, **kwargs):
        analyzed.append(path.name)
        (path / 'analysis').mkdir()
        write_json(path / 'analysis/locality.json', {})

    def checked(path):
        return json.loads((path / 'analysis/locality.json').read_text())

    for name in ('complete', 'incomplete'):
        path = output / 'prepared' / name
        build(dict(workload_id=name), path)
        analysis(path)
    (output / 'prepared/incomplete/analysis/locality.json').unlink()
    built.clear(); analyzed.clear()
    monkeypatch.setattr(collector, 'verify', lambda _: None)
    monkeypatch.setattr(collector, 'prepare', build)
    monkeypatch.setattr(collector, 'analyze', analysis)
    monkeypatch.setattr(collector, 'checked_locality', checked)
    with pytest.raises(SystemExit):
        collector.collect(frozen, output, phase='prepare', workers=1, timeout=120)
    assert built == ['new']
    assert analyzed == ['new']
    report = json.loads((output / 'prepare-progress.json').read_text())
    assert [r['status'] for r in report['workloads']] == ['ok', 'failed', 'ok']
    assert all(r['split_group'] == 'test' for r in report['workloads'])
    assert report['processed_workloads'] == 3
