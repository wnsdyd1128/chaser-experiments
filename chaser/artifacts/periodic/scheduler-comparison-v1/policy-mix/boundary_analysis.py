"""Analyze the policy-boundary run: where does each Partitioned placement win, and can static features tell?

Reads <output>/results.jsonl (pm_run summarize), protocol.json (cells) and every case's wfd
configuration and locality.json. Placements: wfd, cgb, ra, ra-cgb; a run with a deadline
miss is infeasible. Per metric (TAT, TET) it writes to boundary-analysis.json/md:
  cells       per cell (period CV x low x big): cases, deadline misses, median value and mean
              regret per placement (value / best placement of the case - 1), wins (ties
              count for every tied placement)
  hypotheses  (H1) cgb against ra where periods vary little (CV 0, 0.1) and memory-bound
              tasks exist; (H2) ra against wfd where periods vary (CV 0.2, 0.3) without
              them; (H3) ra-cgb against each other placement over all cases. Paired
              relative difference, wins / ties / losses, Wilcoxon signed-rank (zeros
              dropped), Holm over all tests of both metrics
  fixed       each fixed placement's mean regret over all cases (the oracle is 0)
  selector    the feature pre-check RF (precheck.evaluate) per metric: set-level CV and
              leave-one-cell-out CV
Usage: python3 boundary_analysis.py --output <run output dir> [--jobs N]
"""

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from scipy import stats as scipy_stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'feature-precheck'))
sys.path.insert(0, str(HERE))

import precheck
from pm_analysis import feature_tasks, holm, pct

KEYS = ('p', 'p_cgb', 'p_ra', 'p_racgb')
NAMES = dict(p='wfd', p_cgb='cgb', p_ra='ra', p_racgb='ra-cgb')
METRICS = ('tat_ns', 'tet_ns')
ALPHA = 0.05


def value(row, key, metric) -> float:
    return row[key][metric] if row[key].get('state') == 'ok' else float('inf')


def best(row, metric) -> float:
    return min(value(row, k, metric) for k in KEYS)


def placement_summary(rows, metric):
    out = {}
    for key in KEYS:
        regrets = [value(r, key, metric) / best(r, metric) - 1 for r in rows
                   if np.isfinite(best(r, metric)) and np.isfinite(value(r, key, metric))]
        feasible = [value(r, key, metric) / 1e6 for r in rows if np.isfinite(value(r, key, metric))]
        out[NAMES[key]] = dict(infeasible=sum(r[key].get('state') != 'ok' for r in rows),
                               median_ms=float(np.median(feasible)) if feasible else None,
                               mean_regret=float(np.mean(regrets)) if regrets else None,
                               wins=sum(np.isfinite(best(r, metric)) and value(r, key, metric) == best(r, metric)
                                        for r in rows))
    return out


def paired(rows, a, b, metric, name):
    d = [value(r, a, metric) / value(r, b, metric) - 1 for r in rows
         if np.isfinite(value(r, a, metric)) and np.isfinite(value(r, b, metric))]
    entry = dict(test=name, metric=metric.split('_')[0].upper(), pair=f'{NAMES[a]} vs {NAMES[b]}', cases=len(rows),
                 n=len(d), wins=sum(x < 0 for x in d), ties=sum(x == 0 for x in d), losses=sum(x > 0 for x in d),
                 median=float(np.median(d)) if d else None, mean=float(np.mean(d)) if d else None)
    nonzero = [x for x in d if x != 0]
    if len(nonzero) >= 6:
        entry['wilcoxon_p'] = float(scipy_stats.wilcoxon(nonzero).pvalue)
    return entry


def hypotheses(rows):
    flat_memory = [r for r in rows if r['cell']['period_cv'] <= 0.1 and (r['cell']['low'] or r['cell']['big'])]
    varied_light = [r for r in rows if r['cell']['period_cv'] >= 0.2 and not (r['cell']['low'] or r['cell']['big'])]
    tests = []
    for metric in METRICS:
        tests.append(paired(flat_memory, 'p_cgb', 'p_ra', metric, 'H1 period CV <= 0.1 with memory-bound tasks'))
        tests.append(paired(varied_light, 'p_ra', 'p', metric, 'H2 period CV >= 0.2 without memory-bound tasks'))
        for other in ('p', 'p_cgb', 'p_ra'):
            tests.append(paired(rows, 'p_racgb', other, metric, 'H3 combined against each placement'))
    tested = [e for e in tests if 'wilcoxon_p' in e]
    for entry, adjusted in zip(tested, holm([e['wilcoxon_p'] for e in tested])):
        entry.update(holm_p=adjusted, significant=adjusted < ALPHA)
    return tests


def selector(output, rows, metric, jobs):
    precheck.OPTIONS['policy-boundary'] = tuple(NAMES[k] for k in KEYS)
    usable = [r for r in rows if np.isfinite(best(r, metric))]
    other = 'tet_ns' if metric == 'tat_ns' else 'tat_ns'
    samples = [precheck.Sample('policy-boundary', r['heaviness'], r['set_id'], r['cell'], feature_tasks(output, r),
                               tuple(value(r, k, metric) for k in KEYS), tuple(value(r, k, other) for k in KEYS))
               for r in usable]
    results, _ = precheck.evaluate('policy-boundary', samples, jobs)
    return dict(cases=len(samples), labels={NAMES[k]: sum(s.label == i for s in samples) for i, k in enumerate(KEYS)},
                near_ties=sum(s.margin < precheck.MARGIN for s in samples),
                results={scheme: {name: v['mean'] for name, v in methods.items()} for scheme, methods in results.items()})


def markdown(result) -> str:
    lines = ['# Policy-boundary analysis', '',
             'Regret: a placement value / the best placement of the same case - 1, over runs that met every deadline.', '']
    for metric in METRICS:
        label = metric.split('_')[0].upper()
        lines += [f'## {label} per cell', '', '| cell | cases | ' + ' | '.join(
            f'{n} median / regret / wins' for n in NAMES.values()) + ' | deadline misses |',
                  '|---|---:|' + '---|' * len(NAMES) + '---|']
        for cell, entry in result['cells'].items():
            s = entry[metric]
            lines.append(f"| {cell} | {entry['cases']} | " + ' | '.join(
                f"{s[n]['median_ms']:.1f} / {pct(s[n]['mean_regret'])} / {s[n]['wins']}" if s[n]['median_ms'] else '-'
                for n in NAMES.values()) + ' | ' + ', '.join(f"{n} {s[n]['infeasible']}" for n in NAMES.values()) + ' |')
        lines += ['', f'Fixed placements over all cases ({label}): ' + ', '.join(
            f"{n} {pct(v['mean_regret'])}" for n, v in result['fixed'][metric].items()), '']
    lines += ['## Hypothesis tests', '', '| test | metric | pair | n | better / tie / worse | median | mean | Holm p |',
              '|---|---|---|---:|---|---:|---:|---:|']
    for e in result['hypotheses']:
        p = f"{e['holm_p']:.3g}" if 'holm_p' in e else '-'
        lines.append(f"| {e['test']} | {e['metric']} | {e['pair']} | {e['n']} | {e['wins']} / {e['ties']} / {e['losses']} "
                     f"| {pct(e['median'])} | {pct(e['mean'])} | {p} |")
    for metric, sel in result['selector'].items():
        lines += ['', f"## Placement selector ({metric.split('_')[0].upper()} labels)", '',
                  f"{sel['cases']} cases; labels {sel['labels']}; near-ties {sel['near_ties']}", '']
        for scheme, methods in sel['results'].items():
            lines += [f'### {scheme}-level cross-validation', '', '| method | mean regret | p95 | max | accuracy |',
                      '|---|---:|---:|---:|---:|']
            for name, m in methods.items():
                lines.append(f"| {name} | {pct(m['mean_regret'])} | {pct(m['p95_regret'])} | {pct(m['max_regret'])} | "
                             f"{pct(m['accuracy'])} |")
            lines.append('')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=6)
    args = parser.parse_args()
    output = args.output.resolve()
    rows = [json.loads(line) for line in (output / 'results.jsonl').read_text().splitlines()]
    cells = json.loads((output / 'protocol.json').read_text())['cells']
    for r in rows:
        r['cell'] = cells[r['heaviness']]
    order = list(cells)
    result = dict(
        cases=len(rows),
        cells={c: dict(cases=sum(r['heaviness'] == c for r in rows),
                       **{m: placement_summary([r for r in rows if r['heaviness'] == c], m) for m in METRICS})
               for c in order},
        fixed={m: placement_summary(rows, m) for m in METRICS},
        hypotheses=hypotheses(rows),
        selector={m: selector(output, rows, m, args.jobs) for m in METRICS})
    (output / 'boundary-analysis.json').write_text(json.dumps(result, indent=1) + '\n')
    (output / 'boundary-analysis.md').write_text(markdown(result))
    shutil.copyfile(Path(__file__), output / 'boundary_analysis.py')
    print('wrote', output / 'boundary-analysis.md')


if __name__ == '__main__':
    main()
