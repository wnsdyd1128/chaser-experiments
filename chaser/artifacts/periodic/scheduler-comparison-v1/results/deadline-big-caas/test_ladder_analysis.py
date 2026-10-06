"""Specification tests for the pre-registered experiment 28 analysis, on synthetic cases."""
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ladder_analysis as la


def run(state='ok', missed=0, expected=100, inflation=1.1, tat=1000.0, tet=500.0):
    return dict(state=state, missed_jobs=missed, expected_jobs=expected, max_response_ratio=0.5,
                worst_memory_inflation=inflation if state == 'ok' else None,
                tat_ns=tat if state == 'ok' else None, tet_ns=tet if state == 'ok' else None)


def case(set_id=0, cv='cv00', load=0.5, **runs):
    out = dict(heaviness=f'{cv}-low50', load=load, set_id=set_id, runs={p: run() for p in la.PLACEMENTS})
    out['runs'].update(runs)
    return out


def test_entry_marks_a_run_algorithm1_could_not_place_as_unplaceable():
    rt = dict(state='deadline', missed_jobs=40, expected_jobs=100, max_response_ratio=3.0,
              worst_memory_inflation=None, worst_inflation=None, late_jobs=30, lost_jobs=10)
    row = dict(state='deadline', tat_ns=None, tet_ns=None)
    assert la.entry(rt, row, placeable=False)['state'] == 'unplaceable'
    assert la.entry(rt, row, placeable=True)['state'] == 'deadline'
    assert la.entry(None, row, placeable=True) is None


def test_deployability_counts_unplaceable_as_not_meeting_and_drops_startup_failures():
    cases = [case(k, **{'cls-a1': run('unplaceable')}) for k in range(5)]
    cases += [case(10, cgb=run('deadline', 3))]
    cases += [case(11, cgb=run('startup'))]
    result = la.deployable_test(cases, 'cgb', 'cls-a1')
    assert result['pairs'] == 6
    assert (result['only_first'], result['only_second']) == (5, 1)
    assert result['direction_holds']


def test_unplaceable_runs_stay_out_of_paired_violated_job_tests():
    cases = [case(k, caas=run('deadline', 9), **{'cls-a1': run('deadline', 2)}) for k in range(8)]
    cases += [case(20 + k, caas=run('deadline', 9), **{'cls-a1': run('unplaceable')}) for k in range(5)]
    result = la.violation_test(cases, 'cls-a1', 'caas')
    assert result['pairs'] == 8 and result['fewer_first'] == 8


def test_release_step_tests_shorter_tat_on_pairs_that_both_met():
    cases = [case(k, **{'ra-cgb': run(tat=950 - k), 'cgb': run(tat=1000)}) for k in range(10)]
    result = la.tat_test(cases, 'ra-cgb', 'cgb')
    assert result['pairs'] == 10 and result['direction_holds'] and result['p'] < 0.01


def test_confirm_has_four_primary_steps_per_type_under_one_holm_family():
    cases = []
    for k in range(12):
        cases.append(case(k, caas=run('deadline', 20 + k), **{
            'cls-a1': run('unplaceable'), 'cgb': run(tat=1000), 'ra-cgb': run(tat=950 - k)}))
    result = la.confirm(dict(small=cases, big=cases))
    steps = result['primary']
    assert len(steps) == 8 and {s['step'] for s in steps} == set(la.STEPS)
    assert all('holm_p' in s for s in steps)
    supported = result['supported']
    assert supported['small']['L2'] and supported['small']['L3'] and supported['small']['L4']
    assert not supported['small']['L1']  # cls-a1 never placed: no violated-job pairs


def test_summary_counts_placeable_met_and_violated_jobs_per_cell():
    cases = [case(0, **{'cls-a1': run('unplaceable')}), case(1, caas=run('deadline', 7))]
    table = la.summary(cases)['cv00-low50/u0500']
    assert table['cls-a1'] == dict(runs=2, placeable=1, met=1, missed_jobs=0, expected_jobs=100)
    assert table['caas'] == dict(runs=2, placeable=2, met=1, missed_jobs=7, expected_jobs=200)


def test_load_type_joins_both_outputs_and_reads_placeability_and_isolation(tmp_path):
    import json
    key, base, caas = 'cv00-low50/u050/s00', tmp_path / 'base', tmp_path / 'caas'
    rt = lambda state: dict(state=state, missed_jobs=0 if state == 'ok' else 5, expected_jobs=100,
                            max_response_ratio=0.5, worst_memory_inflation=1.1 if state == 'ok' else None)
    ok = dict(state='ok', tat_ns=1000, tet_ns=500)
    row = dict(heaviness='cv00-low50', load=0.5, set_id=0)
    base.mkdir()
    (base / 'results.jsonl').write_text(json.dumps(dict(row, **{k: ok for k in la.BASE.values()})) + '\n')
    (base / 'rt-metrics.json').write_text(json.dumps(dict(cases={key: {p: rt('ok') for p in la.BASE}})))
    (caas / key).mkdir(parents=True)
    (caas / 'results.jsonl').write_text(json.dumps(dict(row, **{k: ok for k in la.ALGORITHM1.values()})) + '\n')
    (caas / 'rt-metrics.json').write_text(json.dumps(dict(cases={key: {p: rt('ok') for p in la.ALGORITHM1}})))
    for p in la.ALGORITHM1:
        (caas / key / p).mkdir()
        config = dict(high_load=dict(placeable=p != 'cls-a1-cal'),
                      tasks=[dict(role='low', core=0), dict(role='high', core=2)])
        (caas / key / p / 'configuration.json').write_text(json.dumps(config))
    cases, isolated = la.load_type(base, caas)
    runs = cases[0]['runs']
    assert runs['ra-cgb']['state'] == 'ok' and runs['caas']['state'] == 'ok'
    assert runs['cls-a1-cal']['state'] == 'unplaceable'
    assert isolated['caas'] == {'low': [1, 1], 'high': [0, 1]} and 'cls-a1-cal' not in isolated
