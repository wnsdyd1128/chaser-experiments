"""Pair the CLS-keyed placements (policy-mix-cls) with the traffic-keyed ones (policy-mix), case by case.

Joins <cls run>/results.jsonl with <policy-mix run>/results.jsonl on (load, set id) and
compares cg with tg and ra-cg with ra-tg on measured TAT and TET:
  identical  cases where both keys give the same core assignment (read from the stored
             configurations); a deterministic simulator must give equal results there
  differ     cases where the assignments differ (low-CLS 32 KiB tasks with matched
             traffic); paired relative difference, wins / ties / losses, Wilcoxon
             signed-rank (zeros dropped) with Holm over the metric x pair tests, and
             deadline-miss counts
  regret     every Partitioned placement of both runs against the best of the six, per
             metric, over all cases and over the differing ones
Writes cls-compare.json and cls-compare.md into the CLS run directory.
Usage: python3 cls_compare.py --cls <policy-mix-cls run> --policy-mix <policy-mix run>
"""

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from scipy import stats as scipy_stats

PAIRS = (('p_cg', 'p_tg', 'cg', 'tg'), ('p_racg', 'p_ratg', 'ra-cg', 'ra-tg'))
PLACEMENTS = dict(p='wfd', p_tg='tg', p_ra='ra', p_ratg='ra-tg', p_cg='cg', p_racg='ra-cg')
METRICS = ('tat_ns', 'tet_ns')
ALPHA = 0.05


def feasible(entry) -> bool:
    return entry.get('state') == 'ok'


def value(row, key, metric) -> float:
    return row[key][metric] if feasible(row[key]) else float('inf')


def holm(ps):
    order, adjusted, running = np.argsort(ps), [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adjusted[i] = running
    return adjusted


def cores(run, row, placement):
    path = run / f"mix/u{round(row['load'] * 100):03d}/s{row['set_id']:02d}/{placement}/configuration.json"
    return [t['core'] for t in json.loads(path.read_text())['tasks']]


def paired(rows, a, b, metric):
    d = [value(r, a, metric) / value(r, b, metric) - 1 for r in rows
         if np.isfinite(value(r, a, metric)) and np.isfinite(value(r, b, metric))]
    entry = dict(n=len(d), wins=sum(x < 0 for x in d), ties=sum(x == 0 for x in d), losses=sum(x > 0 for x in d),
                 median=float(np.median(d)) if d else None, mean=float(np.mean(d)) if d else None,
                 deadline_miss=dict(cls_key=sum(not feasible(r[a]) for r in rows),
                                    traffic_key=sum(not feasible(r[b]) for r in rows)))
    nonzero = [x for x in d if x != 0]
    if len(nonzero) >= 6:
        entry['wilcoxon_p'] = float(scipy_stats.wilcoxon(nonzero).pvalue)
    return entry


def regret(rows, metric):
    out = {}
    for key, name in PLACEMENTS.items():
        values = []
        for r in rows:
            best = min(value(r, k, metric) for k in PLACEMENTS)
            if np.isfinite(best) and np.isfinite(value(r, key, metric)):
                values.append(value(r, key, metric) / best - 1)
        out[name] = dict(mean=float(np.mean(values)) if values else None, at_least_5pct=sum(v >= 0.05 for v in values),
                         infeasible=sum(not feasible(r[key]) for r in rows))
    return out


def pct(v):
    return '-' if v is None else f'{v * 100:.2f}%'


def markdown(result) -> str:
    lines = ['# CLS-keyed against traffic-keyed placements', '',
             f"{result['cases']} cases; identical assignments: " +
             ', '.join(f"{k} {v['cases']} (result mismatches {v['result_mismatches']})"
                       for k, v in result['identical'].items()), '',
             'Relative difference = CLS-keyed / traffic-keyed - 1 (negative: the CLS key is better).', '',
             '## Cases where the assignments differ', '',
             '| pair | metric | n | CLS better / tie / worse | median | mean | Holm p | deadline misses (CLS / traffic) |',
             '|---|---|---:|---|---:|---:|---:|---|']
    for e in result['differ']:
        p = f"{e['holm_p']:.3g}" if 'holm_p' in e else '-'
        lines.append(f"| {e['pair']} | {e['metric']} | {e['n']} | {e['wins']} / {e['ties']} / {e['losses']} | "
                     f"{pct(e['median'])} | {pct(e['mean'])} | {p} | {e['deadline_miss']['cls_key']} / "
                     f"{e['deadline_miss']['traffic_key']} |")
    for scope in ('all', 'differ'):
        for metric in METRICS:
            lines += ['', f"## Regret against the best of six placements ({scope} cases, {metric.split('_')[0].upper()})",
                      '', '| placement | mean regret | regret >= 5% | infeasible |', '|---|---:|---:|---:|']
            for name, e in result['regret'][scope][metric].items():
                lines.append(f"| {name} | {pct(e['mean'])} | {e['at_least_5pct']} | {e['infeasible']} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cls', type=Path, required=True)
    parser.add_argument('--policy-mix', type=Path, required=True)
    args = parser.parse_args()
    cls_run, mix_run = args.cls.resolve(), args.policy_mix.resolve()
    base = {(r['load'], r['set_id']): r for r in map(json.loads, (mix_run / 'results.jsonl').read_text().splitlines())}
    rows = []
    for r in map(json.loads, (cls_run / 'results.jsonl').read_text().splitlines()):
        row = dict(base[(r['load'], r['set_id'])])
        row.update(p_cg=r['p_cg'], p_racg=r['p_racg'])
        for a, b, pa, pb in PAIRS:
            row[f'same_{pa}'] = cores(cls_run, r, pa) == cores(mix_run, r, pb)
        rows.append(row)
    identical = {}
    for a, b, pa, pb in PAIRS:
        same = [r for r in rows if r[f'same_{pa}']]
        mismatches = sum(r[a].get('state') != r[b].get('state') or any(r[a].get(m) != r[b].get(m) for m in METRICS)
                         for r in same)
        identical[f'{pa} = {pb}'] = dict(cases=len(same), result_mismatches=mismatches)
    differ_rows = [r for r in rows if not r['same_cg']]
    tests = []
    for a, b, pa, pb in PAIRS:
        subset = [r for r in rows if not r[f'same_{pa}']]
        for metric in METRICS:
            tests.append(dict(paired(subset, a, b, metric), pair=f'{pa} vs {pb}', metric=metric.split('_')[0].upper()))
    tested = [e for e in tests if 'wilcoxon_p' in e]
    for entry, adjusted in zip(tested, holm([e['wilcoxon_p'] for e in tested])):
        entry.update(holm_p=adjusted, significant=adjusted < ALPHA)
    result = dict(cases=len(rows), identical=identical, differ=tests,
                  regret={scope: {m: regret(subset, m) for m in METRICS}
                          for scope, subset in (('all', rows), ('differ', differ_rows))})
    (cls_run / 'cls-compare.json').write_text(json.dumps(result, indent=1) + '\n')
    (cls_run / 'cls-compare.md').write_text(markdown(result))
    shutil.copyfile(Path(__file__), cls_run / 'cls_compare.py')
    print('wrote', cls_run / 'cls-compare.md')


if __name__ == '__main__':
    main()
