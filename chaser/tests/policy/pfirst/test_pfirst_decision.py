"""Decision rule, candidates and the frozen-policy check of chaser.policy.pfirst."""
import hashlib
import json

import joblib
import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from chaser.policy.pfirst import decision, features, inputs


def tasks(n=8, u=0.3):
    return [dict(task_id=f't{i}', u=u, period=40, cls=0.13 if i < 2 else 0.9, rate=12.0 if i < 2 else 4.0,
                 working_set_kib=32.75, p_l1=0.13 if i < 2 else 0.9, p_mem=0.02) for i in range(n)]


def frozen(tmp_path, names, tau=0.8, tamper=False):
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 1, (60, len(names)))
    model = RandomForestClassifier(n_estimators=5, random_state=0).fit(x, (x[:, 0] < 0.5).astype(int))
    joblib.dump(model, tmp_path / 'model.joblib')
    digest = hashlib.sha256((tmp_path / 'model.joblib').read_bytes()).hexdigest()
    (tmp_path / 'model-spec.json').write_text(json.dumps(dict(model_sha256='0' * 64 if tamper else digest, tau=tau, features=names)))
    return tmp_path


def test_choice_prefers_chaser_then_the_most_likely_global_or_clustered_then_rejects():
    assert decision.choose({'ra-cgb': 0.85, 'g': 0.99}, 0.8) == ('P', 'ra-cgb')
    assert decision.choose({'ra-cgb': 0.5, 'g': 0.82, 'c13': 0.9}, 0.8) == ('fallback_gc', 'c13')
    assert decision.choose({'ra-cgb': 0.5, 'g': 0.6}, 0.8) == ('rejected', None)
    assert decision.choose({'g': 0.9}, 0.8) == ('fallback_gc', 'g')


def test_policy_refuses_a_model_whose_hash_differs_from_the_spec(tmp_path):
    with pytest.raises(ValueError):
        decision.Policy(frozen(tmp_path, ['occupancy', 'total_u'], tamper=True))


def test_decision_records_probabilities_for_every_candidate_and_the_static_rule(tmp_path):
    policy = decision.Policy(frozen(tmp_path, ['occupancy', 'total_u', 'is_ra-cgb']))
    record = decision.decide(tasks(), policy, seed=1)
    assert record['nominal'] == 'feasible' and set(record['probabilities']) == {'ra-cgb', 'g', 'c13', 'c112'}
    assert record['status'] in ('P', 'fallback_gc', 'rejected')
    assert record['static_rule'] == ('P' if record['occupancy'] < decision.STATIC_THRESHOLD else 'rejected')


def test_unknown_nominal_capacity_defers_and_infeasible_partitioned_leaves_only_global_or_clustered(tmp_path):
    policy = decision.Policy(frozen(tmp_path, ['occupancy']))
    unknown = [dict(t, u=0.9) for t in tasks(4)] + [dict(tasks(1)[0], task_id='x', u=0.1)]
    assert decision.decide(unknown, policy)['status'] == 'deferred'
    check, cands, _ = decision.candidates([dict(t, u=0.97) for t in tasks(2)])
    assert check['status'] == 'proven_infeasible' and decision.CHASER not in cands and 'g' in cands


def test_inputs_come_from_the_yarda_outputs_and_missing_ones_defer(tmp_path):
    (tmp_path / 'yarda').mkdir()
    (tmp_path / 'locality.json').write_text(json.dumps(dict(tasks=[dict(task_id='t0', cls=0.2)])))
    (tmp_path / 'yarda/t0.json').write_text(json.dumps(dict(tasks=[dict(
        l1_first_hit_ratio=0.2, all_cache_miss_ratio=0.3, l1=dict(misses=5000, unique_lines=1024))])))
    t = inputs.load_case(tmp_path, [dict(task_id='t0', u=0.25, period=40)])[0]
    assert t['cls'] == 0.2 and t['rate'] == pytest.approx(5000 / (0.25 * 40 * 1000)) and t['working_set_kib'] == 32.0
    with pytest.raises(inputs.MissingInput):
        inputs.load_case(tmp_path, [dict(task_id='t1', u=0.25, period=40)])
    assert set(features.CANDIDATES) >= set(features.GC_CANDIDATES)


def test_inputs_also_come_from_the_periodic_analysis_layout(tmp_path):
    (tmp_path / 'analysis/p/k0').mkdir(parents=True)
    (tmp_path / 'analysis/locality.json').write_text(json.dumps(dict(cases=dict(k0=dict(cls={'0.5': 0.4, '1.0': 0.3})))))
    (tmp_path / 'analysis/p/k0/hierarchy.json').write_text(json.dumps(dict(tasks=[dict(
        l1_first_hit_ratio=0.4, all_cache_miss_ratio=0.1, l1=dict(misses=3000, unique_lines=64))])))
    t = inputs.load_analysis(tmp_path, [dict(task_id='k0', u=0.1, period=20)])[0]
    assert t['cls'] == 0.4 and t['rate'] == pytest.approx(3000 / (0.1 * 20 * 1000)) and t['working_set_kib'] == 2.0
    with pytest.raises(inputs.MissingInput):
        inputs.load_analysis(tmp_path, [dict(task_id='k1', u=0.1, period=20)])


def test_inputs_take_the_job_wrapper_entry_when_the_export_also_lists_its_helpers(tmp_path):
    (tmp_path / 'analysis/p/k0').mkdir(parents=True)
    (tmp_path / 'analysis/locality.json').write_text(json.dumps(dict(cases=dict(k0=dict(cls={'0.5': 0.4})))))
    entry = lambda name, misses: dict(task_id=name, l1_first_hit_ratio=0.4, all_cache_miss_ratio=0.1,
                                      l1=dict(misses=misses, unique_lines=64))
    (tmp_path / 'analysis/p/k0/hierarchy.json').write_text(json.dumps(dict(tasks=[
        entry('kernel_k0', 100), entry('task_job_k0', 3000)])))
    t = inputs.load_analysis(tmp_path, [dict(task_id='k0', u=0.1, period=20)])[0]
    assert t['rate'] == pytest.approx(3000 / (0.1 * 20 * 1000))


def suspending(tmp_path, segments):
    """k0 sleeps once: segment k0 (100 accesses) and resume_k0 (300 accesses), each analyzed from a cold cache."""
    (tmp_path / 'analysis').mkdir()
    (tmp_path / 'analysis/locality.json').write_text(json.dumps(dict(cases=dict(k0=dict(
        cls={'0.5': 0.7}, segments={s: dict(cls={'0.5': 0.0}) for s in ('k0', 'resume_k0')})))))
    for name, accesses, l1, miss, misses, lines in segments:
        (tmp_path / 'analysis/p' / name).mkdir(parents=True)
        (tmp_path / 'analysis/p' / name / 'hierarchy.json').write_text(json.dumps(dict(tasks=[dict(
            task_id='task_job_' + name, modeled_accesses=accesses, l1_first_hit_count=l1, llc_first_hit_count=accesses - l1 - miss,
            all_cache_miss_count=miss, l1_first_hit_ratio=l1 / accesses, all_cache_miss_ratio=miss / accesses,
            l1=dict(misses=misses, unique_lines=lines))])))


def test_a_suspending_jobs_inputs_add_its_cold_segments_and_keep_the_largest_working_set(tmp_path):
    suspending(tmp_path, [('k0', 100, 60, 10, 40, 64), ('resume_k0', 300, 240, 20, 60, 32)])
    t = inputs.load_analysis(tmp_path, [dict(task_id='k0', u=0.1, period=20)])[0]
    assert t['cls'] == 0.7 and t['rate'] == pytest.approx(100 / (0.1 * 20 * 1000)) and t['working_set_kib'] == 2.0
    assert t['p_l1'] == pytest.approx(300 / 400) and t['p_mem'] == pytest.approx(30 / 400)


def test_a_suspending_job_missing_a_segments_output_defers(tmp_path):
    suspending(tmp_path, [('k0', 100, 60, 10, 40, 64)])
    with pytest.raises(inputs.MissingInput):
        inputs.load_analysis(tmp_path, [dict(task_id='k0', u=0.1, period=20)])


def test_inputs_give_the_static_l1_misses_per_thousand_ir_instructions(tmp_path):
    (tmp_path / 'analysis/p/k0').mkdir(parents=True)
    (tmp_path / 'analysis/locality.json').write_text(json.dumps(dict(cases=dict(k0=dict(cls={'0.5': 0.4}, ir_instructions=50_000)))))
    (tmp_path / 'analysis/p/k0/hierarchy.json').write_text(json.dumps(dict(tasks=[dict(
        l1_first_hit_ratio=0.4, all_cache_miss_ratio=0.1, l1=dict(misses=3000, unique_lines=64))])))
    assert inputs.load_analysis(tmp_path, [dict(task_id='k0', u=0.1, period=20)])[0]['mpki'] == pytest.approx(60.0)


def test_inputs_without_an_instruction_count_have_no_mpki(tmp_path):
    (tmp_path / 'analysis/p/k0').mkdir(parents=True)
    (tmp_path / 'analysis/locality.json').write_text(json.dumps(dict(cases=dict(k0=dict(cls={'0.5': 0.4})))))
    (tmp_path / 'analysis/p/k0/hierarchy.json').write_text(json.dumps(dict(tasks=[dict(
        l1_first_hit_ratio=0.4, all_cache_miss_ratio=0.1, l1=dict(misses=3000, unique_lines=64))])))
    assert inputs.load_analysis(tmp_path, [dict(task_id='k0', u=0.1, period=20)])[0]['mpki'] is None


def test_a_suspending_jobs_mpki_uses_its_segments_misses_over_the_jobs_instructions(tmp_path):
    suspending(tmp_path, [('k0', 100, 60, 10, 40, 64), ('resume_k0', 300, 240, 20, 60, 32)])
    path = tmp_path / 'analysis/locality.json'
    report = json.loads(path.read_text())
    report['cases']['k0']['ir_instructions'] = 4000
    path.write_text(json.dumps(report))
    assert inputs.load_analysis(tmp_path, [dict(task_id='k0', u=0.1, period=20)])[0]['mpki'] == pytest.approx(1000 * 100 / 4000)
