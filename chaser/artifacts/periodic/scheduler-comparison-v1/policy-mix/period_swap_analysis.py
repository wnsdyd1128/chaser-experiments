"""Pre-registered analysis of experiment 38 (period swap): memshort against memlong, paired by load and set.

Primary, per placement (wfd = results key p, cgb = p_cgb): exact two-sided McNemar on "met every deadline",
Holm over the two placements (alpha 0.05). Secondary: two-sided sign test on the whole-run late jobs
(rt-metrics.json late_jobs_all), met counts per arm and load, which tasks were late per arm (memory task /
other task on a memory-task core / task on a core without one; task_slack_analysis), and the mean
probability the experiment 35 main model (f35, trained on experiments 17-27) gives each arm.
Usage: python3 period_swap_analysis.py --output <period-swap run output> --cache <.cache dir> --dest <dir>
"""

import argparse
import json
from pathlib import Path
from statistics import mean
import sys

from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'period-distribution'))

from stats import ALPHA, holm
import task_slack_analysis as ts

SHORT, LONG = 'memshort-low50', 'memlong-low50'
PLACEMENTS = {'wfd': 'p', 'cgb': 'p_cgb'}


def _state(row, key):
    state = row[key]['state']
    return state == 'ok' if state in ('ok', 'deadline') else None


def paired(rows, key) -> list[dict]:
    arms = {}
    for r in rows:
        arms.setdefault((r['load'], r['set_id']), {})[r['heaviness']] = _state(r, key)
    return [dict(load=load, set_id=k, short=v[SHORT], long=v[LONG]) for (load, k), v in sorted(arms.items())
            if v.get(SHORT) is not None and v.get(LONG) is not None]


def _binomial(a, b) -> float:
    return float(scipy_stats.binomtest(min(a, b), a + b).pvalue) if a + b else 1.0


def mcnemar(pairs) -> dict:
    only_short = sum(p['short'] and not p['long'] for p in pairs)
    only_long = sum(p['long'] and not p['short'] for p in pairs)
    return dict(pairs=len(pairs), only_short_met=only_short, only_long_met=only_long,
                both_met=sum(p['short'] and p['long'] for p in pairs), neither_met=sum(not p['short'] and not p['long'] for p in pairs),
                p=_binomial(only_short, only_long))


def sign_test(pairs) -> dict:
    fewer_short = sum(p['short'] < p['long'] for p in pairs)
    fewer_long = sum(p['long'] < p['short'] for p in pairs)
    return dict(pairs=len(pairs), fewer_in_short=fewer_short, fewer_in_long=fewer_long, ties=len(pairs) - fewer_short - fewer_long,
                late_short=sum(p['short'] for p in pairs), late_long=sum(p['long'] for p in pairs), p=_binomial(fewer_short, fewer_long))


def primary(tests: dict) -> dict:
    names = list(tests)
    for name, adjusted in zip(names, holm([tests[n]['p'] for n in names])):
        tests[name].update(holm_p=adjusted, significant=adjusted < ALPHA)
    return tests


def late_pairs(rt, build) -> list[dict]:
    arms = {}
    for label, builds in rt['cases'].items():
        heaviness, load, k = label.split('/')
        entry = builds.get(build)
        if entry and entry['state'] in ('ok', 'deadline'):
            arms.setdefault((load, k), {})[heaviness] = entry['late_jobs_all']
    return [dict(short=v[SHORT], long=v[LONG]) for v in arms.values() if SHORT in v and LONG in v]


def who_late(output: Path) -> dict:
    out = {}
    for heaviness in (SHORT, LONG):
        for build in PLACEMENTS:
            rows = [r for case in sorted((output / heaviness).glob('u0*/s*')) for r in ts.run_rows(('38', case, build))]
            out[f'{heaviness} {build}'] = {c: dict(tasks=sum(r['cls'] == c for r in rows),
                                                   late_tasks=sum(r['cls'] == c and r['late_jobs'] > 0 for r in rows))
                                           for c in ts.CLASSES}
    return out


def rf_predictions(output: Path, cache: Path) -> dict:
    """Mean predicted probability of meeting every deadline per arm and placement, f35 trained on experiments 17-27."""
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    import rf_candidates as rc
    import rf_devcheck as rd
    train = rc.load(cache)
    source = (('38 period swap', ((output.name, 'p', 'wfd', 'wfd'), (output.name, 'p_cgb', 'cgb', 'cgb'))),)
    test = rc.load(output.parent, sources=source)
    names = rc.FEATURE_SETS[rc.MAIN]
    model = RandomForestClassifier(n_estimators=500, min_samples_leaf=3, random_state=0, n_jobs=-1).fit(*rd.matrix(train, names))
    probs = model.predict_proba(rd.matrix(test, names)[0])[:, 1]
    out = {}
    for heaviness in (SHORT, LONG):
        for build in PLACEMENTS:
            idx = [i for i, r in enumerate(test) if r['candidate'] == build and f"'{heaviness}'" in r['case']]
            out[f'{heaviness} {build}'] = dict(rows=len(idx), mean_probability=float(np.mean(probs[idx])) if idx else None,
                                               met=sum(test[i]['label'] for i in idx))
    return out


def analyze(rows, rt) -> dict:
    tests = primary({name: mcnemar(paired(rows, key)) for name, key in PLACEMENTS.items()})
    out = dict(primary=tests, late_jobs={b: sign_test(late_pairs(rt, b)) for b in PLACEMENTS}, by_load={})
    for name, key in PLACEMENTS.items():
        for load in sorted({r['load'] for r in rows}):
            pairs = [p for p in paired(rows, key) if p['load'] == load]
            out['by_load'][f'{name} {load}'] = dict(pairs=len(pairs), short_met=sum(p['short'] for p in pairs),
                                                    long_met=sum(p['long'] for p in pairs))
    return out


def markdown(result) -> str:
    lines = ['# Experiment 38: memory tasks with the shortest vs the longest periods (pre-registered)', '',
             '## Primary: sets meeting every deadline, exact McNemar, Holm over the placements', '',
             '| placement | pairs | both met | only memshort met | only memlong met | neither | p | Holm p | significant |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for name, t in result['primary'].items():
        lines.append(f"| {name} | {t['pairs']} | {t['both_met']} | {t['only_short_met']} | {t['only_long_met']} | {t['neither_met']} "
                     f"| {t['p']:.4f} | {t['holm_p']:.4f} | {t['significant']} |")
    lines += ['', '## Secondary: whole-run late jobs, sign test', '',
              '| placement | pairs | fewer in memshort | fewer in memlong | ties | late jobs memshort | late jobs memlong | p |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name, t in result['late_jobs'].items():
        lines.append(f"| {name} | {t['pairs']} | {t['fewer_in_short']} | {t['fewer_in_long']} | {t['ties']} | {t['late_short']} "
                     f"| {t['late_long']} | {t['p']:.4f} |")
    lines += ['', '## Sets meeting every deadline per load (memshort / memlong)', '', '| placement, load | pairs | memshort | memlong |', '|---|---:|---:|---:|']
    lines += [f"| {k} | {v['pairs']} | {v['short_met']} | {v['long_met']} |" for k, v in result['by_load'].items()]
    lines += ['', '## Late tasks by class (late / tasks)', '', '| arm, placement | ' + ' | '.join(ts.CLASSES) + ' |', '|---|---|---|---|']
    for k, v in result['who_late'].items():
        lines.append(f'| {k} | ' + ' | '.join(f"{v[c]['late_tasks']} / {v[c]['tasks']}" for c in ts.CLASSES) + ' |')
    lines += ['', '## Experiment 35 main model (f35) on these sets', '', '| arm, placement | rows | mean predicted probability | met |', '|---|---:|---:|---:|']
    for k, v in result['rf'].items():
        prob = '-' if v['mean_probability'] is None else f"{v['mean_probability']:.3f}"
        lines.append(f"| {k} | {v['rows']} | {prob} | {v['met']} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    rows = [json.loads(line) for line in (output / 'results.jsonl').read_text().splitlines()]
    rt = json.loads((output / 'rt-metrics.json').read_text())
    result = analyze(rows, rt)
    result['who_late'] = who_late(output)
    result['rf'] = rf_predictions(output, args.cache.resolve())
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'period-swap.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'period-swap.md').write_text(markdown(result))
    print('wrote', args.dest / 'period-swap.md')


if __name__ == '__main__':
    main()
