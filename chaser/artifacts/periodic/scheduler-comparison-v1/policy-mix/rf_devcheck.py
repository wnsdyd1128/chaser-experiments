"""RF configuration recommender, development check (EXPERIMENT-PLAN 5-1, exploratory).

Rows are (task set, configuration) for configurations p (CHASER placement ra-cgb; ra-cg for experiments
17 and 18, whose P runs are in experiment 18 and G/C runs in experiment 17), g (G4), c112 (C1+1+2) and,
where experiment 33 ran it, c13 (C1+3). Experiment 19 has P runs only. Label: the run met every deadline over the whole
run (hl_run state ok; startup and other states are left out). Features are task-count-free aggregates of
the planned task values (set_features) and the configuration's domains (config_features); no run result
enters them. Models: RF (main), logistic regression (cache demand, working set, most loaded domain,
configuration), and the static rule (cache demand alone, p rows). Calibration is reported as the Brier
score of the p predictions (no recalibration step in this check). Validation: group 5-fold out-of-fold
predictions, groups = (seed base, set id), and leave-one-experiment-out. The decision rule (decide)
takes p when its probability reaches tau, else the most likely g/c at or above tau, else rejects;
simulate counts saved sets, wrong switches and acceptance errors against "always p" and the oracle.
Judgment fixed beforehand: the RF goes into the confirmatory experiment if, held out by experiment,
it predicts p's outcome better than the static rule (AUC, experiment 20 included) and, at the chosen
tau, it saves more sets than it wrongly switches.
Usage: python3 rf_devcheck.py --cache <.cache dir> --dest <dir>
"""

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev

import numpy as np

L2_REQUESTS_PER_US = 1000 / 48
L2_KIB = 2048
CLS_LOW = 0.5
CORES = 4
DOMAINS = {'p': [[0], [1], [2], [3]], 'g': [[0, 1, 2, 3]], 'c13': [[0], [1, 2, 3]], 'c112': [[0], [1], [2, 3]]}
CONFIGS = tuple(DOMAINS)
RACGB = ('ra-cgb', 'p_racgb')
# (experiment, output with the P run and the set, (P build, its results key), output with G4 and C1+1+2, C1+3 output)
SOURCES = (('17 and 18 mixed tasks', 'policy-mix-cls-v1', ('ra-cg', 'p_racg'), 'policy-mix-v1', None),
           ('19 placement boundary', 'policy-boundary-v1', RACGB, 'policy-boundary-v1', None),
           ('20 768 KiB', 'task-count-v1', RACGB, 'task-count-v1', 'task-count-c13-v1'),
           ('21 32 KiB', 'small-memory-v1', RACGB, 'small-memory-v1', None),
           ('23 continuous CLS', 'cls-spread-v1', RACGB, 'cls-spread-v1', 'cls-spread-c13-v1'),
           ('24 32 KiB under load', 'small-memory-load-v1', RACGB, 'small-memory-load-v1', 'small-memory-load-c13-v1'),
           ('25 conflict-miss', 'conflict-cls-v2', RACGB, 'conflict-cls-v2', None),
           ('27 32 KiB', 'deadline-small-v1', RACGB, 'deadline-small-v1', 'deadline-small-c13-v1'),
           ('27 768 KiB', 'deadline-big-v1', RACGB, 'deadline-big-v1', 'deadline-big-c13-v1'))
TAUS = (0.5, 0.6, 0.7, 0.8, 0.9)
TAU = 0.8  # fixed before the full run (2026-10-06); the sweep is reported alongside


def set_features(tasks) -> dict:
    us = [t['u_planned'] for t in tasks]
    periods = [t['period_ticks'] for t in tasks]
    return dict(tasks=len(tasks), total_u=sum(us), max_u=max(us), u_cv=pstdev(us) / mean(us),
                heavy_tasks=sum(u > 0.5 for u in us), period_cv=pstdev(periods) / mean(periods),
                distinct_periods=len(set(periods)),
                cache_demand=sum(t['u_planned'] * t['traffic_planned'] for t in tasks) / L2_REQUESTS_PER_US,
                low_affinity_u=sum(t['u_planned'] for t in tasks if t['cls_planned'] <= CLS_LOW),
                weighted_one_minus_cls=sum(t['u_planned'] * (1 - t['cls_planned']) for t in tasks),
                working_set_over_l2=sum(t['footprint_kib'] for t in tasks) / L2_KIB,
                max_working_set_kib=max(t['footprint_kib'] for t in tasks))


def config_features(tasks, config) -> dict:
    core_u = [sum(t['u_planned'] for t in tasks if t['core'] == c) for c in range(CORES)]
    out = {f'config_{c}': int(c == config) for c in CONFIGS}
    out['max_domain_u'] = max(sum(core_u[c] for c in d) / len(d) for d in DOMAINS[config])
    groups = sorted({t['core'] for t in tasks if t['cls_planned'] <= CLS_LOW}) if config == 'p' else []
    out['group_cores'] = len(groups)
    out['max_group_core_u'] = max((core_u[c] for c in groups), default=0.0)
    return out


def decide(probs, tau):
    if probs['p'] >= tau:
        return 'p'
    others = [(v, c) for c, v in probs.items() if c != 'p' and v >= tau]
    return max(others)[1] if others else None


def simulate(cases, tau) -> dict:
    out = dict(cases=len(cases), accepted=0, accepted_met=0, false_accept=0, rejected=0, false_reject=0,
               saved=0, wrong_switch=0, chose_gc=0, oracle_saves=0, always_p_met=0, oracle_met=0)
    for c in cases:
        met, choice = c['met'], decide(c['probs'], tau)
        out['always_p_met'] += met['p']
        out['oracle_met'] += any(met.values())
        out['oracle_saves'] += (not met['p']) and any(v for k, v in met.items() if k != 'p')
        if choice is None:
            out['rejected'] += 1
            out['false_reject'] += any(met.values())
            continue
        out['accepted'] += 1
        out['accepted_met'] += met[choice]
        out['false_accept'] += not met[choice]
        if choice != 'p':
            out['chose_gc'] += 1
            out['saved'] += met[choice] and not met['p']
            out['wrong_switch'] += met['p'] and not met[choice]
    return out


def judge(held_out, simulation) -> dict:
    """The pre-fixed judgment: RF's p AUC above the static rule's in every held-out experiment where both
    are defined, and more saved sets than wrong switches at TAU (group out-of-fold simulation)."""
    compared = {s: v['rf'] for s, v in held_out.items() if v['rf']['p_auc'] is not None and v['rf']['rule_auc'] is not None}
    prediction = all(v['p_auc'] > v['rule_auc'] for v in compared.values())
    sim = simulation[str(TAU)]
    decision = sim['saved'] > sim['wrong_switch']
    return {'prediction': prediction, 'decision': decision, 'pass': prediction and decision, 'compared': sorted(compared)}


def markdown(result) -> str:
    lines = ['# RF configuration recommender: development check (exploratory)', '',
             f"{result['rows']} rows: " + ', '.join(f"{c} {v['met']}/{v['rows']} met" for c, v in result['by_config'].items()), '',
             '## Predicting whether p (CHASER placement) meets every deadline (AUC)', '',
             '| validation | RF | logistic regression | static rule (cache demand) | Brier RF | Brier LR |',
             '|---|---:|---:|---:|---:|---:|']
    f = lambda v: '-' if v is None else f'{v:.3f}'
    g = result['group_cv']
    for name, v in [('group 5-fold', g)] + [(f'held out: {s}', v) for s, v in result['held_out'].items()]:
        lines.append(f"| {name} | {f(v['rf']['p_auc'])} | {f(v['lr']['p_auc'])} | {f(v['rf']['rule_auc'])} "
                     f"| {f(v['rf']['p_brier'])} | {f(v['lr']['p_brier'])} |")
    lines += ['', '## Decision simulation (group 5-fold, RF)', '',
              '| tau | accepted (met / false accept) | rejected (false reject) | chose G/C | saved | wrong switch | always P met | oracle met | oracle saves |',
              '|---:|---|---|---:|---:|---:|---:|---:|---:|']
    for t, s in g['rf']['simulation'].items():
        lines.append(f"| {t} | {s['accepted']} ({s['accepted_met']} / {s['false_accept']}) | {s['rejected']} ({s['false_reject']}) | {s['chose_gc']} "
                     f"| {s['saved']} | {s['wrong_switch']} | {s['always_p_met']} | {s['oracle_met']} | {s['oracle_saves']} |")
    j = result['judgment']
    lines += ['', f"## Judgment (tau {TAU}): {'PASS' if j['pass'] else 'FAIL'}", '',
              f"- RF above the static rule in every held-out experiment ({', '.join(j['compared'])}): {j['prediction']}",
              f"- saved > wrong switches at tau {TAU}: {j['decision']}", '',
              '## Feature importance (RF on all rows)', '']
    lines += [f'- {k}: {v:.3f}' for k, v in list(result['importance'].items())[:10]]
    pd = result['partial_dependence_cache_demand']
    lines += ['', f"Partial dependence on cache demand non-increasing: {pd['non_increasing']}"]
    return '\n'.join(lines) + '\n'


def _results(path: Path) -> dict:
    if not path.exists():
        return {}
    return {(r['heaviness'], r['load'], r['set_id']): r for r in map(json.loads, path.read_text().splitlines())}


def load(cache: Path):
    rows = []
    for source, base, (p_build, p_key), gc, c13 in SOURCES:
        base_dir = cache / base
        gc_rows = _results(cache / gc / 'results.jsonl')
        c13_rows = _results(cache / c13 / 'results.jsonl') if c13 else {}
        for key, r in _results(base_dir / 'results.jsonl').items():
            case = base_dir / f"{r['heaviness']}/u{round(r['load'] * 100):03d}/s{r['set_id']:02d}"
            wfd = json.loads((case / 'wfd/configuration.json').read_text())
            states = {'p': r.get(p_key, {}).get('state'), 'g': gc_rows.get(key, {}).get('g', {}).get('state'),
                      'c112': gc_rows.get(key, {}).get('c2', {}).get('state'),
                      'c13': c13_rows.get(key, {}).get('c', {}).get('state')}
            tasks = {'p': json.loads((case / p_build / 'configuration.json').read_text())['tasks']} if states['p'] else {}
            group = (wfd['high_load']['seed'] - r['set_id'], r['set_id'])
            base_features = set_features(wfd['tasks'])
            for config, state in states.items():
                if state not in ('ok', 'deadline'):
                    continue
                features = dict(base_features, **config_features(tasks.get(config, wfd['tasks']), config))
                rows.append(dict(source=source, case=f'{base}/{key}', group=group, config=config,
                                 label=int(state == 'ok'), features=features))
    return rows


def matrix(rows, names):
    return np.array([[r['features'][n] for n in names] for r in rows], dtype=float), np.array([r['label'] for r in rows])


def models():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {'rf': (None, lambda: RandomForestClassifier(n_estimators=500, min_samples_leaf=3, random_state=0, n_jobs=-1)),
            'lr': (['cache_demand', 'working_set_over_l2', 'max_domain_u'] + [f'config_{c}' for c in CONFIGS],
                   lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)))}


def predict_out_of_fold(rows, names, split):
    """split(rows) yields (train indices, test indices); returns per-model probabilities per row."""
    probs = {m: np.full(len(rows), np.nan) for m in models()}
    for train, test in split(rows):
        for m, (cols, make) in models().items():
            x, y = matrix([rows[i] for i in train], cols or names)
            model = make().fit(x, y)
            probs[m][test] = model.predict_proba(matrix([rows[i] for i in test], cols or names)[0])[:, 1]
    return probs


def group_folds(rows, k=5):
    from sklearn.model_selection import GroupKFold
    groups = [str(r['group']) for r in rows]
    yield from GroupKFold(n_splits=k).split(np.zeros(len(rows)), groups=groups)


def experiment_folds(rows):
    for source in sorted({r['source'] for r in rows}):
        test = [i for i, r in enumerate(rows) if r['source'] == source]
        yield [i for i, r in enumerate(rows) if r['source'] != source], test


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s)) if 0 < sum(y) < len(y) else None


def evaluate(rows, probs, model):
    p_rows = [i for i, r in enumerate(rows) if r['config'] == 'p']
    y = [rows[i]['label'] for i in p_rows]
    out = dict(p_auc=auc(y, [probs[model][i] for i in p_rows]),
               rule_auc=auc(y, [-rows[i]['features']['cache_demand'] for i in p_rows]),
               p_brier=float(np.mean([(probs[model][i] - rows[i]['label']) ** 2 for i in p_rows])))
    by_case = {}
    for i, r in enumerate(rows):
        by_case.setdefault(r['case'], {})[r['config']] = (bool(r['label']), float(probs[model][i]))
    cases = [dict(met={c: v[0] for c, v in d.items()}, probs={c: v[1] for c, v in d.items()})
             for d in by_case.values() if {'p', 'g', 'c112'} <= set(d)]
    out['simulation'] = {str(t): simulate(cases, t) for t in TAUS}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    rows = load(args.cache.resolve())
    names = sorted(rows[0]['features'])
    result = dict(rows=len(rows), by_config={c: dict(rows=sum(r['config'] == c for r in rows), met=sum(r['label'] for r in rows if r['config'] == c))
                                             for c in CONFIGS},
                  features=names, group_cv={}, held_out={})
    probs = predict_out_of_fold(rows, names, group_folds)
    for m in models():
        result['group_cv'][m] = evaluate(rows, probs, m)
    held = predict_out_of_fold(rows, names, experiment_folds)
    for source in sorted({r['source'] for r in rows}):
        idx = [i for i, r in enumerate(rows) if r['source'] == source]
        sub = [rows[i] for i in idx]
        result['held_out'][source] = {m: evaluate(sub, {m: held[m][idx]}, m) for m in models()}
    from sklearn.ensemble import RandomForestClassifier
    x, y = matrix(rows, names)
    rf = RandomForestClassifier(n_estimators=500, min_samples_leaf=3, random_state=0, n_jobs=-1).fit(x, y)
    result['importance'] = dict(sorted(zip(names, map(float, rf.feature_importances_)), key=lambda kv: -kv[1]))
    p_rows = [r for r in rows if r['config'] == 'p']
    xp, _ = matrix(p_rows, names)
    grid = np.quantile(xp[:, names.index('cache_demand')], np.linspace(0.05, 0.95, 10))
    curve = []
    for g in grid:
        z = xp.copy()
        z[:, names.index('cache_demand')] = g
        curve.append(float(rf.predict_proba(z)[:, 1].mean()))
    result['partial_dependence_cache_demand'] = dict(grid=list(map(float, grid)), mean_p=curve,
                                                     non_increasing=all(b <= a + 1e-9 for a, b in zip(curve, curve[1:])))
    result['judgment'] = judge(result['held_out'], result['group_cv']['rf']['simulation'])
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'rf-devcheck.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'rf-devcheck.md').write_text(markdown(result))
    print('wrote', args.dest / 'rf-devcheck.md')


if __name__ == '__main__':
    main()
