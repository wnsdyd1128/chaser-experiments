"""Specification tests for the pre-registered experiment 27 analysis, on synthetic cases."""
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import deadline_analysis as da


def run(state='ok', missed=0, expected=100, inflation=1.1, tat=1000.0, tet=500.0):
    return dict(state=state, missed_jobs=missed, expected_jobs=expected, max_response_ratio=0.5,
                worst_memory_inflation=inflation if state == 'ok' else None,
                tat_ns=tat if state == 'ok' else None, tet_ns=tet if state == 'ok' else None)


def case(predicted='ok', cv='cv00', load=0.5, set_id=0, g='deadline', c2='deadline', **runs):
    out = dict(heaviness=f'{cv}-low50', load=load, set_id=set_id, predicted=predicted, demand_ratio=0.5,
               runs={p: run() for p in da.PLACEMENTS})
    out['runs'].update(runs)
    out['runs'].update(g=dict(state=g), c2=dict(state=c2))
    return out


def test_lower_bound_is_the_one_sided_clopper_pearson_bound():
    assert da.lower_bound(20, 20) == pytest.approx(0.05 ** (1 / 20))
    assert da.lower_bound(0, 5) == 0.0
    assert da.lower_bound(9, 10) < 0.9 < da.lower_bound(90, 90)


def test_prediction_counts_a_case_correct_only_when_every_deterministic_placement_agrees():
    cases = [case('ok'), case('ok', wfd=run('deadline', 3)), case('miss', **{p: run('deadline', 5) for p in da.DETERMINISTIC}),
             case('miss'), case('uncertain')]
    result = da.prediction_check(cases)
    assert (result['ok']['cases'], result['ok']['correct']) == (2, 1)
    assert (result['miss']['cases'], result['miss']['correct']) == (2, 1)
    assert result['uncertain']['cases'] == 1


def test_prediction_check_ignores_random_draws_and_drops_cases_with_a_startup_failure():
    cases = [case('ok', rnd0=run('deadline', 9)), case('ok', ra=run('startup'))]
    result = da.prediction_check(cases)
    assert (result['ok']['cases'], result['ok']['correct']) == (1, 1)


def test_prediction_is_supported_when_both_directions_have_a_lower_bound_of_at_least_ninety_percent():
    good = [case('ok', set_id=k) for k in range(40)]
    good += [case('miss', set_id=k, **{p: run('deadline', 5) for p in da.DETERMINISTIC}) for k in range(40)]
    assert da.prediction_check(good)['supported']
    worse = good + [case('miss', set_id=99)] * 4
    assert not da.prediction_check(worse)['supported']


def test_violation_test_uses_only_pairs_where_some_run_violated_and_finds_the_direction():
    cases = [case(set_id=k, **{'ra-cgb': run('deadline', 2), 'ra': run('deadline', 10 + k)}) for k in range(12)]
    cases += [case(set_id=50)]  # both met: left out
    cases += [case(set_id=51, ra=run('startup'))]  # not measured: left out
    result = da.violation_test(cases, 'ra-cgb', 'ra')
    assert (result['pairs'], result['violating_pairs']) == (13, 12)
    assert result['fewer_first'] == 12 and result['median_difference'] < 0 and result['p'] < 0.01
    assert result['direction_holds']


def test_violation_test_compares_violated_job_ratios_not_counts():
    cases = [case(set_id=k, **{'ra-cgb': run('deadline', 10, expected=200), 'ra': run('deadline', 6, expected=100)})
             for k in range(8)]
    assert da.violation_test(cases, 'ra-cgb', 'ra')['fewer_first'] == 8


def test_violation_test_against_random_averages_the_three_draws_per_case():
    cases = [case(set_id=k, **{'ra-cgb': run('deadline', 2), 'rnd0': run('deadline', 3), 'rnd1': run(),
                               'rnd2': run('deadline', 9)}) for k in range(8)]
    result = da.violation_test(cases, 'ra-cgb', 'random')
    assert result['median_difference'] == pytest.approx(0.02 - 0.04)
    assert result['only_first_met'] is None


def test_mcnemar_counts_which_placement_alone_met_every_deadline():
    cases = [case(set_id=k, ra=run('deadline', 4)) for k in range(5)] + [case(set_id=9, **{'ra-cgb': run('deadline', 1)})]
    result = da.violation_test(cases, 'ra-cgb', 'ra')
    assert (result['only_first_met'], result['only_second_met']) == (5, 1)


def test_inflation_test_pairs_runs_that_both_met_every_deadline():
    cases = [case(set_id=k, **{'ra-cgb': run(inflation=1.2), 'ra': run(inflation=1.5)}) for k in range(10)]
    cases.append(case(set_id=20, ra=run('deadline', 3)))
    result = da.inflation_test(cases, 'ra-cgb', 'ra')
    assert result['pairs'] == 10 and result['median_change'] == pytest.approx(1.2 / 1.5 - 1)
    assert result['wins'] == 10 and result['p'] < 0.01 and result['direction_holds']


def test_tat_equivalence_holds_for_ratios_well_inside_the_margin():
    cases = [case(set_id=k, **{'ra-cgb': run(tat=1000 * (1 + 0.002 * (k % 5 - 2))), 'ra': run(tat=1000)})
             for k in range(30)]
    result = da.tat_equivalence(cases, 'ra-cgb', 'ra')
    assert result['pairs'] == 30 and result['p'] < 0.01


def test_tat_equivalence_fails_for_a_shift_beyond_the_margin():
    cases = [case(set_id=k, **{'ra-cgb': run(tat=1050 + k), 'ra': run(tat=1000)}) for k in range(30)]
    assert da.tat_equivalence(cases, 'ra-cgb', 'ra')['p'] > 0.5


def test_rescue_counts_g_or_c2_meeting_deadlines_where_every_deterministic_p_missed():
    missed = {p: run('deadline', 1) for p in da.DETERMINISTIC}
    cases = [case(g='ok', **missed), case(c2='ok', **missed), case(**missed), case(g='ok')]
    assert da.rescue(cases) == dict(all_p_missed=3, g_met=1, c2_met=1, either_met=2)


def test_confirm_applies_holm_within_each_hypothesis_family():
    cases = [case(set_id=k, **{'ra-cgb': run('deadline', 1, inflation=None),
                               'ra': run('deadline', 5 + k), 'wfd': run('deadline', 6 + k)}) for k in range(12)]
    result = da.confirm(dict(small=cases, big=cases))
    family = result['V2']['tests']
    assert len(family) == 4
    raw = sorted(t['p'] for t in family)
    assert max(t['holm_p'] for t in family) >= raw[-1]
    assert min(t['holm_p'] for t in family) == pytest.approx(min(1.0, 4 * raw[0]))
    assert result['V2']['supported'] == dict(small=True, big=True)


def test_summary_counts_runs_and_jobs_per_cell_and_placement():
    cases = [case(load=0.5, ra=run('deadline', 7)), case(load=0.5, set_id=1), case(load=0.6, ra=run('startup'))]
    table = da.summary(cases)
    cell = table['cv00-low50/u0500']
    assert cell['ra'] == dict(runs=2, met=1, missed_jobs=7, expected_jobs=200, excluded=0)
    assert cell['random']['runs'] == 6
    assert table['cv00-low50/u0600']['ra']['excluded'] == 1


def test_label_matches_hl_run_case_directories():
    assert da.label('cv20-low50', 0.475, 3) == 'cv20-low50/u048/s03'
    assert da.label('cv20-low50', 0.525, 3) == 'cv20-low50/u052/s03'
    assert da.label('cv20-low50', 0.575, 3) == 'cv20-low50/u057/s03'


def test_confirm_reports_tat_equivalence_without_a_direction():
    cases = [case(set_id=k, **{'ra-cgb': run(tat=1000 + k % 3), 'ra': run(tat=1000)}) for k in range(30)]
    result = da.confirm(dict(small=cases, big=cases))
    assert result['V4']['supported'] == dict(small=True, big=True)


def test_tet_test_pairs_runs_that_both_met_every_deadline_and_finds_the_direction():
    cases = [case(set_id=k, **{'ra-cgb': run(tet=480 - k), 'ra': run(tet=500)}) for k in range(10)]
    cases.append(case(set_id=20, ra=run('deadline', 3)))
    result = da.tet_test(cases, 'ra-cgb', 'ra')
    assert result['pairs'] == 10 and result['wins'] == 10 and result['median_change'] < 0
    assert result['p'] < 0.01 and result['direction_holds']


def test_confirm_reports_v6_tet_family_with_holm_over_types_and_references():
    cases = [case(set_id=k, **{'ra-cgb': run(tet=450 + k), 'ra': run(tet=500), 'wfd': run(tet=490)}) for k in range(12)]
    result = da.confirm(dict(small=cases, big=cases))
    assert len(result['V6']['tests']) == 4
    assert result['V6']['supported'] == dict(small=True, big=True)
