"""RF configuration recommender with cache-metric distribution statistics (experiment 36, exploratory).

Adds, to experiment 35's main features (rf_candidates f35), fixed-length distribution statistics of the
per-task cache metrics read from the YARDA outputs of the wfd build: CLS, p_L1, p_LLC, p_mem and CA-CSRD,
each summarized by min, quartiles, max, mean, standard deviation and U-weighted mean (set features, the
same for every candidate of a set). Variants: CLS statistics; each YARDA metric's statistics; CLS with
each YARDA metric; all YARDA metrics; CLS with all of them; plus f35 and f35 with another RF seed as the
noise reference. Data, candidates, validation and decision rule are experiment 35's. Reading rule fixed
beforehand (EXPERIMENTS.md 36, helps): held out by experiment, the P-row AUC is above f35's in all but at
most one experiment where it is defined, and the Brier score over all rows is below f35's.
Usage: python3 rf_stats.py --cache <.cache dir> --dest <dir>
"""

import argparse
import json
from pathlib import Path

import numpy as np

import rf_candidates as rc
import rf_devcheck as rd

METRICS = {'cls': 'cls_planned', 'p_l1': 'p_l1', 'p_llc': 'p_llc', 'p_mem': 'p_mem', 'ca': 'ca'}
STATS = ('min', 'q25', 'median', 'q75', 'max', 'mean', 'std', 'u_mean')
YARDA = ('p_l1', 'p_llc', 'p_mem', 'ca')
BASE = rc.FEATURE_SETS[rc.MAIN]


def _columns(*metrics):
    return [f'{m}_{s}' for m in metrics for s in STATS]


VARIANTS = {'f35': BASE, 'f35 (seed 1)': BASE, 'cls': BASE + _columns('cls'),
            **{m: BASE + _columns(m) for m in YARDA},
            **{f'cls+{m}': BASE + _columns('cls', m) for m in YARDA},
            'yarda': BASE + _columns(*YARDA), 'cls+yarda': BASE + _columns('cls', *YARDA)}
SEEDS = {'f35 (seed 1)': 1}


def distribution_stats(tasks) -> dict:
    u = np.array([t['u_planned'] for t in tasks])
    out = {}
    for name, field in METRICS.items():
        x = np.array([t[field] for t in tasks], dtype=float)
        q25, median, q75 = np.quantile(x, (0.25, 0.5, 0.75))
        values = dict(min=x.min(), q25=q25, median=median, q75=q75, max=x.max(), mean=x.mean(), std=x.std(),
                      u_mean=(u * x).sum() / u.sum())
        out.update({f'{name}_{k}': float(v) for k, v in values.items()})
    return out


def stats_by_case(cache: Path) -> dict:
    """Distribution statistics per case, keyed like rf_candidates.load's rows."""
    out = {}
    for source, runs in rc.SOURCES:
        first = runs[0][0]
        for key in rd._results(cache / first / 'results.jsonl'):
            case = cache / first / f'{key[0]}/u{round(key[1] * 100):03d}/s{key[2]:02d}'
            tasks = json.loads((case / 'wfd/configuration.json').read_text())['tasks']
            out[f'{source}/{key}'] = distribution_stats(rc.yarda_tasks(case, tasks))
    return out


def add_stats(rows, stats) -> None:
    for r in rows:
        r['features'].update(stats[r['case']])


def score(rows, probs) -> dict:
    out = rc.evaluate(rows, probs)
    out['brier'] = float(np.mean([(p - r['label']) ** 2 for p, r in zip(probs, rows)]))
    out['p_auc_by_source'] = {}
    for source, _ in rc.SOURCES:
        idx = [i for i, r in enumerate(rows) if r['source'] == source and r['candidate'] in rc.P_CANDIDATES]
        out['p_auc_by_source'][source] = rd.auc([rows[i]['label'] for i in idx], [probs[i] for i in idx])
    return out


def helps(variant, base) -> dict:
    pairs = [(variant['p_auc_by_source'][s], b) for s, b in base['p_auc_by_source'].items()
             if b is not None and variant['p_auc_by_source'][s] is not None]
    higher = sum(a > b for a, b in pairs)
    lower = variant['brier'] < base['brier']
    return dict(higher=higher, compared=len(pairs), brier_lower=lower, helps=higher >= len(pairs) - 1 and lower)


def markdown(result) -> str:
    v = result['variants']
    sources = [s for s, a in v['f35']['held_out']['p_auc_by_source'].items() if a is not None]
    f = lambda x: '-' if x is None else f'{x:.4f}'
    lines = ['# RF with cache-metric distribution statistics (experiment 36, exploratory)', '',
             f"{result['rows']} rows; statistics per metric: {', '.join(STATS)}", '',
             '## Held out by experiment: P-row AUC and Brier score (reading rule)', '',
             '| variant | ' + ' | '.join(sources) + ' | higher than f35 | Brier | lower Brier | helps |',
             '|---|' + '---:|' * len(sources) + '---:|---:|---|---|']
    for name, x in v.items():
        h = result['helps'].get(name)
        aucs = ' | '.join(f(x['held_out']['p_auc_by_source'][s]) for s in sources)
        verdict = f"{h['higher']} / {h['compared']} | {f(x['held_out']['brier'])} | {h['brier_lower']} | {h['helps']}" if h else \
            f"- | {f(x['held_out']['brier'])} | - | baseline"
        lines.append(f'| {name} | {aucs} | {verdict} |')
    t = str(rc.TAU)
    lines += ['', f'## Summary (tau {t} for the decision columns)', '',
              '| variant | AUC all rows (group / held out) | Brier (group / held out) | P choice (group / held out) '
              '| net saves (group / held out) | false accept, held out | false reject, held out |',
              '|---|---|---|---|---|---:|---:|']
    for name, x in v.items():
        g, h = x['group_cv'], x['held_out']
        net = lambda s: s[t]['saved'] - s[t]['wrong_switch']
        lines.append(f"| {name} | {f(g['auc_all'])} / {f(h['auc_all'])} | {f(g['brier'])} / {f(h['brier'])} "
                     f"| {g['choice']['rf']} / {h['choice']['rf']} (of {g['choice']['cases']}) "
                     f"| {net(g['simulation'])} / {net(h['simulation'])} | {h['simulation'][t]['false_accept']} "
                     f"| {h['simulation'][t]['false_reject']} |")
    lines += ['', '## Feature importance (cls+yarda, all rows)', '']
    lines += [f'- {k}: {x:.3f}' for k, x in list(result['importance'].items())[:15]]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    cache = args.cache.resolve()
    rows = rc.load(cache)
    add_stats(rows, stats_by_case(cache))
    result = dict(rows=len(rows), stats=STATS, variants={}, feature_counts={n: len(c) for n, c in VARIANTS.items()})
    for name, names in VARIANTS.items():
        seed = SEEDS.get(name, 0)
        result['variants'][name] = dict(group_cv=score(rows, rc.out_of_fold(rows, names, rd.group_folds, seed)),
                                        held_out=score(rows, rc.out_of_fold(rows, names, rd.experiment_folds, seed)))
    base = result['variants']['f35']['held_out']
    result['helps'] = {n: helps(x['held_out'], base) for n, x in result['variants'].items() if n != 'f35'}
    from sklearn.ensemble import RandomForestClassifier
    rf = RandomForestClassifier(n_estimators=500, min_samples_leaf=3, random_state=0, n_jobs=-1)
    rf.fit(*rd.matrix(rows, VARIANTS['cls+yarda']))
    result['importance'] = dict(sorted(zip(VARIANTS['cls+yarda'], map(float, rf.feature_importances_)), key=lambda kv: -kv[1]))
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'rf-stats.json').write_text(json.dumps(result, indent=1) + '\n')
    (args.dest / 'rf-stats.md').write_text(markdown(result))
    print('wrote', args.dest / 'rf-stats.md')


if __name__ == '__main__':
    main()
